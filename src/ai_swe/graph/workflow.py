"""Ensamblado del grafo de orquestacion.

Topologia (docs/03-flujo-e-implementacion.md, seccion 3.5):

    START -> interpret
      interpret --fuera de alcance?--> explain_limits | plan
      explain_limits -> finalize
      plan --primera subtarea--> researcher
      researcher --intencion--> coder | answer_direct | finalize
      answer_direct -> finalize
      coder --hay cambios?--> run_tests | escalate_no_changes
      escalate_no_changes -> finalize
      run_tests --terminal?--> finalize | reviewer
      reviewer --veredicto--> coder | escalate | mark_awaiting
      escalate -> finalize
      mark_awaiting -> approval_gate
      approval_gate -> finalize
      finalize -> END

Invariantes que la topologia hace cumplir por si misma:

  - **Solo el Coder lleva a escritura.** No hay arista desde `researcher` ni desde
    `reviewer` hacia un nodo con efectos. La separacion de permisos esta en la
    forma del grafo, no solo en un prompt.
  - **Toda promocion pasa por la puerta de aprobacion.** La unica arista que llega
    a `finalize` desde la rama de modificacion pasa por `approval_gate`.
  - **El ciclo de revision esta acotado.** `route_after_review` comprueba
    `review_cycles_used` contra `max_review_cycles`; agotado el limite va a
    `escalate`, no vuelve al Coder.
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
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ai_swe.contracts import RunState
from ai_swe.graph import nodes


def construir_grafo() -> StateGraph:
    grafo = StateGraph(RunState)

    grafo.add_node("interpret", nodes.interpret)
    grafo.add_node("plan", nodes.plan)
    grafo.add_node("researcher", nodes.researcher)
    grafo.add_node("answer_direct", nodes.answer_direct)
    grafo.add_node("explain_limits", nodes.explain_limits)
    grafo.add_node("coder", nodes.coder)
    grafo.add_node("run_tests", nodes.run_tests)
    grafo.add_node("reviewer", nodes.reviewer)
    grafo.add_node("mark_awaiting", nodes.mark_awaiting)
    grafo.add_node("approval_gate", nodes.approval_gate)
    grafo.add_node("escalate", nodes.escalate)
    grafo.add_node("escalate_no_changes", nodes.escalate_no_changes)
    grafo.add_node("finalize", nodes.finalize)

    grafo.add_edge(START, "interpret")
    grafo.add_conditional_edges("interpret", nodes.route_after_interpret)
    grafo.add_conditional_edges("plan", nodes.route_after_plan)
    grafo.add_edge("explain_limits", "finalize")
    grafo.add_conditional_edges("researcher", nodes.route_after_research)
    grafo.add_edge("answer_direct", "finalize")
    grafo.add_conditional_edges("coder", nodes.route_after_coder)
    grafo.add_edge("escalate_no_changes", "finalize")
    grafo.add_conditional_edges("run_tests", nodes.route_after_tests)
    grafo.add_conditional_edges("reviewer", nodes.route_after_review)
    grafo.add_edge("escalate", "finalize")
    grafo.add_edge("mark_awaiting", "approval_gate")
    grafo.add_edge("approval_gate", "finalize")
    grafo.add_edge("finalize", END)

    return grafo


def compilar(store):
    """Compila el grafo con el checkpointer del almacen."""
    return construir_grafo().compile(checkpointer=store.checkpointer())
