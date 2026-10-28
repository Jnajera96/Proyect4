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

from pydantic import BaseModel, Field, StrictBool

from ai_swe.contracts.state import RunStatus


class EventKind(StrEnum):
    """Tipos de evento del flujo de progreso.

    Son un conjunto **cerrado**: el frontend puede hacer un `switch` exhaustivo y
    un tipo nuevo no se cuela sin que alguien lo note.

    **F10 anadio los eventos de ciclo de vida por nodo.** Hasta F9 el progreso se
    contaba con `run.step`, que lleva `{"node": "<nodo>"}`: suficiente para pintar
    una lista, insuficiente para un `switch` exhaustivo, porque el nombre del nodo
    viajaba como **dato** y no como **tipo**.

    **F11 retiro los nombres heredados (AUD-11).** Se fueron `run.step`,
    `run.status`, `run.report`, `run.error` y `run.awaiting_approval`, cada uno con
    un sustituto canonico:

      - `run.step` -> los hitos por nodo (`requirements.completed`, ...);
      - `run.status` -> `GET /runs/{id}`, que es la vista autoritativa del estado;
      - `run.report` -> `final_report`, que viaja en el estado;
      - `run.error` -> `estado.errors` + el desenlace `run.failed`;
      - `run.awaiting_approval` -> `run.awaiting_human`, que cubre las dos puertas.

    **Se conservan** `run.created` y `run.started` (marcas de arranque sin
    sustituto canonico) y `run.done`, que **no es un alias** de nada: es la senal
    con la que el flujo SSE se cierra en cada pausa y reanudacion.
    """

    # --- ciclo de vida de la ejecucion ---------------------------------------
    NODE_STARTED = "node_started"
    MODEL_REQUEST_STARTED = "model_request_started"
    MODEL_RESPONSE_RECEIVED = "model_response_received"
    TEST_TARGET_STARTED = "test_target_started"
    TEST_TARGET_COMPLETED = "test_target_completed"
    NODE_COMPLETED = "node_completed"
    NODE_SKIPPED = "node_skipped"

    RUN_CREATED = "run.created"
    RUN_STARTED = "run.started"
    RUN_DONE = "run.done"  # cierra el flujo SSE (no es un alias)
    RUN_COMPLETED = "run.completed"  # final feliz, explicito
    RUN_FAILED = "run.failed"  # final no feliz, explicito

    # --- puertas humanas ------------------------------------------------------
    RUN_AWAITING_HUMAN = "run.awaiting_human"  # cualquier puerta

    # --- hitos por nodo -------------------------------------------------------
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
    create_if_missing: StrictBool = False


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
