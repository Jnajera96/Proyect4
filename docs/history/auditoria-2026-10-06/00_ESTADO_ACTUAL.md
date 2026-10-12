> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 00 — Estado actual verificado

Fecha de referencia: **2026-10-06**.

## Implementado y verificado
- FastAPI.
- LangGraph `StateGraph(RunState)`.
- Persistencia SQLite + checkpointer.
- Worker en pool de hilos.
- SSE y eventos persistentes.
- Frontend funcional servido en el mismo origen.
- HITL con aprobación y rechazo.
- Policy Engine con denegación por defecto.
- Confinamiento de rutas.
- 153 pruebas pasando.
- 24/24 mutaciones detectadas.

## Parcial
- Researcher: lectura real del repo, sin recuperación semántica.
- Reviewer: determinista, sin revisión semántica del diff.
- STT: contrato + `FakeAdapter`; adapter real pendiente.
- Observabilidad: eventos persistentes, sin Langfuse/logs JSON/métricas.

## No implementado
- LLM.
- Requirements Analyst real.
- Supervisor con razonamiento.
- Coder real.
- Test Runner real.
- Tool Executor real.
- MCP.
- Graphify / Knowledge Graph.
- Memoria semántica.
- Autenticación.
- Redacción de secretos.
