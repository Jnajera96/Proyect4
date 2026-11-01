import pytest

from ai_swe.state.memory_graph import FileMemoryGraph


@pytest.mark.parametrize("filename,padding,target", [
    ("operations.py", "padding = '",
     "def calcular_balance(ingresos, gastos):\n    return ingresos - gastos\n"),
    ("operations.js", "var padding = '",
     "function calcularBalance(ingresos, gastos) {\n  return ingresos - gastos;\n}\n"),
])
def test_long_leading_lines_do_not_displace_relevant_code(tmp_path, filename, padding, target):
    from ai_swe.graph.nodes import _fragmento_relevante

    body = (padding + "x" * 1000 + "';\n") * 6 + target
    (tmp_path / filename).write_text(body, encoding="utf-8")
    snippet = _fragmento_relevante(tmp_path, filename, "Corrige calcular balance")
    assert target.strip() in snippet
    assert len(snippet) <= 1800 and len(snippet.splitlines()) <= 103
    assert snippet.startswith(f"--- inicio {filename} ---")
    assert snippet.endswith("--- fin ---")


def test_content_matches_seed_associated_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "operations.py").write_text("def tangente(angle): return math.tan(angle)")
    candidates = ["aaa.py", "operations.py", "test_operations.py"]
    graph = FileMemoryGraph(tmp_path / "m.sqlite3")
    graph.observe(str(repo), candidates[1:], observation="coedit")
    assert (
        graph.select(str(repo), "El cálculo de la tangente da error", candidates, top_k=2)
        == candidates[1:]
    )


def test_content_reader_is_bounded_and_confined(tmp_path):
    from ai_swe.state.memory_graph import read_candidate_text

    (tmp_path / "large.py").write_bytes(b"a" * 32768 + b"outside_limit")
    (tmp_path / "binary.py").write_bytes(b"a\x00b")
    (tmp_path / ".env").write_text("secret")
    assert len(read_candidate_text(tmp_path, "large.py")) == 32768
    for path in ("../secret", ".env", "binary.py", str(tmp_path / "large.py")):
        assert read_candidate_text(tmp_path, path) == ""


def test_researcher_supplies_bounded_code_body(tmp_path):
    from ai_swe.graph.nodes import _fragmento_relevante

    secret = "hf_" + "a" * 32
    body = "# unrelated\n" * 130 + f"# {secret}\ndef tangente(angle):\n    return math.tan(angle)\n"
    (tmp_path / "operations.py").write_text(body, encoding="utf-8")
    snippet = _fragmento_relevante(tmp_path, "operations.py", "corrige tangente")
    assert "return math.tan(angle)" in snippet
    assert secret not in snippet and "[REDACTED]" in snippet
    assert snippet.startswith("--- inicio operations.py ---")
    assert snippet.endswith("--- fin ---") and len(snippet) <= 1800
    assert len(snippet.splitlines()) <= 103


def test_associations_grow_idempotently_and_are_isolated(tmp_path):
    database = tmp_path / "memory.sqlite3"
    graph = FileMemoryGraph(database, "alice")
    candidates = ["calculator.py", "operations.py", "aaa_unrelated.py"]
    for observation in ("run-1", "run-1", "run-2"):
        graph.observe("repo", candidates[:2], observation=observation)
    assert graph.select("repo", "calculator.py", candidates, top_k=2) == candidates[:2]
    import sqlite3

    with sqlite3.connect(database) as db:
        assert (
            db.execute(
                "SELECT weight FROM file_cooccurrence WHERE source='calculator.py'"
            ).fetchone()[0]
            == 2
        )
    other = FileMemoryGraph(database, "bob")
    assert other.select("repo", "calculator.py", candidates, top_k=2)[1] == "aaa_unrelated.py"
    assert graph.select("other-repo", "calculator.py", candidates, top_k=2)[1] == "aaa_unrelated.py"


def test_context_bound_excludes_noise_without_dropping_explicit_files(tmp_path):
    graph = FileMemoryGraph(tmp_path / "m.sqlite3")
    candidates = [f"module_{i:02}.py" for i in range(24)]
    selected = graph.select("repo", "modify module_23.py", candidates, top_k=8)
    assert len(selected) == 8 and "module_23.py" in selected
    assert 0.5 <= 1 - len(selected) / len(candidates) <= 0.7
    noise = [".env", "node_modules/app.js", "package-lock.json", "../secret.py"]
    assert graph.select("repo", "", noise) == []
    query = " ".join(candidates)
    assert len(graph.select("repo", query, candidates, top_k=2)) == 24


def test_unmatched_query_does_not_claim_a_relevant_neighborhood(tmp_path):
    graph = FileMemoryGraph(tmp_path / "m.sqlite3")
    candidates = [f"module_{i:02}.py" for i in range(24)]
    assert graph.select("repo", "Reorganiza mi agenda", candidates) == candidates


def test_researcher_stops_before_silently_dropping_explicit_files(tmp_path):
    from test_f3_interpret_analyst import estado

    from ai_swe.config import Settings
    from ai_swe.graph import nodes
    from ai_swe.graph.model_routing import bind_settings_node

    repo = tmp_path / "repo"
    repo.mkdir()
    paths = [f"module_{i:02}.py" for i in range(24)]
    for path in paths:
        (repo / path).write_text("value = 1\n", encoding="utf-8")
    settings = Settings(_env_file=None, state_db_path=tmp_path / "state.sqlite3")
    result = bind_settings_node(nodes.researcher, settings)(
        estado("Modifica " + " ".join(paths), repo=str(repo))
    )
    assert result["status"] == "needs_human"
    assert result["errors"][-1].error_class == "CONTEXT_SCOPE_TOO_LARGE"


def test_graph_closes_every_sqlite_connection(tmp_path, monkeypatch):
    import sqlite3

    import pytest

    connect = sqlite3.connect
    connections = []

    def track(*args, **kwargs):
        connection = connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", track)
    graph = FileMemoryGraph(tmp_path / "m.sqlite3")
    graph.observe("repo", ["app.py", "test_app.py"], observation="test")
    graph.select("repo", "app.py", ["app.py", "test_app.py"])
    assert len(connections) == 3
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")
