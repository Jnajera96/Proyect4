# 06 — Evaluation

> **Capa de índice.** Alias de nomenclatura. El contenido canónico vive en los
> documentos enlazados.

## Documentos

| Documento | Qué contiene |
|---|---|
| [`auditoria-2026-10-06/10_EVALUACION_METRICAS.md`](auditoria-2026-10-06/10_EVALUACION_METRICAS.md) | Suite de evaluación single-agent vs multi-agent y métricas |
| [`05-graphify-evaluacion.md`](05-graphify-evaluacion.md) | Evaluación de Graphify como capa de contexto (propuesta `[PROP]`, no implementada) |
| [`01-arquitectura.md`](01-arquitectura.md) §18 | Métricas `MET-01`..`MET-14` y experimentos `EXP-01`..`EXP-07` |

## La pregunta central

> ¿Cuándo se justifica usar varios agentes y cuándo un único agente o un flujo
> determinista es más simple, barato y fiable?

La respuesta se construye **con evidencia de ejecución**, no con opinión: la misma
suite de tareas se ejecuta bajo distintas configuraciones y se compara.

## Experimentos previstos

| ID | Comparación |
|---|---|
| `EXP-01` | Un agente vs. multiagente |
| `EXP-02` | Con y sin Reviewer |
| `EXP-03` | Con y sin MCP |
| `EXP-06` | Eficacia de los guardrails (conjunto adversarial) |

## Métricas

Éxito · tests aprobados · defectos detectados · ciclos Coder↔Reviewer · tokens ·
coste · latencia · *tool calls* · HITL · escalamiento · violaciones de política ·
terminación correcta.

**Todas deben provenir de evidencia de ejecución.** Es la misma regla que gobierna
los nodos: no se fabrica evidencia. Si una prueba no se ejecutó, la métrica no
existe; no se rellena con un valor plausible.

## Estado

| Componente | Estado |
|---|---|
| Arnés de evaluación (`src/ai_swe/evaluation/`) | **NOT_IMPLEMENTED** — solo docstring. Declarado para M2/M6 |
| Métricas derivables de la evidencia actual | Parcial: `TestRun` (target, exit code, duración) y el registro de eventos ya existen y son persistidos |
| Informe comparativo | **NOT_IMPLEMENTED** |

La evidencia **necesaria** ya se captura (es lo que hace `F8`); lo que falta es el
arnés que la agrega y la tabla comparativa.

## Verificación del propio sistema

Aparte de la evaluación comparativa, el proyecto se verifica con:

- **Suite offline** — 435 pruebas, sin red ni credenciales.
- **Mutación** — `tools/mutation_check.py`: se introduce cada fallo a propósito y se
  comprueba que alguna prueba falla. Un corte por tiempo **no** cuenta como
  mutación cazada.
- **Suposiciones de M1** — `tools/verify_m1_assumptions.py`.
- **Frontend** — `tools/verify_frontend.py` (arnés aparte, no incluido en pytest).
- **Reproducibilidad** — reconstrucción desde `uv.lock` en un entorno limpio.
