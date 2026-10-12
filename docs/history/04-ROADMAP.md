# 04 — Roadmap

> **Capa de índice.** Alias de nomenclatura. La definición de las fases está en
> [`auditoria-2026-10-06/09_ROADMAP.md`](auditoria-2026-10-06/09_ROADMAP.md);
> el **estado real** es el de esta tabla, y su fuente estructurada es
> [`PROJECT_SNAPSHOT.json`](../PROJECT_SNAPSHOT.json).

## Estado real (2026-10-08)

| Fase | Descripción | Estado |
|---|---|---|
| `F0` | Git y respaldo | ✅ hecha |
| `F1` | Reproducibilidad | ✅ hecha |
| `F2` | Model Gateway | ✅ hecha |
| `F3` | Requirements Analyst | ✅ hecha — commit `00c52a1` |
| `F4` | Supervisor real (`RunPlan`) | ✅ hecha — commit `fc2c68f` |
| `F5` | Ejecución guiada por el plan | ✅ hecha — commit `2ff2c7d` |
| `F6` | Coder de propuesta (`CodeProposal`) | ✅ hecha — commit `211eb90` |
| `F7` | Sandbox / Worktree + Tool Executor | ✅ hecha |
| `F8` | Test Runner real | ⬜ **siguiente** |
| `F9` | Reviewer semántico | ⬜ no iniciada |
| `F10` | MVP E2E | ⬜ no iniciada |
| `F11`–`F16` | Evaluación, MCP, STT, observabilidad… | ⬜ no iniciadas |

> El `09_ROADMAP.md` de `auditoria-2026-10-06/` refleja el estado **a
> 2026-10-06** (con `F3` como «no iniciada»). Es correcto como registro
> histórico; esta tabla es la que está al día.

## Definition of Done de M2

Fuente: [`auditoria-2026-10-06/11_DEFINITION_OF_DONE_M2.md`](auditoria-2026-10-06/11_DEFINITION_OF_DONE_M2.md).

M2 cierra cuando una tarea controlada recorre entrada → requisitos → confirmación
humana → `RunPlan` → research → `CodeChange` → **cambio aplicado en workspace
aislado** → **tests ejecutados** → **revisión** → ciclo acotado → `ACCEPT` → HITL →
estado terminal → persistencia.

**11 de 15 ítems cumplidos.** Los que faltan:

| Ítem | Estado | Fase que lo cierra |
|---|---|---|
| 3 — Confirmación humana de requisitos | ⬜ | por definir (hoy el HITL es de aprobación del cambio) |
| 7 — Cambio aplicado en workspace aislado | ⬜ | `M3` (cablear el sandbox al grafo) |
| 8 — Test Runner ejecuta targets autorizados | ⬜ | `F8` |
| 9 — Reviewer evalúa requisitos + cambio + tests | ⬜ | `F9` |

## Fuera de alcance de M2 (deliberadamente)

Graphify, MCP, STT real, memoria semántica y despliegue cloud.
