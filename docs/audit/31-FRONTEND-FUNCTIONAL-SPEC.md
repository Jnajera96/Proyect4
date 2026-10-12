# 31 — Especificación funcional del frontend

> **Fuente de verdad para el rediseño.** Basada **exclusivamente** en capacidades
> verificadas del backend (ver `16-…`). **No es un diseño de UI.**
> Commit `065db452`.

## CORE — imprescindible

| # | Capacidad | Datos (ya existen) | Endpoint / evento | Requiere backend nuevo |
|---|---|---|---|---|
| C1 | **Dashboard** | Salud, fase, nº de ejecuciones y proyectos | `GET /health` | No |
| C2 | **Projects** — lista | `Project[]` | `GET /projects` | No |
| C3 | **New Project** — alta con validación | `ProjectRequest` → `Project` | `POST /projects` | No |
| C4 | **New Run** — instrucción + proyecto + **alcance** | `RunRequest` (`options.allowed_paths`, `protected_paths`) | `POST /runs` | No |
| C5 | **Run Detail** — estado y progreso | `RunState`, `RunEvent` | `GET /runs/{id}` + SSE | No |
| C6 | **Run Timeline** — hitos por nodo | `requirements/plan/coder/tests.completed` | SSE | No |
| C7 | **Plan** — subtareas con agente y estado | `RunPlan`, `Subtask.status` | `plan.completed` | No |
| C8 | **Requirements Gate** — ver / confirmar / corregir / rechazar | `TaskInterpretation` | `POST .../confirm-requirements` | No |
| C9 | **Approval Gate** — diff + evidencia + veredicto | `artifacts.diff`, `evidence.test_runs`, `reviewer_output` | `POST .../approve` | No |
| C10 | **Final Report** | `FinalReport` | `run.completed` | No |
| C11 | **Errors** — lista tipada | `RunError[]` | `run.failed` | No |

## ADVANCED — valor alto, datos ya disponibles

| # | Capacidad | Datos | Requiere backend |
|---|---|---|---|
| A1 | **Budget panel** — tokens in/out, coste, llamadas, ciclos usados/máx | `RunState.budget` | No |
| A2 | **Run History** — tabla filtrable | `RunSummary[]` | No |
| A3 | **Approvals audit** — actor, fecha, decisión, hash | `RunState.approvals` | No |
| A4 | **Test evidence detail** — `argv`, `stdout`, `stderr`, duración | `TestRun` | No |
| A5 | **Reviewer findings** — severidad, ruta, línea, evidencia | `ReviewVerdict.findings` | No |
| A6 | **Diff viewer** con resaltado por fichero | `CodeChange.diff` | No |
| A7 | **Security panel** — denegaciones de política | `RunError` (`POLICY_*`, `SANDBOX_PATH_DENIED`) | No |
| A8 | **Fallback warning** — «esta ejecución no usó el modelo» | `MODEL_FALLBACK` | No |
| A9 | **Voice input** — grabar → transcribir → **confirmar** | `Transcript`, `Instruction` | No |
| A10 | **STT status** — disponible / no disponible | `GET /health` → `stt` | No |
| A11 | **Scope editor** — rutas permitidas y protegidas | `RunOptions` | No |

## ADMIN / SETTINGS

| # | Capacidad | Requiere backend nuevo |
|---|---|---|
| S1 | Proveedor y modelo en uso | **Sí** (`GET /config`) |
| S2 | Modelo del Reviewer | **Sí** |
| S3 | Tarifas y coste | **Sí** (hoy `None`) |
| S4 | Repositorios autorizados | **Sí** (y hoy no se aplican) |
| S5 | Nivel de log | **Sí** |
| S6 | STT: modelo e idioma | **Sí** |

## DEVELOPER

| # | Capacidad | Nota |
|---|---|---|
| D1 | Ver el `RunState` completo (JSON) | El estado ya se sirve; útil para depurar |
| D2 | Ver el registro de eventos crudo | `events` existe en la BD; **no hay endpoint** |
| D3 | Ver `ErrorApi.errorClass` y el código HTTP | Ya está en `api.ts` |
| D4 | Indicador de conexión SSE (abierto/cerrado/perdido) | Ya existe en `App.tsx` |

## FUTURE

| # | Capacidad | Depende de |
|---|---|---|
| F1 | Evaluation dashboard | Servir `evaluation_results.json` por API |
| F2 | Cancelar ejecución | Implementar `RF-16` |
| F3 | Purga / retención | Endpoint `DELETE` |
| F4 | Trazas / observabilidad | M6 |
| F5 | Grafo de conocimiento | Propuesta `[PROP]` |
| F6 | MCP: estado de servidores | Fase no implementada |
| F7 | Exportar informe (PDF/Markdown) | `FinalReport` ya estructurado |
| F8 | Multi-usuario | Auth + aislamiento |

## Qué NO debe exponerse

| Dato | Por qué |
|---|---|
| `AI_SWE_MODEL_API_KEY` ni ninguna credencial | Es un secreto del operador |
| Rutas absolutas del sistema de ficheros en la UI | Revela la estructura de la máquina (`SEC-…`) |
| `stderr`/`stdout` crudos sin redactar | Ya vienen redactados del backend, pero **no** rehidratarlos |
| Detalles internos de excepción | El backend ya devuelve `error_class`, no trazas |
| El contenido de `var/state.sqlite3` | No es una capacidad de usuario |

## Resumen: 11 CORE + 11 ADVANCED = 22 capacidades sin tocar el backend

**Sólo 6 capacidades (todas de ADMIN/SETTINGS) requieren backend nuevo.**

Esto es la conclusión operativa del rediseño: **el frontend premium se puede
construir casi entero sobre lo que ya existe y ya está verificado.**
