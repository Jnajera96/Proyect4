"""Model Gateway: la frontera unica entre el sistema y cualquier modelo.

**Que hace y que no hace.**

Hace: comprobar el presupuesto antes de gastar, reintentar solo lo que tiene
sentido reintentar, pasar a un proveedor de respaldo cuando el primario se cae,
acotar el tiempo de espera, validar la salida estructurada contra un contrato
Pydantic, contabilizar tokens y coste, y redactar cualquier secreto que aparezca en
un log o en un error.

No hace: saber que proveedor esta detras (eso es el adapter), ni razonar sobre la
tarea (eso son los agentes). **Ningun agente importa un SDK de proveedor**: todos
hablan con esto.

**Estado.** El gateway no tiene estado global mutable. Recibe un `Budget` y
devuelve el consumo en la respuesta; el dueno del presupuesto aplica el delta con
`consume()`. Sin estado compartido no hay carrera que proteger: dos ejecuciones
concurrentes quedan aisladas por construccion.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Sequence

from pydantic import BaseModel, ValidationError

from ai_swe.config import Settings
from ai_swe.contracts import Budget
from ai_swe.graph.activity import emit
from ai_swe.models.budget import (
    assert_budget_available,
    effective_timeout_s,
)
from ai_swe.models.budget import consume as _consumir
from ai_swe.models.contracts import (
    FinishReason,
    MessageRole,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)
from ai_swe.models.errors import (
    BudgetExceededError,
    ModelConfigurationError,
    ModelGatewayError,
    StructuredOutputError,
)
from ai_swe.models.pricing import TABLA_POR_DEFECTO, PricingTable, pricing_from_json
from ai_swe.models.providers.base import ProviderAdapter, ProviderResponse
from ai_swe.models.registry import (
    build_adapter,
    provider_config_from_settings,
    requires_credentials,
)
from ai_swe.security import redact

log = logging.getLogger(__name__)

# Timeout minimo efectivo. Si el presupuesto esta al limite, un timeout de cero no
# tiene sentido (fallaria siempre por construccion); se deja un margen minimo para
# que la llamada pueda intentarse y falle por una razon real.
_TIMEOUT_MINIMO_S = 0.01

_MAPA_FINISH: dict[str, FinishReason] = {
    "stop": FinishReason.STOP,
    "end_turn": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "max_tokens": FinishReason.LENGTH,
    "content_filter": FinishReason.CONTENT_FILTER,
    "tool_calls": FinishReason.TOOL_CALLS,
    "function_call": FinishReason.TOOL_CALLS,
    "error": FinishReason.ERROR,
}


def _mapear_finish(crudo: str) -> FinishReason:
    """Traduce el motivo de finalizacion. Un valor desconocido **no** es un error.

    Un proveedor que invente un motivo nuevo no debe romper la normalizacion: se
    registra como `UNKNOWN` y se sigue. Fallar aqui convertiria una novedad del
    proveedor en una caida del sistema.
    """
    return _MAPA_FINISH.get(crudo.strip().lower(), FinishReason.UNKNOWN)


def _sin_cercas(texto: str) -> str:
    """Quita las cercas de bloque de codigo si el modelo envolvio el JSON.

    Es habitual que un modelo devuelva ```` ```json ... ``` ````. No quitarlas
    convertiria una respuesta correcta en un fallo de structured output.
    """
    limpio = texto.strip()
    if not limpio.startswith("```"):
        return limpio
    lineas = limpio.splitlines()
    if lineas and lineas[0].startswith("```"):
        lineas = lineas[1:]
    if lineas and lineas[-1].strip().startswith("```"):
        lineas = lineas[:-1]
    return "\n".join(lineas).strip()


def extraer_json(texto: str) -> dict | None:
    """Extrae un objeto JSON del contenido, o `None` si no hay ninguno.

    Tres intentos, de mas estricto a mas tolerante: el texto tal cual, el texto sin
    cercas de codigo, y el fragmento entre la primera `{` y la ultima `}`. No se
    inventa nada: si ninguno da un objeto, se devuelve `None` y el llamante decide.
    """
    if not texto or not texto.strip():
        return None

    candidatos = [texto.strip()]
    sin_cercas = _sin_cercas(texto)
    if sin_cercas != candidatos[0]:
        candidatos.append(sin_cercas)
    inicio, fin = sin_cercas.find("{"), sin_cercas.rfind("}")
    if inicio != -1 and fin > inicio:
        candidatos.append(sin_cercas[inicio : fin + 1])

    for candidato in candidatos:
        try:
            datos = json.loads(candidato)
        except ValueError:
            continue
        if isinstance(datos, dict):
            return datos
    return None


class ModelGateway:
    """Orquesta uno o varios adapters detras de una interfaz unica.

    `adapters[0]` es el primario; el resto son respaldos. El nombre del primario es
    el `provider_requested` de la respuesta, de modo que una respuesta servida por
    un respaldo **no puede parecer** que la sirvio el primario.
    """

    def __init__(
        self,
        adapters: Sequence[ProviderAdapter],
        *,
        timeout_s: float = 60.0,
        max_retries: int = 2,
        backoff_base_s: float = 1.0,
        max_backoff_s: float = 8.0,
        sleep: Callable[[float], None] = time.sleep,
        pricing: PricingTable | None = None,
        profile_settings: Settings | None = None,
    ) -> None:
        if not adapters:
            raise ModelConfigurationError("el gateway necesita al menos un adapter")
        if max_retries < 0:
            raise ModelConfigurationError("max_retries no puede ser negativo")
        self._adapters = list(adapters)
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._backoff_base_s = backoff_base_s
        self._max_backoff_s = max_backoff_s
        # Inyectable para que las pruebas no duerman de verdad: una suite que espera
        # 7 s por el backoff es una suite que nadie ejecuta.
        self._sleep = sleep
        self._pricing = pricing if pricing is not None else TABLA_POR_DEFECTO
        self._profile_settings = profile_settings
        self._ledger = None
        if profile_settings is not None:
            from ai_swe.state.budget_ledger import BudgetLedger

            self._ledger = BudgetLedger(profile_settings.state_db_path)

    # ------------------------------------------------------------------ consulta

    @property
    def requested_provider(self) -> str:
        return self._adapters[0].name

    @property
    def providers(self) -> tuple[str, ...]:
        return tuple(a.name for a in self._adapters)

    def close(self) -> None:
        """Cierra los adapters que lo necesiten (p. ej. el cliente HTTP)."""
        for adapter in self._adapters:
            cerrar = getattr(adapter, "close", None)
            if callable(cerrar):
                cerrar()

    def __enter__(self) -> ModelGateway:
        return self

    def __exit__(self, *_excepcion: object) -> None:
        self.close()

    # ------------------------------------------------------------------ publico

    def generate(self, request: ModelRequest, *, budget: Budget | None = None) -> ModelResponse:
        """Llamada de texto libre."""
        return self._llamar(request, budget=budget, response_model=None)

    def generate_structured(
        self,
        request: ModelRequest,
        *,
        response_model: type[BaseModel],
        budget: Budget | None = None,
    ) -> ModelResponse:
        """Llamada con salida validada contra un contrato Pydantic.

        El esquema que se envia al modelo se **deriva** del contrato con
        `model_json_schema()`: hay una sola fuente de verdad. Escribir el JSON Schema
        a mano en paralelo haria que la estructura enviada y la validada divergieran,
        y el modelo acabaria cumpliendo un contrato que nadie comprueba.
        """
        return self._llamar(request, budget=budget, response_model=response_model)

    def consume(self, budget: Budget, response: ModelResponse) -> Budget:
        """Aplica el consumo de una respuesta al presupuesto. Devuelve uno nuevo.

        Es un metodo ademas de una funcion libre para que el emparejamiento
        «respuesta -> presupuesto» quede a la vista en el punto de uso.
        """
        return _consumir(budget, usage=response.usage, cost=response.cost)

    # ------------------------------------------------------------------ interno

    def _preparar_peticion(
        self, request: ModelRequest, response_model: type[BaseModel] | None, budget: Budget | None
    ) -> ModelRequest:
        pedido = request

        if response_model is not None:
            esquema = response_model.model_json_schema()
            instruccion = ModelMessage(
                role=MessageRole.SYSTEM,
                content=(
                    "Responde UNICAMENTE con un objeto JSON valido que cumpla "
                    "exactamente este JSON Schema. No anadas texto fuera del objeto.\n"
                    + json.dumps(esquema, ensure_ascii=False)
                ),
            )
            pedido = pedido.model_copy(
                update={"messages": [*pedido.messages, instruccion], "json_schema": esquema}
            )

        base = pedido.timeout_s if pedido.timeout_s is not None else self._timeout_s
        if budget is not None:
            acotado = effective_timeout_s(budget, base)
            base = max(_TIMEOUT_MINIMO_S, acotado if acotado is not None else base)

        return pedido.model_copy(update={"timeout_s": base})

    def _espera(self, intento: int, error: ModelGatewayError) -> float:
        """Segundos a esperar antes del siguiente intento.

        Si el proveedor dijo cuanto esperar (`Retry-After`), se respeta; si no,
        retroceso exponencial. En ambos casos con techo: un `Retry-After` de una hora
        no puede bloquear una ejecucion, y un retroceso sin techo crece sin limite.
        """
        sugerida = getattr(error, "retry_after_s", None)
        if isinstance(sugerida, (int, float)) and sugerida > 0:
            return min(float(sugerida), self._max_backoff_s)
        return min(self._backoff_base_s * (2**intento), self._max_backoff_s)

    def _intentar(
        self, adapter: ProviderAdapter, request: ModelRequest
    ) -> tuple[ProviderResponse, float]:
        """Llama al adapter con reintentos. Devuelve la respuesta cruda y la latencia.

        Solo se reintenta lo que el **tipo** de error declara recuperable. Reintentar
        una credencial invalida gasta tiempo y cuota sin posibilidad de exito.
        """
        ultimo: ModelGatewayError | None = None
        for intento in range(self._max_retries + 1):
            from ai_swe.cancellation import current_cancellation

            control = current_cancellation()
            if control:
                control.check()
            inicio = time.perf_counter()
            try:
                reservation = None
                if self._ledger is not None:
                    from ai_swe.state.budget_ledger import LedgerError

                    settings = self._profile_settings
                    model = request.model or settings.model_name
                    if settings.max_cost_per_run is None or request.max_output_tokens is None:
                        raise ModelConfigurationError("El perfil requiere limite y salida acotada")
                    # UTF-8 bytes plus structural overhead are a conservative local estimate.
                    # Without a verified model tokenizer, a bytes/3 heuristic is
                    # not an upper bound. Reserve bytes plus framing overhead;
                    # duplicate schema serialization deliberately over-reserves.
                    inputs = len(request.model_dump_json().encode()) + 1024
                    estimate = self._pricing.cost(
                        model,
                        ModelUsage(input_tokens=inputs, output_tokens=request.max_output_tokens),
                    )
                    if estimate is None:
                        raise ModelConfigurationError("El perfil requiere una tarifa declarada")
                    try:
                        reservation = self._ledger.reserve_call(
                            request.run_id or "",
                            run_limit=settings.max_cost_per_run,
                            estimate=estimate,
                            hourly_limit=settings.max_cost_per_hour,
                        )
                    except LedgerError as exc:
                        raise BudgetExceededError(str(exc), motivos=("ledger",)) from None
                if control:
                    control.check()
                if reservation is not None:
                    self._ledger.mark_dispatched(reservation)
                emit(
                    "model_request_started",
                    mode="remote",
                    model=request.model or getattr(adapter, "_model", None),
                    provider=adapter.name,
                    attempt=intento + 1,
                )
                bruto = adapter.generate(request)
                emit(
                    "model_response_received",
                    mode="remote",
                    model=bruto.model or request.model,
                    provider=adapter.name,
                    duration_ms=(time.perf_counter() - inicio) * 1000,
                    input_tokens=bruto.usage.input_tokens,
                    output_tokens=bruto.usage.output_tokens,
                    cost=self._pricing.cost(bruto.model or request.model or "unknown", bruto.usage),
                )
                if reservation is not None:
                    declared = self._pricing.cost(bruto.model or model, bruto.usage)
                    self._ledger.settle(reservation, declared)
                    if declared is None:
                        raise ModelConfigurationError(
                            "Consumo desconocido; se conserva la reserva y se detiene la ejecucion"
                        )
            except ModelGatewayError as exc:
                ultimo = exc
                if not exc.recoverable or intento >= self._max_retries:
                    raise
                espera = self._espera(intento, exc)
                log.debug(
                    "reintento %d/%d con %s tras %s en %.2fs",
                    intento + 1,
                    self._max_retries,
                    adapter.name,
                    exc.error_class,
                    espera,
                )
                self._sleep(espera)
                continue
            latencia_ms = (time.perf_counter() - inicio) * 1000.0
            return bruto, latencia_ms

        # Inalcanzable: el bucle o devuelve o lanza. Se deja por correccion de tipos.
        if ultimo is not None:  # pragma: no cover
            raise ultimo
        raise ModelGatewayError("fallo sin error")  # pragma: no cover

    def _validar(self, contenido: str, response_model: type[BaseModel], provider: str) -> dict:
        """Valida el contenido contra el contrato. Nunca deja pasar un dict invalido."""
        datos = extraer_json(contenido)
        if datos is None:
            raise StructuredOutputError(
                "la respuesta no contiene un objeto JSON interpretable",
                provider=provider,
                detail=contenido[:300],
            )
        try:
            validado = response_model.model_validate(datos)
        except ValidationError as exc:
            raise StructuredOutputError(
                f"la respuesta no cumple el contrato {response_model.__name__}",
                provider=provider,
                detail=str(exc)[:600],
            ) from exc
        return validado.model_dump()

    def _normalizar(
        self,
        bruto: ProviderResponse,
        latencia_ms: float,
        adapter: ProviderAdapter,
        solicitado: str,
        request: ModelRequest,
        response_model: type[BaseModel] | None,
        error_previo: ModelGatewayError | None,
    ) -> ModelResponse:
        estructurado: dict | None = None
        if response_model is not None:
            estructurado = self._validar(bruto.content, response_model, adapter.name)

        modelo = bruto.model or request.model or ""
        return ModelResponse(
            content=bruto.content,
            structured_data=estructurado,
            provider=adapter.name,
            provider_requested=solicitado,
            model=modelo,
            finish_reason=_mapear_finish(bruto.finish_reason),
            usage=bruto.usage,
            latency_ms=latencia_ms,
            provider_request_id=bruto.provider_request_id,
            fallback_used=adapter.name != solicitado,
            fallback_reason=redact(str(error_previo)) if error_previo is not None else None,
            run_id=request.run_id,
            trace_id=request.trace_id,
            agent_role=request.agent_role,
            cost=self._pricing.cost(modelo, bruto.usage),
        )

    def _llamar(
        self,
        request: ModelRequest,
        *,
        budget: Budget | None,
        response_model: type[BaseModel] | None,
    ) -> ModelResponse:
        solicitado = self.requested_provider

        # ANTES de gastar: el presupuesto se comprueba aqui, de modo que una llamada
        # que no se puede pagar no llega a salir.
        if budget is not None:
            assert_budget_available(budget, provider=solicitado)

        pedido = self._preparar_peticion(request, response_model, budget)
        ultimo_error: ModelGatewayError | None = None

        for indice, adapter in enumerate(self._adapters):
            try:
                bruto, latencia_ms = self._intentar(adapter, pedido)
            except ModelGatewayError as exc:
                ultimo_error = exc
                hay_respaldo = indice + 1 < len(self._adapters)
                # Solo un fallo recuperable justifica probar otro proveedor. Un error
                # de configuracion o de credencial se repetiria igual en el respaldo,
                # y ademas no debe ocultarse detras de un exito ajeno.
                if not exc.recoverable or not hay_respaldo:
                    raise
                log.warning(
                    "proveedor %s fallo (%s); se prueba el respaldo %s",
                    adapter.name,
                    exc.error_class,
                    self._adapters[indice + 1].name,
                )
                continue

            return self._normalizar(
                bruto, latencia_ms, adapter, solicitado, pedido, response_model, ultimo_error
            )

        raise (
            ultimo_error
            if ultimo_error is not None
            else ModelGatewayError(  # pragma: no cover
                "ningun adapter respondio"
            )
        )


def gateway_from_settings(
    settings: Settings,
    *,
    adapters: Sequence[ProviderAdapter] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> ModelGateway:
    """Construye un gateway a partir de la configuracion del sistema.

    Si se pasan `adapters`, se usan esos (util para inyectar respaldos o dobles). Si
    no, se construye el adapter del proveedor configurado.

    **La credencial se exige aqui**, en el borde y solo cuando de verdad se va a usar
    el modelo. Arrancar el sistema sin clave sigue siendo valido: esta funcion no se
    llama al arrancar.

    **Tabla de precios.** Se carga de `AI_SWE_MODEL_PRICING` si esta declarada. Una
    lista declarada pero mal formada **falla aqui**, en el borde: unos precios mal
    escritos no deben degradarse en silencio a «no se sabe», porque entonces el
    presupuesto de coste dejaria de actuar sin que nadie se entere.
    """
    if settings.max_cost_per_hour is not None and not settings.profile_id:
        raise ModelConfigurationError(
            "El límite horario requiere un perfil con ledger de presupuesto"
        )
    tabla = pricing_from_json(settings.model_pricing)

    if adapters is not None:
        return ModelGateway(
            list(adapters),
            sleep=sleep,
            pricing=tabla,
            profile_settings=settings if settings.profile_id else None,
        )

    config = provider_config_from_settings(settings)
    if (
        requires_credentials(config.name) or config.base_url == "https://router.huggingface.co/v1"
    ) and not config.has_credentials:
        raise ModelConfigurationError(
            f"el proveedor '{config.name}' exige una credencial y no hay ninguna configurada",
            provider=config.name,
            detail="define AI_SWE_MODEL_API_KEY en el entorno",
        )

    adapter = build_adapter(config)
    return ModelGateway(
        [adapter],
        timeout_s=config.timeout_s,
        max_retries=config.max_retries,
        sleep=sleep,
        pricing=tabla,
        profile_settings=settings if settings.profile_id else None,
    )
