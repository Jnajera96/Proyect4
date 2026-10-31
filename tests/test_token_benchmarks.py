import base64
import hashlib
import socket
from fractions import Fraction

import pytest

from ai_swe.observability import token_counter as counter
from tools import benchmark_memory_tokens as benchmark


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("El conteo y el benchmark deben funcionar sin red")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", "")


@pytest.fixture
def exact_available():
    pytest.importorskip("tiktoken", reason="Instala el extra token-metrics para medir exactamente")


@pytest.mark.parametrize("encoding", counter.ENCODINGS)
def test_counter_matches_official_constructor_without_network(
    encoding, exact_available, monkeypatch
):
    import tiktoken
    from tiktoken_ext import openai_public

    def local_ranks(url, expected_hash):
        raw = (counter.DATA / url.rsplit("/", 1)[-1]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected_hash
        return {
            base64.b64decode(token): int(rank)
            for token, rank in (line.split() for line in raw.splitlines())
        }

    monkeypatch.setattr(openai_public, "load_tiktoken_bpe", local_ranks)
    reference = tiktoken.Encoding(**getattr(openai_public, encoding)())
    for text in (
        "",
        "hello world",
        "¿Cuánto vale el balance?",
        "こんにちは世界",
        "🧪 café\r\n",
        "def f(x):\n    return x + 1\n",
        "<|endoftext|> literal",
    ):
        result = counter.count_tokens(text, encoding, require_exact=True)
        assert result.exact and result.method.startswith("tiktoken-")
        assert result.tokens == len(reference.encode_ordinary(text))
        assert 0 <= result.tokens <= len(text.encode("utf-8"))
        assert result == counter.count_tokens(text, encoding, require_exact=True)
    assert counter.count_tokens("hello world", encoding).tokens == 2


def test_fallback_is_deterministic_and_never_claims_exact(monkeypatch):
    def unavailable(*args):
        raise ImportError("tiktoken deliberately unavailable")

    monkeypatch.setattr(counter, "_encoder", unavailable)
    result = counter.count_tokens("á😀x")
    assert result.tokens == 2 and not result.exact
    assert result.method == "utf8_bytes_div4_ceiling"
    assert result == counter.count_tokens("á😀x")
    with pytest.raises(counter.TokenizerUnavailable):
        counter.count_tokens("hello", require_exact=True)
    with pytest.raises(ValueError, match="soportado"):
        counter.count_tokens("hello", "unknown-model")


def test_corrupt_vocabulary_aborts_instead_of_estimating(tmp_path, monkeypatch, exact_available):
    (tmp_path / "encodings.json").write_bytes((counter.DATA / "encodings.json").read_bytes())
    (tmp_path / "cl100k_base.tiktoken").write_bytes(b"corrupt")
    counter._encoder.cache_clear()
    monkeypatch.setattr(counter, "DATA", tmp_path)
    try:
        with pytest.raises(ValueError, match="SHA-256"):
            counter.count_tokens("hello", "cl100k_base")
    finally:
        counter._encoder.cache_clear()


def test_benchmark_preserves_critical_code_and_is_reproducible(tmp_path, exact_available):
    report = benchmark.measure(tmp_path / "short")
    repeated = benchmark.measure(tmp_path / "a-different-longer-directory")
    assert report == repeated
    assert report["offline"] and report["paid_calls"] == 0
    assert len(report["fixture_sha256"]) == 15
    for row in report["cases"]:
        cold, warm = (row["arms"][key] for key in ("naive", "asociativa"))
        assert cold["code_blocks"] == 15 and 1 <= warm["code_blocks"] <= 5
        assert warm["history_chars"] > 0 and cold["history_chars"] == 0
        assert warm["missing_required"] == warm["missing_code"] == []
        for encoding in counter.ENCODINGS:
            naive, memory = (arm["counts"][encoding] for arm in (cold, warm))
            assert naive["exact"] and memory["exact"]
            assert 0 < memory["tokens"] < naive["tokens"]
            assert memory["code_tokens"] < naive["code_tokens"]
            ratio = Fraction(naive["tokens"] - memory["tokens"], naive["tokens"])
            assert row["reductions"][encoding]["fraction"] == str(ratio)
    assert all(value["exact"] for value in report["totals"].values())


def test_mention_in_summary_is_not_sufficient_code():
    required = {"api/app.py": "def healthcheck("}
    section = "--- inicio other.py ---\ndef healthcheck(): pass\n--- fin ---"
    assert benchmark._missing_code(section, required) == ["api/app.py"]


def test_benchmark_rejects_savings_that_drop_required_files(tmp_path, monkeypatch, exact_available):
    monkeypatch.setattr(benchmark.FileMemoryGraph, "select", lambda *a, **kw: ["api/app.py"])
    report = benchmark.measure(tmp_path / "loss")
    assert any(row["arms"]["asociativa"]["missing_required"] for row in report["cases"])
    monkeypatch.setattr(benchmark, "measure", lambda *a, **kw: report)
    monkeypatch.setattr("sys.argv", ["benchmark_memory_tokens.py"])
    assert benchmark.main() == 2


def test_approximation_output_is_labeled(tmp_path, monkeypatch, capsys):
    def unavailable(*args):
        raise ImportError("missing optional package")

    monkeypatch.setattr(counter, "_encoder", unavailable)
    report = benchmark.measure(tmp_path / "estimated", require_exact=False)
    assert all(not value["exact"] for value in report["totals"].values())
    monkeypatch.setattr(benchmark, "measure", lambda *a, **kw: report)
    monkeypatch.setattr("sys.argv", ["benchmark_memory_tokens.py", "--allow-approximate"])
    assert benchmark.main() == 0
    assert "Total o200k_base (ESTIMADO)" in capsys.readouterr().out
