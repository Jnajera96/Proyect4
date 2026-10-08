# 00 — Project Brief

> **Capa de índice.** Este fichero existe para alinear la nomenclatura esperada
> (`00-PROJECT-BRIEF.md` … `06-EVALUATION.md`) con la documentación real del
> repositorio. **No sustituye a las fuentes**: cada sección apunta al documento
> canónico. Regla ante contradicción: prevalece el **código ejecutable**, después
> los **tests**, y solo entonces la documentación (`auditoria-2026-10-06/_PROCEDENCIA.txt`).

## Qué es

**AI Software Engineering System** (`proyecto4-ai-swe`). Sistema multiagente que
recibe una instrucción en lenguaje natural y la lleva por un flujo auditable:
interpretación de requisitos → plan → investigación → propuesta de cambio →
aplicación en un *sandbox* aislado → pruebas → revisión → aprobación humana.

El principio que gobierna todo el diseño:

> **El modelo propone; el código determinista valida.**

Ningún nodo escribe en el repositorio del usuario. Ninguna ruta se escribe sin
pasar por el Policy Engine. Ninguna prueba se declara superada sin haberse
ejecutado.

## Estado actual

| Campo | Valor |
|---|---|
| Fase | **M2 en progreso** — `F7` (Sandbox y Tool Executor) implementada y verificada |
| Última fase cerrada con commit | `F6` (`211eb90`) |
| Suite | **435 pruebas, 0 fallos, 1 skip** (`TD-01`) |
| Siguiente fase | `F8` — Test Runner real |
| Verdad sobre el estado | `PROJECT_SNAPSHOT.json` (**raíz del repositorio**) |

## Mapa de la documentación

| Documento pedido | Contenido | Fuente canónica |
|---|---|---|
| `00-PROJECT-BRIEF.md` | Este resumen | — |
| `01-ARCHITECTURE.md` | Arquitectura | [`01-arquitectura.md`](01-arquitectura.md), [`auditoria-2026-10-06/02_ARQUITECTURA_ACTUAL.md`](auditoria-2026-10-06/02_ARQUITECTURA_ACTUAL.md), [`03_ARQUITECTURA_OBJETIVO.md`](auditoria-2026-10-06/03_ARQUITECTURA_OBJETIVO.md) |
| `02-CONTRACTS.md` | Contratos de datos | [`auditoria-2026-10-06/04_CONTRATOS_STATE_BUDGET.md`](auditoria-2026-10-06/04_CONTRATOS_STATE_BUDGET.md), [`06-contrato-frontend-backend.md`](06-contrato-frontend-backend.md), `src/ai_swe/contracts/` |
| `03-SECURITY.md` | Seguridad | [`auditoria-2026-10-06/08_SEGURIDAD_SANDBOX_TOOLS.md`](auditoria-2026-10-06/08_SEGURIDAD_SANDBOX_TOOLS.md), [`AUDITORIA-EXTERNA.md`](AUDITORIA-EXTERNA.md) |
| `04-ROADMAP.md` | Fases | [`auditoria-2026-10-06/09_ROADMAP.md`](auditoria-2026-10-06/09_ROADMAP.md) |
| `05-DECISIONS.md` | Decisiones `DEC-xx` | [`05-DECISIONS.md`](05-DECISIONS.md) |
| `06-EVALUATION.md` | Evaluación y métricas | [`auditoria-2026-10-06/10_EVALUACION_METRICAS.md`](auditoria-2026-10-06/10_EVALUACION_METRICAS.md) |

## Índice general

[`README.md`](README.md) describe las **dos capas** de documentación del
repositorio y cómo decidir cuál consultar.
