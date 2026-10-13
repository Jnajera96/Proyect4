"""Pruebas de los contratos.

Cubren tres cosas:
  1. Que los contratos son **serializables** (se pueden persistir sin perdida).
  2. Que el verificador de serializabilidad **detecta de verdad** un fallo.
  3. Que las invariantes de diseno estan codificadas y no solo documentadas.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable

import pytest
from pydantic import BaseModel, ValidationError

from ai_swe.contracts import (
    SCHEMA_VERSION,
    AgentRole,
    Budget,
    Instruction,
    InstructionSource,
    Intent,
    RunOptions,
    RunPlan,
    RunState,
    RunStatus,
    Scope,
    Subtask,
    SubtaskStatus,
    TaskInterpretation,
    TestRun,
    TranscriptMeta,
)
from ai_swe.contracts.validate import find_non_serializable

NOW = datetime(2026, 10, 6, 12, 0, 0, tzinfo=UTC)


def _scope() -> Scope:
    return Scope(repo_path="/repo/demo", allowed_paths=["src"], protected_paths=["src/db"])


def _instruction(source: InstructionSource = InstructionSource.TEXT) -> Instruction:
    if source is InstructionSource.VOICE:
        return Instruction(
            text="analiza el proyecto y corrige los errores",
            source=source,
            transcript_meta=TranscriptMeta(
                provider="faster-whisper:large-v3",
                language="es",
                confidence=0.91,
                duration_s=6.4,
            ),
            confirmed_by_user=True,
        )
    return Instruction(
        text="analiza el proyecto y corrige los errores",
        source=InstructionSource.TEXT,
        confirmed_by_user=True,
    )


def _subtask(sid: str, agent: AgentRole, depends: list[str] | None = None) -> Subtask:
    return Subtask(
        id=sid,
        description=f"subtarea {sid}",
        agent=agent,
        depends_on=depends or [],
        allowed_tools=["read_file"],
        done_criteria="criterio declarado",
    )


# ------------------------------------------------------------------ 1. serial
@pytest.mark.parametrize(
    "model",
    [
        Instruction,
        TranscriptMeta,
        Scope,
        TaskInterpretation,
        Subtask,
        RunPlan,
        Budget,
        RunState,
    ],
)
def test_contratos_son_serializables(model: type[BaseModel]) -> None:
    problems = find_non_serializable(model)
    assert problems == [], f"{model.__name__} no es serializable: {problems}"


def test_estado_completo_va_y_vuelve_por_json() -> None:
    """Una ejecucion real debe poder persistirse y recuperarse sin perdida."""
    state = RunState(
        run_id="run-001",
        trace_id="trace-001",
        created_at=NOW,
        updated_at=NOW + timedelta(seconds=12),
        instruction=_instruction(InstructionSource.VOICE),
        interpretation=TaskInterpretation(
            intent=Intent.MODIFY, scope=_scope(), constraints=["no toques las pruebas"], confidence=0.88,
            rationale="la instruccion pide corregir codigo",
        ),
        plan=RunPlan(
            subtasks=[
                _subtask("investigar", AgentRole.RESEARCHER),
                _subtask("corregir", AgentRole.CODER, ["investigar"]),
                _subtask("revisar", AgentRole.REVIEWER, ["corregir"]),
            ],
            max_review_cycles=2,
            rationale="patron modify: researcher -> coder -> reviewer",
        ),
        status=RunStatus.RUNNING,
        next_step="researcher",
    )

    restored = RunState.model_validate_json(state.model_dump_json())
    assert restored == state
    assert restored.instruction.transcript_meta is not None
    assert restored.instruction.transcript_meta.confidence == pytest.approx(0.91)


# ------------------------------------------------- 2. el verificador funciona
def test_el_verificador_detecta_una_funcion_escondida() -> None:
    """Si el verificador no cazara esto, no estaria comprobando nada."""

    class ContratoRoto(BaseModel):
        nombre: str
        callback: Callable[[], None]

    problems = find_non_serializable(ContratoRoto)
    assert problems, "el verificador no detecto un campo Callable"
    assert "callback" in problems[0]


def test_el_verificador_detecta_una_funcion_anidada() -> None:
    class Interno(BaseModel):
        handler: Callable[[str], str]

    class Externo(BaseModel):
        interno: Interno

    problems = find_non_serializable(Externo)
    assert problems, "el verificador no detecto un Callable anidado a dos niveles"
    assert "Interno.handler" in problems[0]


# --------------------------------------------------- 3. invariantes de diseno
def test_instruccion_de_voz_sin_metadatos_es_rechazada() -> None:
    """RF-03: el audio crudo no puede llegar al Supervisor."""
    with pytest.raises(ValidationError, match="transcript_meta"):
        Instruction(text="corrige el parser", source=InstructionSource.VOICE, confirmed_by_user=True)


def test_instruccion_de_voz_sin_confirmacion_es_rechazada() -> None:
    with pytest.raises(ValidationError, match="confirmed_by_user"):
        Instruction(
            text="corrige el parser",
            source=InstructionSource.VOICE,
            transcript_meta=TranscriptMeta(
                provider="faster-whisper:large-v3", language="es", confidence=0.9, duration_s=3.0
            ),
            confirmed_by_user=False,
        )


def test_instruccion_de_texto_no_lleva_metadatos_de_transcripcion() -> None:
    with pytest.raises(ValidationError, match="no debe llevar metadatos"):
        Instruction(
            text="corrige el parser",
            source=InstructionSource.TEXT,
            transcript_meta=TranscriptMeta(
                provider="x", language="es", confidence=0.9, duration_s=3.0
            ),
            confirmed_by_user=True,
        )


def test_una_subtarea_no_puede_asignarse_al_supervisor() -> None:
    with pytest.raises(ValidationError, match="no puede asignarse al supervisor"):
        _subtask("coordinar", AgentRole.SUPERVISOR)


def test_una_subtarea_sin_herramientas_es_rechazada() -> None:
    with pytest.raises(ValidationError, match="allowed_tools"):
        Subtask(
            id="vacia",
            description="sin herramientas",
            agent=AgentRole.CODER,
            allowed_tools=[],
            done_criteria="nada",
        )


def test_el_plan_rechaza_dependencias_inexistentes() -> None:
    with pytest.raises(ValidationError, match="depende de subtareas inexistentes"):
        RunPlan(
            subtasks=[_subtask("a", AgentRole.CODER, ["fantasma"])],
            rationale="plan invalido",
        )


def test_el_plan_rechaza_un_ciclo_de_dependencias() -> None:
    """Un ciclo en el plan es un bucle infinito disfrazado de dependencia."""
    with pytest.raises(ValidationError, match="ciclo de dependencias"):
        RunPlan(
            subtasks=[
                _subtask("a", AgentRole.CODER, ["b"]),
                _subtask("b", AgentRole.CODER, ["a"]),
            ],
            rationale="plan ciclico",
        )


def test_el_plan_rechaza_identificadores_duplicados() -> None:
    with pytest.raises(ValidationError, match="duplicados"):
        RunPlan(
            subtasks=[_subtask("a", AgentRole.CODER), _subtask("a", AgentRole.REVIEWER)],
            rationale="ids repetidos",
        )


def test_un_estado_terminal_no_debe_tener_siguiente_paso() -> None:
    with pytest.raises(ValidationError, match="next_step"):
        RunState(
            run_id="run-002",
            trace_id="trace-002",
            created_at=NOW,
            updated_at=NOW,
            instruction=_instruction(),
            status=RunStatus.COMPLETED,
            next_step="researcher",
        )


def test_el_presupuesto_detecta_agotamiento() -> None:
    assert not Budget(max_tokens=1000, used_tokens=999).exhausted
    assert Budget(max_tokens=1000, used_tokens=1000).exhausted
    assert Budget(max_tool_calls=10, used_tool_calls=10).exhausted
    assert Budget(max_seconds=10.0, elapsed_seconds=10.0).exhausted
    assert Budget(max_review_cycles=1, review_cycles_used=2).exhausted


# ---------------------- 4. campos retirados, version del esquema y pendientes


def test_los_campos_que_prometian_algo_inexistente_ya_no_estan() -> None:
    """Un campo que se documenta y no se implementa se cree: peor que su ausencia.

    `RunOptions.dry_run` declaraba "ejecuta el flujo sin tocar el repositorio" y
    ningun codigo lo leia. `TestRun.reproducible` prometia que "el Reviewer
    re-ejecuta para confirmar que el resultado es reproducible", y el Reviewer no
    vuelve a lanzar el target: el valor nunca llegaba a `True` salvo en las pruebas,
    de modo que la insignia que el frontend dibujaba a partir de el estaba
    permanentemente apagada. Los dos se retiraron; esta prueba impide que vuelvan
    por descuido.
    """
    assert "dry_run" not in RunOptions.model_fields
    assert "reproducible" not in TestRun.model_fields


def test_un_estado_de_otra_version_de_esquema_se_rechaza() -> None:
    """`schema_version` se escribia en cada estado y no lo leia nadie. Ahora se comprueba.

    Un sello de version que no se verifica no protege de nada: un estado escrito por
    otra version se leeria igual y **en silencio**, que es la peor forma de leer mal
    un dato. Comprobado, el fallo es inmediato y nombra las dos versiones.
    """
    with pytest.raises(ValidationError, match="esquema"):
        RunState(
            run_id="run-003",
            trace_id="trace-003",
            created_at=NOW,
            updated_at=NOW,
            instruction=_instruction(),
            schema_version="0.0.1",
        )


def test_un_estado_sin_sello_de_version_se_acepta() -> None:
    """La ausencia **no** es un fallo: es la regla de compatibilidad declarada.

    Un estado serializado antes de que el campo existiera se deserializa con el
    valor por defecto. Solo un valor distinto se rechaza, y eso es lo que permite
    que un campo nuevo entre sin subir la version.
    """
    crudo = RunState(
        run_id="run-004",
        trace_id="trace-004",
        created_at=NOW,
        updated_at=NOW,
        instruction=_instruction(),
    ).model_dump()
    crudo.pop("schema_version")

    assert RunState.model_validate(crudo).schema_version == SCHEMA_VERSION


def test_las_subtareas_conservan_su_estado_para_la_fase_de_cierre() -> None:
    """`Subtask.status` y `attempts` se **conservan** a proposito, no por olvido.

    Hoy nadie los actualiza: se quedan porque la fase de cierre de capacidades los
    rellena -el frontend necesita saber por que subtarea va el plan- y retirarlos
    ahora para volver a anadirlos despues seria trabajo para nada. Quedan aqui
    declarados como **pendientes**, no como implementados.
    """
    assert Subtask.model_fields["status"].default is SubtaskStatus.PENDING
    assert Subtask.model_fields["attempts"].default == 0


# ------------------------------------------- contrato exportado para el frontend


def test_el_contrato_exportado_esta_al_dia() -> None:
    """`frontend/contracts.json` no puede quedarse obsoleto en silencio.

    El frontend no comparte el sistema de tipos del backend. Si el fichero
    exportado se queda atras, los dos lados divergen y los fallos aparecen en el
    navegador, en tiempo de ejecucion. Esta prueba obliga a regenerarlo.
    """
    import importlib.util
    import json

    raiz = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "export_contracts", raiz / "tools" / "export_contracts.py"
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    generado = modulo.construir()
    actual = json.loads((raiz / "frontend" / "contracts.json").read_text(encoding="utf-8"))

    assert generado == actual, (
        "el contrato exportado esta obsoleto: ejecuta python tools/export_contracts.py"
    )
    # Control positivo: un fichero vacio tambien seria "igual" a si mismo.
    assert len(generado["schemas"]) >= 15
    assert "run.done" in generado["schemas"]["EventKind"]["enum"]
