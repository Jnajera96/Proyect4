> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 04 — Contratos, State y Budget

## Regla
Todo cruce entre módulos debe usar contratos validados.

`RunState` ya contiene campos como `run_id`, `trace_id`, `instruction`, `interpretation`, `plan`, `outputs`, `artifacts`, `evidence`, `approvals`, `errors`, `budget`, `final_report`, `status`, `next_step` y `schema_version`.

## Para M2
- No sustituir `RunState` por historial de chat.
- Reutilizar `RunPlan` y `Subtask`.
- El Coder debe producir `CodeChange`.
- Reviewer debe producir un veredicto estructurado.
- Todo output LLM debe validar con Pydantic.
- Cada llamada de modelo y herramienta debe consumir presupuesto.

## Budget mínimo
- `max_tokens` / `used_tokens`
- `max_calls` / `used_calls`
- `max_cost` / `used_cost`
- `max_seconds` / `deadline`

Ningún agente puede saltarse el presupuesto.

## Estado real del `Budget` (cerrado en `F1`)

Lo anterior era el mínimo deseado. El `Budget` implementado
(`src/ai_swe/contracts/state.py`) cubre ese mínimo con nombres algo distintos y
**más granularidad**, separando llamadas a herramienta de llamadas al modelo
porque el coste y el riesgo son distintos:

| Deseado | Implementado |
|---|---|
| `max_tokens` / `used_tokens` | ✅ `max_tokens` / `used_tokens` |
| `max_calls` / `used_calls` | ✅ desdoblado: `max_tool_calls`/`used_tool_calls` **y** `max_model_calls`/`used_model_calls` |
| `max_cost` / `used_cost` | ✅ `max_cost` (`None` = sin límite) / `used_cost` |
| `max_seconds` / `deadline` | ✅ `max_seconds` / `elapsed_seconds` |
| — | ✅ `max_review_cycles` / `review_cycles_used` |

**Notas de diseño (por qué así):**

- `max_cost = None` significa «sin límite declarado», **distinto de cero**, que
  significa «no se permite gastar nada».
- Los contadores viven en el estado persistido, no en quien llama al modelo: si
  vivieran solo en el llamante, una reanudación tras un corte arrancaría a cero y
  volvería a gastar lo ya gastado.
- `exhausted_reasons()` devuelve la **lista de motivos**, no un booleano: hay que
  poder decir *por qué* se detuvo el sistema, no solo que se detuvo.
- Los campos nuevos entran **con valor por defecto**, así que **no** hicieron falta
  subir `ESQUEMA_VERSION` ni migrar nada.

Evidencia y verificación: [`../BASELINE-PRE-M2.md`](../BASELINE-PRE-M2.md) §12.
