"""Pruebas del Model Gateway: la frontera con el modelo.

**Como se prueba sin red y sin credenciales.** Todo se ejercita con
`FakeModelAdapter`, que provoca a voluntad los fallos que hay que manejar
(timeout, 429, 5xx, credencial invalida, respuesta malformada). Probar esos caminos
contra un proveedor real seria lento, caro y no reproducible; con el fake son
deterministas.

El adapter real tambien se prueba aqui, pero **sin abrir un socket**: se inyecta un
`httpx.MockTransport`. Asi el codigo de produccion se ejecuta entero sin red.

No hay ninguna credencial real en este fichero, y no debe haberla nunca.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, SecretStr, ValidationError

from ai_swe.contracts import Budget
from ai_swe.models import (
    BudgetExceededError,
    FakeModelAdapter,
    FinishReason,
    InvalidResponseError,
    MessageRole,
    ModelAuthenticationError,
    ModelConfigurationError,
    ModelGateway,
    ModelGatewayError,
    ModelMessage,
    ModelPricing,
    ModelRateLimitError,
    ModelRequest,
    ModelTimeoutError,
    ModelUsage,
    PricingTable,
    ProviderConfig,
    ProviderUnavailableError,
    StructuredOutputError,
    UnknownProviderError,
    build_adapter,
    consume,
    effective_timeout_s,
    provider_config_from_settings,
    registered_providers,
)
from ai_swe.models.gateway import extraer_json
from ai_swe.security import clear_registered_secrets, register_secret

# Clave de fantasia. Se nombra para que sea evidente que no es real.
CLAVE_FALSA = "clave-falsisima-para-pruebas-1234567890"


def peticion(texto: str = "di hola", **extra) -> ModelRequest:
    return ModelRequest(
        messages=[ModelMessage(role=MessageRole.USER, content=texto)], **extra
    )


@pytest.fixture(autouse=True)
def _sin_secretos_registrados():
    """El registro de secretos es estado global; se aisla entre pruebas."""
    clear_registered_secrets()
    yield
    clear_registered_secrets()


@pytest.fixture
def sin_espera():
    """Evita que el backoff duerma de verdad.

    Sin esto, probar «reintentos agotados» con 3 intentos tardaria 1+2 = 3 s. Una
    suite que duerme es una suite que nadie ejecuta.
    """
    return lambda _s: None


def gateway(adapters, **kwargs) -> ModelGateway:
    kwargs.setdefault("sleep", lambda _s: None)
    return ModelGateway(adapters, **kwargs)


class Salida(BaseModel):
    """Contrato minimo para probar structured output."""

    valor: int
    nombre: str


# ============================================================ 1. exito basico


def test_fake_adapter_exito(sin_espera) -> None:
    fake = FakeModelAdapter(content="hola mundo")
    respuesta = gateway([fake]).generate(peticion())
    assert respuesta.content == "hola mundo"
    assert respuesta.provider == "fake"
    assert respuesta.provider_requested == "fake"
    assert respuesta.fallback_used is False
    assert respuesta.error is None


def test_la_respuesta_lleva_la_metadata_de_correlacion(sin_espera) -> None:
    """Es lo que permitira registrar la traza mas adelante sin rehacer la frontera."""
    from ai_swe.contracts import AgentRole

    fake = FakeModelAdapter()
    respuesta = gateway([fake]).generate(
        peticion(run_id="run-1", trace_id="trace-1", agent_role=AgentRole.CODER)
    )
    assert respuesta.run_id == "run-1"
    assert respuesta.trace_id == "trace-1"
    assert respuesta.agent_role is AgentRole.CODER
    assert respuesta.latency_ms >= 0.0


def test_el_motivo_de_finalizacion_se_normaliza(sin_espera) -> None:
    assert gateway([FakeModelAdapter(finish_reason="stop")]).generate(peticion()).finish_reason is FinishReason.STOP
    assert gateway([FakeModelAdapter(finish_reason="length")]).generate(peticion()).finish_reason is FinishReason.LENGTH


def test_un_motivo_de_finalizacion_desconocido_no_rompe(sin_espera) -> None:
    """Un valor nuevo del proveedor no es un error del sistema."""
    respuesta = gateway([FakeModelAdapter(finish_reason="motivo_inventado")]).generate(peticion())
    assert respuesta.finish_reason is FinishReason.UNKNOWN


# ============================================================ 2-3. structured output


def test_structured_output_valido(sin_espera) -> None:
    fake = FakeModelAdapter(structured={"valor": 42, "nombre": "respuesta"})
    respuesta = gateway([fake]).generate_structured(peticion("42"), response_model=Salida)
    assert respuesta.structured_data == {"valor": 42, "nombre": "respuesta"}
    assert respuesta.structured_as(Salida).valor == 42


def test_structured_output_se_pide_con_el_esquema_del_contrato(sin_espera) -> None:
    """Una sola fuente de verdad: el esquema se **deriva** del contrato Pydantic."""
    fake = FakeModelAdapter(structured={"valor": 1, "nombre": "x"})
    gateway([fake]).generate_structured(peticion(), response_model=Salida)
    esquema_enviado = fake.calls[0].json_schema
    assert esquema_enviado == Salida.model_json_schema()
    # Y ademas viaja en los mensajes, que es lo que entienden todos los endpoints.
    assert "valor" in fake.calls[0].messages[-1].content


def test_structured_output_invalido_lanza(sin_espera) -> None:
    """Un dict que no cumple el contrato NO puede cruzar al sistema."""
    fake = FakeModelAdapter(structured={"valor": "no-es-un-entero", "nombre": "x"})
    with pytest.raises(StructuredOutputError) as info:
        gateway([fake]).generate_structured(peticion(), response_model=Salida)
    assert info.value.error_class == "STRUCTURED_OUTPUT_ERROR"


def test_structured_output_sin_json_lanza(sin_espera) -> None:
    fake = FakeModelAdapter(content="esto no es json en absoluto")
    with pytest.raises(StructuredOutputError):
        gateway([fake]).generate_structured(peticion(), response_model=Salida)


def test_structured_output_acepta_json_envuelto_en_cercas(sin_espera) -> None:
    """Un modelo que envuelve el JSON en ``` es correcto, no un fallo."""
    fake = FakeModelAdapter(content='```json\n{"valor": 7, "nombre": "siete"}\n```')
    respuesta = gateway([fake]).generate_structured(peticion(), response_model=Salida)
    assert respuesta.structured_data == {"valor": 7, "nombre": "siete"}


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('ruido antes {"a": 1} ruido despues', {"a": 1}),
        ("", None),
        ("sin json", None),
        ("[1, 2, 3]", None),  # una lista no es un objeto
    ],
)
def test_extraer_json(texto: str, esperado: dict | None) -> None:
    assert extraer_json(texto) == esperado


# ============================================================ 4. provider desconocido


def test_provider_desconocido_lanza_y_dice_cuales_hay() -> None:
    with pytest.raises(UnknownProviderError) as info:
        build_adapter(ProviderConfig(name="proveedor-que-no-existe", model="x"))
    assert "fake" in str(info.value)  # el mensaje es accionable


def test_el_registro_no_resuelve_por_import_dinamico() -> None:
    """Un nombre no registrado nunca debe resolver a codigo importable.

    Si el registro usara `importlib` con el nombre de la configuracion, un valor
    como `os` o `subprocess` seria una via de ejecucion arbitraria.
    """
    for peligroso in ("os", "subprocess", "sys", "ai_swe.models.gateway"):
        with pytest.raises(UnknownProviderError):
            build_adapter(ProviderConfig(name=peligroso, model="x"))


# ============================================================ 5. configuracion incompleta


def test_proveedor_con_credencial_sin_credencial_falla_en_el_borde() -> None:
    from ai_swe.models import gateway_from_settings
    from ai_swe.config import Settings

    ajustes = Settings(model_provider="openai", model_name="gpt-x", model_api_key="")
    with pytest.raises(ModelConfigurationError):
        gateway_from_settings(ajustes)


def test_proveedor_local_sin_credencial_es_valido() -> None:
    from ai_swe.config import Settings

    config = provider_config_from_settings(
        Settings(model_provider="ollama", model_name="llama3", model_api_key="")
    )
    assert config.name == "ollama"
    assert config.has_credentials is False


def test_proveedor_con_credencial_sin_modelo_falla() -> None:
    from ai_swe.config import Settings

    with pytest.raises(ModelConfigurationError):
        provider_config_from_settings(
            Settings(model_provider="openai", model_name="", model_api_key=CLAVE_FALSA)
        )


def test_el_adapter_exige_modelo() -> None:
    from ai_swe.models import OpenAICompatibleAdapter

    with pytest.raises(ModelConfigurationError):
        OpenAICompatibleAdapter(name="openai", model="   ")


# ============================================================ 6. timeout


def test_timeout_es_recuperable(sin_espera) -> None:
    with pytest.raises(ModelTimeoutError) as info:
        gateway([FakeModelAdapter(fault="timeout")], max_retries=0).generate(peticion())
    assert info.value.recoverable is True


def test_el_timeout_efectivo_se_acota_al_presupuesto(sin_espera) -> None:
    """Un agente no puede esperar mas de lo que le queda de presupuesto."""
    fake = FakeModelAdapter()
    presupuesto = Budget(max_seconds=10.0, elapsed_seconds=9.5)
    gateway([fake], timeout_s=60.0).generate(peticion(), budget=presupuesto)
    # 60 s solicitados, pero solo quedan 0,5 s de presupuesto.
    assert fake.calls[0].timeout_s == pytest.approx(0.5)


def test_effective_timeout_s() -> None:
    assert effective_timeout_s(Budget(max_seconds=10.0, elapsed_seconds=0.0), 30.0) == 10.0
    assert effective_timeout_s(Budget(max_seconds=10.0, elapsed_seconds=0.0), 3.0) == 3.0
    assert effective_timeout_s(Budget(max_seconds=10.0, elapsed_seconds=10.0), 30.0) == 0.0


# ============================================================ 7. rate limit


def test_rate_limit_es_recuperable(sin_espera) -> None:
    with pytest.raises(ModelRateLimitError) as info:
        gateway([FakeModelAdapter(fault="rate_limit")], max_retries=0).generate(peticion())
    assert info.value.recoverable is True


def test_rate_limit_respeta_retry_after(sin_espera) -> None:
    """Si el proveedor dice cuanto esperar, se espera eso, no el backoff ciego."""
    esperas: list[float] = []
    fake = FakeModelAdapter(faults=["rate_limit"], retry_after_s=3.0)
    ModelGateway([fake], max_retries=2, backoff_base_s=1.0, sleep=esperas.append).generate(
        peticion()
    )
    assert esperas == [3.0]


def test_retry_after_desmedido_se_acota(sin_espera) -> None:
    """Un `Retry-After` de una hora no puede bloquear la ejecucion."""
    esperas: list[float] = []
    fake = FakeModelAdapter(faults=["rate_limit"], retry_after_s=3600.0)
    ModelGateway([fake], max_retries=2, max_backoff_s=8.0, sleep=esperas.append).generate(
        peticion()
    )
    assert esperas == [8.0]


# ============================================================ 8-10. reintentos


def test_reintento_exitoso(sin_espera) -> None:
    """Falla dos veces y a la tercera funciona: la respuesta llega."""
    fake = FakeModelAdapter(faults=["timeout", "rate_limit"], content="a la tercera")
    respuesta = gateway([fake], max_retries=2).generate(peticion())
    assert respuesta.content == "a la tercera"
    assert len(fake.calls) == 3


def test_retry_agotado_propaga_el_ultimo_error(sin_espera) -> None:
    fake = FakeModelAdapter(fault="timeout")
    with pytest.raises(ModelTimeoutError):
        gateway([fake], max_retries=2).generate(peticion())
    assert len(fake.calls) == 3  # intento inicial + 2 reintentos


def test_backoff_exponencial(sin_espera) -> None:
    esperas: list[float] = []
    fake = FakeModelAdapter(fault="timeout")
    with pytest.raises(ModelTimeoutError):
        ModelGateway([fake], max_retries=3, backoff_base_s=1.0, sleep=esperas.append).generate(
            peticion()
        )
    assert esperas == [1.0, 2.0, 4.0]


def test_error_no_reintentable_no_se_reintenta(sin_espera) -> None:
    """Reintentar una credencial invalida gasta tiempo y cuota sin poder exito."""
    fake = FakeModelAdapter(fault="auth_error")
    with pytest.raises(ModelAuthenticationError):
        gateway([fake], max_retries=3).generate(peticion())
    assert len(fake.calls) == 1


def test_respuesta_invalida_no_se_reintenta(sin_espera) -> None:
    fake = FakeModelAdapter(fault="invalid_response")
    with pytest.raises(InvalidResponseError):
        gateway([fake], max_retries=3).generate(peticion())
    assert len(fake.calls) == 1


# ============================================================ 11-12. fallback


def test_fallback_exitoso(sin_espera) -> None:
    primario = FakeModelAdapter(name="primario", fault="unavailable")
    respaldo = FakeModelAdapter(name="respaldo", content="desde el respaldo")
    respuesta = gateway([primario, respaldo]).generate(peticion())

    assert respuesta.content == "desde el respaldo"
    assert respuesta.provider == "respaldo"
    assert respuesta.provider_requested == "primario"
    # No se oculta que hubo fallback.
    assert respuesta.fallback_used is True
    assert respuesta.fallback_reason is not None


def test_fallback_agotado_propaga_el_ultimo_error(sin_espera) -> None:
    adapters = [
        FakeModelAdapter(name="a", fault="unavailable"),
        FakeModelAdapter(name="b", fault="unavailable"),
    ]
    with pytest.raises(ProviderUnavailableError):
        gateway(adapters).generate(peticion())


def test_un_error_no_recuperable_no_activa_el_fallback(sin_espera) -> None:
    """Un fallo de credencial no debe quedar oculto tras un exito ajeno."""
    primario = FakeModelAdapter(name="primario", fault="auth_error")
    respaldo = FakeModelAdapter(name="respaldo", content="no deberia usarse")
    with pytest.raises(ModelAuthenticationError):
        gateway([primario, respaldo]).generate(peticion())
    assert respaldo.calls == []


# ============================================================ 13-16. presupuesto


def test_budget_model_calls_agotado_no_gasta_la_llamada(sin_espera) -> None:
    fake = FakeModelAdapter()
    presupuesto = Budget(max_model_calls=1, used_model_calls=1)
    with pytest.raises(BudgetExceededError) as info:
        gateway([fake]).generate(peticion(), budget=presupuesto)
    assert "model_calls" in info.value.motivos
    assert fake.calls == []  # no se gasto nada


def test_budget_tokens_agotado(sin_espera) -> None:
    presupuesto = Budget(max_tokens=100, used_tokens=100)
    with pytest.raises(BudgetExceededError) as info:
        gateway([FakeModelAdapter()]).generate(peticion(), budget=presupuesto)
    assert "tokens" in info.value.motivos


def test_budget_deadline_agotado(sin_espera) -> None:
    presupuesto = Budget(max_seconds=10.0, elapsed_seconds=10.0)
    with pytest.raises(BudgetExceededError) as info:
        gateway([FakeModelAdapter()]).generate(peticion(), budget=presupuesto)
    assert "seconds" in info.value.motivos


def test_budget_coste_agotado(sin_espera) -> None:
    presupuesto = Budget(max_cost=1.0, used_cost=1.0)
    with pytest.raises(BudgetExceededError) as info:
        gateway([FakeModelAdapter()]).generate(peticion(), budget=presupuesto)
    assert "cost" in info.value.motivos


def test_sin_limite_de_coste_no_bloquea(sin_espera) -> None:
    """`max_cost=None` es «sin limite declarado», no «cero permitido»."""
    presupuesto = Budget(max_cost=None)
    assert gateway([FakeModelAdapter()]).generate(peticion(), budget=presupuesto).content


def test_el_presupuesto_de_herramientas_no_lo_comprueba_el_modelo(sin_espera) -> None:
    """`tool_calls` es de otra capa: el gateway no debe bloquear por eso."""
    presupuesto = Budget(max_tool_calls=1, used_tool_calls=1)
    respuesta = gateway([FakeModelAdapter()]).generate(peticion(), budget=presupuesto)
    assert respuesta.content


# ============================================================ 17. redaccion


def test_la_clave_no_aparece_en_la_peticion(sin_espera) -> None:
    """La clave vive en el adapter, nunca en la peticion: serializarla no la filtra."""
    fake = FakeModelAdapter()
    gateway([fake]).generate(peticion(metadata={"nota": "sin secretos"}))
    assert CLAVE_FALSA not in fake.calls[0].model_dump_json()


def test_un_error_del_proveedor_no_filtra_la_clave(sin_espera) -> None:
    """Un 401 puede devolver la clave en el cuerpo; no debe llegar al mensaje."""
    register_secret(CLAVE_FALSA)
    fake = FakeModelAdapter(fault="auth_error")
    with pytest.raises(ModelAuthenticationError) as info:
        gateway([fake]).generate(peticion())
    assert CLAVE_FALSA not in str(info.value)


def test_el_fallback_reason_esta_redactado(sin_espera) -> None:
    register_secret(CLAVE_FALSA)
    primario = FakeModelAdapter(name="primario", fault="unavailable")
    respaldo = FakeModelAdapter(name="respaldo", content="ok")
    respuesta = gateway([primario, respaldo]).generate(peticion())
    assert CLAVE_FALSA not in (respuesta.fallback_reason or "")


def test_el_constructor_de_errores_redacta_el_mensaje() -> None:
    """Aisla la redaccion que hace el propio constructor de errores.

    Sin esta prueba, la redaccion del adapter **enmascara** a la del constructor:
    se puede desactivar cualquiera de las dos y la suite sigue verde, porque la
    otra cubre el mismo texto. Es el mismo fallo de capas que ya aparecio en el
    redactor de secretos, y se detecto porque una mutacion no caia.
    """
    register_secret(CLAVE_FALSA)
    error = ModelGatewayError(f"fallo al autenticar con {CLAVE_FALSA}")
    assert CLAVE_FALSA not in str(error)


def test_el_detalle_de_un_error_se_redacta() -> None:
    register_secret(CLAVE_FALSA)
    error = ModelGatewayError("fallo", detail=f"cuerpo del proveedor: {CLAVE_FALSA}")
    assert CLAVE_FALSA not in (error.detail or "")
    assert CLAVE_FALSA not in str(error)


def test_el_registro_no_usa_import_dinamico() -> None:
    """Propiedad de seguridad comprobada en la fuente.

    Es dificil de comprobar por comportamiento: un `importlib` que no encuentre un
    atributo `.adapter` acaba en el mismo `UnknownProviderError` que no usarlo, asi
    que la prueba de comportamiento pasa en ambos casos. La propiedad -que un valor
    de configuracion no puede convertirse en un import- vive en la fuente.

    Se analiza el **AST**, no el texto. Una comprobacion por subcadena encontraria
    la palabra en el docstring que explica precisamente por que no se usa, y daria
    un falso positivo: el mismo cepo que ya aparecio midiendo otros modulos.
    """
    import ast
    from pathlib import Path

    fuente = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "ai_swe"
        / "models"
        / "registry.py"
    ).read_text(encoding="utf-8")
    arbol = ast.parse(fuente)

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            assert all(alias.name != "importlib" for alias in nodo.names), "importa importlib"
        elif isinstance(nodo, ast.ImportFrom):
            assert nodo.module != "importlib", "importa de importlib"
        elif isinstance(nodo, ast.Attribute):
            assert nodo.attr != "import_module", "llama a import_module"


# ============================================================ 18. usage y coste


def test_usage_agregado_al_presupuesto(sin_espera) -> None:
    presupuesto = Budget()
    respuesta = gateway([FakeModelAdapter()]).generate(peticion())
    actualizado = consume(presupuesto, usage=respuesta.usage, cost=respuesta.cost)

    assert actualizado.used_model_calls == presupuesto.used_model_calls + 1
    assert actualizado.used_tokens == presupuesto.used_tokens + 15  # 10 + 5
    assert actualizado.used_cost == presupuesto.used_cost  # coste desconocido -> no se toca
    # El original no se modifica: `consume` devuelve uno nuevo.
    assert presupuesto.used_model_calls == 0


def test_usage_desconocido_no_se_convierte_en_cero() -> None:
    """`None` es «no se sabe», distinto de `0`, que afirma que no se consumio nada."""
    uso = ModelUsage()
    actualizado = consume(Budget(), usage=uso)
    assert actualizado.used_tokens == 0
    assert actualizado.used_model_calls == 1  # la llamada si cuenta


def test_usage_calcula_el_total_solo_si_tiene_las_partes() -> None:
    assert ModelUsage(input_tokens=10, output_tokens=5).total_tokens == 15
    assert ModelUsage(input_tokens=10).total_tokens is None
    assert ModelUsage(total_tokens=99).total_tokens == 99


def test_el_gateway_expone_consume(sin_espera) -> None:
    gw = gateway([FakeModelAdapter()])
    presupuesto = Budget()
    respuesta = gw.generate(peticion())
    assert gw.consume(presupuesto, respuesta).used_model_calls == 1


def test_coste_es_none_sin_tabla_de_precios(sin_espera) -> None:
    """No se inventan precios: sin tabla, el coste es desconocido."""
    respuesta = gateway([FakeModelAdapter()]).generate(peticion())
    assert respuesta.cost is None


def test_coste_se_calcula_con_una_tabla_rellenada(sin_espera) -> None:
    tabla = PricingTable()
    tabla.add("fake-model", ModelPricing(input_per_1k=0.01, output_per_1k=0.02))
    fake = FakeModelAdapter(usage=ModelUsage(input_tokens=1000, output_tokens=1000))
    respuesta = gateway([fake], pricing=tabla).generate(peticion())
    assert respuesta.cost == pytest.approx(0.03)


def test_la_tabla_de_precios_no_inventa_si_faltan_tokens() -> None:
    tabla = PricingTable()
    tabla.add("m", ModelPricing(input_per_1k=1.0, output_per_1k=1.0))
    assert tabla.cost("m", ModelUsage()) is None
    assert tabla.cost("desconocido", ModelUsage(input_tokens=1, output_tokens=1)) is None


def test_un_precio_negativo_es_invalido() -> None:
    with pytest.raises(ValueError):
        ModelPricing(input_per_1k=-1.0, output_per_1k=1.0)


# ============================================================ 19. seleccion de proveedor


def test_el_registro_construye_el_adapter_del_proveedor_pedido() -> None:
    from ai_swe.models import OpenAICompatibleAdapter

    adapter = build_adapter(
        ProviderConfig(name="ollama", model="llama3", api_key=SecretStr(""), base_url="http://localhost:11434/v1")
    )
    assert isinstance(adapter, OpenAICompatibleAdapter)
    assert adapter.name == "ollama"
    assert adapter.base_url == "http://localhost:11434/v1"


def test_el_registro_incluye_los_proveedores_previstos() -> None:
    assert set(registered_providers()) >= {"fake", "openai_compatible", "openai", "ollama", "vllm"}


def test_cambiar_de_proveedor_es_cambiar_la_configuracion() -> None:
    """El mismo codigo construye adapters distintos segun el nombre."""
    a = build_adapter(ProviderConfig(name="openai", model="gpt-x", api_key=SecretStr("k")))
    b = build_adapter(ProviderConfig(name="vllm", model="llama3", base_url="http://localhost:8000/v1"))
    assert a.name == "openai" and b.name == "vllm"
    assert type(a) is type(b)  # mismo adapter, distinta configuracion


# ============================================================ 20. sin serializar la clave


def test_la_configuracion_no_serializa_la_clave() -> None:
    config = ProviderConfig(name="openai", model="gpt-x", api_key=SecretStr(CLAVE_FALSA))
    assert CLAVE_FALSA not in repr(config)
    assert CLAVE_FALSA not in str(config.model_dump())
    assert CLAVE_FALSA not in config.model_dump_json()


def test_la_peticion_no_tiene_ningun_campo_de_credencial() -> None:
    """Estructural: no hay donde poner una clave, asi que no puede filtrarse.

    Se compara por **partes** del nombre, no por subcadena: `max_output_tokens` es
    un contador, no una credencial, y una comprobacion por subcadena lo marcaria
    como sospechoso. Un falso positivo aqui empujaria a renombrar un campo que no
    tiene nada que ver con la seguridad.
    """
    partes_prohibidas = {"key", "secret", "password", "credential", "credentials", "authorization", "bearer"}
    sospechosos = set()
    for campo in ModelRequest.model_fields:
        partes = set(campo.lower().split("_"))
        if partes & partes_prohibidas:
            sospechosos.add(campo)
    assert sospechosos == set()


# ============================================================ adapter real sin red


def test_adapter_real_sin_red(monkeypatch) -> None:
    """El adapter real se ejercita entero con un transporte falso: sin socket."""
    import httpx

    from ai_swe.models import OpenAICompatibleAdapter

    capturado: dict = {}

    def manejador(peticion_http: httpx.Request) -> httpx.Response:
        capturado["url"] = str(peticion_http.url)
        capturado["auth"] = peticion_http.headers.get("authorization")
        capturado["cuerpo"] = json.loads(peticion_http.content)
        return httpx.Response(
            200,
            json={
                "id": "req-1",
                "model": "gpt-x",
                "choices": [
                    {"message": {"role": "assistant", "content": "hola"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            },
        )

    cliente = httpx.Client(transport=httpx.MockTransport(manejador))
    adapter = OpenAICompatibleAdapter(
        name="openai", model="gpt-x", api_key=CLAVE_FALSA, client=cliente
    )
    respuesta = gateway([adapter]).generate(peticion("hi"))

    assert respuesta.content == "hola"
    assert respuesta.usage.total_tokens == 18
    assert capturado["url"].endswith("/chat/completions")
    assert capturado["cuerpo"]["model"] == "gpt-x"
    assert capturado["auth"].startswith("Bearer ")


def test_el_adapter_real_no_filtra_la_clave_en_un_401() -> None:
    import httpx

    from ai_swe.models import OpenAICompatibleAdapter

    def manejador(_peticion_http: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": {"message": f"Invalid API key: {CLAVE_FALSA}"}}
        )

    cliente = httpx.Client(transport=httpx.MockTransport(manejador))
    adapter = OpenAICompatibleAdapter(
        name="openai", model="gpt-x", api_key=CLAVE_FALSA, client=cliente
    )
    with pytest.raises(ModelAuthenticationError) as info:
        gateway([adapter]).generate(peticion())
    assert CLAVE_FALSA not in str(info.value)


def test_el_adapter_real_mapea_429_con_retry_after() -> None:
    import httpx

    from ai_swe.models import OpenAICompatibleAdapter

    def manejador(_peticion_http: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "2"}, text="slow down")

    cliente = httpx.Client(transport=httpx.MockTransport(manejador))
    adapter = OpenAICompatibleAdapter(name="openai", model="gpt-x", client=cliente)
    with pytest.raises(ModelRateLimitError) as info:
        gateway([adapter], max_retries=0).generate(peticion())
    assert info.value.retry_after_s == 2.0


def test_el_adapter_real_mapea_5xx_a_no_disponible() -> None:
    import httpx

    from ai_swe.models import OpenAICompatibleAdapter

    cliente = httpx.Client(
        transport=httpx.MockTransport(lambda _r: httpx.Response(503, text="unavailable"))
    )
    adapter = OpenAICompatibleAdapter(name="openai", model="gpt-x", client=cliente)
    with pytest.raises(ProviderUnavailableError):
        gateway([adapter], max_retries=0).generate(peticion())


def test_el_adapter_real_mapea_timeout_de_httpx() -> None:
    import httpx

    from ai_swe.models import OpenAICompatibleAdapter

    def manejador(_peticion_http: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulado")

    cliente = httpx.Client(transport=httpx.MockTransport(manejador))
    adapter = OpenAICompatibleAdapter(name="openai", model="gpt-x", client=cliente)
    with pytest.raises(ModelTimeoutError):
        gateway([adapter], max_retries=0).generate(peticion())


def test_el_adapter_real_rechaza_una_respuesta_sin_choices() -> None:
    import httpx

    from ai_swe.models import OpenAICompatibleAdapter

    cliente = httpx.Client(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={"nada": 1}))
    )
    adapter = OpenAICompatibleAdapter(name="openai", model="gpt-x", client=cliente)
    with pytest.raises(InvalidResponseError):
        gateway([adapter], max_retries=0).generate(peticion())


def test_el_adapter_real_rechaza_json_malformado() -> None:
    import httpx

    from ai_swe.models import OpenAICompatibleAdapter

    cliente = httpx.Client(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, text="<html>no json</html>"))
    )
    adapter = OpenAICompatibleAdapter(name="openai", model="gpt-x", client=cliente)
    with pytest.raises(InvalidResponseError):
        gateway([adapter], max_retries=0).generate(peticion())


def test_el_adapter_real_aplica_el_timeout_de_la_peticion() -> None:
    """El timeout efectivo llega de verdad a httpx, no solo al objeto de peticion."""
    import httpx

    from ai_swe.models import OpenAICompatibleAdapter

    visto: dict = {}

    def manejador(peticion_http: httpx.Request) -> httpx.Response:
        visto["timeout"] = peticion_http.extensions.get("timeout")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "model": "gpt-x",
            },
        )

    cliente = httpx.Client(transport=httpx.MockTransport(manejador))
    adapter = OpenAICompatibleAdapter(name="openai", model="gpt-x", client=cliente)
    gateway([adapter]).generate(
        ModelRequest(
            messages=[ModelMessage(role=MessageRole.USER, content="x")], timeout_s=1.25
        )
    )
    assert visto["timeout"]["read"] == pytest.approx(1.25)


# ============================================================ estructura del paquete


def test_solo_los_adapters_conocen_la_libreria_http() -> None:
    """Fuera de `models/providers/` nadie habla HTTP: es lo que hace sustituible al proveedor."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent / "src"
    infractores = []
    for archivo in raiz.rglob("*.py"):
        if "models/providers" in archivo.as_posix():
            continue
        if "import httpx" in archivo.read_text(encoding="utf-8"):
            infractores.append(archivo.name)
    assert infractores == []


def test_ningun_modulo_importa_un_sdk_de_proveedor() -> None:
    """El criterio de salida de la fase, comprobado estructuralmente."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent / "src"
    sdks = ("import openai", "from openai", "import anthropic", "from anthropic", "google.generativeai", "import cohere")
    infractores = []
    for archivo in raiz.rglob("*.py"):
        texto = archivo.read_text(encoding="utf-8")
        for sdk in sdks:
            if sdk in texto:
                infractores.append((archivo.name, sdk))
    assert infractores == []


def test_solo_interpret_habla_con_el_gateway() -> None:
    """**F3**: de todos los nodos del grafo, solo `interpret` usa el gateway.

    La version anterior de esta prueba afirmaba que *ningun* fichero del grafo
    contuviera la cadena `ai_swe.models`, y buscaba subcadenas con `in` sobre el
    texto completo. Eso la hacia fragil en los dos sentidos: **fallaba por una
    mencion en un comentario** (falso positivo, y asi ocurrio al escribir F3) y
    **no habria detectado** un `importlib.import_module("ai_swe.models")`, porque
    esa cadena no aparece. Se reescribe con `ast` para mirar los `import` de verdad.

    **Que se comprueba exactamente.** No basta con «solo `nodes.py` importa»: una
    mutacion que anadio `from ai_swe.models import ModelGateway` dentro de
    `researcher` (el **segundo** nodo) seguia dejando el conjunto de ficheros en
    `{nodes.py}` y pasaba sin ser cazada. Lo que de verdad protege la arquitectura
    es **la funcion** que importa: solo las funciones que sirven a `interpret`
    pueden hacerlo. Se comparan nombres de funcion, no ficheros.

    Y se comprueba que esos imports sean **perezosos** (dentro de una funcion),
    porque un `import ai_swe.models` en el cuerpo del modulo obligaria a tener el
    gateway instalado para poder importar el grafo.
    """
    import ast
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent / "src" / "ai_swe" / "graph"

    # Las funciones que pueden importar el gateway. Todo lo demas es una violacion
    # de la regla «una fase conecta un nodo».
    funciones_autorizadas = {
        "_gateway_por_defecto",
        "_interpretacion_del_modelo",
        "_es_fallo_esperado",
    }
    funciones_con_modelo: set[str] = set()
    a_nivel_de_modulo: list[str] = []

    for archivo in raiz.rglob("*.py"):
        modulo = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
        for nodo in ast.walk(modulo):
            if isinstance(nodo, ast.Import):
                nombres = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                nombres = [nodo.module or ""]
            else:
                continue
            if not any(n == "ai_swe.models" or n.startswith("ai_swe.models.") for n in nombres):
                continue
            contenedora = _funcion_contenedora(arbol_funciones(modulo), nodo)
            if contenedora is None:
                a_nivel_de_modulo.append(f"{archivo.name}:{nodo.lineno}")
            else:
                funciones_con_modelo.add(contenedora)

    assert funciones_con_modelo <= funciones_autorizadas, (
        "solo las funciones que sirven a `interpret` pueden importar el gateway; "
        f"tambien lo hacen: {sorted(funciones_con_modelo - funciones_autorizadas)}"
    )
    assert a_nivel_de_modulo == [], (
        f"el gateway debe importarse de forma perezosa, no al cargar el modulo: {a_nivel_de_modulo}"
    )


def arbol_funciones(modulo):
    """Todas las funciones del modulo, para poder saber quien contiene a quien."""
    import ast

    return [n for n in ast.walk(modulo) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _funcion_contenedora(funciones, objetivo) -> str | None:
    """Nombre de la funcion **mas interna** que contiene al nodo, o `None`.

    Se elige la mas interna por su rango de lineas: una funcion anidada tiene un
    rango estrictamente dentro de la que la contiene, y ese es el ambito real del
    `import`.
    """
    candidatas = [
        f
        for f in funciones
        if f.lineno <= objetivo.lineno <= (f.end_lineno or f.lineno)
    ]
    if not candidatas:
        return None
    return min(candidatas, key=lambda f: (f.end_lineno or f.lineno) - f.lineno).name


def test_interpret_es_el_unico_nodo_conectado_al_modelo() -> None:
    """La invariante de F3, comprobada sobre el **comportamiento**, no sobre el texto.

    Se ejecuta `interpret` sin gateway y se comprueba que sigue clasificando por
    vocabulario; y con un gateway falso, que usa el modelo y contabiliza el gasto.
    Una prueba estructural puede pasar con un nodo desconectado; esta no.
    """
    estado = _estado_interpret("corrige el bug del parser")
    from ai_swe.graph import nodes

    previo = nodes._GATEWAY
    try:
        # Sin modelo: clasificacion determinista, sin errores, sin gasto.
        nodes.usar_gateway(nodes.SIN_GATEWAY)
        delta = nodes.interpret(estado)
        assert delta["interpretation"].intent.value == "modify"
        assert "errors" not in delta
        assert "budget" not in delta

        # Con modelo que responde bien: lo usa y cobra.
        from ai_swe.models import FakeModelAdapter, ModelGateway

        fake = FakeModelAdapter(
            structured={
                "intent": "out_of_scope",
                "scope": {"repo_path": "/x", "allowed_paths": [], "protected_paths": []},
                "constraints": [],
                "confidence": 0.8,
                "rationale": "lo decide el modelo",
            }
        )
        nodes.usar_gateway(ModelGateway([fake]))
        delta = nodes.interpret(estado)
        assert delta["interpretation"].intent.value == "out_of_scope"
        assert delta["budget"].used_model_calls == 1
    finally:
        nodes.usar_gateway(previo)


def _estado_interpret(texto: str):
    from datetime import UTC, datetime

    from ai_swe.contracts import Instruction, InstructionSource, RunOptions, RunState

    ahora = datetime.now(UTC)
    return RunState(
        run_id="run-t",
        trace_id="trace-t",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text=texto, source=InstructionSource.TEXT, confirmed_by_user=True
        ),
        options=RunOptions(),
    )


def test_el_codigo_fuente_no_esta_excluido_por_gitignore() -> None:
    """Un `.gitignore` demasiado amplio excluye codigo fuente **en silencio**.

    Ocurrio de verdad: la regla `models/`, pensada para los pesos de STT
    descargados, coincide con **cualquier** directorio llamado `models` a cualquier
    profundidad -un patron sin barra inicial no significa «en la raiz», significa
    «en cualquier sitio»-. `src/ai_swe/models/` quedaba por tanto fuera del control
    de versiones: las pruebas pasaban, `git status` no avisaba, y el paquete del
    Model Gateway no se habria commiteado nunca. Se descubrio al notar que no
    aparecia como nuevo.

    Se comprueba con `git check-ignore`, que es la unica fuente de verdad sobre lo
    que git ignora. Si no hay repositorio, se omite en vez de fingir que comprobo.
    """
    import subprocess
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    if not (raiz / ".git").exists():
        pytest.skip("no hay repositorio git")

    archivos = sorted((raiz / "src").rglob("*.py"))
    assert archivos, "no se encontro codigo fuente que comprobar"

    resultado = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=raiz,
        input="\n".join(p.relative_to(raiz).as_posix() for p in archivos),
        capture_output=True,
        text=True,
        check=False,
    )
    ignorados = [linea for linea in resultado.stdout.splitlines() if linea.strip()]
    assert ignorados == [], f"codigo fuente excluido por .gitignore: {ignorados}"
