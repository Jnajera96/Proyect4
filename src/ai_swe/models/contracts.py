"""Contratos del Model Gateway.

Es la frontera entre el sistema y cualquier modelo. **Ningun agente futuro deberia
importar un SDK de proveedor**: todos hablan estos tipos.

**Lo que NO esta aqui, y es deliberado.** El contrato de presupuesto (`Budget`) ya
existe en `ai_swe.contracts.state` y se **reutiliza**; no se redefine. La identidad
del solicitante (`AgentRole`) tambien se reutiliza. Duplicar un contrato crea dos
fuentes de verdad que divergen.

**Sin secretos.** La clave de API vive en la configuracion del adapter, nunca en
`ModelRequest`. Consecuencia: serializar una peticion -en un log, en un evento, en
un punto de control- no puede filtrar una credencial. Es una propiedad del diseno,
no una precaucion.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from ai_swe.contracts.tasks import AgentRole


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class FinishReason(StrEnum):
    """Por que termino la generacion.

    `UNKNOWN` existe para no fallar ante un valor que el proveedor invente: un
    motivo de finalizacion nuevo no es un error del sistema. Se registra como
    desconocido y se sigue.
    """

    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    TOOL_CALLS = "tool_calls"
    ERROR = "error"
    UNKNOWN = "unknown"


class ModelMessage(BaseModel):
    """Un mensaje de la conversacion. El minimo que el sistema necesita hoy.

    No se modela tool-calling todavia: ningun agente lo usa aun y seria superficie
    sin uso, que es deuda disfrazada de prevision.
    """

    role: MessageRole
    content: str = Field(min_length=1, max_length=200_000)


class ProviderConfig(BaseModel):
    """Como hablar con un proveedor concreto.

    `api_key` es `SecretStr`: su `repr` no filtra el valor, de modo que volcar la
    configuracion en un diagnostico no la expone.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=120)
    api_key: SecretStr = Field(default=SecretStr(""))
    base_url: str | None = None
    timeout_s: float = Field(default=60.0, gt=0)
    max_retries: int = Field(default=2, ge=0, le=8)

    @property
    def has_credentials(self) -> bool:
        return self.api_key.get_secret_value().strip().lower() not in {"", "local", "none", "null"}


class ModelUsage(BaseModel):
    """Consumo reportado por el proveedor.

    **No se inventan valores.** Si el proveedor no reporta un campo, queda en
    `None`, que es distinto de `0`: `0` afirma que no se consumio nada, `None`
    admite que no se sabe. Confundirlos falsearia la contabilidad de coste.
    """

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cached_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _derive_total_when_possible(self) -> ModelUsage:
        """Si el proveedor no dio el total pero si las dos partes, se suman.

        No es inventar un dato: es aritmetica sobre dos valores que el proveedor
        si reporto. Si falta cualquiera de los dos, el total se queda en `None`.
        """
        if (
            self.total_tokens is None
            and self.input_tokens is not None
            and self.output_tokens is not None
        ):
            self.total_tokens = self.input_tokens + self.output_tokens
        return self

    @property
    def known_total(self) -> int | None:
        """Total utilizable para contabilidad, o `None` si no se puede saber."""
        return self.total_tokens


class ModelRequest(BaseModel):
    """Una peticion al modelo. Independiente del proveedor."""

    model_config = ConfigDict(extra="forbid")

    messages: list[ModelMessage] = Field(min_length=1, max_length=200)
    model: str | None = Field(default=None, max_length=120)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, ge=1)
    # El gateway la rellena en `generate_structured`; el adapter solo la reenvia.
    json_schema: dict[str, Any] | None = None
    # El gateway fija el timeout efectivo (acotado por el presupuesto); el adapter
    # lo respeta. Si es `None`, el adapter usa el suyo por configuracion.
    timeout_s: float | None = Field(default=None, gt=0)

    # --- metadata de correlacion (observabilidad futura) ---------------------
    run_id: str | None = Field(default=None, max_length=64)
    trace_id: str | None = Field(default=None, max_length=64)
    agent_role: AgentRole | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ModelResponse(BaseModel):
    """Respuesta normalizada, ya independiente del proveedor."""

    content: str = ""
    structured_data: dict[str, Any] | None = None

    # El que respondio y el que se pidio. Se registran los dos para que una
    # respuesta que vino del secundario no pueda parecer que vino del primario.
    provider: str
    provider_requested: str
    model: str
    finish_reason: FinishReason = FinishReason.UNKNOWN

    usage: ModelUsage = Field(default_factory=ModelUsage)
    latency_ms: float = Field(ge=0.0)
    provider_request_id: str | None = None

    fallback_used: bool = False
    fallback_reason: str | None = None
    # Reservado: el gateway lanza una excepcion tipada en vez de devolver una
    # respuesta fallida, asi que hoy siempre es `None`. Existe para que un
    # consumidor pueda serializar la respuesta sin ramificar por tipo.
    error: str | None = None

    # --- metadata de correlacion (observabilidad futura) ---------------------
    run_id: str | None = None
    trace_id: str | None = None
    agent_role: AgentRole | None = None
    cost: float | None = None

    def structured_as(self, modelo: type[BaseModel]) -> BaseModel:
        """Devuelve la salida estructurada como instancia del contrato pedido.

        El gateway ya la valido antes de devolver la respuesta: si `structured_data`
        no es `None`, es que cumplia el contrato. Esto solo la rehidrata en su tipo
        para quien prefiera el objeto a un `dict`.
        """
        if self.structured_data is None:
            raise ValueError("esta respuesta no contiene salida estructurada")
        return modelo.model_validate(self.structured_data)
