> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 10 — Evaluación single-agent vs multi-agent

## Pregunta central
¿Cuándo se justifica varios agentes y cuándo un único agente/workflow es más simple, barato y confiable?

## Suite recomendada
Crear 10–20 tareas controladas: bugfix, endpoint, validación, test, refactor pequeño, documentación, configuración, revisión de seguridad.

Ejecutar cada tarea con:
- A: single-agent
- B: multi-agent

## Métricas
- éxito,
- tests aprobados,
- defectos detectados,
- ciclos Coder↔Reviewer,
- tokens,
- costo,
- latencia,
- tool calls,
- HITL,
- escalamiento,
- violaciones de política,
- terminación correcta.

Las métricas deben provenir de evidencia de ejecución.
