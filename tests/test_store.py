"""Pruebas del almacen de estado.

La prueba central de este fichero es
`test_el_estado_completo_sobrevive_al_checkpoint`. Existe porque se encontro un
fallo real: la lista de tipos permitidos se construia a partir de `__all__`, que
no exportaba `Outputs`, `Artifacts` ni `Evidence`. El resultado no era una
excepcion, era peor: el checkpoint los **descartaba en silencio** y el estado
recuperado perdia datos sin avisar.

Una prueba que solo ejercitara el camino que el grafo puebla no lo habria
detectado, porque el grafo no rellena `artifacts.changed_files`, `evidence.test_runs`
ni `approvals`. Por eso aqui se puebla el estado **entero** a mano.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from langgraph.graph import END, START, StateGraph

from ai_swe.contracts import (
    Approval,
    ApprovalDecision,
    Artifacts,
    Budget,
    CodeChange,
    Evidence,
    FileChange,
    FinalReport,
    Finding,
    Instruction,
    InstructionSource,
    Intent,
    Outputs,
    ResearchOutput,
    ReviewDecision,
    ReviewVerdict,
    RunError,
    RunOptions,
    RunState,
    RunStatus,
    Scope,
    Severity,
    TaskInterpretation,
    TestRun,
)
from ai_swe.graph.engine import RunEngine, RunNotFound
from ai_swe.state import RunStore, msgpack_allowlist

AHORA = datetime(2026, 10, 6, 12, 0, 0, tzinfo=UTC)
SHA = "a" * 64


def _estado_completo(run_id: str = "run-completo") -> RunState:
    """Un RunState con **todos** los campos poblados, anidados incluidos."""
    return RunState(
        run_id=run_id,
        trace_id="trace-completo",
        created_at=AHORA,
        updated_at=AHORA + timedelta(seconds=30),
        instruction=Instruction(
            text="corrige parse_duration",
            source=InstructionSource.TEXT,
            confirmed_by_user=True,
        ),
        options=RunOptions(
            repo_path="/repo/demo", allowed_paths=["src"], protected_paths=["src/db"], dry_run=True
        ),
        interpretation=TaskInterpretation(
            intent=Intent.MODIFY,
            scope=Scope(repo_path="/repo/demo", allowed_paths=["src"], protected_paths=["src/db"]),
            constraints=["no toques las pruebas"],
            confidence=0.9,
            rationale="pide corregir codigo",
        ),
        outputs=Outputs(
            researcher_output=ResearchOutput(
                findings=[
                    Finding(
                        severity=Severity.HIGH,
                        path="src/util/timeparse.py",
                        line=42,
                        explanation="no maneja el formato H:MM:SS",
                        evidence="return int(match.group(1)) * 60",
                    )
                ],
                unknowns=["no se reviso el resto del paquete"],
                files_read=["src/util/timeparse.py"],
            ),
            coder_output=CodeChange(
                files_changed=[
                    FileChange(path="src/util/timeparse.py", added=12, removed=3, sha256=SHA)
                ],
                diff="--- a\n+++ b\n",
                rationale="anade el formato H:MM:SS",
                diff_sha256=SHA,
            ),
            reviewer_output=ReviewVerdict(
                decision=ReviewDecision.ACCEPT,
                findings=[
                    Finding(
                        severity=Severity.INFO,
                        path="(pruebas)",
                        explanation="las pruebas pasan",
                        evidence="pytest.unit -> exit 0",
                    )
                ],
                summary="el cambio satisface el criterio",
            ),
        ),
        artifacts=Artifacts(
            worktree_path="/tmp/wt",
            base_commit="deadbeef",
            changed_files=[FileChange(path="src/util/timeparse.py", added=12, removed=3, sha256=SHA)],
            diff="--- a\n+++ b\n",
        ),
        evidence=Evidence(
            test_runs=[
                TestRun(
                    target="pytest.unit",
                    exit_code=0,
                    stdout="3 passed",
                    stderr="",
                    duration_s=1.25,
                    reproducible=True,
                )
            ],
            findings=[
                Finding(
                    severity=Severity.LOW,
                    path="src/app.py",
                    line=7,
                    explanation="import sin usar",
                    evidence="import os",
                )
            ],
        ),
        approvals=[
            Approval(
                action="promote_changes",
                actor="pepe",
                decided_at=AHORA,
                content_sha256=SHA,
                decision=ApprovalDecision.APPROVED,
                reason="",
            )
        ],
        errors=[
            RunError(
                error_class="TEST_TIMEOUT",
                agent="coder",
                message="la primera ejecucion expiro",
                recoverable=True,
                occurred_at=AHORA,
            )
        ],
        budget=Budget(used_tokens=1234, used_tool_calls=7, elapsed_seconds=12.5, review_cycles_used=1),
        final_report=FinalReport(
            summary="corregido",
            changes_applied=["src/util/timeparse.py (+12/-3)"],
            tests_executed=["pytest.unit: exit 0 en 1.25s"],
            review="el cambio satisface el criterio",
            pending=["no se reviso el resto del paquete"],
        ),
        status=RunStatus.COMPLETED,
        next_step=None,
    )


def _grafo_eco(store: RunStore):
    """Grafo minimo que solo deja pasar el estado, para aislar el checkpoint."""
    grafo = StateGraph(RunState)
    grafo.add_node("eco", lambda _estado: {})
    grafo.add_edge(START, "eco")
    grafo.add_edge("eco", END)
    return grafo.compile(checkpointer=store.checkpointer())


# ------------------------------------------------------------- serializacion


def test_la_lista_de_tipos_permitidos_no_esta_vacia() -> None:
    """Control positivo: una lista vacia haria pasar la prueba de ida y vuelta
    solo si el estado tambien estuviera vacio."""
    permitidos = msgpack_allowlist()
    assert len(permitidos) >= 30
    assert ("ai_swe.contracts.state", "RunState") in permitidos
    assert ("ai_swe.contracts.state", "Outputs") in permitidos
    assert ("ai_swe.contracts.state", "Artifacts") in permitidos
    assert ("ai_swe.contracts.state", "Evidence") in permitidos


def test_el_estado_completo_sobrevive_al_checkpoint(tmp_path) -> None:
    """Ida y vuelta por el checkpoint sin perder **ningun** campo anidado.

    Este es el fallo que se encontro: los objetos anidados se descartaban en
    silencio. La igualdad profunda es lo que lo detecta.
    """
    store = RunStore(tmp_path / "estado.db")
    try:
        app = _grafo_eco(store)
        original = _estado_completo()
        app.invoke(original, {"configurable": {"thread_id": original.run_id}})

        instantanea = app.get_state({"configurable": {"thread_id": original.run_id}})
        recuperado = RunState.model_validate(instantanea.values)
    finally:
        store.close()

    assert recuperado == original, "el checkpoint no conservo el estado completo"
    # Comprobaciones concretas de los objetos que se perdian en silencio.
    assert recuperado.outputs.coder_output is not None
    assert recuperado.outputs.coder_output.files_changed[0].sha256 == SHA
    assert recuperado.artifacts.changed_files[0].path == "src/util/timeparse.py"
    assert recuperado.evidence.test_runs[0].duration_s == pytest.approx(1.25)
    assert recuperado.approvals[0].actor == "pepe"


# -------------------------------------------------------------------- indice


def test_el_indice_refleja_el_estado(tmp_path) -> None:
    store = RunStore(tmp_path / "estado.db")
    try:
        motor = RunEngine(store)
        estado = motor.crear_estado("¿Dónde se valida el token?")
        inicial = motor.start(estado)

        # M2: la primera parada es la puerta de requisitos, y el indice la refleja.
        assert inicial.status is RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION
        assert store.summary(inicial.run_id).status is (
            RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION
        )

        final = motor.resume(inicial.run_id, "approved")

        resumen = store.summary(final.run_id)
        assert resumen is not None
        assert resumen.status is RunStatus.COMPLETED
        assert resumen.intent == "question"

        listado = store.list_summaries()
        assert [r.run_id for r in listado] == [final.run_id]
    finally:
        store.close()


def test_consultar_una_ejecucion_inexistente_falla(tmp_path) -> None:
    store = RunStore(tmp_path / "estado.db")
    try:
        with pytest.raises(RunNotFound):
            RunEngine(store).get("run-que-no-existe")
    finally:
        store.close()


# ------------------------------------------------------------------ eventos


def test_el_registro_de_eventos_es_monotono(tmp_path) -> None:
    store = RunStore(tmp_path / "estado.db")
    try:
        motor = RunEngine(store)
        final = motor.start(motor.crear_estado("explica el modulo de auth"))

        eventos = store.events(final.run_id)
        assert [e.seq for e in eventos] == sorted(e.seq for e in eventos)
        assert eventos[0].kind == "run.created"
        assert any(e.kind == "run.status" for e in eventos)

        # `after_seq` filtra de verdad, no devuelve todo.
        assert store.events(final.run_id, after_seq=eventos[0].seq) == eventos[1:]
        assert store.events(final.run_id, after_seq=eventos[-1].seq) == []
    finally:
        store.close()


def test_los_eventos_estan_aislados_por_ejecucion(tmp_path) -> None:
    store = RunStore(tmp_path / "estado.db")
    try:
        motor = RunEngine(store)
        primera = motor.start(motor.crear_estado("explica el modulo de auth"))
        segunda = motor.start(motor.crear_estado("¿Dónde se valida el token?"))

        assert {e.kind for e in store.events(primera.run_id)} >= {"run.created"}
        assert all(e.seq >= 1 for e in store.events(segunda.run_id))
        assert primera.run_id != segunda.run_id
    finally:
        store.close()


def test_el_almacen_se_puede_usar_como_gestor_de_contexto(tmp_path) -> None:
    with RunStore(tmp_path / "estado.db") as store:
        assert store.list_summaries() == []
