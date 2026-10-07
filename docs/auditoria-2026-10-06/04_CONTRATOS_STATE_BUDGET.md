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
