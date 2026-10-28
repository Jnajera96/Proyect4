"""Pruebas de F5: ejecucion iterativa dirigida por el plan.

**Que protege este fichero.** Que `researcher` acumule evidencia sin sobrescribir,
que `plan_index` avance tras cada subtarea, que el enrutador `route_after_execution`
lea el indice y envie al agente correcto, y que el plan se agote sin bucles infinitos.

Ninguna prueba toca la red ni exige credenciales.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai_swe.contracts import (
    AgentRole,
    Budget,
    Evidence,
    Finding,
    Instruction,
    InstructionSource,
    Intent,
    RunOptions,
    RunPlan,
    RunState,
    RunStatus,
    Scope,
    Severity,
    Subtask,
    TaskInterpretation,
)
from ai_swe.graph import nodes

# --------------------------------------------------------------- utilidades


def _subtarea(sid: str, agent: AgentRole, depends: list[str] | None = None) -> Subtask:
    return Subtask(
        id=sid,
        description=f"subtarea {sid}",
        agent=agent,
        depends_on=depends or [],
        allowed_tools=["read_file"],
        done_criteria="criterio declarado",
    )


def _plan(*agentes: AgentRole) -> RunPlan:
    return RunPlan(
        subtasks=[_subtarea(f"t{i}", a) for i, a in enumerate(agentes)],
        max_review_cycles=2,
        rationale="plan de prueba",
    )


def _estado(
    *,
    plan: RunPlan | None = None,
    plan_index: int = 0,
    intencion: Intent = Intent.MODIFY,
) -> RunState:
    ahora = datetime.now(UTC)
    return RunState(
        run_id="run-f5",
        trace_id="trace-f5",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text="arregla el parser", source=InstructionSource.TEXT, confirmed_by_user=True
        ),
        options=RunOptions(repo_path="/repo/autorizado"),
        interpretation=TaskInterpretation(
            intent=intencion,
            scope=Scope(repo_path="/repo/autorizado"),
            constraints=[],
            confidence=0.9,
            rationale="prueba",
        ),
        plan=plan,
        plan_index=plan_index,
        budget=Budget(),
    )


# --------------------------------------------------------------- 1. contrato


def test_runstate_acepta_plan_index_por_defecto() -> None:
    """El campo nuevo entra con default=0 y no rompe la serializacion."""
    estado = _estado()
    assert estado.plan_index == 0
    # Debe poder ir y volver por JSON sin perder el valor.
    recuperado = RunState.model_validate_json(estado.model_dump_json())
    assert recuperado.plan_index == 0


def test_runstate_plan_index_no_puede_ser_negativo() -> None:
    """ge=0 en el Field."""
    with pytest.raises(Exception):  # pydantic.ValidationError
        _estado(plan_index=-1)


# --------------------------------------------------------------- 2. researcher


def test_researcher_avanza_plan_index() -> None:
    """Tras ejecutar, el indice aumenta en 1."""
    estado = _estado(plan=_plan(AgentRole.RESEARCHER))
    delta = nodes.researcher(estado)
    assert delta["plan_index"] == 1


def test_researcher_acumula_hallazgos_sin_sobrescribir() -> None:
    """La evidencia previa se conserva; la nueva se concatena."""
    previo = Finding(severity=Severity.INFO, path="a.py", explanation="previo", evidence="x")
    estado = _estado(plan=_plan(AgentRole.RESEARCHER, AgentRole.RESEARCHER))
    estado = estado.model_copy(update={
        "evidence": Evidence(findings=[previo]),
        "plan_index": 0,
    })

    delta = nodes.researcher(estado)
    hallazgos = delta["evidence"].findings
    assert any(f.path == "a.py" for f in hallazgos), "se perdio el hallazgo previo"
    # Si el repo no existe, solo queda el previo; si existe, se anaden mas.
    # La propiedad que importa es que el previo NO se pierda, no el numero total.


def test_researcher_acumula_files_read() -> None:
    """Los archivos leidos de subtareas anteriores se conservan."""
    estado = _estado(plan=_plan(AgentRole.RESEARCHER, AgentRole.RESEARCHER))
    # Primera pasada simulada
    estado = estado.model_copy(update={
        "outputs": estado.outputs.model_copy(update={
            "researcher_output": nodes.ResearchOutput(
                findings=[],
                unknowns=[],
                files_read=["primero.py"],
            )
        }),
        "plan_index": 0,
    })
    delta = nodes.researcher(estado)
    leidos = delta["outputs"].researcher_output.files_read
    assert "primero.py" in leidos


# --------------------------------------------------------------- 3. enrutador


def test_route_after_plan_va_a_la_primera_subtarea() -> None:
    """Tras planificar, se empieza por el agente de la primera subtarea."""
    estado = _estado(plan=_plan(AgentRole.RESEARCHER))
    assert nodes.route_after_plan(estado) == "researcher"


def test_route_after_plan_con_coder_primero() -> None:
    """Un plan que empiece por coder debe enrutar a coder."""
    estado = _estado(plan=_plan(AgentRole.CODER))
    assert nodes.route_after_plan(estado) == "coder"


def test_route_after_execution_va_a_la_siguiente_subtarea() -> None:
    """Con plan_index=1, se salta la primera y va a la segunda."""
    estado = _estado(plan=_plan(AgentRole.RESEARCHER, AgentRole.CODER), plan_index=1)
    assert nodes.route_after_execution(estado) == "coder"


def test_route_after_execution_modify_no_omite_coder_con_plan_agotado() -> None:
    """Una solicitud modify no termina si el plan solo hizo investigacion."""
    estado = _estado(plan=_plan(AgentRole.RESEARCHER), plan_index=1)
    assert nodes.route_after_execution(estado) == "coder"


def test_route_after_execution_inspect_finaliza_con_plan_agotado() -> None:
    estado = _estado(plan=_plan(AgentRole.RESEARCHER), plan_index=1, intencion=Intent.INSPECT)
    assert nodes.route_after_execution(estado) == "finalize"


def test_route_after_execution_sin_plan_usa_la_ruta_estatica() -> None:
    """Sin plan, F5 no aplica: se comporta como M1."""
    estado = _estado(plan=None, intencion=Intent.QUESTION)
    assert nodes.route_after_execution(estado) == "answer_direct"


def test_route_after_execution_sin_plan_modify_va_a_coder() -> None:
    """Sin plan e intencion modify, la ruta estatica va a coder."""
    estado = _estado(plan=None, intencion=Intent.MODIFY)
    assert nodes.route_after_execution(estado) == "coder"


# --------------------------------------------------------------- 4. ciclo acotado


def test_el_indice_nunca_decrece() -> None:
    """El researcher siempre suma 1; nunca resta."""
    estado = _estado(plan=_plan(AgentRole.RESEARCHER), plan_index=5)
    delta = nodes.researcher(estado)
    assert delta["plan_index"] == 6


def test_route_after_execution_no_buclea_con_plan_vacio() -> None:
    """Un plan sin subtareas no crea un bucle: va directo a finalize.

    Nota: RunPlan exige min_length=1 en subtasks, asi que un plan 'vacio'
    no es un plan valido. El caso real es plan=None con intencion inspect,
    que cae a finalize.
    """
    estado = _estado(plan=None, intencion=Intent.INSPECT)
    assert nodes.route_after_execution(estado) == "finalize"


# --------------------------------------------------------------- 5. integracion


def test_dos_subtareas_researcher_se_ejecutan_en_secuencia() -> None:
    """Modify: dos investigaciones consecutivas todavia deben llegar al Coder."""
    estado = _estado(plan=_plan(AgentRole.RESEARCHER, AgentRole.RESEARCHER))

    # Primera subtarea
    assert nodes.route_after_plan(estado) == "researcher"
    delta1 = nodes.researcher(estado)
    assert delta1["plan_index"] == 1
    estado = estado.model_copy(update=delta1)

    # Segunda subtarea
    assert nodes.route_after_execution(estado) == "researcher"
    delta2 = nodes.researcher(estado)
    assert delta2["plan_index"] == 2
    estado = estado.model_copy(update=delta2)

    # Plan agotado, pero aun falta el Coder solicitado por modify.
    assert nodes.route_after_execution(estado) == "coder"


def test_researcher_luego_coder_luego_finalize() -> None:
    """Flujo: researcher -> coder -> finalize."""
    estado = _estado(plan=_plan(AgentRole.RESEARCHER, AgentRole.CODER))

    assert nodes.route_after_plan(estado) == "researcher"
    delta1 = nodes.researcher(estado)
    estado = estado.model_copy(update=delta1)

    assert nodes.route_after_execution(estado) == "coder"
    delta2 = nodes.coder(estado)
    # El coder tambien debe avanzar el indice: cada ejecutor consume la subtarea
    # que le toca y declara que la ha completado.
    assert delta2["plan_index"] == 2
    estado = estado.model_copy(update=delta2)

    # Plan agotado: se finaliza
    assert nodes.route_after_execution(estado) == "finalize"
