"""Contratos de la superficie que consume el navegador.

Estos tipos no son infraestructura: son el **acuerdo entre el frontend y el
backend**. El frontend se valida contra ellos y se exportan como JSON Schema en
`frontend/contracts.json` (`tools/export_contracts.py`), de modo que hay una sola
fuente de verdad y no dos que se desincronizan.

Motivo de que existan como contrato explicito: con la ejecucion dentro de la
peticion, el cliente recibia el `run_id` cuando la ejecucion **ya habia
terminado**, asi que no podia suscribirse al progreso. El flujo pasa a ser
asincrono y el evento pasa a ser la unidad de comunicacion, no un efecto
secundario.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from ai_swe.contracts.state import RunStatus


class EventKind(StrEnum):
    """Tipos de evento del flujo de progreso.

    Son un conjunto **cerrado**: el frontend puede hacer un `switch` exhaustivo y
    un tipo nuevo no se cuela sin que alguien lo note.

    **F10 anade los eventos de ciclo de vida por nodo.** Hasta F9 el progreso se
    contaba con `run.step`, que lleva `{"node": "<nodo>"}`: suficiente para pintar
    una lista, insuficiente para un `switch` exhaustivo, porque el nombre del nodo
    viaja como **dato** y no como **tipo**. Ahora cada hito tiene su propio tipo.

    **Los eventos antiguos se conservan.** `run.created`, `run.step`, `run.status`,
    `run.awaiting_approval`, `run.report`, `run.error` y `run.done` siguen
    emitiendose porque el frontend actual escucha varios de ellos (cierra el flujo
    con `run.done`). Retirarlos ahora romperia una interfaz que **no** forma parte
    de esta fase. Quedan marcados como heredados y se retiraran cuando el frontend
    se reescriba, en la fase que lo autorice.
    """

    # --- ciclo de vida de la ejecucion ---------------------------------------
    RUN_CREATED = "run.created"  # heredado
    RUN_STARTED = "run.started"
    RUN_STEP = "run.step"  # heredado: el nodo viaja en `data.node`
    RUN_STATUS = "run.status"  # heredado
    RUN_REPORT = "run.report"  # heredado
    RUN_ERROR = "run.error"  # heredado: un error, no el final
    RUN_DONE = "run.done"  # heredado: el frontend cierra el flujo con el
    RUN_COMPLETED = "run.completed"  # F10: final feliz, explicito
    RUN_FAILED = "run.failed"  # F10: final no feliz, explicito

    # --- puertas humanas ------------------------------------------------------
    RUN_AWAITING_HUMAN = "run.awaiting_human"  # F10: cualquier puerta
    RUN_AWAITING_APPROVAL = "run.awaiting_approval"  # heredado: solo la de aprobacion

    # --- hitos por nodo (F10) -------------------------------------------------
    REQUIREMENTS_COMPLETED = "requirements.completed"
    PLAN_COMPLETED = "plan.completed"
    CODER_COMPLETED = "coder.completed"
    TESTS_COMPLETED = "tests.completed"


# Nodo del grafo -> evento que se emite cuando ese nodo **termina**.
#
# **Por que `coder.completed` y no `coder.started`.** El motor lee el grafo con
# `stream_mode="updates"`, que entrega el resultado de un nodo **cuando ya ha
# terminado**. Emitir un evento llamado `started` en ese momento seria mentir sobre
# el instante, y un cliente que midiera duraciones con el obtendria numeros falsos.
# El hito que el flujo puede observar de verdad es el de finalizacion.
EVENTO_POR_NODO: dict[str, EventKind] = {
    "interpret": EventKind.REQUIREMENTS_COMPLETED,
    "plan": EventKind.PLAN_COMPLETED,
    "coder": EventKind.CODER_COMPLETED,
    "run_tests": EventKind.TESTS_COMPLETED,
}


class Project(BaseModel):
    """Un repositorio registrado sobre el que se puede ejecutar (F10).

    Hasta F10 cada ejecucion llevaba su `repo_path` suelto en `RunOptions`, sin
    nada que lo validara antes de lanzar el trabajo. Un proyecto es ese mismo
    repositorio **con nombre y validado una vez**: la ruta se comprueba al
    registrarlo, de modo que un repositorio inexistente o que no sea git se
    rechaza en el alta y no dentro de una ejecucion ya en marcha.
    """

    project_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=200)
    repo_path: str = Field(min_length=1)
    created_at: datetime


class ProjectRequest(BaseModel):
    """Alta de un proyecto. El `project_id` lo asigna el servidor, no el cliente."""

    name: str = Field(min_length=1, max_length=200)
    repo_path: str = Field(min_length=1)


class RunSummary(BaseModel):
    """Vista ligera de una ejecucion, para listados y paneles."""

    run_id: str
    trace_id: str
    status: RunStatus
    intent: str | None = None
    created_at: datetime
    updated_at: datetime
    error_count: int = Field(default=0, ge=0)
    awaiting_approval: bool = Field(
        default=False,
        description="Atajo para que el panel sepa si debe mostrar la puerta de aprobacion.",
    )


class RunEvent(BaseModel):
    """Un evento del progreso de una ejecucion.

    `seq` es monotonamente creciente por ejecucion y se envia como `id:` en el
    flujo SSE. Eso permite que el navegador se reconecte con `Last-Event-ID` y
    reciba **solo lo que se perdio**, en lugar de empezar de cero o perder
    eventos. Es la razon de que el registro sea persistente y no una cola en
    memoria.
    """

    seq: int = Field(ge=1)
    at: datetime
    kind: EventKind
    data: dict = Field(
        default_factory=dict,
        description="Carga estructurada. El frontend la consume directamente, sin parsear texto.",
    )


class RunSummary(BaseModel):
    """Vista ligera de una ejecucion, para listados y paneles."""

    run_id: str
    trace_id: str
    status: RunStatus
    intent: str | None = None
    created_at: datetime
    updated_at: datetime
    error_count: int = Field(default=0, ge=0)
    awaiting_approval: bool = Field(
        default=False,
        description="Atajo para que el panel sepa si debe mostrar la puerta de aprobacion.",
    )
