"""Pruebas herméticas offline del flujo de pausa y recuperación por presupuesto.

Verifica:
1. El fallo de presupuesto en Coder no cae en needs_human ni produce parches vacíos:
   transiciona a `RunStatus.PAUSED` con `next_step="coder"` y conserva requisitos, plan y evidencia.
2. La verificación previa comprueba el saldo/bóveda antes de reanudar y rechaza si sigue insuficiente.
3. La protección contra dobles clics impide que dos peticiones concurrentes lancen ejecuciones duplicadas.
4. Tras recargar saldo/presupuesto, `resume_paused` retoma Coder sin repetir nodos previos y
   mantiene intacta la puerta de aprobación humana posterior.
5. Las reservas con consumo incierto (despachadas sin confirmación) se conservan intactas y
   se advierten explícitamente en el diagnóstico.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_swe.config import Settings
from ai_swe.contracts import (
    AgentRole,
    EventKind,
    Intent,
    RunError,
    RunOptions,
    RunStatus,
)
from ai_swe.graph import NothingToResume, RunEngine, model_routing, nodes
from ai_swe.models import (
    BudgetExceededError,
    FakeModelAdapter,
    ModelGateway,
)
from ai_swe.state import RunStore
from ai_swe.state.budget_ledger import BudgetLedger, LedgerError


def _crear_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@test.local",
            "commit",
            "--allow-empty",
            "-qm",
            "base",
        ],
        cwd=path,
        check=True,
    )
    return path


def test_coder_budget_exceeded_enters_paused_preserving_plan_and_evidence(
    tmp_path: Path, monkeypatch
):
    repo = _crear_repo(tmp_path / "repo")
    db_path = tmp_path / "budget_test.sqlite3"

    class FailingCoderAdapter(FakeModelAdapter):
        def generate(self, request):
            if request.agent_role == AgentRole.CODER:
                raise BudgetExceededError(
                    "Presupuesto por ejecución agotado: tokens (usado: 200000 / máx: 200000)",
                    motivos=("tokens",),
                )
            return super().generate(request)

    adapter = FailingCoderAdapter()
    gw = ModelGateway([adapter])
    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: gw)

    settings = Settings(
        _env_file=None,
        network_egress_enabled=True,
        profile_id="budget-pause-test",
        remote_model_roles=["coder"],
        workspace_root=tmp_path / "worktrees",
        allowed_test_targets=["pytest.unit"],
    )

    try:
        with RunStore(db_path) as store:
            engine = RunEngine(store, settings=settings)
            state = engine.crear_estado(
                "Construye una funcion suma en app.py",
                options=RunOptions(repo_path=str(repo)),
            )
            # 1. Iniciar ejecucion: llega hasta confirmacion de requisitos
            first = engine.start(state)
            assert first.status is RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION

            # 2. Confirmar requisitos: el flujo pasa supervisor (plan), researcher,
            #    y al llegar a Coder se eleva BudgetExceededError.
            paused = engine.resume(state.run_id, "approved")

            # 1. El flujo queda "Pausado por presupuesto", conservando requisitos y plan
            assert paused.status is RunStatus.PAUSED
            assert paused.next_step == "coder"
            assert paused.interpretation is not None
            assert paused.interpretation.intent is Intent.MODIFY
            assert paused.plan is not None
            assert len(paused.plan.subtasks) > 0

            # Verificacion del error registrado
            assert any(e.error_class == "BUDGET_EXCEEDED" for e in paused.errors)
            budget_err = [e for e in paused.errors if e.error_class == "BUDGET_EXCEEDED"][0]
            assert budget_err.agent == "coder"
            assert budget_err.recoverable is True
            assert "tokens" in budget_err.message

            # Evento emitido al almacen
            eventos = [e for e in store.events(state.run_id) if e.kind == EventKind.RUN_PAUSED]
            assert len(eventos) >= 1
            assert eventos[0].data["reason"] == "BUDGET_EXCEEDED"
            assert eventos[0].data["node"] == "coder"
    finally:
        gw.close()


def test_resume_verifies_budget_preflight_and_blocks_if_still_exhausted(tmp_path: Path):
    repo = _crear_repo(tmp_path / "repo")
    db_path = tmp_path / "preflight_test.sqlite3"

    with RunStore(db_path) as store:
        settings = Settings(
            _env_file=None,
            profile_id="vault-test",
            workspace_root=tmp_path / "worktrees",
        )
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado(
            "Corrige error",
            options=RunOptions(repo_path=str(repo)),
        )
        engine.start(state)

        # Crear estado pausado por presupuesto con error registrado
        ahora = datetime.now(UTC)
        error = RunError(
            error_class="BUDGET_EXCEEDED",
            agent="coder",
            message="Saldo local insuficiente en la bóveda: disponible $0.00, requerido $0.50 (límite de bóveda: $5.00)",
            recoverable=True,
            occurred_at=ahora,
        )
        config = engine._config(state.run_id)
        engine._app.update_state(
            config,
            {
                "status": RunStatus.PAUSED,
                "next_step": "coder",
                "errors": [*engine.get(state.run_id).errors, error],
            },
        )
        engine.continuity.set_checkpoint_status(state.run_id, RunStatus.PAUSED)

        # Configurar bóveda sin saldo disponible (límite 5.0, consumido 5.0)
        ledger = BudgetLedger(db_path)
        ledger.set_limit(5.0)
        res_id = ledger.reserve(state.run_id, 5.0, run_limit=10.0)
        ledger.settle(res_id, 5.0)
        assert ledger.summary()["available"] == 0.0

        # Verificar preflight: debe fallar explicando que el saldo es insuficiente
        with pytest.raises(BudgetExceededError) as exc_info:
            engine.verificar_presupuesto_reanudacion(state.run_id)

        assert "saldo disponible en la bóveda es $0.00" in str(exc_info.value)
        assert engine.get(state.run_id).status is RunStatus.PAUSED


def test_double_click_protection_prevents_duplicate_resume(tmp_path: Path):
    repo = _crear_repo(tmp_path / "repo")
    db_path = tmp_path / "double_click_test.sqlite3"

    with RunStore(db_path) as store:
        engine = RunEngine(store)
        state = engine.crear_estado("Peticion", options=RunOptions(repo_path=str(repo)))
        paused_state = state.model_copy(update={"status": RunStatus.PAUSED, "next_step": "coder"})
        engine.create(paused_state)
        engine.continuity.set_checkpoint_status(state.run_id, RunStatus.PAUSED)

        # Primera reclamación exitosa
        engine.reclamar_reanudacion_pausa(state.run_id)

        # Segunda reclamación concurrente (doble clic) debe lanzar NothingToResume
        with pytest.raises(NothingToResume, match="ya tiene una reanudacion en curso"):
            engine.reclamar_reanudacion_pausa(state.run_id)

        # Liberar reclamación
        engine.olvidar_reclamacion(state.run_id)

        # Tras liberar, otra reclamación puede proceder
        engine.reclamar_reanudacion_pausa(state.run_id)
        engine.olvidar_reclamacion(state.run_id)


def test_budget_recovery_resumes_coder_and_preserves_subsequent_approvals(
    tmp_path: Path, monkeypatch
):
    repo = _crear_repo(tmp_path / "repo")
    db_path = tmp_path / "recovery_test.sqlite3"

    proposal = {
        "files": [
            {
                "path": "suma.py",
                "operation": "create",
                "new_content": "def sumar(a: int, b: int) -> int:\n    return a + b\n",
                "rationale": "Implementacion de sumar",
            },
            {
                "path": "test_suma.py",
                "operation": "create",
                "new_content": "from suma import sumar\n\ndef test_sumar():\n    assert sumar(2, 3) == 5\n",
                "rationale": "Pruebas de sumar",
            },
        ],
        "rationale": "Propuesta completa con pruebas",
    }

    should_fail = [True]

    class RecoveringAdapter(FakeModelAdapter):
        def generate(self, request):
            if request.agent_role == AgentRole.CODER:
                if should_fail[0]:
                    raise BudgetExceededError(
                        "Saldo local insuficiente en la bóveda: disponible $0.00",
                        motivos=("ledger",),
                    )
                return super().generate(request)
            return super().generate(request)

    adapter = RecoveringAdapter(structured=proposal)
    gw = ModelGateway([adapter])
    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: gw)

    settings = Settings(
        _env_file=None,
        network_egress_enabled=True,
        profile_id="budget-recovery-profile",
        remote_model_roles=["coder"],
        workspace_root=tmp_path / "worktrees",
        allowed_test_targets=["pytest.unit"],
    )

    try:
        with RunStore(db_path) as store:
            engine = RunEngine(store, settings=settings)
            state = engine.crear_estado(
                "Implementa suma en suma.py",
                options=RunOptions(repo_path=str(repo)),
            )
            # 1. Iniciar y pasar puerta de requisitos
            first = engine.start(state)
            assert first.status is RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION

            # 2. Coder falla por presupuesto -> RunStatus.PAUSED
            paused = engine.resume(state.run_id, "approved")
            assert paused.status is RunStatus.PAUSED
            assert paused.next_step == "coder"

            # 3. Corregir presupuesto simulado (recargar saldo)
            should_fail[0] = False

            # 4. Reanudar ejecución: retoma Coder sin repetir nodos anteriores
            resumed = engine.resume_paused(state.run_id)

            # Coder corrió, el sandbox aplicó el parche, corrieron pruebas, reviewer aprobó
            # y se detiene en la puerta humana de aprobación
            assert resumed.status is RunStatus.AWAITING_APPROVAL
            assert len(resumed.evidence.test_runs) > 0
            assert all(t.exit_code == 0 for t in resumed.evidence.test_runs)
            assert resumed.outputs.coder_output is not None
            assert len(resumed.outputs.coder_output.files_changed) == 2

            # 5. Humano aprueba los cambios -> completado
            completed = engine.resume(state.run_id, "approved")
            assert completed.status is RunStatus.COMPLETED
            assert (repo / "suma.py").is_file()
            assert "def sumar" in (repo / "suma.py").read_text(encoding="utf-8")
    finally:
        gw.close()


def test_uncertain_consumption_reservation_retained_and_warned(tmp_path: Path):
    db_path = tmp_path / "uncertain_test.sqlite3"
    ledger = BudgetLedger(db_path)
    ledger.set_limit(1.0)

    # 1. Reservar llamada
    res_id = ledger.reserve_call("run-uncertain", run_limit=1.0, estimate=0.2)

    # 2. Marcar como despachada (salió la llamada hacia el proveedor)
    ledger.mark_dispatched(res_id)

    # 3. La llamada tuvo consumo incierto (timeout / red interrumpida sin coste declarado)
    ledger.settle(res_id, None)

    # 4. La reserva NO se libera automáticamente
    info = ledger.unresolved_reservations_for_run("run-uncertain")
    assert info["count"] == 1
    assert info["amount"] > 0

    # 5. Cancelar la ejecución NO libera reservas ya despachadas
    cancelled = ledger.reconcile_cancelled("run-uncertain")
    assert cancelled["released"] == 0
    assert cancelled["unresolved"] == 1

    # 6. Al intentar otra llamada con saldo restante insuficiente, el diagnóstico
    #    advierte explícitamente sobre la reserva previa de cobro incierto retenida
    with pytest.raises(LedgerError) as exc:
        ledger.reserve_call("run-uncertain", run_limit=1.0, estimate=0.5)

    assert "cobro incierto" in str(exc.value)
    assert "retenida" in str(exc.value)


def test_gateway_retries_reuse_reservation_without_budget_starvation(tmp_path: Path):
    """Verifica que un reintento transitorio por rate limit u otro error recuperable
    no duplique la reserva en el ledger ni cause un falso agotamiento de presupuesto.
    """
    from ai_swe.contracts import Instruction, InstructionSource
    from ai_swe.models import (
        MessageRole,
        ModelMessage,
        ModelPricing,
        ModelRateLimitError,
        ModelRequest,
        PricingTable,
    )

    db_path = tmp_path / "retry_budget_test.sqlite3"
    ledger = BudgetLedger(db_path)
    ledger.set_limit(5.0)

    intentos = 0

    class RateLimitThenSucceedAdapter(FakeModelAdapter):
        def generate(self, request):
            nonlocal intentos
            intentos += 1
            if intentos == 1:
                raise ModelRateLimitError("Quota / Rate limit temporal", retry_after_s=0.001)
            return super().generate(request)

    adapter = RateLimitThenSucceedAdapter(name="gemini_test", content="respuesta recuperada")
    pricing = PricingTable({
        "fake-model": ModelPricing(input_per_1k=0.001, output_per_1k=0.002)
    })
    settings = Settings(
        profile_id="test_profile",
        model_name="fake-model",
        max_cost_per_run=1.0,
        max_cost_per_hour=10.0,
        state_db_path=db_path,
    )
    gw = ModelGateway(
        [adapter],
        profile_settings=settings,
        pricing=pricing,
        max_retries=2,
        sleep=lambda _s: None,
    )

    req = ModelRequest(
        messages=[ModelMessage(role=MessageRole.USER, content="test")],
        model="fake-model",
        run_id="run-retry-ok",
        max_output_tokens=100,
    )

    resp = gw.generate(req)
    assert resp.content == "respuesta recuperada"
    assert intentos == 2

    # Verificar que las reservas no quedaron colgadas
    unresolved = ledger.unresolved_reservations_for_run("run-retry-ok")
    assert unresolved["count"] == 0

