> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 07 — Agentes de M2

## Requirements Analyst
Produce requisitos estructurados, detecta contradicciones y genera preguntas faltantes. Debe separar transcripción literal de requisitos interpretados. No crea código ni ejecuta tools.

## Supervisor
Genera `RunPlan`, divide en `Subtask`, resuelve dependencias y decide reintentar, reasignar o escalar.

## Researcher
Recupera evidencia relevante del repositorio y devuelve fuentes/ubicaciones. No debe limitarse a enumerar archivos.

## Coder
Produce `CodeChange` estructurado. En la primera iteración no escribe directamente en el proyecto principal.

## Reviewer
Evalúa **requisitos + cambio + evidencia de tests** y devuelve `ACCEPT`, `REQUEST_CHANGES` o `ESCALATE`.

El ciclo Coder ↔ Reviewer debe estar limitado por budget y `max_review_cycles`.
