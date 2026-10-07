"""Adapter falso: determinista, sin red y con inyeccion de fallos.

**Por que es el primer adapter que se implementa.** La suite completa tiene que
pasar sin Internet, sin credenciales y sin proveedor externo. Eso solo es posible
si existe un adapter que no toque la red, y si ademas puede **provocar a voluntad**
los fallos que hay que manejar: timeout, 429, 5xx, credencial invalida, respuesta
malformada. Probar esos caminos contra un proveedor real seria lento, caro y no
reproducible.

Se configura por constructor y **no usa estado global**: dos pruebas pueden tener
dos fakes distintos a la vez sin pisarse.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from ai_swe.models.contracts import ModelRequest, ModelUsage
from ai_swe.models.errors import (
    InvalidResponseError,
    ModelAuthenticationError,
    ModelRateLimitError,
    ModelTimeoutError,
    ProviderUnavailableError,
)
from ai_swe.models.providers.base import ProviderResponse

# Nombres de fallo que el fake sabe provocar. Se exponen como constantes para que
# una prueba no dependa de escribir bien una cadena suelta.
FALLO_TIMEOUT = "timeout"
FALLO_RATE_LIMIT = "rate_limit"
FALLO_UNAVAILABLE = "unavailable"
FALLO_AUTH = "auth_error"
FALLO_INVALID_RESPONSE = "invalid_response"

FALLOS_CONOCIDOS = frozenset(
    {FALLO_TIMEOUT, FALLO_RATE_LIMIT, FALLO_UNAVAILABLE, FALLO_AUTH, FALLO_INVALID_RESPONSE}
)


class FakeModelAdapter:
    """Adapter determinista para pruebas y para desarrollo sin credenciales.

    Modos de fallo:

    - `fault="timeout"`: falla **siempre** con ese error.
    - `faults=["timeout", "rate_limit"]`: falla en secuencia y luego responde bien.
      Es lo que permite probar «falla, falla, funciona» (reintento exitoso) y
      «falla, falla, falla» (reintentos agotados) sin esperas reales.
    """

    def __init__(
        self,
        *,
        name: str = "fake",
        model: str = "fake-model",
        content: str = "respuesta falsa",
        structured: dict[str, Any] | None = None,
        usage: ModelUsage | None = None,
        finish_reason: str = "stop",
        provider_request_id: str | None = "fake-request-1",
        fault: str | None = None,
        faults: Sequence[str] | None = None,
        retry_after_s: float | None = None,
    ) -> None:
        self._name = name
        self._model = model
        self._content = content
        self._structured = structured
        self._usage = usage if usage is not None else ModelUsage(input_tokens=10, output_tokens=5)
        self._finish_reason = finish_reason
        self._provider_request_id = provider_request_id
        self._fault = fault
        self._fallos_pendientes: list[str] = list(faults or [])
        self._retry_after_s = retry_after_s
        # Registro de peticiones recibidas, para poder afirmar sobre ellas.
        self.calls: list[ModelRequest] = []

        for nombre_fallo in filter(None, [fault, *self._fallos_pendientes]):
            if nombre_fallo not in FALLOS_CONOCIDOS:
                raise ValueError(
                    f"fallo desconocido: {nombre_fallo!r}; "
                    f"los conocidos son {sorted(FALLOS_CONOCIDOS)}"
                )

    @property
    def name(self) -> str:
        return self._name

    # ------------------------------------------------------------------ interno

    def _siguiente_fallo(self) -> str | None:
        """Devuelve el fallo que toca, o `None` si esta llamada debe salir bien.

        Un `fault` fijo gana siempre; si no, se consume la lista en orden. Se
        consume **por llamada**, que es lo que hace observable el numero de
        reintentos desde fuera.
        """
        if self._fault is not None:
            return self._fault
        if self._fallos_pendientes:
            return self._fallos_pendientes.pop(0)
        return None

    def _lanzar(self, fallo: str) -> None:
        comun = {"provider": self._name, "model": self._model}
        if fallo == FALLO_TIMEOUT:
            raise ModelTimeoutError("el proveedor falso simula un timeout", **comun)
        if fallo == FALLO_RATE_LIMIT:
            raise ModelRateLimitError(
                "el proveedor falso simula un 429",
                retry_after_s=self._retry_after_s,
                **comun,
            )
        if fallo == FALLO_UNAVAILABLE:
            raise ProviderUnavailableError("el proveedor falso simula un 503", **comun)
        if fallo == FALLO_AUTH:
            raise ModelAuthenticationError(
                "el proveedor falso simula credencial invalida", **comun
            )
        if fallo == FALLO_INVALID_RESPONSE:
            raise InvalidResponseError("el proveedor falso simula respuesta malformada", **comun)
        raise AssertionError(f"fallo no contemplado: {fallo}")  # pragma: no cover

    # ------------------------------------------------------------------ publico

    def generate(self, request: ModelRequest) -> ProviderResponse:
        self.calls.append(request)

        fallo = self._siguiente_fallo()
        if fallo is not None:
            self._lanzar(fallo)

        # Si el gateway pidio salida estructurada, se devuelve JSON valido; el
        # gateway lo validara contra el contrato. Si `structured` es `None` y hay
        # esquema, se devuelve el `content` tal cual, que es como se simula una
        # respuesta que **no** cumple el contrato.
        if request.json_schema is not None and self._structured is not None:
            contenido = json.dumps(self._structured)
        else:
            contenido = self._content

        return ProviderResponse(
            content=contenido,
            model=request.model or self._model,
            finish_reason=self._finish_reason,
            usage=self._usage,
            provider_request_id=self._provider_request_id,
        )
