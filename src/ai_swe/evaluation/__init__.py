"""Arnes de evaluacion y metricas (F14).

**Que hay aqui.**

  - `tasks.py`  — el catalogo de tareas controladas (`EXP-01`..`EXP-12`) con su
    criterio de exito objetivo: una suite de validacion que falla antes del cambio y
    pasa despues.
  - `runner.py` — el arnes que ejecuta esa bateria bajo `SINGLE_AGENT` y
    `MULTI_AGENT`, recolecta metricas tipadas de **evidencia de ejecucion** y genera
    `var/evaluation_results.json` y `docs/06-EVALUATION.md`.

Metricas: MET-01 a MET-14 (docs/01-arquitectura.md, seccion 18.1).
Experimentos: EXP-01 a EXP-08 (seccion 18.3).

El arnes ejecuta la **misma** suite de tareas bajo distintas configuraciones y
produce una tabla comparativa. Eso es lo que convierte la defensa de Multi-Agent en
evidencia y no en opinion:

  EXP-01  un agente vs. multiagente  <- implementado aqui
  EXP-02  con y sin Reviewer
  EXP-03  con y sin MCP
  EXP-06  eficacia de los guardrails (conjunto adversarial)
"""

from ai_swe.evaluation.runner import (
    InformeEvaluacion,
    MetricasCorrida,
    Modo,
    ResultadoTarea,
    compilar_single_agent,
    construir_grafo_single_agent,
    ejecutar_bateria,
    ejecutar_corrida,
    escribir_resultados,
    generar_informe,
    materializar_repo,
)
from ai_swe.evaluation.tasks import TAREAS, EvalTask, tarea_por_id

__all__ = [
    "TAREAS",
    "EvalTask",
    "InformeEvaluacion",
    "MetricasCorrida",
    "Modo",
    "ResultadoTarea",
    "compilar_single_agent",
    "construir_grafo_single_agent",
    "ejecutar_bateria",
    "ejecutar_corrida",
    "escribir_resultados",
    "generar_informe",
    "materializar_repo",
    "tarea_por_id",
]
