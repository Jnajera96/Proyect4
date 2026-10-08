"""Pruebas de F4: el Supervisor planifica (nodo `plan`), con fallback determinista.

**Que protege este fichero.** Que `plan` use el modelo **cuando se puede**, que
convierta su propuesta en un `RunPlan` validado, que la guarde en `RunState.plan`,
que contabilice el gasto, y que **sin modelo siga habiendo plan**: la suite offline
y el desarrollo local sin red tienen que seguir funcionando al 100%.

Ninguna prueba toca la red ni exige credenciales. El modelo se sustituye por
`FakeModelAdapter`.

**Lecciones de F3 aplicadas aqui.** Comprobar el valor en el punto donde se calcula
(no un acumulado que puede ser 0 por dos motivos distintos), y hacer que cada
comprobacion **alcance** la linea que dice proteger: en F3 tres mutaciones no se
cazaban porque nadie llegaba al codigo mutado.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai_swe.contracts import (
    Budget,
    Instruction,
    InstructionSource,
    Intent,
    RunOptions,
    RunState,
    Scope,
    TaskInterpretation,
)
from ai_swe.graph import nodes
from ai_swe.models import FakeModelAdapter, ModelGateway

# --------------------------------------------------------------- utilidades


def interpretacion(intent: Intent = Intent.MODIFY) -> TaskInterpretation:
    return TaskInterpretation(
        intent=intent,
        scope=Scope(repo_path="/repo/autorizado"),
        constraints=["no tocar produccion"],
        confidence=0.9,
        rationale="la instruccion pide un cambio",
    )


def estado(
    texto: str = "arregla el parser",
    *,
    intencion: Intent = Intent.MODIFY,
    max_review_cycles: int = 2,
    **opciones,
) -> RunState:
    ahora = datetime.now(UTC)
    return RunState(
        run_id="run-f4",
        trace_id="trace-f4",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text=texto, source=InstructionSource.TEXT, confirmed_by_user=True
        ),
        options=RunOptions(repo_path="/repo/autorizado", **opciones),
        interpretation=interpretacion(intencion),
        budget=Budget(max_review_cycles=max_review_cycles),
    )


def plan_valido(**cambios) -> dict:
    """El plan que un modelo bien portado devolveria."""
    base = {
        "subtasks": [
            {
                "id": "leer_codigo",
                "description": "Leer el modulo afectado.",
                "agent": "researcher",
                "depends_on": [],
                "allowed_tools": ["read_file", "search_text"],
                "done_criteria": "Se ha citado el archivo y la linea relevante.",
            },
            {
                "id": "aplicar_parche",
                "description": "Aplicar el parche propuesto.",
                "agent": "coder",
                "depends_on": ["leer_codigo"],
                "allowed_tools": ["read_file", "write_file"],
                "done_criteria": "El diff aplica y es revisable.",
            },
        ],
        "max_review_cycles": 2,
        "rationale": "plan propuesto por el modelo",
    }
    base.update(cambios)
    return base


@pytest.fixture(autouse=True)
def _restaurar_gateway():
    """Deja el gateway como estaba aunque la prueba falle a mitad."""
    previo = nodes._GATEWAY
    yield
    nodes.usar_gateway(previo)


# ------------------------------------------- 1. sin modelo: el fallback manda


def test_sin_gateway_plan_produce_un_plan_determinista() -> None:
    """La garantia que no debe romperse: **siempre hay plan**, aunque no haya modelo."""
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    delta = nodes.plan(estado())

    assert delta["plan"] is not None
    assert delta["plan"].subtasks, "un plan sin subtareas no planifica nada"
    assert "budget" not in delta
    assert "errors" not in delta


def test_el_fallback_encadena_investigacion_y_cambio_para_modify() -> None:
    """Para `modify`, el plan de respaldo investiga **y luego** aplica.

    El orden importa y la dependencia tambien: aplicar cambios sin la evidencia de
    la investigacion seria planificar una escritura a ciegas.
    """
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    delta = nodes.plan(estado(intencion=Intent.MODIFY))
    subtareas = delta["plan"].subtasks

    assert [s.id for s in subtareas] == ["investigar", "aplicar_cambios"]
    assert subtareas[0].agent.value == "researcher"
    assert subtareas[1].agent.value == "coder"
    assert subtareas[1].depends_on == ["investigar"]


@pytest.mark.parametrize("intencion", [Intent.QUESTION, Intent.INSPECT])
def test_el_fallback_no_planifica_escrituras_para_lectura(intencion: Intent) -> None:
    """Una pregunta o una inspeccion **no** deben generar una subtarea de escritura.

    Planificar un cambio cuando el usuario solo pregunto seria un plan que no
    corresponde a la peticion, y ademas llevaria la ejecucion hacia el Coder.
    """
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    delta = nodes.plan(estado(intencion=intencion))

    agentes = {s.agent.value for s in delta["plan"].subtasks}
    assert agentes == {"researcher"}, f"un plan de lectura no puede incluir {agentes}"


def test_el_plan_de_respaldo_es_valido_contra_su_propio_contrato() -> None:
    """El fallback no puede ser un plan que el contrato rechazaria.

    Un plan de respaldo invalido seria peor que no tenerlo: reventaria justo en el
    camino que existe para que el sistema no se caiga.
    """
    from ai_swe.contracts import RunPlan

    nodes.usar_gateway(nodes.SIN_GATEWAY)
    delta = nodes.plan(estado())

    revalidado = RunPlan.model_validate(delta["plan"].model_dump())
    assert revalidado.model_dump() == delta["plan"].model_dump()


def test_las_herramientas_del_fallback_pertenecen_al_rol() -> None:
    """La asignacion efectiva es la **interseccion** con las del rol.

    Un plan que declare una herramienta que el rol no tiene promete algo que no se
    puede ejecutar: el plan quedaria mintiendo aunque fuese sintacticamente valido.
    """
    from ai_swe.tools.registry import tools_for

    nodes.usar_gateway(nodes.SIN_GATEWAY)
    delta = nodes.plan(estado())

    for subtarea in delta["plan"].subtasks:
        permitidas = tools_for(subtarea.agent)
        fuera = set(subtarea.allowed_tools) - permitidas
        assert not fuera, f"la subtarea '{subtarea.id}' declara herramientas ajenas a su rol: {fuera}"


# ------------------------------------------------- 2. con modelo: el plan suyo


def test_con_modelo_el_plan_es_el_del_modelo() -> None:
    """Si el modelo responde y cumple el contrato, su plan es el que se guarda."""
    fake = FakeModelAdapter(structured=plan_valido())
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.plan(estado())

    assert [s.id for s in delta["plan"].subtasks] == ["leer_codigo", "aplicar_parche"]
    assert delta["plan"].rationale == "plan propuesto por el modelo"


def test_el_prompt_lleva_la_interpretacion_y_la_peticion() -> None:
    """Planificar sin la interpretacion ni la peticion seria planificar el vacio."""
    fake = FakeModelAdapter(structured=plan_valido())
    nodes.usar_gateway(ModelGateway([fake]))
    nodes.plan(estado("refactoriza el cliente http"))

    assert len(fake.calls) == 1
    enviado = "\n".join(m.content for m in fake.calls[0].messages)
    assert "refactoriza el cliente http" in enviado
    assert "modify" in enviado  # la intencion de F3 viaja al prompt
    # El esquema se deriva del contrato `RunPlan`, no se escribe a mano.
    assert fake.calls[0].json_schema is not None
    assert "subtasks" in fake.calls[0].json_schema.get("properties", {})


def test_el_esquema_enviado_es_el_de_runplan() -> None:
    """El contrato que se pide es `RunPlan`, derivado del tipo."""
    from ai_swe.contracts import RunPlan

    fake = FakeModelAdapter(structured=plan_valido())
    nodes.usar_gateway(ModelGateway([fake]))
    nodes.plan(estado())

    enviado = fake.calls[0].json_schema
    assert set(enviado["properties"]) == set(RunPlan.model_json_schema()["properties"])


def test_el_plan_se_inyecta_en_el_estado() -> None:
    """El requisito literal de F4: el plan va a `RunState.plan`."""
    fake = FakeModelAdapter(structured=plan_valido())
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.plan(estado())

    assert "plan" in delta
    # Y el estado acepta el plan: se construye un RunState real con el delta.
    base = estado()
    fusionado = base.model_copy(update={"plan": delta["plan"]})
    assert fusionado.plan is not None
    assert fusionado.subtask("leer_codigo") is not None


# --------------------------------- 3. el contrato acota el plan del modelo


def test_un_plan_con_ciclo_de_dependencias_no_pasa() -> None:
    """**La salvaguarda central.** Un ciclo es un bucle infinito disfrazado.

    El contrato `RunPlan` aplica un DFS y lo rechaza. Si el modelo propone un ciclo,
    no cruza: la ejecucion cae al fallback con plan valido en lugar de quedarse
    colgada esperando a que dos subtareas se completen mutuamente.
    """
    ciclico = plan_valido(
        subtasks=[
            {
                "id": "a",
                "description": "a",
                "agent": "researcher",
                "depends_on": ["b"],
                "allowed_tools": ["read_file"],
                "done_criteria": "ok",
            },
            {
                "id": "b",
                "description": "b",
                "agent": "coder",
                "depends_on": ["a"],
                "allowed_tools": ["write_file"],
                "done_criteria": "ok",
            },
        ]
    )
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=ciclico)]))
    delta = nodes.plan(estado())

    assert delta["errors"][0].error_class == "MODEL_FALLBACK"
    assert [s.id for s in delta["plan"].subtasks] == ["investigar", "aplicar_cambios"]


def test_una_subtarea_que_depende_de_si_misma_no_pasa() -> None:
    """Autodependencia: el caso mas simple de ciclo."""
    bucle = plan_valido(
        subtasks=[
            {
                "id": "a",
                "description": "a",
                "agent": "researcher",
                "depends_on": ["a"],
                "allowed_tools": ["read_file"],
                "done_criteria": "ok",
            }
        ]
    )
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=bucle)]))
    delta = nodes.plan(estado())

    assert delta["errors"][0].error_class == "MODEL_FALLBACK"


def test_una_dependencia_inexistente_no_pasa() -> None:
    """Depender de una subtarea que no existe es un plan que no se puede ordenar."""
    roto = plan_valido(
        subtasks=[
            {
                "id": "a",
                "description": "a",
                "agent": "researcher",
                "depends_on": ["fantasma"],
                "allowed_tools": ["read_file"],
                "done_criteria": "ok",
            }
        ]
    )
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=roto)]))
    delta = nodes.plan(estado())

    assert delta["errors"][0].error_class == "MODEL_FALLBACK"


def test_un_plan_demasiado_largo_no_pasa() -> None:
    """El contrato acota a 32 subtareas: un plan infinito no cabe."""
    larguisimo = plan_valido(
        subtasks=[
            {
                "id": f"t{i}",
                "description": f"tarea {i}",
                "agent": "researcher",
                "depends_on": [],
                "allowed_tools": ["read_file"],
                "done_criteria": "ok",
            }
            for i in range(33)
        ]
    )
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=larguisimo)]))
    delta = nodes.plan(estado())

    assert delta["errors"][0].error_class == "MODEL_FALLBACK"


def test_ids_duplicados_no_pasan() -> None:
    """Dos subtareas con el mismo id hacen ambiguo el grafo de dependencias."""
    duplicado = plan_valido(
        subtasks=[
            {
                "id": "misma",
                "description": "una",
                "agent": "researcher",
                "depends_on": [],
                "allowed_tools": ["read_file"],
                "done_criteria": "ok",
            },
            {
                "id": "misma",
                "description": "otra",
                "agent": "coder",
                "depends_on": [],
                "allowed_tools": ["write_file"],
                "done_criteria": "ok",
            },
        ]
    )
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=duplicado)]))
    delta = nodes.plan(estado())

    assert delta["errors"][0].error_class == "MODEL_FALLBACK"


def test_una_subtarea_asignada_al_supervisor_no_pasa() -> None:
    """El Supervisor coordina, no ejecuta: el contrato lo prohibe explicitamente."""
    al_supervisor = plan_valido(
        subtasks=[
            {
                "id": "coordinar",
                "description": "coordinar",
                "agent": "supervisor",
                "depends_on": [],
                "allowed_tools": ["read_file"],
                "done_criteria": "ok",
            }
        ]
    )
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=al_supervisor)]))
    delta = nodes.plan(estado())

    assert delta["errors"][0].error_class == "MODEL_FALLBACK"


def test_una_subtarea_sin_herramientas_no_pasa() -> None:
    """`allowed_tools` vacio no ejecuta nada, y el contrato lo rechaza."""
    sin_tools = plan_valido(
        subtasks=[
            {
                "id": "a",
                "description": "a",
                "agent": "researcher",
                "depends_on": [],
                "allowed_tools": [],
                "done_criteria": "ok",
            }
        ]
    )
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=sin_tools)]))
    delta = nodes.plan(estado())

    assert delta["errors"][0].error_class == "MODEL_FALLBACK"


def test_una_respuesta_que_no_es_json_cae_al_fallback() -> None:
    """Texto plano no es un plan."""
    nodes.usar_gateway(
        ModelGateway([FakeModelAdapter(content="lo siento, no puedo planificar eso")])
    )
    delta = nodes.plan(estado())

    assert delta["errors"][0].error_class == "MODEL_FALLBACK"
    assert delta["plan"].subtasks


def test_el_nodo_revalida_aunque_el_gateway_ya_haya_validado() -> None:
    """Defensa en profundidad, igual que en F3.

    Se inyecta un gateway que **no** valida y devuelve datos crudos para comprobar
    que el nodo los rechaza por su cuenta en lugar de confiar en el de arriba.
    """
    from ai_swe.models import ModelResponse, ModelUsage

    class GatewayQueNoValida:
        requested_provider = "permisivo"

        def generate_structured(self, request, *, response_model, budget=None):
            return ModelResponse(
                content="{}",
                structured_data=plan_valido(
                    subtasks=[
                        {
                            "id": "a",
                            "description": "a",
                            "agent": "researcher",
                            "depends_on": ["a"],  # autodependencia: invalido
                            "allowed_tools": ["read_file"],
                            "done_criteria": "ok",
                        }
                    ]
                ),
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
    delta = nodes.plan(estado())

    assert delta["errors"][0].error_class == "MODEL_FALLBACK"
    assert delta["plan"].subtasks, "debe quedar un plan valido del fallback"


# ------------------------------------------- 4. presupuesto y trazabilidad


def test_una_planificacion_se_contabiliza() -> None:
    """`RNF-C1`: planificar es una llamada al modelo y tiene que contar."""
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=plan_valido())]))
    delta = nodes.plan(estado())

    assert delta["budget"].used_model_calls == 1
    assert delta["budget"].used_tokens > 0


def test_el_presupuesto_devuelto_es_uno_nuevo() -> None:
    """No se muta el presupuesto de entrada."""
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=plan_valido())]))
    original = estado()
    original_calls = original.budget.used_model_calls

    delta = nodes.plan(original)

    assert original.budget.used_model_calls == original_calls
    assert delta["budget"].used_model_calls == 1


def test_el_plan_se_acota_al_presupuesto_de_ciclos() -> None:
    """**Hallazgo de F4.** `RunPlan` permite hasta 5 ciclos; el presupuesto manda.

    Un plan que pidiera 5 ciclos cuando el presupuesto declara 2 prometeria trabajo
    que el sistema no va a poder pagar: el bucle de revision se cortaria antes y el
    plan quedaria mintiendo. Se comprueba el **valor** acotado y que el recorte se
    declara en el rationale.
    """
    pide_cinco = plan_valido(max_review_cycles=5)
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=pide_cinco)]))
    delta = nodes.plan(estado(max_review_cycles=2))

    assert delta["plan"].max_review_cycles == 2
    assert "acotado" in delta["plan"].rationale


def test_un_plan_dentro_del_presupuesto_no_se_toca() -> None:
    """El recorte solo actua cuando hace falta; si no, el plan queda intacto."""
    pide_uno = plan_valido(max_review_cycles=1)
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=pide_uno)]))
    delta = nodes.plan(estado(max_review_cycles=3))

    assert delta["plan"].max_review_cycles == 1
    assert "acotado" not in delta["plan"].rationale


def test_sin_tokens_reportados_no_se_inventan_tokens() -> None:
    """`None` no es `0`: la llamada cuenta, los tokens no se inventan."""
    from ai_swe.models import ModelUsage

    nodes.usar_gateway(
        ModelGateway(
            [
                FakeModelAdapter(
                    structured=plan_valido(),
                    usage=ModelUsage(input_tokens=None, output_tokens=None),
                )
            ]
        )
    )
    delta = nodes.plan(estado())

    assert delta["budget"].used_model_calls == 1
    assert delta["budget"].used_tokens == 0


# ---------------------------------------- 5. fallos del proveedor


@pytest.mark.parametrize(
    "fallo",
    ["timeout", "rate_limit", "unavailable", "auth_error", "invalid_response"],
)
def test_cualquier_fallo_del_proveedor_deja_un_plan_valido(fallo: str) -> None:
    """**La regla inquebrantable.** El sistema nunca se queda sin plan."""
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(fault=fallo)], max_retries=0))
    delta = nodes.plan(estado())

    assert delta["plan"].subtasks
    assert delta["errors"][0].error_class == "MODEL_FALLBACK"
    assert delta["errors"][0].recoverable is True
    assert delta["status"].value == "running"


def test_el_fallo_deja_el_motivo_escrito() -> None:
    """Un fallback declarado, nunca silencioso."""
    nodes.usar_gateway(
        ModelGateway([FakeModelAdapter(fault="auth_error")], max_retries=0)
    )
    delta = nodes.plan(estado())

    error = delta["errors"][0]
    assert "plan determinista de respaldo" in error.message
    assert "ModelAuthenticationError" in error.message
    assert "determinista" in delta["plan"].rationale


def test_un_error_de_programacion_no_se_traga() -> None:
    """Un defecto propio no se convierte en fallback silencioso."""

    class GatewayRoto:
        requested_provider = "roto"

        def generate_structured(self, request, *, response_model, budget=None):
            raise TypeError("defecto del codigo propio, no del modelo")

        def consume(self, budget, response):  # pragma: no cover
            return budget

    nodes.usar_gateway(GatewayRoto())
    with pytest.raises(TypeError):
        nodes.plan(estado())


def test_el_error_de_fallback_no_filtra_la_credencial() -> None:
    """`RNF-S3` en el camino nuevo: una credencial no llega al estado persistido."""
    from ai_swe.models import ModelGatewayError
    from ai_swe.security import clear_registered_secrets, register_secret

    clear_registered_secrets()
    secreto = "clave-de-planificacion-1a2b3c4d5e6f"
    register_secret(secreto)

    class GatewayQueFiltra:
        requested_provider = "fugador"

        def generate_structured(self, request, *, response_model, budget=None):
            raise ModelGatewayError(f"401 unauthorized: key={secreto}")

        def consume(self, budget, response):  # pragma: no cover
            return budget

    nodes.usar_gateway(GatewayQueFiltra())
    delta = nodes.plan(estado())
    clear_registered_secrets()

    assert secreto not in delta["errors"][0].message
    assert "[REDACTED]" in delta["errors"][0].message


# --------------------------------------------- 6. enrutado de la topologia


def test_una_instruccion_fuera_de_alcance_no_se_planifica() -> None:
    """Planificar lo que el sistema ya sabe que no hara no tiene sentido."""
    delta = estado(intencion=Intent.OUT_OF_SCOPE)
    assert nodes.route_after_interpret(delta) == "explain_limits"


@pytest.mark.parametrize(
    "intencion", [Intent.QUESTION, Intent.INSPECT, Intent.MODIFY]
)
def test_una_instruccion_planificable_va_al_nodo_de_plan(intencion: Intent) -> None:
    """Todo lo que tiene accion posible pasa por el plan antes de trabajar."""
    assert nodes.route_after_interpret(estado(intencion=intencion)) == "plan"


def test_tras_planificar_se_empieza_por_la_primera_subtarea() -> None:
    """El enrutado sigue al plan, no a una suposicion fija."""
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    delta = nodes.plan(estado())
    con_plan = estado().model_copy(update={"plan": delta["plan"]})

    assert nodes.route_after_plan(con_plan) == "researcher"


def test_sin_plan_el_enrutado_cae_al_comienzo_seguro() -> None:
    """Sin plan no deberia llegarse, pero una caida a `researcher` es segura."""
    assert nodes.route_after_plan(estado()) == "researcher"
