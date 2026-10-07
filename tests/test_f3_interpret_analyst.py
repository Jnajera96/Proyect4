"""Pruebas de F3: el Requirements Analyst, unico nodo conectado al modelo.

**Que protege este fichero.** Que `interpret` use el modelo **cuando se puede**,
que **no lo use** cuando no se puede (sin credencial, proveedor caido, respuesta
invalida), y que ninguna de las dos vias rompa la garantia que ya existia antes de
M2: la suite offline tiene que seguir clasificando bien sin red y sin proveedor.

Ninguna prueba de aqui toca la red ni exige credenciales. El modelo se sustituye
por `FakeModelAdapter`, que ademas sabe provocar a voluntad los fallos que hay que
manejar. Una prueba que necesitara un proveedor real no podria ser parte de la
verificacion continua, y por tanto no protegeria nada.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai_swe.contracts import Instruction, InstructionSource, RunOptions, RunState
from ai_swe.graph import nodes
from ai_swe.models import FakeModelAdapter, ModelGateway, ModelPricing, PricingTable

# --------------------------------------------------------------- utilidades


def estado(texto: str, *, repo: str | None = None, **opciones) -> RunState:
    ahora = datetime.now(UTC)
    return RunState(
        run_id="run-f3",
        trace_id="trace-f3",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text=texto, source=InstructionSource.TEXT, confirmed_by_user=True
        ),
        options=RunOptions(repo_path=repo, **opciones),
    )


def json_valido(**cambios) -> dict:
    """El objeto que un modelo bien portado devolveria."""
    base = {
        "intent": "modify",
        "scope": {"repo_path": "/del-modelo", "allowed_paths": [], "protected_paths": []},
        "constraints": ["no toques produccion"],
        "confidence": 0.9,
        "rationale": "la instruccion pide un cambio concreto",
    }
    base.update(cambios)
    return base


@pytest.fixture(autouse=True)
def _restaurar_gateway():
    """Deja el gateway del nodo como estaba, pase lo que pase en la prueba.

    Sin esto, una prueba que fallara a mitad dejaria `interpret` apuntando a un
    fake y contaminaria las siguientes. Es el mismo peligro que llevo a no usar una
    variable global de entorno.
    """
    previo = nodes._GATEWAY
    yield
    nodes.usar_gateway(previo)


# ------------------------------------------------- 1. sin modelo: el fallback


def test_sin_gateway_interpret_sigue_clasificando_por_vocabulario() -> None:
    """La garantia de `M1`/`F2` que **no debe romperse** en F3.

    Sin modelo conectado, `interpret` debe comportarse exactamente como antes:
    clasificar por vocabulario y no tocar el presupuesto ni los errores.
    """
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    delta = nodes.interpret(estado("corrige el bug del parser"))

    assert delta["interpretation"].intent.value == "modify"
    assert delta["next_step"] == "modify"
    # Sin modelo no hay gasto ni error: el delta debe ser el de siempre.
    assert "budget" not in delta
    assert "errors" not in delta


@pytest.mark.parametrize(
    ("instruccion", "esperada"),
    [
        ("sube los cambios a github", "out_of_scope"),
        ("despliega esto en produccion", "out_of_scope"),
        ("arregla el fallo de parseo", "modify"),
        ("¿que hace el modulo de politicas?", "question"),
        ("analiza la estructura del repositorio", "inspect"),
    ],
)
def test_el_fallback_mantiene_la_clasificacion_de_siempre(
    instruccion: str, esperada: str
) -> None:
    """El fallback no es un camino degradado: clasifica igual que en M1."""
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    delta = nodes.interpret(estado(instruccion))
    assert delta["interpretation"].intent.value == esperada


# ------------------------------------------------------ 2. con modelo: lo usa


def test_con_modelo_usa_su_clasificacion() -> None:
    """Si el modelo responde y cumple el contrato, su veredicto es el que vale."""
    fake = FakeModelAdapter(structured=json_valido(intent="question", confidence=0.77))
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.interpret(estado("arregla el parser"))

    assert delta["interpretation"].intent.value == "question"
    assert delta["interpretation"].confidence == pytest.approx(0.77)
    assert delta["next_step"] == "question"


def test_el_prompt_lleva_la_instruccion_del_usuario() -> None:
    """Un prompt que no incluyera la instruccion clasificaria el vacio."""
    fake = FakeModelAdapter(structured=json_valido())
    nodes.usar_gateway(ModelGateway([fake]))
    nodes.interpret(estado("refactoriza el cliente http"))

    assert len(fake.calls) == 1
    enviados = "\n".join(m.content for m in fake.calls[0].messages)
    assert "refactoriza el cliente http" in enviados
    # El esquema se deriva del contrato, no se escribe a mano: debe ir en la peticion.
    assert fake.calls[0].json_schema is not None
    assert "intent" in fake.calls[0].json_schema.get("properties", {})


def test_el_modelo_usa_la_herramienta_de_salida_estructurada() -> None:
    """El contrato que se envia es el de `TaskInterpretation`, derivado del tipo.

    Si el nodo pidiera `generate` en lugar de `generate_structured`, el modelo
    podria devolver cualquier cosa y nadie la validaria. Se comprueba observando
    que la peticion lleva `json_schema`, que solo `_preparar_peticion` anade.
    """
    from ai_swe.contracts import TaskInterpretation

    fake = FakeModelAdapter(structured=json_valido())
    gateway = ModelGateway([fake])
    nodes.usar_gateway(gateway)
    nodes.interpret(estado("arregla el parser"))

    esquema_enviado = fake.calls[0].json_schema
    assert esquema_enviado is not None
    assert set(esquema_enviado["properties"]) == set(
        TaskInterpretation.model_json_schema()["properties"]
    )


# --------------------------------------------- 3. el contrato no se relaja


def test_una_respuesta_que_no_cumple_el_contrato_cae_al_fallback() -> None:
    """**El contrato Pydantic es la puerta absoluta.** Un JSON que no valida no pasa.

    El fake devuelve un texto que no es JSON. El gateway lanza
    `StructuredOutputError`; `interpret` lo trata como fallo esperado y cae al
    fallback, declarandolo. Lo que **no** puede ocurrir es que el nodo siga
    adelante con una interpretacion construida a medias.
    """
    fake = FakeModelAdapter(content="esto no es JSON, lo siento")
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.interpret(estado("arregla el parser"))

    assert delta["interpretation"].intent.value == "modify"  # clasificado por vocabulario
    assert len(delta["errors"]) == 1
    assert delta["errors"][0].error_class == "MODEL_FALLBACK"


def test_un_json_que_viola_las_restricciones_del_contrato_no_pasa() -> None:
    """`confidence` esta acotada a [0,1]; un 5.0 no puede cruzar la frontera."""
    fake = FakeModelAdapter(structured=json_valido(confidence=5.0))
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.interpret(estado("arregla el parser"))

    assert delta["errors"][0].error_class == "MODEL_FALLBACK"
    # Y la confianza que queda es la del fallback, no la invalida.
    assert delta["interpretation"].confidence == pytest.approx(0.5)


def test_el_nodo_revalida_aunque_el_gateway_ya_haya_validado() -> None:
    """Defensa en profundidad: el nodo **no confia** en que el gateway valido.

    **Hallazgo de la verificacion por mutacion.** La mutacion que sustituia
    `TaskInterpretation.model_validate(datos)` por `model_construct(datos)` -que
    **se salta toda la validacion**- no se cazaba con las pruebas anteriores. La
    razon no era que la linea sobrara, sino que **nadie la alcanzaba con un dato
    invalido**: el gateway valida antes y lanza `StructuredOutputError`, asi que
    el dato corrupto nunca llegaba hasta aqui.

    Eso deja la linea sin proteger: si un dia el gateway cambiara (o alguien
    inyectara otro gateway), el nodo pasaria a aceptar un objeto sin validar y
    ninguna prueba lo notaria. Se simula exactamente ese escenario con un gateway
    que **devuelve datos crudos sin validar**, y se comprueba que el nodo los
    rechaza por su cuenta.
    """
    from ai_swe.models import ModelResponse, ModelUsage

    class GatewayQueNoValida:
        """Devuelve `structured_data` crudo, como si no hubiera validado nada."""

        requested_provider = "permisivo"

        def generate_structured(self, request, *, response_model, budget=None):
            return ModelResponse(
                content="{}",
                structured_data=json_valido(confidence=5.0),  # fuera de [0,1]
                provider="permisivo",
                provider_requested="permisivo",
                model="m",
                finish_reason="stop",
                usage=ModelUsage(input_tokens=1, output_tokens=1),
                latency_ms=1.0,
            )

        def consume(self, budget, response):
            return budget

    nodes.usar_gateway(GatewayQueNoValida())
    delta = nodes.interpret(estado("arregla el parser"))

    # El nodo detecta el dato invalido y cae al fallback, en vez de aceptarlo.
    assert delta["errors"][0].error_class == "MODEL_FALLBACK"
    assert delta["interpretation"].confidence == pytest.approx(0.5)


def test_un_campo_obligatorio_ausente_no_pasa() -> None:
    """Sin `rationale` no hay interpretacion valida: es un campo obligatorio."""
    incompleto = json_valido()
    del incompleto["rationale"]
    fake = FakeModelAdapter(structured=incompleto)
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.interpret(estado("arregla el parser"))

    assert delta["errors"][0].error_class == "MODEL_FALLBACK"


# -------------------------------------------- 4. el alcance lo fija el usuario


def test_el_modelo_no_puede_ampliar_el_alcance_autorizado() -> None:
    """**Restriccion de seguridad.** El alcance es del usuario, no del modelo.

    Un modelo al que se le pregunta por su alcance puede devolver el que quiera.
    Si ese valor llegara al estado, un prompt malicioso ampliaria las rutas que el
    sistema considera autorizadas. El alcance se sobrescribe con el del usuario.
    """
    fake = FakeModelAdapter(
        structured=json_valido(
            scope={
                "repo_path": "/otro/repo/no-autorizado",
                "allowed_paths": ["/", "/etc"],
                "protected_paths": [],
            }
        )
    )
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.interpret(
        estado("arregla el parser", repo="/repo/autorizado", allowed_paths=["src"])
    )

    alcance = delta["interpretation"].scope
    assert alcance.repo_path == "/repo/autorizado"
    assert alcance.allowed_paths == ["src"]


# ------------------------------------------------ 5. gasto del presupuesto


def test_una_llamada_al_modelo_se_contabiliza() -> None:
    """`RNF-C1`: el gasto tiene que quedar en el estado, no perderse."""
    fake = FakeModelAdapter(structured=json_valido())
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.interpret(estado("arregla el parser"))

    assert delta["budget"].used_model_calls == 1
    assert delta["budget"].used_tokens > 0


def test_el_presupuesto_devuelto_es_uno_nuevo() -> None:
    """No se muta el presupuesto de entrada: se devuelve uno nuevo.

    Es la misma disciplina que ya usaban los nodos. Si se mutara el estado de
    entrada, dos ejecuciones concurrentes se pisarian y la reanudacion tras un
    corte arrancaria con contadores ya gastados.
    """
    fake = FakeModelAdapter(structured=json_valido())
    nodes.usar_gateway(ModelGateway([fake]))
    original = estado("arregla el parser").budget

    delta = nodes.interpret(estado("arregla el parser"))

    assert original.used_model_calls == 0  # el de entrada no se toco
    assert delta["budget"].used_model_calls == 1


def test_sin_tokens_reportados_no_se_inventan_tokens() -> None:
    """`None` no es `0`. Un proveedor que no reporta tokens no consume tokens.

    Fingir un cero seria afirmar que no se gasto nada; sumarlo como cero falsearia
    el acumulado. La llamada si cuenta, porque es lo que evita el bucle infinito.
    """
    from ai_swe.models import ModelUsage

    fake = FakeModelAdapter(
        structured=json_valido(), usage=ModelUsage(input_tokens=None, output_tokens=None)
    )
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.interpret(estado("arregla el parser"))

    assert delta["budget"].used_model_calls == 1
    assert delta["budget"].used_tokens == 0


def test_sin_tarifa_declarada_el_coste_no_se_suma_y_sigue_siendo_desconocido() -> None:
    """Sin precio conocido el coste **no se suma**; nunca se asume 0.0.

    **Por que esta prueba no mira `used_cost` a secas.** La primera version
    afirmaba `used_cost == 0.0`, y eso era cierto **tanto si el coste valia `None`
    como si el gateway hubiera devuelto `0.0`**: `consume` solo suma cuando
    `cost is not None`, asi que ambos casos dan 0.0 acumulado. La asercion pasaba
    con el defecto dentro y la mutacion «la tabla devuelve 0.0» no se cazaba.
    Comprobar un acumulado no distingue «no se sumo» de «se sumo cero».

    Lo que **si** distingue los dos casos es mirar la tabla en el punto donde se
    calcula: `PricingTable.cost` debe devolver `None`, no `0.0`. `None` significa
    «no se sabe» y obliga a mirar; `0.0` afirmaria que la llamada fue gratis.
    """
    from ai_swe.models.contracts import ModelUsage

    tabla = PricingTable()  # sin entradas
    uso = ModelUsage(input_tokens=1000, output_tokens=1000)
    assert tabla.cost("fake-model", uso) is None, (
        "sin tarifa, el coste debe ser None (desconocido), no un cero con apariencia de dato"
    )

    # Y en el nodo, el resultado sigue siendo el de siempre: no se suma nada.
    fake = FakeModelAdapter(structured=json_valido())
    nodes.usar_gateway(ModelGateway([fake], pricing=tabla))
    delta = nodes.interpret(estado("arregla el parser"))
    assert delta["budget"].used_cost == 0.0


def test_con_tarifa_declarada_el_coste_se_calcula() -> None:
    """Con tarifa **y** tokens, el coste se calcula y se suma.

    Los valores de la tarifa son inventados a proposito para que la aritmetica sea
    verificable: lo que se comprueba es la formula, no que ninguna tarifa real sea
    la vigente.
    """
    from ai_swe.models import ModelUsage

    tabla = PricingTable()
    tabla.add("fake-model", ModelPricing(input_per_1k=1.0, output_per_1k=2.0))
    fake = FakeModelAdapter(
        structured=json_valido(), usage=ModelUsage(input_tokens=1000, output_tokens=500)
    )
    nodes.usar_gateway(ModelGateway([fake], pricing=tabla))
    delta = nodes.interpret(estado("arregla el parser"))

    # 1000/1000*1.0 + 500/1000*2.0 = 1.0 + 1.0 = 2.0
    assert delta["budget"].used_cost == pytest.approx(2.0)


# ------------------------------------- 6. fallos del proveedor: al fallback


@pytest.mark.parametrize(
    "fallo",
    ["timeout", "rate_limit", "unavailable", "auth_error", "invalid_response"],
)
def test_cualquier_fallo_del_proveedor_cae_al_fallback(fallo: str) -> None:
    """**La regla critica de F3.** Con el proveedor caido, el sistema sigue.

    Los cinco modos de fallo que el fake sabe provocar deben terminar en una
    clasificacion determinista, no en una excepcion que aborte la ejecucion.
    """
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(fault=fallo)], max_retries=0))
    delta = nodes.interpret(estado("sube esto a github"))

    assert delta["interpretation"].intent.value == "out_of_scope"
    assert delta["errors"][0].error_class == "MODEL_FALLBACK"
    assert delta["status"].value == "running"


def test_el_fallo_deja_el_motivo_escrito() -> None:
    """Un fallback que no se declara es indistinguible de un acierto.

    Si el motivo no quedara escrito, nadie podria saber que el modelo no llego a
    usarse, y una demo que funcionase «por el fallback» pareceria funcionar por el
    modelo.
    """
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(fault="auth_error")], max_retries=0))
    delta = nodes.interpret(estado("arregla el parser"))

    error = delta["errors"][0]
    assert error.recoverable is True
    assert "modelo no se pudo usar" in error.message
    # El motivo nombra el tipo de fallo: un mensaje generico no ayuda a nadie.
    assert "ModelAuthenticationError" in error.message
    # Y la propia interpretacion declara su origen.
    assert "determinista" in delta["interpretation"].rationale


def test_el_error_de_fallback_no_filtra_la_credencial() -> None:
    """`RNF-S3`: si el fallo mencionara la clave, quedaria en el estado persistido.

    El adapter real registra su credencial en el redactor central. Aqui se comprueba
    que un valor que la mencione **no llega** al mensaje del error que se guarda.
    """
    from ai_swe.security import clear_registered_secrets, register_secret

    clear_registered_secrets()
    secreto = "clave-realista-para-esta-prueba-9f8e7d6c"
    register_secret(secreto)

    class AdapterQueFiltra:
        name = "fugador"
        model = "m"

        def generate(self, request):
            from ai_swe.models import ModelAuthenticationError

            raise ModelAuthenticationError(f"401 unauthorized: key={secreto}")

    class GatewayQueEnvuelve:
        requested_provider = "fugador"

        def generate_structured(self, request, *, response_model, budget=None):
            raise __import__("ai_swe.models", fromlist=["ModelGatewayError"]).ModelGatewayError(
                f"fallo con credencial {secreto}"
            )

        def consume(self, budget, response):  # pragma: no cover - no se alcanza
            return budget

    nodes.usar_gateway(GatewayQueEnvuelve())
    delta = nodes.interpret(estado("arregla el parser"))
    clear_registered_secrets()

    assert secreto not in delta["errors"][0].message
    assert "[REDACTED]" in delta["errors"][0].message


def test_un_error_de_programacion_no_se_traga() -> None:
    """Un `TypeError` propio es un defecto, no un fallo del modelo.

    Si la frontera capturase `Exception` a secas, un defecto de programacion se
    convertiria en un fallback silencioso que nunca se depuraria.
    """

    class GatewayRoto:
        requested_provider = "roto"

        def generate_structured(self, request, *, response_model, budget=None):
            raise TypeError("esto es un defecto del codigo propio, no del modelo")

        def consume(self, budget, response):  # pragma: no cover
            return budget

    nodes.usar_gateway(GatewayRoto())
    with pytest.raises(TypeError):
        nodes.interpret(estado("arregla el parser"))


# ----------------------------------------------- 7. sin credenciales reales


def test_sin_credencial_configurada_interpret_no_intenta_llamar() -> None:
    """El caso mas probable en una demo: no hay clave.

    `interpret` no debe intentar siquiera construir el cliente; debe clasificar por
    vocabulario de inmediato. Se comprueba con `SIN_GATEWAY`, que es exactamente lo
    que deja el sistema cuando no hay proveedor usable.
    """
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    delta = nodes.interpret(estado("¿que hace el policy engine?"))
    assert delta["interpretation"].intent.value == "question"
    assert "errors" not in delta
    assert "budget" not in delta
