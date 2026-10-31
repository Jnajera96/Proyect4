"""Offline comparison of full-repository input and the production context policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from ai_swe.config import Settings
from ai_swe.contracts import Instruction, RunOptions, RunState, Scope, TaskInterpretation
from ai_swe.graph import model_routing, nodes
from ai_swe.models import FakeModelAdapter, ModelGateway
from ai_swe.observability.token_counter import DATA, ENCODINGS, TokenizerUnavailable, count_tokens
from ai_swe.security import bloque_no_confiable, redact
from ai_swe.security.untrusted import MARCA_FIN, MARCA_INICIO
from ai_swe.state.memory import MemoryStore
from ai_swe.state.memory_graph import FileMemoryGraph

FIXTURES = Path(__file__).with_name("fixtures") / "memory_tokens"
HISTORY = (
    (
        "Healthcheck y rutas HTTP compartidas",
        ("api/app.py", "api/responses.py", "tests/test_routes.py"),
    ),
    (
        "Balance y cálculo decimal sin redondeo intermedio",
        ("models/ledger.py", "utils/arithmetic.py", "tests/test_ledger.py"),
    ),
    (
        "Formato de respuestas y contratos de los endpoints",
        ("api/responses.py", "api/inventory.py", "api/tasks.py", "tests/test_responses.py"),
    ),
)
CASES = (
    (
        "explicito",
        "Modifica la ruta de healthcheck en app.py",
        {
            "api/app.py": "def healthcheck(",
            "api/responses.py": "def response_ok(",
            "tests/test_routes.py": "def test_healthcheck(",
        },
    ),
    (
        "contenido",
        "Ajusta la fórmula del cálculo del balance",
        {
            "models/ledger.py": "def calcular_balance(",
            "utils/arithmetic.py": "def amount(",
            "tests/test_ledger.py": "def test_balance(",
        },
    ),
    (
        "transversal",
        "Agrega un validador de formato a todas las respuestas",
        {
            "api/app.py": "def healthcheck(",
            "api/inventory.py": "def list_products(",
            "api/responses.py": "def response_ok(",
            "api/tasks.py": "def list_tasks(",
            "tests/test_responses.py": "def test_respuestas_success(",
        },
    ),
)


def _naive_code(request, repo, candidates):
    """Controlled ablation: replace only the code block's five-file cap with all files."""
    text = request.messages[1].content
    opening = f"{MARCA_INICIO} (origen: código existente parcial) -----\n"
    closing = MARCA_FIN + " -----"
    assert text.count(opening) == 1
    start = text.index(opening)
    end = text.index(closing, start) + len(closing)
    blocks = []
    for relative in candidates:
        body = redact((repo / relative).read_text(encoding="utf-8"))
        assert len(body) <= 1800 and len(body.splitlines()) <= 100
        blocks.append(f"--- inicio {relative} ---\n{body}\n--- fin ---")
    message = request.messages[1].model_copy(
        update={
            "content": text[:start]
            + bloque_no_confiable("código existente parcial", "\n\n".join(blocks))
            + text[end:],
        }
    )
    return request.model_copy(update={"messages": [request.messages[0], message]})


def _code_section(text):
    opening = f"{MARCA_INICIO} (origen: código existente parcial) -----\n"
    return text.split(opening, 1)[1].split(MARCA_FIN + " -----", 1)[0]


def _missing_code(section, required):
    missing = []
    for path, anchor in required.items():
        marker = f"--- inicio {path} ---\n"
        if (
            marker not in section
            or anchor not in section.split(marker, 1)[1].split("\n--- fin ---", 1)[0]
        ):
            missing.append(path)
    return missing


def measure(directory: Path, *, require_exact: bool = True) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    repo = directory / "repository"
    shutil.copytree(FIXTURES, repo)
    candidates = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*") if p.is_file())
    assert len(candidates) == 15
    results = []
    for name, query, required in CASES:
        arms = {}
        for arm in ("naive", "asociativa"):
            settings = Settings(
                _env_file=None,
                state_db_path=directory / f"{name}-{arm}.sqlite3",
                profile_id="benchmark",
                remote_model_roles=[],
                allowed_test_targets=[],
            )
            now = datetime(2026, 10, 31, tzinfo=UTC)
            state = RunState(
                run_id="current",
                trace_id="offline-token-benchmark",
                created_at=now,
                updated_at=now,
                instruction=Instruction(text=query, source="text", confirmed_by_user=True),
                options=RunOptions(repo_path=str(repo)),
                interpretation=TaskInterpretation(
                    intent="modify",
                    scope=Scope(repo_path=str(repo)),
                    confidence=0.9,
                    rationale="Synthetic confirmed task",
                ),
            )
            if arm == "asociativa":
                graph = FileMemoryGraph(settings.state_db_path, "benchmark")
                # Same predeclared history for every query, independent of its oracle.
                for index, (lesson, paths) in enumerate(HISTORY):
                    for observation in range(3):
                        graph.observe(
                            str(repo), list(paths), observation=f"prior-{index}-{observation}"
                        )
                    previous = state.model_copy(deep=True)
                    previous.run_id = f"prior-task-{index}"
                    previous.interpretation.scope.repo_path = "<repo>"
                    previous.instruction.text = lesson
                    MemoryStore(settings.state_db_path, "benchmark").project(previous)
            research = model_routing.bind_settings_node(nodes.researcher, settings)
            if arm == "naive":
                with patch.object(
                    FileMemoryGraph,
                    "select",
                    lambda self, repository, query, candidates: sorted(candidates),
                ):
                    state = state.model_copy(update=research(state))
            else:
                state = state.model_copy(update=research(state))
            adapter = FakeModelAdapter(structured={"files": [], "rationale": "Offline measurement"})
            with patch.object(
                model_routing, "gateway_for_node", return_value=ModelGateway([adapter])
            ):
                model_routing.bind_settings_node(nodes._coder_del_modelo, settings)(state)
            assert len(adapter.calls) == 1
            request = adapter.calls[0]
            if arm == "naive":
                request = _naive_code(request, repo, candidates)
            # Remove host-specific paths equally in both arms, including JSON-escaped paths.
            texts = [
                m.content.replace(json.dumps(str(repo))[1:-1], "<repo>").replace(
                    str(repo), "<repo>"
                )
                for m in request.messages
            ]
            code_section = _code_section(texts[1])
            measured = {}
            for encoding in ENCODINGS:
                counts = [count_tokens(t, encoding, require_exact=require_exact) for t in texts]
                measured[encoding] = {
                    "tokens": sum(c.tokens for c in counts),
                    "exact": all(c.exact for c in counts),
                    "method": counts[0].method,
                    "code_tokens": count_tokens(
                        code_section, encoding, require_exact=require_exact
                    ).tokens,
                }
            selected = state.outputs.researcher_output.files_read
            arms[arm] = {
                "bytes": sum(len(t.encode("utf-8")) for t in texts),
                "counts": measured,
                "selected_files": selected,
                "missing_required": sorted(set(required) - set(selected)),
                "missing_code": _missing_code(code_section, required),
                "history_chars": len(nodes._historial_para_coder(state)),
                "code_blocks": 15
                if arm == "naive"
                else sum(f.evidence.startswith("--- inicio ") for f in state.evidence.findings),
                "message_sha256": hashlib.sha256(
                    json.dumps(texts, ensure_ascii=False).encode()
                ).hexdigest(),
            }
        reductions = {}
        for encoding in ENCODINGS:
            cold, warm = [arms[a]["counts"][encoding] for a in ("naive", "asociativa")]
            ratio = Fraction(cold["tokens"] - warm["tokens"], cold["tokens"])
            code_ratio = Fraction(cold["code_tokens"] - warm["code_tokens"], cold["code_tokens"])
            reductions[encoding] = {
                "fraction": str(ratio),
                "percent": float(ratio * 100),
                "exact": cold["exact"] and warm["exact"],
                "code_percent": float(code_ratio * 100),
                "full_prompt_target_met": Fraction(2, 5) <= ratio <= Fraction(7, 10),
            }
        results.append(
            {
                "case": name,
                "query": query,
                "required": list(required),
                "arms": arms,
                "reductions": reductions,
            }
        )
    definitions = json.loads((DATA / "encodings.json").read_text(encoding="utf-8"))
    totals = {}
    for encoding in ENCODINGS:
        cold = sum(row["arms"]["naive"]["counts"][encoding]["tokens"] for row in results)
        warm = sum(row["arms"]["asociativa"]["counts"][encoding]["tokens"] for row in results)
        cold_code = sum(row["arms"]["naive"]["counts"][encoding]["code_tokens"] for row in results)
        warm_code = sum(
            row["arms"]["asociativa"]["counts"][encoding]["code_tokens"] for row in results
        )
        ratio = Fraction(cold - warm, cold)
        totals[encoding] = {
            "naive_tokens": cold,
            "memory_tokens": warm,
            "fraction": str(ratio),
            "percent": float(ratio * 100),
            "exact": all(row["reductions"][encoding]["exact"] for row in results),
            "naive_code_tokens": cold_code,
            "memory_code_tokens": warm_code,
            "code_percent": 100 * (cold_code - warm_code) / cold_code,
        }
    return {
        "offline": True,
        "paid_calls": 0,
        "adapter": "FakeModelAdapter",
        "cases": results,
        "totals": totals,
        "vocabularies": definitions,
        "fixture_sha256": {
            p: hashlib.sha256((repo / p).read_text(encoding="utf-8").encode()).hexdigest()
            for p in candidates
        },
        "scope": (
            "Sum of ordinary text tokens per message; "
            "excludes chat framing, schema and provider billing"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-approximate", action="store_true")
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix="memory-tokens-") as temporary:
            report = measure(Path(temporary), require_exact=not args.allow_approximate)
    except TokenizerUnavailable as exc:
        parser.error(str(exc))
    print(
        "Caso | Encoding | Bytes sin/con | Tokens sin/con | "
        "Reducción total | Reducción código | Suficiencia"
    )
    sufficient = True
    for row in report["cases"]:
        cold, warm = [row["arms"][a] for a in ("naive", "asociativa")]
        covered = not warm["missing_required"] and not warm["missing_code"]
        sufficient &= covered
        for encoding, reduction in row["reductions"].items():
            quality = "exacto" if reduction["exact"] else "ESTIMADO"
            print(
                f"{row['case']} | {encoding} ({quality}) | {cold['bytes']}/{warm['bytes']} | "
                f"{cold['counts'][encoding]['tokens']}/{warm['counts'][encoding]['tokens']} | "
                f"{reduction['percent']:.6f}% | {reduction['code_percent']:.6f}% | {covered}"
            )
    for encoding, total in report["totals"].items():
        quality = "exacto" if total["exact"] else "ESTIMADO"
        print(f"Total {encoding} ({quality}): {total['percent']:.6f}% ({total['fraction']})")
    goal_met = all(
        r["exact"] and r["full_prompt_target_met"]
        for row in report["cases"]
        for r in row["reductions"].values()
    )
    print(f"Objetivo 40–70% del prompt completo: {goal_met}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
    return 0 if sufficient else 2


if __name__ == "__main__":
    raise SystemExit(main())
