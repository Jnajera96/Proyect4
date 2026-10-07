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
    """

    RUN_CREATED = "run.created"
    RUN_STARTED = "run.started"
    RUN_STEP = "run.step"
    RUN_STATUS = "run.status"
    RUN_AWAITING_APPROVAL = "run.awaiting_approval"
    RUN_REPORT = "run.report"
    RUN_ERROR = "run.error"
    RUN_DONE = "run.done"


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
