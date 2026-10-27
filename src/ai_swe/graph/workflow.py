"""Ensamblado del grafo de orquestacion.

Topologia (docs/03-flujo-e-implementacion.md, seccion 3.5):

    START -> interpret
      interpret --fuera de alcance?--> explain_limits | confirmar requisitos | plan
      explain_limits -> finalize
      mark_awaiting_requirements -> confirm_requirements_gate
      confirm_requirements_gate --confirmado?--> plan | finalize (rechazado)
      plan --primera subtarea--> researcher
      researcher --siguiente subtarea?--> <agente> | finalize
      coder --hay cambios?--> apply_sandbox | escalate_no_changes
      escalate_no_changes -> finalize
      apply_sandbox --aplicado?--> run_tests | finalize
      run_tests --terminal?--> finalize | reviewer
      reviewer --veredicto--> coder | escalate | mark_awaiting
      escalate -> finalize
      mark_awaiting -> approval_gate
      approval_gate --ACCEPT--> promote_changes -> finalize
      approval_gate --REQUEST_CHANGES--> coder
      approval_gate --REJECT/terminal--> finalize
      finalize -> END

Invariantes que la topologia hace cumplir por si misma:

  - **Solo el Coder lleva a escritura.** No hay arista desde `researcher` ni desde
    `reviewer` hacia un nodo con efectos. La separacion de permisos esta en la
    forma del grafo, no solo en un prompt.
  - **La unica arista al repositorio del usuario pasa por la puerta humana.** El
    nodo `promote_changes` (F12) es el unico que escribe fuera del sandbox, y su
    unica arista de entrada es `approval_gate`. No hay camino que lo alcance sin una
    decision humana explicita.
  - **Dos puertas humanas, en dos momentos distintos (M2).** `confirm_requirements_gate`
    confirma lo que el sistema **entendio**, antes de planificar; `approval_gate`
    aprueba lo que el sistema **hizo**, despues de probarlo. Ninguna se puede saltar:
    la unica arista hacia `plan` desde la rama de interpretacion pasa por la primera,
    y la unica arista hacia el repositorio del usuario pasa por la segunda.
  - **El ciclo de revision esta acotado.** El nodo `reviewer` (F9) aplica la guarda
    determinista: un `REQUEST_CHANGES` sin ciclos disponibles se convierte en
    `ESCALATE`. El router `route_after_review` solo traduce el veredicto ya
    definitivo a una ruta, asi que no puede volver al Coder mas alla del limite.
  - **Una instruccion fuera de alcance no se planifica** (`F4`). `route_after_interpret`
    la manda a `explain_limits`: planificar lo que el sistema ya sabe que no hara
    produciria un plan sin accion posible, y gastaria una llamada al modelo para
    justificar una negativa.

**El plan es dato, no topologia (`F4`).** `RunPlan` se guarda en `RunState.plan`,
pero el grafo tiene una forma **fija**: las aristas estan escritas arriba y no se
generan a partir del plan. Por eso ningun plan -ni circular ni gigante- puede crear
un bucle en la ejecucion, y el contrato `RunPlan` (ids unicos, dependencias
existentes, DFS de ciclos, maximo de 32 subtareas) acota el dato antes de que entre
al estado.

**Iteracion por subtareas (`F5`).** El enrutador `route_after_execution` lee
`plan_index` para saber cuantas subtareas se han completado, y envia al agente de
la siguiente. El indice avanza en el nodo ejecutor, no en el router: el router solo
compara, nunca calcula. Cuando el plan se agota, se cae a la ruta estatica de M1.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ai_swe.contracts import RunState
from ai_swe.graph import nodes


def construir_grafo(*, settings=None) -> StateGraph:
    grafo = StateGraph(RunState)

    def configured_node(node):
        if settings is None:
            return node
        from ai_swe.graph.model_routing import bind_settings_node

        return bind_settings_node(node, settings)

    def model_node(node, role):
        if settings is None or (not settings.remote_model_roles and not settings.profile_id):
            return configured_node(node)
        from ai_swe.graph.model_routing import bind_model_node

        return bind_model_node(node, role, settings, nodes.SIN_GATEWAY)

    grafo.add_node("interpret", model_node(nodes.interpret, "requirements_analyst"))
    grafo.add_node("mark_awaiting_requirements", nodes.mark_awaiting_requirements)
    grafo.add_node("confirm_requirements_gate", nodes.confirm_requirements_gate)
    grafo.add_node("plan", model_node(nodes.plan, "supervisor"))
    grafo.add_node("researcher", configured_node(nodes.researcher))
    grafo.add_node("answer_direct", nodes.answer_direct)
    grafo.add_node("explain_limits", nodes.explain_limits)
    grafo.add_node("coder", model_node(nodes.coder, "coder"))
    grafo.add_node("apply_sandbox", configured_node(nodes.apply_sandbox))
    grafo.add_node("run_tests", configured_node(nodes.run_tests))
    grafo.add_node("reviewer", model_node(nodes.reviewer, "reviewer"))
    grafo.add_node("mark_awaiting", nodes.mark_awaiting)
    grafo.add_node("approval_gate", nodes.approval_gate)
    grafo.add_node("promote_changes", configured_node(nodes.promote_changes))
    grafo.add_node("escalate", nodes.escalate)
    grafo.add_node("escalate_no_changes", nodes.escalate_no_changes)
    grafo.add_node("finalize", nodes.finalize)

    grafo.add_edge(START, "interpret")
    grafo.add_conditional_edges("interpret", nodes.route_after_interpret)
    grafo.add_edge("mark_awaiting_requirements", "confirm_requirements_gate")
    grafo.add_conditional_edges(
        "confirm_requirements_gate", nodes.route_after_requirements_gate
    )
    grafo.add_conditional_edges("plan", nodes.route_after_plan)
    grafo.add_edge("explain_limits", "finalize")
    grafo.add_conditional_edges("researcher", nodes.route_after_execution)
    grafo.add_edge("answer_direct", "finalize")
    grafo.add_conditional_edges("coder", nodes.route_after_coder)
    grafo.add_edge("escalate_no_changes", "finalize")
    grafo.add_conditional_edges("apply_sandbox", nodes.route_after_apply)
    grafo.add_conditional_edges("run_tests", nodes.route_after_tests)
    grafo.add_conditional_edges("reviewer", nodes.route_after_review)
    grafo.add_edge("escalate", "finalize")
    grafo.add_edge("mark_awaiting", "approval_gate")
    grafo.add_conditional_edges("approval_gate", nodes.route_after_approval)
    grafo.add_edge("promote_changes", "finalize")
    grafo.add_edge("finalize", END)

    return grafo


def compilar(store, *, settings=None):
    """Compila el grafo con el checkpointer del almacen."""
    return construir_grafo(settings=settings).compile(checkpointer=store.checkpointer())
