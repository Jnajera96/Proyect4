"""Nodos del grafo de orquestacion.

En la fase M1 los nodos son **deterministas y sin modelo**. Eso no significa que
sean simulados: el Researcher enumera el repositorio de verdad, el Policy Engine
decide de verdad, y el registro de eventos es real. Lo que falta es el
razonamiento del modelo, y cada nodo lo declara en el campo de texto que le
corresponde en lugar de inventar un resultado.

Regla que se respeta en todo el modulo: **no se fabrica evidencia**. El nodo de
pruebas registra un error tipado diciendo que no hay ejecutor, en vez de devolver
un `TestRun` con exito falso. Un sistema que se inventa que las pruebas pasaron es
peor que uno que admite que no las ejecuto.
"""

from __future__ import annotations

import difflib
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

from langgraph.types import interrupt

from ai_swe.contracts import (
    AgentRole,
    Approval,
    ApprovalDecision,
    Artifacts,
    Budget,
    CodeChange,
    CodeProposal,
    Evidence,
    FileChange,
    FileOperation,
    FinalReport,
    Finding,
    Intent,
    Outputs,
    PolicyEffect,
    ResearchOutput,
    ReviewDecision,
    ReviewVerdict,
    RunError,
    RunPlan,
    RunState,
    RunStatus,
    Scope,
    Severity,
    Subtask,
    TaskInterpretation,
    TestRun,
)
from ai_swe.sandbox import Sandbox, SandboxError, crear
from ai_swe.tools.patcher import aplicar
from ai_swe.tools.policy import DecisionContext, decide
from ai_swe.tools.runner import RunnerError
from ai_swe.tools.runner import ejecutar as ejecutar_target

log = logging.getLogger(__name__)

# --------------------------------------------------------------- vocabulario

# Clasificador determinista. Es un marcador de posicion honesto: en M2 lo
# sustituye el modelo. Se mantiene determinista en M1 porque asi `MET-13` es
# medible sin depender de la latencia ni del coste de una llamada.
_FUERA_DE_ALCANCE = (
    "push", "sube", "subir", "publica", "publicar", "despliega", "deploy",
    "produccion", "producción", "github", "pull request", " merge",
)
_MODIFICAR = (
    "corrige", "corregir", "arregla", "arreglar", "modifica", "modificar",
    "cambia", "cambiar", "añade", "anade", "añadir", "implementa", "implementar",
    "refactoriza", "refactorizar", "crea", "crear", "elimina", "borra",
)
_PREGUNTA = (
    "¿", "?", "que hace", "qué hace", "como ", "cómo ", "donde ", "dónde ",
    "explica", "explicar", "por que", "por qué", "cual ", "cuál ",
)
_INSPECCIONAR = (
    "analiza", "analizar", "revisa", "revisar", "inspecciona", "inspeccionar",
    "lista", "listar", "enumera", "enumerar", "describe", "describir",
)

_EXTENSIONES = {".py", ".md", ".toml", ".cfg", ".txt", ".json", ".yaml", ".yml"}
_MAX_ARCHIVOS = 20
_MAX_LINEAS_POR_ARCHIVO = 4000


def _ahora() -> datetime:
    return datetime.now(UTC)


def _clasificar(texto: str) -> Intent:
    """Clasificacion determinista de la intencion.

    El orden importa. Las acciones con efectos se detectan primero: "sube los
    cambios a GitHub" no debe clasificarse como modificacion local, porque el
    sistema no puede hacerlo y decirlo es parte de su comportamiento correcto
    (`RF-15`).
    """
    plano = texto.lower()
    if any(pista in plano for pista in _FUERA_DE_ALCANCE):
        return Intent.OUT_OF_SCOPE
    if any(pista in plano for pista in _MODIFICAR):
        return Intent.MODIFY
    if any(pista in plano for pista in _PREGUNTA):
        return Intent.QUESTION
    if any(pista in plano for pista in _INSPECCIONAR):
        return Intent.INSPECT
    return Intent.INSPECT  # por defecto, la opcion sin efectos


# ------------------------------------------------------------- constructores


def _con_salidas(state: RunState, **cambios) -> Outputs:
    datos = state.outputs.model_dump()
    datos.update(cambios)
    return Outputs.model_validate(datos)


def _con_presupuesto(state: RunState, **cambios) -> Budget:
    datos = state.budget.model_dump()
    datos.update(cambios)
    return Budget.model_validate(datos)


def _con_evidencia(state: RunState, **cambios) -> Evidence:
    """Constructor inmutable de la evidencia: copia y actualiza sin mutar."""
    datos = state.evidence.model_dump()
    datos.update(cambios)
    return Evidence.model_validate(datos)


def _con_artefactos(state: RunState, **cambios) -> Artifacts:
    """Constructor inmutable de los artefactos (F8).

    Se construye el objeto **completo** y no un parche parcial: el delta de
    LangGraph **reemplaza** el valor de la clave, no lo fusiona campo a campo. Un
    `Artifacts(worktree_path=...)` suelto borraria `base_commit` y `changed_files`.
    """
    datos = state.artifacts.model_dump()
    datos.update(cambios)
    return Artifacts.model_validate(datos)


def _error(
    state: RunState, clase: str, agente: str, mensaje: str, *, recuperable: bool
) -> list[RunError]:
    return [
        *state.errors,
        RunError(
            error_class=clase,
            agent=agente,
            message=mensaje,
            recoverable=recuperable,
            occurred_at=_ahora(),
        ),
    ]


def _escalar(state: RunState, errores: list[RunError]) -> dict:
    return {
        "errors": errores,
        "status": RunStatus.NEEDS_HUMAN,
        "next_step": None,
        "updated_at": _ahora(),
    }


# -------------------------------------------------------------------- nodos


# ------------------------------------------------------------------ F3: modelo

# **El unico punto del grafo que habla con el modelo.** `interpret` es el unico nodo
# conectado al `ModelGateway`; los demas siguen siendo deterministas. Es deliberado:
# una fase = un nodo, y asi el efecto del modelo es medible de forma aislada.
#
# La frontera se construye de forma **perezosa**, no al importar el modulo:
#   - importar `ai_swe.models` al cargar `nodes` obligaria a tener el gateway
#     instalado para poder importar el grafo, y el grafo debe poder importarse sin
#     proveedor;
#   - la credencial solo se exige cuando de verdad se va a llamar (`gateway_from_settings`
#     falla en el borde), no al arrancar el sistema.


def _gateway_por_defecto():
    """Construye el gateway real desde la configuracion. Puede lanzar.

    **No se captura aqui el error de credencial**: quien llama decide si un fallo de
    configuracion se degrada a fallback o se propaga. Capturar en el constructor
    ocultaria la diferencia entre «no hay proveedor» y «hay proveedor mal configurado».
    """
    from ai_swe.config import load_settings
    from ai_swe.models import gateway_from_settings

    return gateway_from_settings(load_settings())


class _SinGateway:
    """Centinela: «este nodo no debe llamar al modelo».

    Se distingue de `None` porque `None` significaria «construye el de por defecto».
    Con el centinela, un nodo sin gateway **no** intenta abrir una conexion.
    """

    __slots__ = ()


SIN_GATEWAY = _SinGateway()

# El gateway se inyecta por atributo de modulo, no por variable global de entorno.
# Motivo: una variable global mutable se puede cambiar desde cualquier sitio y deja
# el estado de las pruebas dependiendo del orden. Aqui solo lo toca
# `usar_gateway(...)`, y `usar_gateway(None)` restaura el comportamiento por defecto.
_GATEWAY: object = SIN_GATEWAY


def usar_gateway(gateway) -> None:
    """Inyecta el gateway que usara `interpret`.

    - `usar_gateway(gateway)` -> usa ese gateway (una prueba, un respaldo).
    - `usar_gateway(None)` -> vuelve a construir el de por defecto (produccion).
    - `usar_gateway(SIN_GATEWAY)` -> **desconecta** el modelo: `interpret` usa solo
      el clasificador determinista, que es el comportamiento de `M1`/`F1`/`F2`.

    Existe para que la suite offline pueda ejercitar el nodo con y sin modelo sin
    tocar la red ni las credenciales, y para que el fallback sea comprobable de
    verdad en lugar de por inspeccion.
    """
    global _GATEWAY
    if gateway is None:
        _GATEWAY = SIN_GATEWAY
    else:
        _GATEWAY = gateway


# Instruccion del sistema. Pide **solo** el objeto de `TaskInterpretation`: el
# esquema JSON se anade automaticamente en el gateway (`generate_structured`), que
# lo **deriva** del contrato Pydantic. No se escribe el esquema aqui a mano: una
# copia paralela divergiria del contrato y el modelo cumpliria uno que nadie valida.
PROMPT_INTERPRETACION = """\
Eres el Requirements Analyst de un sistema de ingenieria de software. Tu unica
tarea es CLASIFICAR una instruccion y delimitar su alcance. No ejecutas nada, no
escribes codigo y no inventas datos que la instruccion no contenga.

Clasifica la instruccion en exactamente una de estas intenciones:
  - "question": el usuario pregunta algo o pide una explicacion, sin pedir cambios.
  - "inspect": el usuario pide analizar, revisar, listar o describir algo.
  - "modify": el usuario pide un cambio concreto en el codigo (corregir, anadir,
    refactorizar, eliminar...).
  - "out_of_scope": el usuario pide algo que este sistema NO puede hacer: publicar,
    desplegar, hacer push o merge, tocar produccion o GitHub. Ante la duda entre
    "modify" y "out_of_scope", elige "out_of_scope" si la accion sale del sistema.

Rellena el campo "scope" con el repositorio y las rutas tal como aparezcan en la
instruccion, o con el texto disponible si no se indica ninguna.
En "constraints", lista las prohibiciones o condiciones EXPLICITAS del usuario
(por ejemplo, "no toques X"). No inventes restricciones que no se hayan dicho.
"confidence" es tu seguridad real entre 0.0 y 1.0: usa un valor bajo si la
instruccion es ambigua, no 1.0 por defecto.
"rationale" explica en una o dos frases por que elegiste esa intencion.
"""


def _alcance(state: RunState) -> Scope:
    """Alcance declarado por el usuario. Se calcula en un solo sitio.

    Se prefiere el `scope` de la interpretacion (F3) cuando existe, porque es el
    que lleva los limites de tamano (`max_files_changed`, `max_lines_changed`); el
    de `RunOptions` no los tiene. Si aun no hay interpretacion, se construye desde
    las opciones, que es lo unico disponible.
    """
    if state.interpretation is not None:
        return state.interpretation.scope
    opciones = state.options
    return Scope(
        repo_path=opciones.repo_path or "(sin repositorio configurado)",
        allowed_paths=opciones.allowed_paths,
        protected_paths=opciones.protected_paths,
    )


def _interpretacion_determinista(state: RunState, *, motivo: str) -> TaskInterpretation:
    """Clasificacion por vocabulario. Es el **fallback**, y sigue siendo valido.

    No es codigo muerto ni un andamio: es la via por la que el sistema sigue
    funcionando sin credenciales, sin red o con el proveedor caido. Por eso su
    `rationale` **dice** que fue determinista: una interpretacion que no declara su
    origen no se puede auditar.
    """
    intencion = _clasificar(state.instruction.text)
    return TaskInterpretation(
        intent=intencion,
        scope=_alcance(state),
        constraints=["clasificacion determinista por vocabulario (fallback sin modelo)"],
        confidence=0.5,
        rationale=(
            f"clasificacion determinista por vocabulario -> {intencion.value}"
            + ("" if state.options.repo_path else "; no se configuro repositorio")
            + f"; motivo del fallback: {motivo}"
        ),
    )


def _interpretacion_del_modelo(
    state: RunState,
) -> tuple[TaskInterpretation, Budget, int] | None:
    """Intenta interpretar con el modelo. `None` si hay que caer al fallback.

    Devuelve `(interpretacion, presupuesto_consumido, tokens)` cuando el modelo
    responde y **cumple el contrato**. La validacion no se relaja aqui: el gateway
    lanza `StructuredOutputError` si el JSON no valida, y ese caso tambien cae al
    fallback. El contrato Pydantic sigue siendo la puerta absoluta.

    Un fallo **no recuperable** que no sea de la llamada (credencial invalida,
    proveedor desconocido, configuracion incompleta) tampoco se oculta: se registra
    como error tipado recuperable y se sigue con el fallback, que es lo que permite
    que la demo funcione sin proveedor. Lo que NO se hace es fingir que el modelo
    respondio.
    """
    from ai_swe.models import (
        MessageRole,
        ModelGatewayError,
        ModelMessage,
        ModelRequest,
        StructuredOutputError,
    )
    from pydantic import ValidationError

    gateway = _GATEWAY
    if isinstance(gateway, _SinGateway):
        return None
    gateway = _gateway_por_defecto() if gateway is None else gateway

    peticion = ModelRequest(
        messages=[
            ModelMessage(role=MessageRole.SYSTEM, content=PROMPT_INTERPRETACION),
            ModelMessage(role=MessageRole.USER, content=state.instruction.text),
        ],
        max_output_tokens=1024,
        temperature=0.0,
        agent_role=AgentRole.SUPERVISOR,
        run_id=state.run_id,
        trace_id=state.trace_id,
    )
    respuesta = gateway.generate_structured(
        peticion, response_model=TaskInterpretation, budget=state.budget
    )
    datos = respuesta.structured_data
    if datos is None:  # pragma: no cover - el gateway nunca devuelve None validado
        raise StructuredOutputError("structured_data vacio tras la validacion")
    # El gateway ya valido, pero **no se confia en ello**: aqui se revalida. Si un
    # dia el gateway cambiara, el nodo no debe pasar a aceptar datos sin comprobar.
    # La revalidacion se envuelve para que un dato fuera de contrato se trate como
    # un fallo del modelo (fallback) y no como un `ValidationError` crudo que
    # **abortaria la ejecucion**: la frontera debe degradar, no reventar.
    try:
        interpretacion = TaskInterpretation.model_validate(datos)
    except ValidationError as exc:
        raise StructuredOutputError(
            "el modelo devolvio datos que no cumplen TaskInterpretation",
            provider=respuesta.provider,
            detail=str(exc)[:600],
        ) from exc
    # El alcance lo fija el **usuario**, no el modelo. Si el modelo devuelve un
    # repositorio distinto del configurado, se queda el del usuario: el alcance es
    # una restriccion de seguridad, y un modelo no la amplia por su cuenta.
    interpretacion = interpretacion.model_copy(update={"scope": _alcance(state)})
    nuevo_presupuesto = gateway.consume(state.budget, respuesta)
    tokens = nuevo_presupuesto.used_tokens - state.budget.used_tokens
    return interpretacion, nuevo_presupuesto, tokens


def interpret(state: RunState) -> dict:
    """Interpreta la instruccion y produce un plan.

    **Unico nodo conectado al modelo (F3).** Si hay gateway y el modelo responde
    con un JSON que cumple `TaskInterpretation`, se usa su clasificacion y se
    contabiliza el gasto. En cualquier otro caso -sin gateway, sin credencial,
    proveedor caido, sin red, o respuesta que no valida- se cae de forma
    **transparente** al clasificador determinista por vocabulario, que sigue
    existiendo y sigue siendo el comportamiento por defecto del sistema.

    La caida al fallback **no es silenciosa**: deja un `RunError` recuperable con
    el motivo. Un fallback que no se declara es indistinguible de un acierto, y
    eso haria imposible saber que el modelo no llego a usarse.
    """
    errores = list(state.errors)

    try:
        resultado = _interpretacion_del_modelo(state)
    except Exception as exc:  # noqa: BLE001 - la frontera convierte cualquier fallo
        if not _es_fallo_esperado(exc):
            raise
        motivo = f"{type(exc).__name__}: {exc}"[:500]
        log.warning("interpret: el modelo no respondio, se usa el fallback (%s)", motivo)
        errores = _error(
            state,
            "MODEL_FALLBACK",
            AgentRole.SUPERVISOR.value,
            f"interpretacion determinista: el modelo no se pudo usar ({motivo})",
            recuperable=True,
        )
        return {
            "interpretation": _interpretacion_determinista(state, motivo="modelo no disponible"),
            "status": RunStatus.RUNNING,
            "next_step": _clasificar(state.instruction.text).value,
            "errors": errores,
            "updated_at": _ahora(),
        }

    if resultado is None:
        interpretacion = _interpretacion_determinista(state, motivo="modelo no conectado")
        return {
            "interpretation": interpretacion,
            "status": RunStatus.RUNNING,
            "next_step": interpretacion.intent.value,
            "updated_at": _ahora(),
        }

    interpretacion, presupuesto, _tokens = resultado
    return {
        "interpretation": interpretacion,
        "budget": presupuesto,
        "status": RunStatus.RUNNING,
        "next_step": interpretacion.intent.value,
        "updated_at": _ahora(),
    }


def _es_fallo_esperado(exc: BaseException) -> bool:
    """Si el fallo es de los que justifican caer al fallback.

    Se enumeran por **tipo** en lugar de capturar `Exception` a secas: un `TypeError`
    o un `KeyError` en el codigo propio son defectos, y tragarselos los convertiria
    en un fallback silencioso que nunca se depuraria. Lo que se degrada es el fallo
    del **modelo o de su configuracion**, no un error de programacion.

    Se comparte entre `interpret` (F3) y `plan` (F4): el contrato de degradacion es
    el mismo en las dos fases, y duplicarlo permitiria que divergieran.
    """
    from ai_swe.models import ModelGatewayError

    return isinstance(exc, ModelGatewayError)


# ------------------------------------------------------ F4: Supervisor (plan)

# Planificacion determinista de respaldo. No es un andamio temporal: es la via por
# la que el sistema sigue planificando sin credenciales, sin red o con el proveedor
# caido, y la garantia de que la suite offline y el desarrollo local funcionan.
#
# Herramientas por rol: se declaran **subconjuntos** de `ROLE_TOOLS` (ver
# `tools/registry.py`). La asignacion efectiva es la interseccion, asi que declarar
# una herramienta que el rol no tiene no ampliaria permisos: solo daria un plan que
# promete algo que no se puede ejecutar.
_HERRAMIENTAS_RESEARCHER = ("list_files", "read_file", "search_text", "git_status", "git_diff")
_HERRAMIENTAS_CODER = ("read_file", "write_file", "apply_patch")


def _plan_determinista(state: RunState, *, motivo: str) -> RunPlan:
    """Plan minimo y seguro: investigar y, si procede, aplicar cambios.

    Es **duro** a proposito: dos subtareas fijas, sin dependencias creativas y con
    criterios de termino explicitos. Un plan de respaldo que intentara adivinar la
    estructura de la tarea seria un plan inventado, y eso es peor que uno generico:
    el generico se lee y se ve que es generico.

    La intencion decide la forma. Para `modify` se encadenan investigacion y cambio
    (la segunda depende de la primera); para el resto, solo investigacion, porque
    planificar una escritura cuando el usuario pregunto algo seria un plan que no
    corresponde a la peticion.
    """
    intencion = state.interpretation.intent if state.interpretation else Intent.INSPECT

    investigar = Subtask(
        id="investigar",
        description="Investigar el repositorio y reunir la evidencia necesaria.",
        agent=AgentRole.RESEARCHER,
        depends_on=[],
        allowed_tools=list(_HERRAMIENTAS_RESEARCHER),
        done_criteria="Se han enumerado los archivos relevantes y citado rutas reales.",
    )

    subtareas = [investigar]
    if intencion is Intent.MODIFY:
        subtareas.append(
            Subtask(
                id="aplicar_cambios",
                description="Aplicar los cambios propuestos sobre la evidencia reunida.",
                agent=AgentRole.CODER,
                depends_on=["investigar"],
                allowed_tools=list(_HERRAMIENTAS_CODER),
                done_criteria="Los cambios estan aplicados y el diff es revisable.",
            )
        )

    return RunPlan(
        subtasks=subtareas,
        max_review_cycles=state.budget.max_review_cycles,
        rationale=(
            "plan determinista de respaldo: "
            f"{len(subtareas)} subtarea(s) para la intencion '{intencion.value}'"
            f"; motivo del fallback: {motivo}"
        ),
    )


# Instruccion del sistema para planificar. Se pide **solo** el objeto `RunPlan`: el
# esquema se deriva del contrato en el gateway, igual que en F3. Aqui se explican
# las reglas que el contrato **no** puede expresar por si solo (que herramienta
# tiene cada rol, que no se puede planificar algo fuera de alcance).
PROMPT_PLANIFICACION = """\
Eres el Supervisor de un sistema de ingenieria de software. Recibes una
interpretacion ya validada de la peticion del usuario y debes producir un PLAN de
ejecucion. No ejecutas nada: solo planificas.

Reglas obligatorias:
  - Cada subtarea se asigna a un agente: "researcher" (solo lectura del repositorio),
    "coder" (puede escribir) o "reviewer" (revisa, no escribe). NUNCA "supervisor".
  - `allowed_tools` debe enumerar solo herramientas validas para ese agente:
      researcher: list_files, read_file, search_text, git_status, git_log, git_diff
      coder:      read_file, write_file, apply_patch, run_tests
      reviewer:   list_files, read_file, search_text, git_status, git_log, git_diff, run_tests
    Una subtarea sin herramientas no ejecuta nada: nunca dejes la lista vacia.
  - `depends_on` solo puede nombrar ids de OTRAS subtareas de este mismo plan. No
    inventes ids ni crees ciclos: si A depende de B, B no puede depender de A.
  - Usa como maximo unas pocas subtareas. Un plan de una sola tarea es valido y a
    menudo preferible a uno inflado.
  - `done_criteria` debe ser comprobable, no una intencion vaga.
  - Si la intencion es "question" o "inspect", planifica SOLO trabajo de lectura: no
    incluyas ninguna subtarea que escriba.
  - Si la intencion es "out_of_scope", no planifiques la accion prohibida.
"""


def _plan_del_modelo(state: RunState) -> tuple[RunPlan, Budget, int] | None:
    """Intenta planificar con el modelo. `None` si hay que caer al fallback.

    Devuelve `(plan, presupuesto_consumido, tokens)` cuando el modelo responde y el
    plan **cumple el contrato**. La validacion no se relaja: el gateway valida con
    `RunPlan` -que aplica el DFS de ciclos, la unicidad de ids y el limite de 32
    subtareas- y si no cumple, lanza `StructuredOutputError` y aqui se cae al
    fallback. El modelo **propone**; el contrato **decide**.
    """
    from ai_swe.models import (
        MessageRole,
        ModelMessage,
        ModelRequest,
        StructuredOutputError,
    )
    from pydantic import ValidationError

    gateway = _GATEWAY
    if isinstance(gateway, _SinGateway):
        return None
    gateway = _gateway_por_defecto() if gateway is None else gateway

    interpretacion = state.interpretation
    contexto = (
        "Interpretacion de la peticion:\n"
        f"- intencion: {interpretacion.intent.value if interpretacion else 'desconocida'}\n"
        f"- alcance: {interpretacion.scope.model_dump_json() if interpretacion else '{}'}\n"
        f"- restricciones: {interpretacion.constraints if interpretacion else []}\n\n"
        f"Peticion original del usuario:\n{state.instruction.text}"
    )

    peticion = ModelRequest(
        messages=[
            ModelMessage(role=MessageRole.SYSTEM, content=PROMPT_PLANIFICACION),
            ModelMessage(role=MessageRole.USER, content=contexto),
        ],
        max_output_tokens=2048,
        temperature=0.0,
        agent_role=AgentRole.SUPERVISOR,
        run_id=state.run_id,
        trace_id=state.trace_id,
    )
    respuesta = gateway.generate_structured(
        peticion, response_model=RunPlan, budget=state.budget
    )
    datos = respuesta.structured_data
    if datos is None:  # pragma: no cover - el gateway nunca devuelve None validado
        raise StructuredOutputError("structured_data vacio tras la validacion")
    # Revalidacion defensiva, igual que en F3: si un dia el gateway cambiara, el
    # nodo no debe pasar a aceptar un plan sin comprobar. Y se envuelve el error
    # para que un dato fuera de contrato degrade al fallback en lugar de abortar.
    try:
        plan = RunPlan.model_validate(datos)
    except ValidationError as exc:
        raise StructuredOutputError(
            "el modelo devolvio un plan que no cumple RunPlan",
            provider=respuesta.provider,
            detail=str(exc)[:600],
        ) from exc

    plan = _acotar_al_presupuesto_plan(plan, state)
    nuevo_presupuesto = gateway.consume(state.budget, respuesta)
    tokens = nuevo_presupuesto.used_tokens - state.budget.used_tokens
    return plan, nuevo_presupuesto, tokens


def _acotar_al_presupuesto_plan(plan: RunPlan, state: RunState) -> RunPlan:
    """Devuelve un plan cuyos ciclos de revision no excedan el presupuesto.

    **Por que no basta con el contrato.** `RunPlan.max_review_cycles` esta acotado a
    [0,5], pero el presupuesto de la ejecucion puede ser menor. Un plan que pidiera
    5 ciclos cuando `Budget.max_review_cycles` es 2 prometeria un trabajo que el
    sistema no va a poder pagar, y el bucle de revision se cortaria antes de cumplir
    lo planificado: el plan quedaria mintiendo.

    Devuelve un objeto **nuevo** en lugar de mutar el recibido: mutar un modelo
    Pydantic en su lugar deja el objeto en un estado que no ha pasado por sus
    validadores, y el siguiente que lo lea no puede confiar en el.
    """
    if plan.max_review_cycles <= state.budget.max_review_cycles:
        return plan

    motivo = (
        f" [acotado: max_review_cycles reducido a {state.budget.max_review_cycles} "
        "por el presupuesto de la ejecucion]"
    )
    return plan.model_copy(
        update={
            "max_review_cycles": state.budget.max_review_cycles,
            "rationale": (plan.rationale + motivo)[:4000],
        }
    )


def plan(state: RunState) -> dict:
    """Planificacion del Supervisor. **Segundo nodo conectado al modelo (F4).**

    Recibe la `TaskInterpretation` de `interpret` y produce un `RunPlan` que se
    guarda en `RunState.plan`. Es el paso 6 de `docs/03-flujo-e-implementacion.md`.

    Igual que en F3, si no hay modelo o el que hay falla, se aplica un **fallback
    determinista transparente y declarado**: un `RunError` recuperable con
    `error_class=MODEL_FALLBACK` y el motivo. La ejecucion nunca se queda sin plan.
    """
    try:
        resultado = _plan_del_modelo(state)
    except Exception as exc:  # noqa: BLE001 - la frontera convierte cualquier fallo
        if not _es_fallo_esperado(exc):
            raise
        motivo = f"{type(exc).__name__}: {exc}"[:500]
        log.warning("plan: el modelo no respondio, se usa el fallback (%s)", motivo)
        plan_fallback = _plan_determinista(state, motivo="modelo no disponible")
        return {
            "plan": plan_fallback,
            "errors": _error(
                state,
                "MODEL_FALLBACK",
                AgentRole.SUPERVISOR.value,
                f"plan determinista de respaldo: el modelo no se pudo usar ({motivo})",
                recuperable=True,
            ),
            "status": RunStatus.RUNNING,
            "next_step": plan_fallback.subtasks[0].agent.value,
            "updated_at": _ahora(),
        }

    if resultado is None:
        plan_fallback = _plan_determinista(state, motivo="modelo no conectado")
        return {
            "plan": plan_fallback,
            "status": RunStatus.RUNNING,
            "next_step": plan_fallback.subtasks[0].agent.value,
            "updated_at": _ahora(),
        }

    plan_modelo, presupuesto, _tokens = resultado
    return {
        "plan": plan_modelo,
        "budget": presupuesto,
        "status": RunStatus.RUNNING,
        "next_step": plan_modelo.subtasks[0].agent.value,
        "updated_at": _ahora(),
    }


def _subtarea_actual(state: RunState) -> Subtask | None:
    """Devuelve la subtarea que toca ejecutar ahora, o None si no hay plan."""
    if state.plan is None or not state.plan.subtasks:
        return None
    if state.plan_index >= len(state.plan.subtasks):
        return None
    return state.plan.subtasks[state.plan_index]


def researcher(state: RunState) -> dict:
    """Enumera el repositorio autorizado. Lectura real, sin modelo.

    **F5: ahora es iterativo.** Acumula hallazgos en `evidence.findings` sin
    sobrescribir los de subtareas anteriores, y avanza `plan_index`.
    """
    hallazgos: list[Finding] = []
    leidos: list[str] = []
    incognitas = [
        "M1: el Researcher enumera el repositorio; la seleccion semantica de "
        "evidencia relevante llega en M2 con el modelo conectado"
    ]

    raiz_texto = state.options.repo_path
    if not raiz_texto:
        incognitas.append("no se configuro repositorio, no hay nada que inspeccionar")
    else:
        raiz = Path(raiz_texto).resolve()
        if not raiz.is_dir():
            incognitas.append(f"la ruta configurada no es un directorio: {raiz_texto}")
        else:
            for ruta in sorted(raiz.rglob("*")):
                if len(hallazgos) >= _MAX_ARCHIVOS:
                    incognitas.append(
                        f"listado truncado a {_MAX_ARCHIVOS} archivos; el resto no se reviso"
                    )
                    break
                if not ruta.is_file() or ruta.suffix.lower() not in _EXTENSIONES:
                    continue
                resuelta = ruta.resolve()
                if not _dentro_de(raiz, resuelta):
                    continue  # enlace simbolico que sale del area autorizada
                relativa = resuelta.relative_to(raiz).as_posix()
                leidos.append(relativa)
                hallazgos.append(
                    Finding(
                        severity=Severity.INFO,
                        path=relativa,
                        explanation=f"archivo presente en el repositorio ({resuelta.suffix})",
                        evidence=_primera_linea(resuelta),
                    )
                )

    # Acumulacion inmutable de la evidencia (F5): se concatenan los hallazgos
    # nuevos a los que ya existian, en lugar de sobrescribir.
    hallazgos_previos = list(state.evidence.findings)
    hallazgos_totales = hallazgos_previos + hallazgos
    leidos_previos = state.outputs.researcher_output.files_read if state.outputs.researcher_output else []
    leidos_totales = list(leidos_previos) + leidos
    incognitas_previas = state.outputs.researcher_output.unknowns if state.outputs.researcher_output else []
    incognitas_totales = list(incognitas_previas) + incognitas

    salida = ResearchOutput(
        findings=hallazgos_totales,
        unknowns=incognitas_totales,
        files_read=leidos_totales,
    )

    # Avance del indice: el nodo que ejecuta la tarea es el que declara que
    # la ha completado. El router solo compara, nunca calcula.
    return {
        "outputs": _con_salidas(state, researcher_output=salida),
        "evidence": _con_evidencia(state, findings=hallazgos_totales),
        "plan_index": state.plan_index + 1,
        "updated_at": _ahora(),
    }


def _dentro_de(raiz: Path, candidata: Path) -> bool:
    """Comprueba que una ruta resuelta sigue dentro del area autorizada (`RNF-S2`).

    Se resuelve **antes** de comparar: es lo que hace que un enlace simbolico que
    apunte fuera del repositorio no pueda ampliar el alcance. Se extrae a una
    funcion propia para poder comprobarla directamente, en lugar de confiar en que
    el bucle que la usa la ejercite.
    """
    try:
        return candidata.resolve().is_relative_to(raiz.resolve())
    except (OSError, ValueError):
        return False


def _primera_linea(ruta: Path) -> str:
    try:
        with ruta.open("r", encoding="utf-8", errors="replace") as fh:
            for _ in range(_MAX_LINEAS_POR_ARCHIVO):
                linea = fh.readline()
                if not linea:
                    break
                limpia = linea.strip()
                if limpia:
                    return limpia[:200]
    except OSError as exc:
        return f"(no se pudo leer: {type(exc).__name__})"
    return "(archivo vacio)"


def answer_direct(state: RunState) -> dict:
    """Responde a una pregunta con la evidencia reunida. Sin modelo en M1."""
    investigacion = state.outputs.researcher_output
    rutas = investigacion.files_read if investigacion else []
    informe = FinalReport(
        summary=(
            "M1: no hay modelo conectado, asi que el sistema no puede redactar una "
            "respuesta. Lo que si puede hacer ya es reunir la evidencia sobre la que "
            "se respondera en M2."
        ),
        changes_applied=[],
        tests_executed=[],
        review="no aplica: la intencion era responder, no modificar",
        pending=[
            "M2: conectar el modelo para redactar la respuesta a partir de la evidencia",
            *([f"archivos considerados: {len(rutas)}"] if rutas else []),
        ],
    )
    return {"final_report": informe, "status": RunStatus.COMPLETED, "next_step": None,
            "updated_at": _ahora()}


def explain_limits(state: RunState) -> dict:
    """Rechaza una instruccion fuera de alcance explicando el limite (`RF-15`).

    No es un fallo: es el comportamiento correcto. Por eso termina en `completed`
    y no registra error. Un sistema que intenta `git push` "a ver que pasa" esta
    peor disenado que uno que explica por que no lo hace.
    """
    informe = FinalReport(
        summary=(
            "La instruccion pide una accion fuera del alcance declarado del sistema. "
            "El prototipo no realiza operaciones remotas ni publica cambios."
        ),
        changes_applied=[],
        tests_executed=[],
        review="no aplica",
        pending=[
            "fuera de alcance: publicar en un remoto, git push, o cualquier accion externa",
            "el sistema si puede preparar el cambio y dejarlo confirmado en local con aprobacion",
        ],
    )
    return {"final_report": informe, "status": RunStatus.COMPLETED, "next_step": None,
            "updated_at": _ahora()}


# ------------------------------------------------------------- F6: Coder real

# Instruccion del sistema para el Coder. Se pide **solo** `CodeProposal`: el esquema
# se deriva del contrato en el gateway. Aqui se explican las reglas que el contrato
# no puede expresar por si solo (que el diff y los hashes los calcula el sistema).
PROMPT_CODIFICACION = """\
Eres el Coder de un sistema de ingenieria de software. Recibes una subtarea, la
interpretacion de la peticion y la evidencia ya reunida por el Researcher. Tu tarea
es PROPONER los cambios de codigo, no aplicarlos.

Reglas obligatorias:
  - Devuelve una lista de archivos. Para cada uno indica:
      "operation": "create" (nuevo), "modify" (existe) o "delete" (se elimina).
      "new_content": el CONTENIDO COMPLETO resultante del archivo. En "delete" se omite.
      "rationale": por que ese archivo concreto necesita el cambio.
  - `new_content` es el fichero entero, no un fragmento ni un diff. El sistema
    calcula el diff y los hashes a partir de tu contenido; **no los inventes**.
  - No declares rutas absolutas ni que escapen del repositorio.
  - Respeta el criterio de termino de la subtarea: si no puedes cumplirlo, deja
    `files` vacio y explicalo en `rationale` en lugar de proponer un cambio falso.
  - No propongas mas archivos de los que permite el alcance declarado.
"""


def _contar_lineas(texto: str) -> int:
    """Cuenta lineas de la forma en que `diff` las cuenta.

    Un texto vacio tiene 0 lineas; un texto que termina en salto tiene una linea
    final vacia que no se cuenta. Se centraliza para que el conteo de anadidas y
    el de eliminadas usen exactamente el mismo criterio.
    """
    if not texto:
        return 0
    lineas = texto.split("\n")
    if lineas and lineas[-1] == "":
        lineas.pop()
    return len(lineas)


def _diff_unificado(propuesta: FileProposal, contenido_previo: str | None = None) -> str:
    """Diff unificado **real** para un archivo: compara el contenido viejo con el nuevo.

    **Resuelve la deuda declarada en F6.** Con solo el contenido nuevo el diff era de
    lineas completas -trataba el archivo como si se anadiera entero-, porque el Coder
    no podia leer el original. Ahora el contenido previo se pasa como argumento, y el
    diff sale de `difflib.unified_diff`: contexto real, lineas `-`/`+`/` ` correctas y
    cabeceras `@@` con los rangos verdaderos.

    **De donde sale `contenido_previo`.** No de que el Coder lea el repositorio del
    usuario -no debe, y no puede-. Lo aporta quien tiene acceso legitimo: en F7, el
    sandbox, que lee el archivo dentro del worktree aislado antes de aplicar el
    parche. Si no se pasa -el camino del Coder puro, sin sandbox-, el diff degrada al
    comportamiento de F6 y **lo declara en la cabecera**, para que nadie confunda un
    diff sin contexto con un diff real.

    Un `create` no tiene contenido previo por definicion, y se marca con
    `--- /dev/null`, que es la convencion de git.
    """
    ruta = propuesta.path
    nuevo = propuesta.new_content or ""

    if propuesta.operation is FileOperation.DELETE:
        viejo = contenido_previo or ""
        nuevo = ""
        etiqueta_vieja, etiqueta_nueva = f"a/{ruta}", "/dev/null"
    elif propuesta.operation is FileOperation.CREATE or contenido_previo is None:
        viejo = ""
        etiqueta_vieja, etiqueta_nueva = "/dev/null", f"b/{ruta}"
    else:
        viejo = contenido_previo
        etiqueta_vieja, etiqueta_nueva = f"a/{ruta}", f"b/{ruta}"

    trozos = difflib.unified_diff(
        viejo.splitlines(keepends=True),
        nuevo.splitlines(keepends=True),
        fromfile=etiqueta_vieja,
        tofile=etiqueta_nueva,
        n=3,
    )
    texto = "".join(trozos)

    # Un `delete` **siempre** produce un trozo, aunque no haya contenido previo.
    # `difflib` no emite nada cuando ambos lados son iguales -y dos cadenas vacias lo
    # son-, asi que sin esto un borrado quedaba como un diff vacio: indistinguible de
    # "no hay cambio". Se sintetiza la cabecera, que es lo que git escribe para un
    # archivo eliminado.
    if not texto and propuesta.operation is FileOperation.DELETE:
        return f"--- {etiqueta_vieja}\n+++ {etiqueta_nueva}\n"
    return texto


def _respetar_limites(propuesta: CodeProposal, scope: Scope) -> tuple[CodeProposal, str | None]:
    """Recorta la propuesta a los limites del `Scope`. Devuelve (propuesta, motivo).

    **Por que recortar y no rechazar en bloque.** El alcance declara cuanto se
    permite cambiar, no que el trabajo entero se descarte. Recortar deja el cambio
    parcial y **declarado**; rechazar entero convierte un exceso de una linea en
    cero progreso. El motivo se devuelve para que el nodo lo registre: un recorte
    silencioso seria tan malo como no aplicarlo.
    """
    if not propuesta.files:
        return propuesta, None

    motivo: str | None = None
    archivos = list(propuesta.files)

    if len(archivos) > scope.max_files_changed:
        motivo = (
            f"la propuesta tocaba {len(archivos)} archivos y el alcance permite "
            f"{scope.max_files_changed}: se conservan los primeros"
        )
        archivos = archivos[: scope.max_files_changed]

    # Limite de lineas: se van descartando archivos por el final hasta que el
    # total de lineas de contenido nuevo quepa.
    def _lineas(fs: list[FileProposal]) -> int:
        return sum(_contar_lineas(f.new_content or "") for f in fs)

    while archivos and _lineas(archivos) > scope.max_lines_changed:
        quitado = archivos.pop()
        extra = (
            f"la propuesta superaba {scope.max_lines_changed} lineas y el alcance "
            f"permite {scope.max_lines_changed}: se descarto '{quitado.path}'"
            if motivo is None
            else f"; ademas se descarto '{quitado.path}' por el limite de lineas"
        )
        motivo = (motivo or "") + extra if motivo else extra

    return propuesta.model_copy(update={"files": archivos}), motivo


def _contar_desde_diff(trozo: str) -> tuple[int, int]:
    """Cuenta anadidas y eliminadas leyendo el diff, no el contenido.

    Se cuentan las lineas que empiezan por `+` o `-` **excluyendo las cabeceras**
    (`+++`/`---`). Contar sobre el diff y no sobre el texto es lo que hace que el
    numero y el parche no puedan divergir: si el diff dice que se anaden tres lineas,
    el conteo dice tres, porque sale de las mismas lineas.
    """
    anadidas = eliminadas = 0
    for linea in trozo.splitlines():
        if linea.startswith("+++") or linea.startswith("---"):
            continue
        if linea.startswith("+"):
            anadidas += 1
        elif linea.startswith("-"):
            eliminadas += 1
    return anadidas, eliminadas


def _cambio_desde_propuesta(
    propuesta: CodeProposal, *, contenidos_previos: dict[str, str | None] | None = None
) -> CodeChange:
    """Convierte la propuesta del modelo en el `CodeChange` derivado.

    Aqui se calcula **toda** la metainformacion de forma determinista: conteo de
    lineas, diff unificado y hashes. El modelo nunca aporta un hash, porque no
    puede conocerlo; si lo aportara, seria un dato inventado.

    **`contenidos_previos` es la entrada de F7.** El Coder puro no lo pasa -no lee el
    repositorio- y obtiene el diff de F6 (sin contexto). Cuando F7 aplica el parche,
    pasa el contenido que leyo del sandbox, y entonces el diff y los conteos son
    reales: `added` y `removed` reflejan el cambio de verdad, no el archivo entero.
    """
    previos = contenidos_previos or {}
    cambios: list[FileChange] = []
    trozos_dif: list[str] = []

    for archivo in propuesta.files:
        # El sha256 es siempre del contenido **resultante**: es la huella del archivo
        # tal como queda, que es lo que permite comprobar despues que se aplico.
        contenido = archivo.new_content or ""
        nuevo_sha = hashlib.sha256(contenido.encode("utf-8")).hexdigest()

        trozo = _diff_unificado(archivo, previos.get(archivo.path))
        anadidas, eliminadas = _contar_desde_diff(trozo)

        cambios.append(
            FileChange(
                path=archivo.path,
                added=anadidas,
                removed=eliminadas,
                sha256=nuevo_sha,
            )
        )
        trozos_dif.append(trozo)

    diferencias = "".join(trozos_dif)
    return CodeChange(
        files_changed=cambios,
        diff=diferencias,
        rationale=propuesta.rationale,
        diff_sha256=hashlib.sha256(diferencias.encode("utf-8")).hexdigest(),
    )


def _coder_del_modelo(state: RunState) -> tuple[CodeChange, Budget, list[str]] | None:
    """Intenta que el modelo proponga el cambio. `None` si hay que caer al fallback.

    Devuelve `(cambio, presupuesto_consumido, avisos)`. Los avisos son los recortes
    por alcance, que el nodo registra para que el recorte no sea silencioso.
    """
    from ai_swe.models import (
        MessageRole,
        ModelMessage,
        ModelRequest,
        StructuredOutputError,
    )
    from pydantic import ValidationError

    gateway = _GATEWAY
    if isinstance(gateway, _SinGateway):
        return None
    gateway = _gateway_por_defecto() if gateway is None else gateway

    interpretacion = state.interpretation
    subtarea = _subtarea_actual(state)
    hallazgos = state.evidence.findings[-20:] if state.evidence.findings else []

    lineas_evidencia = "\n".join(
        f"- [{f.severity.value}] {f.path}: {f.explanation} (evidencia: {f.evidence[:120]})"
        for f in hallazgos
    ) or "(sin hallazgos previos)"

    contexto = (
        "Interpretacion de la peticion:\n"
        f"- intencion: {interpretacion.intent.value if interpretacion else 'desconocida'}\n"
        f"- restricciones: {interpretacion.constraints if interpretacion else []}\n\n"
        f"Subtarea a completar:\n"
        f"- descripcion: {subtarea.description if subtarea else 'no declarada'}\n"
        f"- criterio de termino: {subtarea.done_criteria if subtarea else 'no declarado'}\n\n"
        f"Evidencia acumulada por el Researcher:\n{lineas_evidencia}\n\n"
        f"Peticion original del usuario:\n{state.instruction.text}"
    )

    peticion = ModelRequest(
        messages=[
            ModelMessage(role=MessageRole.SYSTEM, content=PROMPT_CODIFICACION),
            ModelMessage(role=MessageRole.USER, content=contexto),
        ],
        max_output_tokens=4096,
        temperature=0.0,
        agent_role=AgentRole.CODER,
        run_id=state.run_id,
        trace_id=state.trace_id,
    )
    respuesta = gateway.generate_structured(
        peticion, response_model=CodeProposal, budget=state.budget
    )
    datos = respuesta.structured_data
    if datos is None:  # pragma: no cover - el gateway nunca devuelve None validado
        raise StructuredOutputError("structured_data vacio tras la validacion")
    # Revalidacion defensiva, igual que en F3/F4. Se envuelve el fallo para que
    # un dato fuera de contrato degrade al fallback en lugar de abortar la ejecucion.
    try:
        propuesta = CodeProposal.model_validate(datos)
    except ValidationError as exc:
        raise StructuredOutputError(
            "el modelo devolvio una propuesta que no cumple CodeProposal",
            provider=respuesta.provider,
            detail=str(exc)[:600],
        ) from exc

    propuesta, motivo = _respetar_limites(propuesta, _alcance(state))
    avisos = [motivo] if motivo else []
    cambio = _cambio_desde_propuesta(propuesta)
    nuevo_presupuesto = gateway.consume(state.budget, respuesta)
    return cambio, nuevo_presupuesto, avisos


def _cambio_vacio(motivo: str) -> CodeChange:
    """Cambio vacio controlado: no se propone nada, y se dice por que.

    Es el fallback obligatorio. Un cambio vacio es **honesto**: no hay parche
    porque no hubo modelo. Inventar uno seria fabricar un cambio que nadie ha
    razonado.
    """
    return CodeChange(
        files_changed=[],
        diff="",
        rationale=motivo,
        diff_sha256=hashlib.sha256(b"").hexdigest(),
    )


def coder(state: RunState) -> dict:
    """Coder real (F6). Propone un parche **estructurado**; no escribe en disco.

    El modelo devuelve un `CodeProposal` (archivos y contenido); este nodo deriva
    de forma determinista el diff unificado, el conteo de lineas y los `sha256`.
    El modelo propone; el codigo verifica.

    **No escribe en el sistema de archivos.** Aplicar parches es F7 (sandbox). Aqui
    el resultado queda en `RunState.outputs.coder_output`.

    **F5:** cada nodo ejecutor avanza `plan_index`; el router solo lee.
    """
    errores = list(state.errors)
    avisos: list[str] = []
    try:
        resultado = _coder_del_modelo(state)
    except Exception as exc:  # noqa: BLE001 - la frontera convierte cualquier fallo
        if not _es_fallo_esperado(exc):
            raise
        motivo = f"{type(exc).__name__}: {exc}"[:500]
        log.warning("coder: el modelo no respondio, se usa el fallback (%s)", motivo)
        cambio = _cambio_vacio(
            "cambio vacio de respaldo: el modelo no se pudo usar "
            f"({motivo}). No se propone ningun parche inventado."
        )
        return {
            "outputs": _con_salidas(state, coder_output=cambio),
            "errors": _error(
                state,
                "MODEL_FALLBACK",
                AgentRole.CODER.value,
                f"cambio determinista de respaldo: el modelo no se pudo usar ({motivo})",
                recuperable=True,
            ),
            "plan_index": state.plan_index + 1,
            "next_step": "run_tests",
            "updated_at": _ahora(),
        }

    if resultado is None:
        cambio = _cambio_vacio(
            "cambio vacio de respaldo: no hay modelo conectado. La generacion real "
            "de parches requiere el ModelGateway; no se propone un parche inventado."
        )
        return {
            "outputs": _con_salidas(state, coder_output=cambio),
            "plan_index": state.plan_index + 1,
            "next_step": "run_tests",
            "updated_at": _ahora(),
        }

    cambio, presupuesto, avisos = resultado
    # Un recorte por alcance no puede quedar sin dejar rastro.
    for aviso in avisos:
        errores = _error(
            state,
            "SCOPE_TRIMMED",
            AgentRole.CODER.value,
            aviso,
            recuperable=True,
        )
    salida = {
        "outputs": _con_salidas(state, coder_output=cambio),
        "budget": presupuesto,
        "plan_index": state.plan_index + 1,
        "next_step": "run_tests",
        "updated_at": _ahora(),
    }
    if avisos:
        salida["errors"] = errores
    return salida


# --------------------------------------------------------------- F8: sandbox
#
# Inyeccion por atributo de modulo, con el mismo criterio que `usar_gateway`: una
# prueba puede fijar la raiz de worktrees y los targets permitidos sin depender de
# variables de entorno ni del orden de ejecucion.

_WORKSPACE_ROOT: Path | None = None
_TARGETS_PERMITIDOS: tuple[str, ...] | None = None


def usar_workspace_root(raiz: Path | str | None) -> None:
    """Fija la raiz donde se crean los worktrees. `None` = leerla de la configuracion."""
    global _WORKSPACE_ROOT
    _WORKSPACE_ROOT = Path(raiz) if raiz is not None else None


def usar_targets_permitidos(targets: tuple[str, ...] | list[str] | None) -> None:
    """Fija los objetivos de prueba permitidos. `None` = leerlos de la configuracion."""
    global _TARGETS_PERMITIDOS
    _TARGETS_PERMITIDOS = tuple(targets) if targets is not None else None


def _workspace_root() -> Path:
    if _WORKSPACE_ROOT is not None:
        return _WORKSPACE_ROOT
    from ai_swe.config import load_settings

    return load_settings().workspace_root


def _targets_permitidos() -> tuple[str, ...]:
    if _TARGETS_PERMITIDOS is not None:
        return _TARGETS_PERMITIDOS
    from ai_swe.config import load_settings

    return tuple(load_settings().allowed_test_targets)


def apply_sandbox(state: RunState) -> dict:
    """Aplica el cambio del Coder en un worktree aislado (F8).

    Es el nodo que convierte una **propuesta** en un arbol de trabajo real, sin
    tocar el repositorio del usuario. Hasta F8 el `CodeChange` vivia solo en el
    estado; aqui se materializa donde las pruebas puedan ejercitarlo.

    **El sandbox no se destruye aqui ni al final del grafo** (`DEC-16`). Destruirlo
    antes de la aprobacion humana destruiria justo lo que se esta aprobando. La
    limpieza ocurre al recrear con el mismo `run_id`, que ya hace `crear()`.

    **Un rechazo de ruta escala.** El patcher (F7) no aborta el cambio por una ruta
    denegada -los demas archivos siguen siendo legitimamente aplicables-, pero en el
    grafo un rechazo significa que el Coder propuso escribir **fuera** de lo
    autorizado. Eso no es un resultado normal: se registra como error y se escala a
    un humano en lugar de continuar como si nada.

    Nunca propaga una excepcion: un fallo del sandbox se convierte en un error
    tipado y la ejecucion termina en `needs_human`, no en una traza de LangGraph.
    """
    cambio = state.outputs.coder_output
    if cambio is None or not cambio.files_changed:
        return _escalar(
            state,
            _error(
                state,
                "SANDBOX_NOTHING_TO_APPLY",
                AgentRole.CODER.value,
                "no hay propuesta de cambio que aplicar en el sandbox",
                recuperable=False,
            ),
        )

    alcance = _alcance(state)
    repo = Path(alcance.repo_path)
    if not repo.is_dir():
        return _escalar(
            state,
            _error(
                state,
                "SANDBOX_NO_REPO",
                AgentRole.CODER.value,
                f"el repositorio autorizado '{alcance.repo_path}' no existe; sin "
                "repositorio no hay worktree que crear",
                recuperable=False,
            ),
        )

    try:
        sandbox = crear(repo, state.run_id, workspace_root=_workspace_root())
    except SandboxError as exc:
        return _escalar(
            state,
            _error(
                state,
                "SANDBOX_CREATE_FAILED",
                AgentRole.CODER.value,
                str(exc),
                recuperable=False,
            ),
        )

    resultado = aplicar(
        sandbox,
        cambio,
        allowed_paths=tuple(alcance.allowed_paths),
        protected_paths=tuple(alcance.protected_paths),
    )

    if resultado.denegados:
        detalle = "; ".join(f"{ruta}: {motivo}" for ruta, motivo in resultado.denegados.items())
        return _escalar(
            state,
            _error(
                state,
                "SANDBOX_PATH_DENIED",
                AgentRole.CODER.value,
                f"el cambio propone rutas que el confinamiento rechaza: {detalle}",
                recuperable=False,
            ),
        )

    if resultado.fallos:
        detalle = "; ".join(f"{ruta}: {motivo}" for ruta, motivo in resultado.fallos.items())
        return _escalar(
            state,
            _error(
                state,
                "SANDBOX_APPLY_FAILED",
                AgentRole.CODER.value,
                f"no se pudo aplicar el cambio en el sandbox: {detalle}",
                recuperable=False,
            ),
        )

    return {
        "artifacts": _con_artefactos(
            state,
            worktree_path=str(sandbox.raiz),
            base_commit=sandbox.base_commit,
            changed_files=cambio.files_changed,
            diff=sandbox.diff(),
        ),
        "next_step": "run_tests",
        "updated_at": _ahora(),
    }


def run_tests(state: RunState) -> dict:
    """Ejecuta de verdad los objetivos autorizados dentro del sandbox (F8).

    Sustituye al marcador de M1, que registraba `TEST_EXECUTOR_NOT_IMPLEMENTED`
    porque no habia ejecutor. Ahora lo hay, y **la evidencia es real**: target,
    codigo de salida, salida capturada, duracion y el comando exacto.

    **Solo se ejecutan objetivos de la lista permitida**, y cada uno pasa por el
    Policy Engine antes de lanzarse. El identificador no es un comando: se traduce
    con la tabla cerrada de `tools/runner.py` y se pasa a `subprocess` como lista
    de argumentos con `shell=False`.

    **Un fallo de pruebas no es un error del sistema.** Un `TestRun` con codigo
    distinto de cero es un **resultado**: se registra como evidencia y se deja que
    el Reviewer juzgue. Escalar aqui impediria que el ciclo de correccion
    Coder↔Reviewer hiciera su trabajo.

    Nunca propaga una excepcion: un fallo del ejecutor se convierte en un error
    tipado y la ejecucion termina en `needs_human`.
    """
    ruta_worktree = state.artifacts.worktree_path
    if not ruta_worktree:
        return _escalar(
            state,
            _error(
                state,
                "TEST_NO_SANDBOX",
                AgentRole.CODER.value,
                "no hay worktree aplicado: las pruebas se ejecutan sobre el cambio "
                "aplicado, y sin sandbox no hay nada que probar",
                recuperable=False,
            ),
        )

    permitidos = _targets_permitidos()
    sandbox = Sandbox(
        raiz=Path(ruta_worktree),
        repo_original=Path(_alcance(state).repo_path),
        base_commit=state.artifacts.base_commit or "",
        run_id=state.run_id,
        # No lo creamos en este nodo: se reconstruye desde el estado. Con `False`,
        # un teardown accidental no destruiria un arbol que no abrimos aqui.
        creado_por_nosotros=False,
    )

    evidencia: list[TestRun] = []
    errores = list(state.errors)
    llamadas = state.budget.used_tool_calls

    for target in permitidos:
        decision = decide(
            "run_tests",
            {"target": target},
            DecisionContext(
                run_id=state.run_id,
                agent=AgentRole.CODER,
                allowed_test_targets=permitidos,
                budget_exhausted=state.budget.exhausted,
            ),
        )
        if decision.effect is not PolicyEffect.ALLOW:
            errores = _error(
                state,
                "POLICY_DENIED",
                AgentRole.CODER.value,
                f"el Policy Engine no permitio ejecutar '{target}': {decision.reason}",
                recuperable=False,
            )
            continue

        try:
            corrida = ejecutar_target(sandbox, target, permitidos=permitidos)
        except RunnerError as exc:
            errores = _error(
                state,
                "TEST_EXECUTOR_FAILED",
                AgentRole.CODER.value,
                f"no se pudo ejecutar '{target}': {exc}",
                recuperable=False,
            )
            continue

        evidencia.append(corrida)
        llamadas += 1

    if not evidencia:
        return _escalar(state, errores)

    return {
        "evidence": _con_evidencia(
            state, test_runs=[*state.evidence.test_runs, *evidencia]
        ),
        "budget": _con_presupuesto(state, used_tool_calls=llamadas),
        "errors": errores,
        "next_step": "reviewer",
        "updated_at": _ahora(),
    }


def reviewer(state: RunState) -> dict:
    """Juzga el resultado con la evidencia disponible."""
    pruebas = state.evidence.test_runs

    if not pruebas:
        veredicto = ReviewVerdict(
            decision=ReviewDecision.ESCALATE,
            findings=[],
            summary="no hay evidencia de pruebas que revisar; no se puede aceptar ni rechazar",
        )
    elif all(p.passed for p in pruebas):
        veredicto = ReviewVerdict(
            decision=ReviewDecision.ACCEPT,
            findings=[
                Finding(
                    severity=Severity.INFO,
                    path="(pruebas)",
                    explanation="todas las ejecuciones de prueba registradas pasaron",
                    evidence="; ".join(f"{p.target} -> exit {p.exit_code}" for p in pruebas),
                )
            ],
            summary="el cambio pasa las pruebas registradas",
        )
    else:
        fallidas = [p.target for p in pruebas if not p.passed]
        veredicto = ReviewVerdict(
            decision=ReviewDecision.REQUEST_CHANGES,
            findings=[
                Finding(
                    severity=Severity.HIGH,
                    path="(pruebas)",
                    explanation="hay ejecuciones de prueba con codigo de salida distinto de cero",
                    evidence=f"objetivos fallidos: {', '.join(fallidas)}",
                )
            ],
            required_fixes=[f"corregir el fallo en {t}" for t in fallidas],
            summary=f"{len(fallidas)} objetivo(s) de prueba en rojo",
        )

    return {
        "outputs": _con_salidas(state, reviewer_output=veredicto),
        "budget": _con_presupuesto(state, review_cycles_used=state.budget.review_cycles_used + 1),
        "next_step": "approval_gate" if veredicto.decision is ReviewDecision.ACCEPT else "escalate",
        "updated_at": _ahora(),
    }


def mark_awaiting(state: RunState) -> dict:
    """Marca la ejecucion como pendiente de aprobacion.

    Es un nodo aparte a proposito: `interrupt()` no confirma las escrituras
    parciales del nodo en el que se llama, porque el nodo se reejecuta al
    reanudar. Sin este nodo previo, el estado persistido nunca mostraria
    `awaiting_approval` y una interfaz no podria saber que hay que aprobar algo.
    """
    return {"status": RunStatus.AWAITING_APPROVAL, "next_step": "approval_gate",
            "updated_at": _ahora()}


def approval_gate(state: RunState) -> dict:
    """Solicita aprobacion humana y reanuda con la decision."""
    veredicto = state.outputs.reviewer_output
    decision = interrupt(
        {
            "pregunta": "¿promover los cambios del worktree al repositorio del usuario?",
            "run_id": state.run_id,
            "resumen_revision": veredicto.summary if veredicto else "(sin revision)",
        }
    )

    try:
        eleccion = ApprovalDecision(str(decision))
    except ValueError:
        eleccion = ApprovalDecision.REJECTED

    aprobacion = Approval(
        action="promote_changes",
        actor="usuario",
        decided_at=_ahora(),
        content_sha256=state.outputs.coder_output.diff_sha256
        if state.outputs.coder_output
        else hashlib.sha256(b"").hexdigest(),
        decision=eleccion,
        reason="" if eleccion is ApprovalDecision.APPROVED else "rechazado por el usuario",
    )

    if eleccion is not ApprovalDecision.APPROVED:
        return {
            "approvals": [*state.approvals, aprobacion],
            "errors": _error(
                state,
                "APPROVAL_REJECTED",
                AgentRole.SUPERVISOR.value,
                "el usuario rechazo la promocion de cambios",
                recuperable=False,
            ),
            "status": RunStatus.NEEDS_HUMAN,
            "next_step": None,
            "updated_at": _ahora(),
        }

    return {
        "approvals": [*state.approvals, aprobacion],
        "status": RunStatus.RUNNING,
        "next_step": "finalize",
        "updated_at": _ahora(),
    }


def escalate(state: RunState) -> dict:
    """Escala al humano. Se usa cuando un nodo ya dejo un error sin resolver."""
    return _escalar(state, state.errors or _error(
        state,
        "UNSPECIFIED_ESCALATION",
        AgentRole.SUPERVISOR.value,
        "se escalo sin un error registrado; es un fallo del propio orquestador",
        recuperable=False,
    ))


def escalate_no_changes(state: RunState) -> dict:
    """El Coder no produjo cambios, asi que no hay nada que probar ni revisar."""
    return _escalar(
        state,
        _error(
            state,
            "CODER_PRODUCED_NO_CHANGES",
            AgentRole.CODER.value,
            "el Coder no produjo ningun cambio; en M1 es lo esperado al no haber modelo",
            recuperable=False,
        ),
    )


def finalize(state: RunState) -> dict:
    """Cierra la ejecucion.

    Respeta un estado terminal ya fijado: si un nodo anterior escalo, finalizar no
    debe convertir ese `needs_human` en un `completed` exitoso.
    """
    if state.status.is_terminal:
        return {"updated_at": _ahora()}

    cambios = [f"{c.path} (+{c.added}/-{c.removed})" for c in state.artifacts.changed_files]
    pruebas = [
        f"{p.target}: exit {p.exit_code} en {p.duration_s:.2f}s" for p in state.evidence.test_runs
    ]
    revision = state.outputs.reviewer_output
    pendientes = list(
        state.outputs.researcher_output.unknowns if state.outputs.researcher_output else []
    )

    informe = FinalReport(
        summary=(
            f"ejecucion completada con intencion "
            f"'{state.interpretation.intent.value if state.interpretation else 'desconocida'}'"
        ),
        changes_applied=cambios,
        tests_executed=pruebas,
        review=revision.summary if revision else "no se ejecuto revision",
        pending=pendientes,
    )
    return {
        "final_report": informe,
        "status": RunStatus.COMPLETED,
        "next_step": None,
        "updated_at": _ahora(),
    }


# ------------------------------------------------------------------ enrutado


def route_intent(state: RunState) -> str:
    """Mapea la intencion al nodo de destino **de la rama de trabajo**.

    Antes de F4 esta funcion era la arista de salida de `interpret`. Ahora esa
    arista es `route_after_interpret`, que decide primero si hay que planificar.
    Se conserva porque es el mapa puro intencion -> nodo y sigue siendo la
    referencia de a donde va cada intencion una vez planificada; eliminarla
    dejaria el mapeo sin una unica fuente de verdad.
    """
    intencion = state.interpretation.intent if state.interpretation else Intent.INSPECT
    return {
        Intent.QUESTION: "researcher",
        Intent.INSPECT: "researcher",
        Intent.MODIFY: "researcher",
        Intent.OUT_OF_SCOPE: "explain_limits",
    }[intencion]


def route_after_interpret(state: RunState) -> str:
    """Tras interpretar: planificar, o explicar los limites. **Nunca las dos.**

    Una instruccion fuera de alcance no se planifica. Planificar algo que el sistema
    ya sabe que no va a hacer produciria un plan que no corresponde a ninguna accion
    posible, y ademas gastaria una llamada al modelo para justificar una negativa.
    La rama `explain_limits` explica por que no se puede, que es la respuesta util.
    """
    intencion = state.interpretation.intent if state.interpretation else Intent.INSPECT
    if intencion is Intent.OUT_OF_SCOPE:
        return "explain_limits"
    return "plan"


def route_after_plan(state: RunState) -> str:
    """Tras planificar, se empieza por el agente de la primera subtarea.

    Se enruta por la **primera subtarea del plan** en lugar de asumir `researcher`,
    de modo que un plan que empiece por otro agente no se contradiga con la
    topologia. Si no hay plan -no deberia ocurrir, el nodo siempre produce uno- se
    cae a `researcher`, que es el comienzo seguro.
    """
    if state.plan is None or not state.plan.subtasks:
        return "researcher"
    return state.plan.subtasks[0].agent.value


def route_after_execution(state: RunState) -> str:
    """Enrutador iterativo (F5). Decide el siguiente nodo tras ejecutar una subtarea.

    Lee `plan_index` para saber cuantas subtareas se han completado, y elige el
    agente de la siguiente. Si no quedan subtareas, finaliza.

    **Por que no un nodo `next_subtask`.** El enrutador es puro: no tiene efectos
    secundarios, no gasta presupuesto, no llama al modelo. Un nodo extra solo
    anadiria un paso vacio al grafo y un punto de friccion al checkpoint. El
    enrutador condicional de LangGraph esta disenado exactamente para esto.
    """
    # Si no hay plan, no hay iteracion: se cae a la ruta estatica de M1.
    if state.plan is None or not state.plan.subtasks:
        return _ruta_estatica_m1(state)

    # Si aun quedan subtareas por ejecutar, se va a la siguiente.
    if state.plan_index < len(state.plan.subtasks):
        siguiente = state.plan.subtasks[state.plan_index]
        return siguiente.agent.value

    # Plan agotado: se finaliza. El plan ya dicto todo lo que habia que hacer;
    # la ruta estatica de M1 no aplica porque el plan es la fuente de verdad.
    return "finalize"


def _ruta_estatica_m1(state: RunState) -> str:
    """Ruta de cierre cuando NO hay plan (compatibilidad M1, F5 no aplica)."""
    intencion = state.interpretation.intent if state.interpretation else Intent.INSPECT
    if intencion is Intent.MODIFY:
        return "coder"
    if intencion is Intent.QUESTION:
        return "answer_direct"
    return "finalize"


def route_after_research(state: RunState) -> str:
    intencion = state.interpretation.intent if state.interpretation else Intent.INSPECT
    if intencion is Intent.MODIFY:
        return "coder"
    if intencion is Intent.QUESTION:
        return "answer_direct"
    return "finalize"


def route_after_coder(state: RunState) -> str:
    """Un cambio propuesto va al sandbox; sin cambios, no hay nada que probar.

    F8 introduce `apply_sandbox` entre el Coder y las pruebas: el parche debe
    existir en un arbol de trabajo **antes** de que `run_tests` pueda ejercitarlo.
    Antes de F8 esta arista iba directo a `run_tests`, que no tenia donde correr.
    """
    salida = state.outputs.coder_output
    return "apply_sandbox" if salida and salida.files_changed else "escalate_no_changes"


def route_after_apply(state: RunState) -> str:
    """Si el cambio se aplico, se prueba; si el sandbox fallo, se cierra.

    Un fallo del sandbox ya dejo el estado en terminal (`needs_human`) con su error
    tipado. Se comprueba el estado y no el resultado del nodo: el nodo solo devuelve
    un delta, y la unica fuente de verdad de "ocurrio un fallo" es `RunState.status`.
    """
    return "finalize" if state.status.is_terminal else "run_tests"


def route_after_tests(state: RunState) -> str:
    return "finalize" if state.status.is_terminal else "reviewer"


def route_after_review(state: RunState) -> str:
    veredicto = state.outputs.reviewer_output
    if veredicto is None:
        return "escalate"
    if veredicto.decision is ReviewDecision.REQUEST_CHANGES:
        return "coder" if state.budget.review_cycles_used < state.budget.max_review_cycles else "escalate"
    if veredicto.decision is ReviewDecision.ACCEPT:
        return "mark_awaiting"
    return "escalate"
