"""Orquestacion con LangGraph: nodos, aristas, motor y transiciones.

Invariantes que la topologia hace cumplir (docs/03-flujo-e-implementacion.md, 3.5):
  - El Researcher y el Reviewer no tienen aristas hacia nodos de escritura.
  - Toda promocion pasa por la puerta de aprobacion.
  - `max_review_cycles` se evalua en la arista condicional.
  - Toda ejecucion termina en un estado terminal o en `awaiting_approval`
    (`MET-13 = 0`), garantizado por la red de seguridad del motor y no solo por
    la forma del grafo.
"""

from ai_swe.graph.engine import NothingToResume, RunEngine, RunNotFound, nuevo_run_id
from ai_swe.graph.worker import RunWorker
from ai_swe.graph.workflow import compilar, construir_grafo

__all__ = [
    "NothingToResume",
    "RunEngine",
    "RunNotFound",
    "RunWorker",
    "compilar",
    "construir_grafo",
    "nuevo_run_id",
]
