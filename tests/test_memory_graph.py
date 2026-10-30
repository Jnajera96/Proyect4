from ai_swe.state.memory_graph import FileMemoryGraph


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
