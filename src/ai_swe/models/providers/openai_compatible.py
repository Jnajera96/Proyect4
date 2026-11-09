"""Adapter para cualquier endpoint compatible con la API de OpenAI.

**Por que HTTP y no un SDK.** «Compatible con OpenAI» es un **contrato HTTP**, no un
paquete. Hablando HTTP directamente, el mismo adapter sirve para OpenAI, Ollama,
vLLM, OpenRouter, Together y cualquier endpoint compatible, sin escribir uno por
proveedor. Ademas no anade dependencia (el proyecto ya usa `httpx`) y permite
ejercitar el adapter **sin abrir un socket**, inyectando un transporte falso: eso
es lo que hace posible probar el codigo real sin Internet.

**Aislamiento.** Este es el unico modulo del proyecto que conoce la forma concreta
de un proveedor. Fuera de `models/providers/` no hay ni un import de proveedor.
"""

from __future__ import annotations

from typing import Any

import httpx

from ai_swe.models.contracts import ModelRequest, ModelUsage
from ai_swe.models.errors import (
    InvalidResponseError,
    ModelAuthenticationError,
    ModelBillingError,
    ModelConfigurationError,
    ModelRateLimitError,
    ModelTimeoutError,
    ProviderUnavailableError,
)
from ai_swe.models.providers.base import ProviderResponse
from ai_swe.security import redact, register_secret

BASE_URL_POR_DEFECTO = "https://api.openai.com/v1"
PROVIDER_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "openai_compatible": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com",
    "openrouter": "https://openrouter.ai/api/v1",
    "together": "https://api.together.xyz/v1",
    "mistral": "https://api.mistral.ai/v1",
    "ollama": "http://localhost:11434/v1",
    "vllm": "http://localhost:8000/v1",
}
# Tope al detalle de error que se propaga. Un cuerpo de error de miles de lineas
# no aporta y acaba en un log; se recorta antes de redactar.
_MAX_DETALLE_ERROR = 800


def _entero_no_negativo(valor: Any) -> int | None:
    """Convierte a entero no negativo, o `None` si no es un numero usable.

    No se inventa un cero: `None` significa «el proveedor no lo reporto», que es
    distinto de «consumio cero».
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int) and valor >= 0:
        return valor
    return None


def _subcampo(datos: dict[str, Any], clave: str, subclave: str) -> int | None:
    """Lee `datos[clave][subclave]` sin fallar si falta o no es un objeto."""
    contenedor = datos.get(clave)
    if not isinstance(contenedor, dict):
        return None
    return _entero_no_negativo(contenedor.get(subclave))


class OpenAICompatibleAdapter:
    """Habla con un endpoint `/chat/completions` compatible con OpenAI.

    Acepta un `client` inyectable: en produccion se deja en `None` y se crea uno
    perezosamente (una sola vez, para reutilizar conexiones); en pruebas se pasa un
    `httpx.Client` con `MockTransport`, de modo que el adapter real se ejecuta
    entero sin red. Un cliente inyectado **no se cierra** aqui: es de quien lo paso.
    """

    def __init__(
        self,
        *,
        name: str,
        model: str,
        api_key: str = "",
        base_url: str | None = None,
        timeout_s: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not model.strip():
            raise ModelConfigurationError(
                "el adapter OpenAI-compatible exige un modelo", provider=name
            )
        self._name = name
        self._model = model
        self._api_key = api_key
        default_base = PROVIDER_BASE_URLS.get(name.lower(), BASE_URL_POR_DEFECTO)
        self._base_url = (base_url or default_base).rstrip("/")
        self._timeout_s = timeout_s
        self._client = client
        self._cliente_propio = client is None

        # **La clave se registra aqui, no en quien construye el adapter.**
        # El adapter es quien *posee* la credencial, asi que es quien puede
        # garantizar que el redactor la conozca. Si dependiera de que el llamante
        # hubiera pasado antes por `load_settings()`, un adapter construido a mano
        # -como en una prueba, o desde un script- quedaria sin proteccion, y una
        # clave sin prefijo reconocible (`sk-`, `ghp_`...) se filtraria entera en el
        # cuerpo de un 401. Se descubrio con una prueba, no leyendo el codigo.
        register_secret(api_key)

    @property
    def name(self) -> str:
        return self._name

    @property
    def base_url(self) -> str:
        return self._base_url

    # ------------------------------------------------------------------ interno

    def _cliente(self) -> httpx.Client:
        """Cliente HTTP, creado una sola vez.

        Crear un cliente por llamada descartaria el conjunto de conexiones en cada
        peticion, que es justo lo que `httpx` ofrece para no pagar el coste de TLS
        en cada vuelta.
        """
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout_s)
        return self._client

    def close(self) -> None:
        """Cierra el cliente propio. Un cliente inyectado no se toca."""
        if self._cliente_propio and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> OpenAICompatibleAdapter:
        return self

    def __exit__(self, *_excepcion: object) -> None:
        self.close()

    def _is_loopback(self) -> bool:
        from urllib.parse import urlparse

        try:
            parsed = urlparse(self._base_url)
            host = (parsed.hostname or "").lower()
            return host in ("localhost", "127.0.0.1", "::1")
        except Exception:
            return False

    def _cabeceras(self) -> dict[str, str]:
        """Cabeceras de la peticion. **Nunca se registran en un log.**

        Se construyen aqui y se pasan a `httpx`; no se devuelven ni se guardan en
        ningun sitio que pueda acabar serializado.
        """
        cabeceras = {"Content-Type": "application/json"}
        api_key = self._api_key.strip()
        if not self._is_loopback() and api_key and api_key.lower() not in ("local", "none", "null"):
            cabeceras["Authorization"] = f"Bearer {api_key}"
        return cabeceras

    def _resolver_modelo_loopback(self, solicitado: str) -> str | None:
        """En endpoints loopback (como OmniRoute), consulta /models para resolver prefijos o combos."""
        if not self._is_loopback():
            return None
        url = f"{self._base_url}/models"
        try:
            resp = self._cliente().get(url, timeout=3.0)
            if resp.status_code != 200:
                return None
            datos = resp.json()
            items = datos.get("data", [])
            modelos: list[str] = [
                m.get("id") for m in items if isinstance(m, dict) and isinstance(m.get("id"), str)
            ]
            if not modelos:
                return None
            sol_lower = solicitado.strip().lower()
            for m in modelos:
                if m.lower() == sol_lower:
                    return m
            coincidencias = [m for m in modelos if m.lower().endswith(f"/{sol_lower}")]
            return coincidencias[0] if len(coincidencias) == 1 else None
        except Exception:
            return None

    def _cuerpo(self, request: ModelRequest) -> dict[str, Any]:
        model_name = request.model or self._model
        if model_name.startswith("models/") and "googleapis.com" in self._base_url:
            model_name = model_name[len("models/"):]
        cuerpo: dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": m.role.value, "content": m.content} for m in request.messages
            ],
        }
        if request.temperature is not None:
            cuerpo["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            cuerpo["max_tokens"] = request.max_output_tokens
        if request.json_schema is not None:
            # Pista de modo JSON. El esquema completo va en los mensajes, que es lo
            # que entienden todos los endpoints compatibles; esto solo ayuda a los
            # que soportan el parametro.
            cuerpo["response_format"] = {"type": "json_object"}
        return cuerpo

    def _detalle(self, respuesta: httpx.Response) -> str:
        """Cuerpo del error, recortado y **redactado**.

        Un 401 puede devolver la clave en el cuerpo. Se redacta antes de que el
        texto se convierta en mensaje de excepcion, de modo que la garantia no
        dependa de que el llamante se acuerde.
        """
        try:
            texto = respuesta.text
        except Exception:  # noqa: BLE001 - un cuerpo ilegible no debe tapar el error real
            return ""
        return redact(texto[:_MAX_DETALLE_ERROR])

    def _error_por_estado(self, respuesta: httpx.Response) -> Exception:
        detalle = self._detalle(respuesta)
        codigo = respuesta.status_code
        comun: dict[str, Any] = {"provider": self._name, "detail": detalle or None, "status_code": codigo}

        if codigo in (401, 403):
            return ModelAuthenticationError(f"credencial rechazada (HTTP {codigo})", **comun)
        if codigo == 402:
            return ModelBillingError("pago o credito requerido (HTTP 402)", **comun)
        if codigo == 429:
            espera: float | None = None
            crudo = respuesta.headers.get("retry-after")
            if crudo:
                try:
                    espera = float(crudo)
                except ValueError:
                    espera = None
            return ModelRateLimitError(
                "limite de tasa alcanzado (HTTP 429)", retry_after_s=espera, **comun
            )
        if codigo >= 500:
            return ProviderUnavailableError(
                f"el proveedor no esta disponible (HTTP {codigo})", **comun
            )
        if codigo in (408, 504):
            return ModelTimeoutError(f"timeout del proveedor (HTTP {codigo})", **comun)
        return InvalidResponseError(
            f"respuesta inesperada del proveedor (HTTP {codigo})", **comun
        )

    def _extraer(self, datos: Any) -> ProviderResponse:
        if not isinstance(datos, dict):
            raise InvalidResponseError(
                "el cuerpo de la respuesta no es un objeto JSON", provider=self._name
            )
        opciones = datos.get("choices")
        if not isinstance(opciones, list) or not opciones:
            raise InvalidResponseError("la respuesta no trae 'choices'", provider=self._name)
        primera = opciones[0]
        if not isinstance(primera, dict):
            raise InvalidResponseError("'choices[0]' no es un objeto", provider=self._name)

        contenido = ""
        mensaje = primera.get("message")
        if isinstance(mensaje, dict) and isinstance(mensaje.get("content"), str):
            contenido = mensaje["content"]
        if not contenido:
            # Algunos proveedores devuelven el texto en `choices[0].text`.
            alterno = primera.get("text")
            if isinstance(alterno, str):
                contenido = alterno

        motivo = primera.get("finish_reason")
        modelo = datos.get("model")
        identificador = datos.get("id")

        crudo_uso = datos.get("usage")
        uso = ModelUsage()
        if isinstance(crudo_uso, dict):
            uso = ModelUsage(
                input_tokens=_entero_no_negativo(crudo_uso.get("prompt_tokens")),
                output_tokens=_entero_no_negativo(crudo_uso.get("completion_tokens")),
                total_tokens=_entero_no_negativo(crudo_uso.get("total_tokens")),
                cached_tokens=_subcampo(crudo_uso, "prompt_tokens_details", "cached_tokens"),
                reasoning_tokens=_subcampo(
                    crudo_uso, "completion_tokens_details", "reasoning_tokens"
                ),
            )

        return ProviderResponse(
            content=contenido,
            model=modelo if isinstance(modelo, str) else (self._model),
            finish_reason=motivo if isinstance(motivo, str) else "",
            usage=uso,
            provider_request_id=identificador if isinstance(identificador, str) else None,
        )

    # ------------------------------------------------------------------ publico

    def generate(self, request: ModelRequest) -> ProviderResponse:
        url = f"{self._base_url}/chat/completions"
        timeout = request.timeout_s or self._timeout_s
        cuerpo = self._cuerpo(request)
        cabeceras = self._cabeceras()

        try:
            respuesta = self._cliente().post(
                url,
                json=cuerpo,
                headers=cabeceras,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise ModelTimeoutError(
                f"el proveedor no respondio en {timeout:g}s",
                provider=self._name,
                detail=type(exc).__name__,
            ) from exc
        except httpx.HTTPError as exc:
            # Errores de red (conexion rechazada, DNS, TLS). Transitorios por
            # naturaleza; el gateway decidira si reintenta.
            raise ProviderUnavailableError(
                "no se pudo contactar con el proveedor",
                provider=self._name,
                detail=type(exc).__name__,
            ) from exc

        # Condición 1: En loopback, si se rechaza con 401/403 y se envió Authorization,
        # reintentar inmediatamente en modo local sin cabecera Authorization.
        if self._is_loopback() and respuesta.status_code in (401, 403) and "Authorization" in cabeceras:
            cabeceras_sin_auth = {k: v for k, v in cabeceras.items() if k.lower() != "authorization"}
            try:
                segunda = self._cliente().post(
                    url,
                    json=cuerpo,
                    headers=cabeceras_sin_auth,
                    timeout=timeout,
                )
                if segunda.status_code < 400 or (segunda.status_code != respuesta.status_code):
                    respuesta = segunda
                    cabeceras = cabeceras_sin_auth
            except Exception:
                pass

        # Condición 2: En loopback, si responde 400 (modelo no encontrado, ambiguo o combo no registrado),
        # consultar /models y reintentar con el identificador resuelto.
        if self._is_loopback() and respuesta.status_code == 400:
            solicitado = str(cuerpo.get("model", ""))
            resuelto = self._resolver_modelo_loopback(solicitado)
            if resuelto and resuelto != solicitado:
                nuevo_cuerpo = dict(cuerpo)
                nuevo_cuerpo["model"] = resuelto
                try:
                    segunda = self._cliente().post(
                        url,
                        json=nuevo_cuerpo,
                        headers=cabeceras,
                        timeout=timeout,
                    )
                    if segunda.status_code < 400 or (segunda.status_code != respuesta.status_code):
                        respuesta = segunda
                        cuerpo = nuevo_cuerpo
                except Exception:
                    pass

        if respuesta.status_code >= 400:
            raise self._error_por_estado(respuesta)

        try:
            datos = respuesta.json()
        except ValueError as exc:
            raise InvalidResponseError(
                "la respuesta no es JSON valido", provider=self._name
            ) from exc

        return self._extraer(datos)


__all__ = ["BASE_URL_POR_DEFECTO", "OpenAICompatibleAdapter"]
