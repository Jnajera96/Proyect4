# Índice de documentación

## Cierre v0.1.0

Entrega canónica y alcance local aprobado: [producto](PRODUCT-v0.1.0.md),
[instalación](INSTALLATION-WINDOWS.md), [matriz](RELEASE-MATRIX-v0.1.0.md),
[limitaciones](KNOWN-LIMITATIONS-v0.1.0.md) y [evidencia SAC](SAC-DISTRIBUTION-EVIDENCE.json).
Se conserva la estructura académica y sus formatos editables originales.

**Entrega organizada:** [estructura](ESTRUCTURA-DE-ENTREGA.md),
[SRS IEEE 830](SRS/README.md), [arquitectura](arquitectura/README.md),
[administración](administracion/README.md), [estimación](estimacion/README.md)
y [diagramas](../diagramas/README.md). Se omiten las carpetas documentales de
pruebas y métricas según solicitud del usuario.

> **Único índice del proyecto.** Creado en la Fase 1 del plan de evolución
> controlada. Sustituye a los índices duplicados (`01-ARCHITECTURE.md`,
> `02-CONTRACTS.md`, `03-SECURITY.md`, `04-ROADMAP.md`, `05-DECISIONS.md`), que se
> archivaron en `history/`.

---

## Estado verificado del proyecto

Para orientarse durante la productización pausada: [mapa y guía de lectura](MAPA-DEL-PROYECTO.md),
[progreso actual](PRODUCTIZATION-PROGRESS.md) y [punto de reanudación](RESUME-PRODUCTIZATION-v0.1.0.md).
El laboratorio está preparado parcialmente; no confundir catálogo con benchmarks reales.

| Fuente | Qué es |
|---|---|
| [`RELEASE-CANDIDATE-PHASE-C.md`](RELEASE-CANDIDATE-PHASE-C.md) | Candidato local de entrega, correcciones reproducidas y límites de Fase C |
| [`../PROJECT_SNAPSHOT.json`](../PROJECT_SNAPSHOT.json) | **Fuente estructurada del estado**: fases, métricas, deudas `AUD-xx`, mutaciones |
| [`audit/00-EXECUTIVE-AUDIT.md`](audit/00-EXECUTIVE-AUDIT.md) | Auditoría integral de solo lectura (2026-10-12) |
| [`audit/FINAL-PROJECT-AUDIT.md`](audit/FINAL-PROJECT-AUDIT.md) | Informe maestro de esa auditoría |
| [`BASELINE-PRE-STABILIZATION.md`](BASELINE-PRE-STABILIZATION.md) | Baseline congelado antes de la evolución controlada |

---

## Documentación vigente

### Diseño y arquitectura (canónicos — referenciados desde el código)

| Documento | Contenido |
|---|---|
| [`00-PROJECT-BRIEF.md`](00-PROJECT-BRIEF.md) | Problema, objetivos y alcance |
| [`01-arquitectura.md`](01-arquitectura.md) | Arquitectura, decisiones `DEC-xx`, requisitos `RF-xx`/`RNF-xx`, métricas `MET-01..14`, experimentos `EXP-01..08` |
| [`02-tecnologias.md`](02-tecnologias.md) | Selección de tecnologías con las ocho preguntas de justificación |
| [`03-flujo-e-implementacion.md`](03-flujo-e-implementacion.md) | Topología del grafo, flujo paso a paso y plan de fases |
| [`04-defensa.md`](04-defensa.md) | Preguntas del tribunal con la respuesta técnica preparada |
| [`05-graphify-evaluacion.md`](05-graphify-evaluacion.md) | Evaluación de Graphify como capa de contexto (propuesta `[PROP]`, **no implementada**) |
| [`07-contrato-frontend-backend.md`](07-contrato-frontend-backend.md) | Contrato entre el frontend y el backend |

> **Nota de numeración.** Este documento se llamaba `06-contrato-frontend-backend.md`
> y chocaba con `06-EVALUATION.md` (generado). Se renumeró a `07-` en la Fase 1.
> Las rutas canónicas `01-arquitectura.md`, `02-tecnologias.md`,
> `03-flujo-e-implementacion.md` y `MODEL-GATEWAY-DESIGN.md` **no se renombran**
> porque están citadas desde el código (`src/`, `frontend/contracts.json`,
> `pyproject.toml`, `Dockerfile`, `docker-compose.yml`).

### Modelo (F2)

| Documento | Contenido |
|---|---|
| [`MODEL-GATEWAY.md`](MODEL-GATEWAY.md) | Referencia de uso: contratos, adapters, errores, retry, fallback, presupuesto, structured output |
| [`MODEL-GATEWAY-DESIGN.md`](MODEL-GATEWAY-DESIGN.md) | Diseño previo y su justificación |

### Generados (no editar a mano)

| Documento | Generado por |
|---|---|
| [`06-EVALUATION.md`](06-EVALUATION.md) | `src/ai_swe/evaluation/runner.py` — resultados `EXP-01` single vs multi agent |
| [`diagrama-arquitectura.svg`](diagrama-arquitectura.svg) / [`.png`](diagrama-arquitectura.png) | `tools/build_diagram.py` |

### Baselines de la evolución controlada

| Documento | Fase |
|---|---|
| [`BASELINE-PRE-STABILIZATION.md`](BASELINE-PRE-STABILIZATION.md) | Fase 0 — baseline congelado |

> Los baselines de las fases anteriores (`F1`..`F14`) están en `history/`.

---

## `audit/` — Auditoría integral (2026-10-12)

36 documentos de solo lectura sobre el commit `065db452`. Es el **punto de partida
técnico** del plan de evolución. Empieza por
[`audit/00-EXECUTIVE-AUDIT.md`](audit/00-EXECUTIVE-AUDIT.md).

| Grupo | Documentos |
|---|---|
| Resumen | `00-EXECUTIVE-AUDIT`, `FINAL-PROJECT-AUDIT`, `AUDIT-SNAPSHOT.json` |
| Inventario | `01-FILE-INVENTORY` (+ `file-inventory.json`), `02-FUNCTIONAL-INVENTORY`, `03-INTERNAL-DEPENDENCY-MAP`, `04-CLEANUP-CANDIDATES` |
| Subsistemas | `05-DOCUMENTATION-AUDIT` … `15-FRONTEND-AUDIT` |
| Frontend | `16-FRONTEND-BACKEND-MAPPING`, `17-FRONTEND-CAPABILITY-PLAN`, `31-FRONTEND-FUNCTIONAL-SPEC`, `32-FRONTEND-DESIGN-READINESS` |
| Seguridad | `19-THREAT-MODEL`, `20-SECURITY-RISK-REGISTER`, `21-CYBERSECURITY-MATURITY`, `22-CYBERSECURITY-HARDENING-PLAN` |
| Operación | `18-USER-ACTIONS-REQUIRED`, `23-INFRASTRUCTURE-AUDIT` … `27-DATA-PRIVACY-AUDIT` |
| Cierre | `28-FEATURE-GAP-ANALYSIS`, `29-PROJECT-COMPLETENESS-MATRIX`, `30-PROPOSED-CLEAN-ARCHITECTURE` |

---

## `history/` — Evidencia histórica

**No es documentación vigente.** Se conserva porque es la prueba de lo que se hizo y
por qué.

| Documento | Qué fue |
|---|---|
| `BASELINE-M1-POST-DOCUMENTACION.md` | Cierre de M1 |
| `BASELINE-PRE-M2.md` | Cierre de F1 (reproducibilidad + hardening) |
| `BASELINE-MODEL-GATEWAY.md` | Cierre de F2 |
| `BASELINE-F3-REQUIREMENTS-ANALYST.md`, `BASELINE-F4-SUPERVISOR.md`, `BASELINE-F6-REAL-CODER.md`, `BASELINE-F7-SANDBOX.md` | Actas de cierre de fase |
| `AUDITORIA-EXTERNA.md` | Auditoría técnica externa del 2026-10-06 (origen de `AUD-01..14`) |
| `AUDITORIA-F2-PARA-ARQUITECTO.md` | Entrega puntual de F2 |
| `auditoria-2026-10-06/` | Conjunto documental original (17 ficheros) |
| `01-ARCHITECTURE.md` … `05-DECISIONS.md` | Índices de nomenclatura en inglés, **duplicados** de los canónicos en español |

---

## Cómo decidir qué consultar

- **«¿Esto funciona?»** → `audit/AUDIT-SNAPSHOT.json` y `PROJECT_SNAPSHOT.json`.
- **«¿Qué está mal y qué lo arregla?»** → `audit/20-SECURITY-RISK-REGISTER.md` y `audit/28-FEATURE-GAP-ANALYSIS.md`.
- **«¿Por qué se decidió así?»** → `01-arquitectura.md` (decisiones `DEC-xx`).
- **«¿Cómo se defiende esto?»** → `04-defensa.md`.
- **«¿Qué se hizo en la fase X?»** → `history/BASELINE-*.md`.

## Regla ante contradicción

Prevalece, en este orden: **comportamiento ejecutado → tests → código conectado al
runtime → contratos → configuración efectiva → documentación vigente →
`docs/audit/` → documentación histórica → comentarios**.

Una afirmación de estado que no esté respaldada por una ejecución o una prueba se
considera **no verificada**.
