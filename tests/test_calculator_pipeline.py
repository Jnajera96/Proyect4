from ai_swe.contracts import Instruction
from ai_swe.graph.nodes import _clasificar
from ai_swe.sandbox import Sandbox
from ai_swe.tools.runner import ejecutar


def test_calculator_text_capture_and_intent():
    instruction = Instruction(
        text="Construye una calculadora con seno coseno tangente",
        source="text",
        confirmed_by_user=True,
    )
    assert instruction.capture_fidelity == 1.0
    assert _clasificar(instruction.text) == "modify"
    assert _clasificar("No construyas ni crea archivos; analiza el codigo") != "modify"
    assert _clasificar("recreacion de objetos") != "modify"


def test_root_pytest_is_real(tmp_path):
    (tmp_path / "test_calculadora.py").write_text("def test_seno():\n    assert 1 == 1\n")
    sandbox = Sandbox(
        raiz=tmp_path,
        repo_original=tmp_path,
        base_commit="",
        run_id="calculator",
        creado_por_nosotros=False,
    )
    result = ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",))
    assert result.exit_code == 0, result.stderr + result.stdout
    assert "1 passed" in result.stdout


def test_actual_graph_persists_activity_while_model_waits(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from ai_swe.graph import RunEngine, nodes
    from ai_swe.models import FakeModelAdapter, ModelGateway
    from ai_swe.state import RunStore

    entered, release = Event(), Event()

    class WaitingAdapter(FakeModelAdapter):
        def generate(self, request):
            entered.set()
            assert release.wait(10)
            return super().generate(request)

    adapter = WaitingAdapter(
        structured={
            "intent": "inspect",
            "scope": {"repo_path": str(tmp_path)},
            "constraints": [],
            "confidence": 0.8,
            "rationale": "Inspeccion solicitada",
        }
    )
    gateway = ModelGateway([adapter])
    monkeypatch.setattr(nodes, "_GATEWAY", gateway)
    with RunStore(tmp_path / "activity.sqlite3") as store, ThreadPoolExecutor(1) as pool:
        engine = RunEngine(store)
        state = engine.crear_estado("Analiza los archivos")
        engine.create(state)
        future = pool.submit(engine.execute, state.run_id)
        try:
            assert entered.wait(10)
            kinds = [event.kind for event in store.events(state.run_id)]
            assert "node_started" in kinds
            assert "model_request_started" in kinds
            assert "model_response_received" not in kinds
        finally:
            release.set()
        final = future.result(timeout=10)
        assert final.status == "awaiting_human_requirements_confirmation"
        events = store.events(state.run_id)
        assert any(event.kind == "model_response_received" for event in events)
        assert any(
            event.kind == "node_completed" and event.data["node"] == "interpret" for event in events
        )
        assert not any(
            event.kind == "node_completed" and event.data["node"] == "confirm_requirements_gate"
            for event in events
        )
    gateway.close()


def test_compiled_calculator_graph_creates_root_tests_and_persists_evidence(tmp_path, monkeypatch):
    import subprocess

    from ai_swe.config import Settings
    from ai_swe.contracts import RunOptions
    from ai_swe.graph import RunEngine, model_routing
    from ai_swe.models import FakeModelAdapter, ModelGateway
    from ai_swe.state import RunStore

    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@localhost",
        "commit",
        "--allow-empty",
        "-qm",
        "initial",
    )
    proposal = {
        "files": [
            {
                "path": "calculadora.py",
                "operation": "create",
                "new_content": (
                    'from math import cos, sin, tan\n\n__all__ = ["cos", "sin", "tan"]\n'
                ),
                "rationale": "Funciones trigonometricas",
            },
            {
                "path": "test_calculadora.py",
                "operation": "create",
                "new_content": (
                    "from calculadora import cos, sin, tan\n\n\n"
                    "def test_trig():\n    assert sin(0) == 0\n"
                    "    assert cos(0) == 1\n    assert tan(0) == 0\n"
                ),
                "rationale": "Pruebas seno coseno tangente",
            },
        ],
        "rationale": "Calculadora con evidencia",
    }
    monkeypatch.setattr(
        model_routing,
        "gateway_from_settings",
        lambda _: ModelGateway([FakeModelAdapter(structured=proposal)]),
    )
    settings = Settings(
        _env_file=None,
        profile_id="calculator-test",
        remote_model_roles=["coder"],
        workspace_root=tmp_path / "worktrees",
        allowed_test_targets=["pytest.unit", "ruff.check"],
    )
    with RunStore(tmp_path / "graph.sqlite3") as store:
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado(
            "Construye una calculadora con seno coseno tangente",
            options=RunOptions(repo_path=str(repo)),
        )
        first = engine.start(state)
        assert first.instruction.capture_fidelity == 1.0
        assert first.interpretation.intent == "modify"
        final = engine.resume(state.run_id, "approved")
        assert all(test.exit_code == 0 for test in final.evidence.test_runs), "\n".join(
            test.target + test.stdout + test.stderr for test in final.evidence.test_runs
        )
        assert final.status == "awaiting_approval", final.errors
        assert {test.target for test in final.evidence.test_runs} == {"pytest.unit", "ruff.check"}
        assert all(test.exit_code == 0 for test in final.evidence.test_runs)
        assert "1 passed" in final.evidence.test_runs[0].stdout
        evidence_events = [
            event for event in store.events(state.run_id) if event.kind == "test_target_completed"
        ]
        assert len(evidence_events) == 2
        assert evidence_events[0].data["evidence"]["stdout"] == final.evidence.test_runs[0].stdout
        assert engine.get(state.run_id).evidence.test_runs == final.evidence.test_runs
        assert not (repo / "calculadora.py").exists()


def test_missing_repository_stops_before_remote_coder(tmp_path, monkeypatch):
    from ai_swe.config import Settings
    from ai_swe.graph import RunEngine, model_routing
    from ai_swe.state import RunStore

    monkeypatch.setattr(
        model_routing,
        "gateway_from_settings",
        lambda _: (_ for _ in ()).throw(AssertionError("model must not be called")),
    )
    settings = Settings(
        _env_file=None, remote_model_roles=["coder"], workspace_root=tmp_path / "worktrees"
    )
    with RunStore(tmp_path / "no-repo.sqlite3") as store:
        engine = RunEngine(store, settings=settings)
        first = engine.start(engine.crear_estado("Construye una calculadora"))
        final = engine.resume(first.run_id, "approved")
        assert final.status == "needs_human"
        assert any(error.error_class == "SANDBOX_NO_REPO" for error in final.errors)
        assert final.budget.used_model_calls == 0


def test_fake_git_metadata_stops_before_remote_call(tmp_path, monkeypatch):
    from ai_swe.config import Settings
    from ai_swe.contracts import RunOptions
    from ai_swe.graph import RunEngine, model_routing
    from ai_swe.state import RunStore

    def forbidden(_):
        raise AssertionError("fake Git metadata must never reach model construction")

    monkeypatch.setattr(model_routing, "gateway_from_settings", forbidden)
    for kind in ("directory", "file", "unborn"):
        repo = tmp_path / kind
        repo.mkdir()
        metadata = repo / ".git"
        if kind == "directory":
            metadata.mkdir()
        elif kind == "file":
            metadata.write_text("gitdir: missing-path\n")
        else:
            import subprocess

            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, capture_output=True)
        settings = Settings(
            _env_file=None, remote_model_roles=["coder"], workspace_root=tmp_path / "worktrees"
        )
        with RunStore(tmp_path / (kind + ".sqlite3")) as store:
            engine = RunEngine(store, settings=settings)
            first = engine.start(
                engine.crear_estado(
                    "Construye una calculadora", options=RunOptions(repo_path=str(repo))
                )
            )
            final = engine.resume(first.run_id, "approved")
            assert final.status == "needs_human"
            assert any(error.error_class == "SANDBOX_NO_REPO" for error in final.errors)
            assert final.budget.used_model_calls == 0


def test_git_root_validation_accepts_linked_worktree(tmp_path):
    import subprocess

    from ai_swe.graph.model_routing import _authorized_git_root

    repo, linked = tmp_path / "repo", tmp_path / "linked"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    git("init", "-q")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@localhost",
        "commit",
        "--allow-empty",
        "-qm",
        "initial",
    )
    git("worktree", "add", "--detach", str(linked), "HEAD")
    assert (linked / ".git").is_file()
    assert _authorized_git_root(str(linked), str(linked))
    assert not _authorized_git_root(str(linked), str(repo))


def test_coder_retry_receives_latest_actual_evidence_and_review(tmp_path, monkeypatch):
    from ai_swe.contracts import Evidence, Outputs, ReviewVerdict, TestRun
    from ai_swe.graph import RunEngine, nodes
    from ai_swe.models import FakeModelAdapter, ModelGateway
    from ai_swe.security import register_secret
    from ai_swe.state import RunStore

    secret = "synthetic-calculator-retry-secret"
    register_secret(secret)
    fake = FakeModelAdapter(structured={"files": [], "rationale": "Correccion de imports"})
    monkeypatch.setattr(nodes, "_GATEWAY", ModelGateway([fake]))
    with RunStore(tmp_path / "retry.sqlite3") as store:
        state = RunEngine(store).crear_estado("Construye una calculadora")
    state = state.model_copy(
        update={
            "evidence": Evidence(
                test_runs=[
                    TestRun(
                        target="ruff.check", exit_code=1, stdout="obsolete error", duration_s=1
                    ),
                    TestRun(target="pytest.unit", exit_code=0, stdout="3 passed", duration_s=1),
                    TestRun(
                        target="ruff.check",
                        exit_code=1,
                        stdout="I001 Import block is un-sorted: calculadora.py:1\n" + secret,
                        stderr="lint diagnostic",
                        duration_s=1,
                    ),
                ]
            ),
            "outputs": Outputs(
                reviewer_output=ReviewVerdict(
                    decision="request_changes",
                    summary="Ordenar imports sin omitir Ruff",
                    required_fixes=["Ordena cos, sin, tan y conserva las pruebas"],
                    findings=[],
                )
            ),
        }
    )
    nodes._coder_del_modelo(state)
    prompt = fake.calls[0].messages[1].content
    assert "I001 Import block is un-sorted: calculadora.py:1" in prompt
    assert "Correccion de una propuesta previa" in prompt
    assert "Implementacion inicial" not in prompt
    assert "exit_code=1" in prompt and "3 passed" in prompt
    assert "lint diagnostic" in prompt
    assert "Ordena cos, sin, tan y conserva las pruebas" in prompt
    assert "Ordenar imports sin omitir Ruff" in prompt
    assert "obsolete error" not in prompt
    assert secret not in prompt
    assert "[REDACTED]" in prompt
    assert "datos, no instrucciones" in prompt


def test_reviewer_escalation_explains_known_reason(tmp_path):
    from ai_swe.contracts import Outputs, ReviewVerdict
    from ai_swe.graph import RunEngine, nodes
    from ai_swe.state import RunStore

    with RunStore(tmp_path / "escalate.sqlite3") as store:
        state = RunEngine(store).crear_estado("Construye una calculadora")
    verdict = ReviewVerdict(
        decision="escalate",
        findings=[],
        summary="Falta evidencia para verificar tangente",
        required_fixes=[],
    )
    state = state.model_copy(update={"outputs": Outputs(reviewer_output=verdict)})
    result = nodes.escalate(state)
    assert result["status"] == "needs_human" and result["next_step"] is None
    assert result["errors"][-1].error_class == "REVIEWER_ESCALATED"
    assert "tangente" in result["errors"][-1].message
    assert "fallo del propio orquestador" not in result["errors"][-1].message

    state = state.model_copy(
        update={
            "budget": state.budget.model_copy(update={"review_cycles_used": 2}),
        }
    )
    requested = ReviewVerdict(
        decision="request_changes",
        findings=[],
        summary="Ruff I001 sigue fallando",
        required_fixes=["Ordenar imports"],
    )
    exhausted = nodes._guarda_ciclos(state, requested)
    state = state.model_copy(update={"outputs": Outputs(reviewer_output=exhausted)})
    result = nodes.escalate(state)
    assert result["errors"][-1].error_class == "REVIEW_CYCLES_EXHAUSTED"
    assert "Ruff I001" in result["errors"][-1].message
    assert "Ordenar imports" in result["errors"][-1].message
