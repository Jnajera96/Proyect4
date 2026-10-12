> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera y, más abajo, el estado real de cada fase.
> Ver `_PROCEDENCIA.txt`.

# 09 — Roadmap actualizado

**Estado real a 2026-10-06 (tras cerrar `F1` y `F2`):**

| Fase | Estado |
|---|---|
| `F0` — Git y respaldo | ✅ hecha |
| `F1` — Reproducibilidad | ✅ hecha |
| `F2` — Model Gateway | ✅ **hecha** (frontera única; **no conectada todavía** a LangGraph) |
| `F3` — Requirements Analyst | ⬜ siguiente, **no iniciada** |
| `F4`–`F16` | ⬜ no iniciadas |

Evidencia del cierre de `F1`: [`../BASELINE-PRE-M2.md`](../BASELINE-PRE-M2.md).
Evidencia del cierre de `F2`: [`../BASELINE-MODEL-GATEWAY.md`](../BASELINE-MODEL-GATEWAY.md).
Referencia de uso del gateway: [`../MODEL-GATEWAY.md`](../MODEL-GATEWAY.md).

**Nota sobre `M2`:** el hito `M2` (agentes reales) está **en progreso**: `F2` es su
primera fase y está terminada, pero ningún nodo de LangGraph llama todavía al
gateway. Eso es deliberado: permite comprobar que `F2` no degradó `M1`.

## F0 — Git y respaldo
Repositorio propio para `proyecto4-ai-swe`; commit del estado M1.

## F1 — Reproducibilidad
Lockfile, versión de Python, manifiesto de dependencias.

## F2 — Model Gateway
Structured output, retries, fallback, budget, secretos.

## F3 — Requirements Analyst
Requisitos estructurados + confirmación humana.

## F4 — Supervisor real
`RunPlan`, `Subtask`, dependencias.

## F5 — Researcher semántico
Evidencia relevante.

## F6 — Coder de propuesta
Generar `CodeChange`, sin escritura principal.

## F7 — Worktree/Sandbox + Tool Executor
Policy en cada tool call.

## F8 — Test Runner real
Evidencia de pruebas.

## F9 — Reviewer semántico
Requisitos + diff + tests + ciclo de corrección.

## F10 — MVP E2E
Requirements → Plan → Research → Code → Tests → Review → HITL → Final.

## F11 — Evaluación single vs multi-agent
Suite controlada y métricas.

## F12 — Graphify / Knowledge Graph
Solo si mejora contexto de forma medible.

## F13 — MCP
Después de tools básicos.

## F14 — STT real
Faster-whisper u otro adapter real.

## F15 — Observabilidad
Langfuse/logs JSON/métricas/redacción.

## F16 — Auth y exposición
Antes de LAN/Internet.
