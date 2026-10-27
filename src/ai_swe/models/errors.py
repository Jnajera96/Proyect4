"""Errores tipados del Model Gateway.

**Por que una jerarquia y no excepciones genericas.** La politica de reintento es
una consecuencia del *tipo* de fallo, no una decision que cada llamante repita. Si
un adapter lanza `RuntimeError`, el gateway solo puede adivinar si conviene
reintentar; si lanza `ModelAuthenticationError`, reintentar seria un error evidente.
Codificar el tipo es lo que hace que la politica sea una sola vez y correcta.

**`recoverable` es de la clase, no del constructor.** Un parametro por instancia
permitiria que el mismo tipo de fallo se tratara como reintentable en un sitio y no
en otro. Se fija en la definicion y no se discute en el punto de uso.

**`RNF-S3`.** Todo mensaje pasa por el redactor antes de construirse. Un proveedor
puede devolver la clave de API dentro del cuerpo de un 401; ese cuerpo llega aqui
como `detail` y se redacta. La garantia no depende de que el llamante se acuerde.
"""

from __future__ import annotations

from ai_swe.security import redact


class ModelGatewayError(Exception):
    """Base de todos los errores del gateway. Nunca se lanza directamente.

    `error_class` es un identificador estable para observabilidad: sobrevive a
    renombrar la clase y es lo que se registra en una traza, no el `repr`.
    """

    error_class: str = "MODEL_GATEWAY_ERROR"
    recoverable: bool = False

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        detail: str | None = None,
    ) -> None:
        # El redactor se aplica aqui, en el unico sitio por el que pasan todos los
        # errores del paquete. Si se dejara al llamante, bastaria un olvido.
        self.provider = provider
        self.model = model
        self.detail = redact(detail) if detail is not None else None
        self.message = redact(message)
        super().__init__(self.message)

    def __str__(self) -> str:
        partes = [self.message]
        if self.provider:
            partes.append(f"proveedor={self.provider}")
        if self.model:
            partes.append(f"modelo={self.model}")
        if self.detail:
            partes.append(f"detalle={self.detail}")
        return " | ".join(partes)


# ------------------------------------------------------- no reintentables


class ModelConfigurationError(ModelGatewayError):
    """Configuracion ausente o invalida. Reintentar no cambia la configuracion."""

    error_class = "MODEL_CONFIGURATION_ERROR"


class ModelAuthenticationError(ModelGatewayError):
    """Credencial rechazada. Reintentar una clave invalida gasta tiempo y cuota."""

    error_class = "MODEL_AUTHENTICATION_ERROR"


class ModelBillingError(ModelGatewayError):
    """Pago o credito rechazado; repetir peticiones no resuelve la facturacion."""

    error_class = "MODEL_BILLING_ERROR"


class UnknownProviderError(ModelGatewayError):
    """Proveedor no registrado. Es un fallo de programa, no de red."""

    error_class = "UNKNOWN_PROVIDER"


class InvalidResponseError(ModelGatewayError):
    """El proveedor respondio algo que no se puede interpretar.

    No es recuperable por defecto: una respuesta malformada que se repite identica
    no mejora con reintentos. Si el problema fuera transitorio, el proveedor habria
    devuelto un 5xx, que si es recuperable.
    """

    error_class = "INVALID_RESPONSE"


class StructuredOutputError(ModelGatewayError):
    """La respuesta no valida contra el contrato Pydantic pedido.

    Existe para que esto **no** continue en silencio: un `dict` que no cumple el
    contrato no puede cruzar al sistema.
    """

    error_class = "STRUCTURED_OUTPUT_ERROR"


class BudgetExceededError(ModelGatewayError):
    """El presupuesto esta agotado. No se gasta la llamada."""

    error_class = "BUDGET_EXCEEDED"

    def __init__(self, message: str, *, motivos: tuple[str, ...] = (), **kwargs) -> None:
        self.motivos = motivos
        super().__init__(message, **kwargs)


# ------------------------------------------------------- reintentables


class ModelRateLimitError(ModelGatewayError):
    """Limite de tasa (429). Es el caso de manual de `reintentar con espera`."""

    error_class = "MODEL_RATE_LIMIT"
    recoverable = True

    def __init__(self, message: str, *, retry_after_s: float | None = None, **kwargs) -> None:
        self.retry_after_s = retry_after_s
        super().__init__(message, **kwargs)


class ModelTimeoutError(ModelGatewayError):
    """El proveedor no respondio a tiempo. Transitorio."""

    error_class = "MODEL_TIMEOUT"
    recoverable = True


class ProviderUnavailableError(ModelGatewayError):
    """El proveedor no esta disponible (5xx, conexion rechazada). Transitorio."""

    error_class = "PROVIDER_UNAVAILABLE"
    recoverable = True
