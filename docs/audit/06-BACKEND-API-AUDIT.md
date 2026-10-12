# 06 — Auditoría del backend (API HTTP)

> FastAPI sobre Uvicorn. `src/ai_swe/api/app.py` (~590 líneas). Commit `065db452`.

## 1. Arquitectura

| Aspecto | Implementación | Estado |
|---|---|---|
| Framework | FastAPI + Uvicorn | IMPLEMENTED_AND_VERIFIED |
| Creación de la app | `crear_app(store=None, worker=None, stt=None, cors_origins=None)` — fábrica, sin efectos al importar | IMPLEMENTED_AND_VERIFIED |
| Ciclo de vida | `lifespan=ciclo_de_vida` (arranque/parada del `RunWorker`) | IMPLEMENTED_AND_VERIFIED |
| Estado compartido | `app.state.store / engine / worker` | IMPLEMENTED_AND_VERIFIED |
| Concurrencia | Trabajador en **hilo** separado; cerrojo por ejecución; SQLite un solo escritor | IMPLEMENTED_AND_VERIFIED |
| `async` | Solo `transcribir` y `eventos_run`. El resto son `def` (FastAPI las lleva al threadpool) | IMPLEMENTED_AND_VERIFIED |
| Bloqueo del bucle de eventos | **Mitigado**: la transcripción (CPU-intensiva) va a `run_in_threadpool` | IMPLEMENTED_AND_VERIFIED |
| Handlers de error | 6 tipados (ver §3) | IMPLEMENTED_AND_VERIFIED |
| CORS | `CORSMiddleware` **solo si** se pasan orígenes; por defecto `[]` (sin CORS) | IMPLEMENTED_AND_VERIFIED |
| Estáticos | `app.mount("/app", StaticFiles(dist, html=True))` **si existe `frontend/dist`** | IMPLEMENTED_AND_VERIFIED |
| Autenticación | **NO EXISTE** | **NOT_IMPLEMENTED** |
| Rate limiting | **NO EXISTE** | **NOT_IMPLEMENTED** |
| Migraciones | **NO EXISTE** sistema de migraciones | **NOT_IMPLEMENTED** |
| WebSockets | No hay | — |

## 2. Endpoints

| # | METHOD PATH | PROPÓSITO | REQUEST | RESPONSE | AUTH | VALIDACIÓN | EFECTO | ERRORES | TESTS | RIESGO |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `GET /health` | Sonda de vida + fase + STT | — | `{status, fase, stt, ejecuciones, proyectos}` | ❌ | — | Lectura; **cuenta hasta 1.000 filas por sonda** | — | `test_api.py` | INFO: `list_summaries(1000)` en cada *poll* es O(n) |
| 2 | `POST /projects` | Alta de proyecto | `{name, repo_path}` | `Project` 201 | ❌ | `validar_repositorio()` exige `.git` | Crea fila | 422 (ruta no git), 409 (id duplicado) | `test_f10_api.py` | MEDIA: **no se comprueba `authorized_repos`** |
| 3 | `GET /projects` | Listar | `?limit=50` | `[Project]` | ❌ | `max(1, limit)` — **sin tope superior** | Lectura | — | `test_f10_api.py` | BAJA: paginación sin techo |
| 4 | `GET /projects/{id}` | Consultar | — | `Project` | ❌ | — | Lectura | 404 | `test_f10_api.py` | BAJA: **enumeración de proyectos** (IDOR por diseño, sin usuarios) |
| 5 | `POST /transcriptions` | Audio → texto | multipart `audio`, `vocabulary` | `Transcript` | ❌ | Rechaza audio vacío (422) | **No crea ejecución** (`RF-02`) | 422, 503 (`STTNotAvailable`) | `test_f13_stt.py` | MEDIA: **sin límite de tamaño de subida** |
| 6 | `POST /runs` | Crear y encolar | `{instruction, source, transcript_meta, options, project_id}` | `RunState` **202** | ❌ | Contrato `Instruction` (voice ⇒ metadatos + confirmación) | Crea + encola | 404 (proyecto), 422 (contrato) | `test_api.py`, `test_f10_api.py` | ALTA sin auth: **crear un run es ejecutar código** |
| 7 | `GET /runs` | Listar | `?limit=50` | `[RunSummary]` | ❌ | Idem #3 | Lectura | — | `test_api.py` | BAJA |
| 8 | `GET /runs/{id}` | Estado autoritativo | — | `RunState` | ❌ | — | Lectura del checkpoint | 404 | `test_api.py` | BAJA |
| 9 | `GET /runs/{id}/events` | **SSE** en vivo | `?after`, `Last-Event-ID`, `?timeout_s=300` | `text/event-stream` | ❌ | `last_event_id.isdigit()` | Lectura + streaming | 404 | `test_f10_api.py` | MEDIA: **conexiones SSE sin límite** (DoS) |
| 10 | `POST /runs/{id}/confirm-requirements` | Puerta 1 | `{decision, intent?, constraints?, rationale?}` | `RunState` | ❌ | Reserva atómica + puerta esperada | **Reanuda el grafo** | 404, 409 `NOTHING_TO_RESUME` | `test_f10_api.py` | ALTA sin auth |
| 11 | `POST /runs/{id}/approve` | Puerta 2 | `{decision, comments?}` | `RunState` | ❌ | Idem; `puerta_esperada="approval_gate"` | **Reanuda y puede PROMOVER al repo del usuario** | 404, 409 | `test_f10_api.py`, `test_f12_promotion.py` | **ALTA**: la acción de mayor impacto del sistema |
| 12 | `POST /runs/{id}/cancel` | Cancelar | — | — | ❌ | — | **Ninguno** | **501 explícito** (`RF-16` no implementado) | — | INFO: declarado honestamente |

### Endpoints ausentes que el frontend necesitaría

| Endpoint | Para qué | Estado |
|---|---|---|
| `GET /runs/{id}/trace` | Trazas/observabilidad | PLANNED (M6) |
| `GET /config` o `/models` | Selección de modelo desde la UI | **NOT_IMPLEMENTED** |
| `GET /runs/{id}/usage` | Tokens/coste por ejecución (hoy van dentro de `RunState.budget`) | Cubierto parcialmente por #8 |
| `DELETE /runs/{id}` | Purga/retención | **NOT_IMPLEMENTED** |
| `POST /runs/{id}/cancel` real | Cancelar de verdad | **NOT_IMPLEMENTED** (501) |

## 3. Manejo de errores

| Excepción | HTTP | `error_class` | Valoración |
|---|---|---|---|
| `RunNotFound` | 404 | — | Correcto |
| `NothingToResume` | 409 | `NOTHING_TO_RESUME` | Correcto; cierra la carrera de doble reanudación |
| `SandboxError` | 422 | `SANDBOX_ERROR` | Correcto (4xx, no 500) |
| `BudgetExceededError` | 429 | `BUDGET_EXCEEDED` | Correcto |
| `STTNotAvailable` | 503 | `STT_NOT_AVAILABLE` | **Bien elegido**: capacidad no instalada ≠ defecto del servidor |
| `STTError` | 422 | `STT_ERROR` | Correcto |

**Diseño correcto y verificado**: un `TypeError` **no** se mapea, de modo que un
defecto del servidor no se disfraza de error de cliente (probado en `test_f10_api.py`).

**Riesgo residual**: no hay *handler* global que garantice la ausencia de trazas en
la respuesta ante una excepción no prevista. FastAPI devuelve un 500 con
`Internal Server Error` sin traza por defecto — aceptable —, pero **no hay
verificación** de que ninguna ruta de error filtre rutas de fichero o detalles del
proveedor (`16-…`, `19.16`).

## 4. Observaciones de seguridad del backend

1. **Sin autenticación (AUD-06).** Mitigado por `HOST = "127.0.0.1"` **en el código**
   (`__main__.py`). **Pero el `Dockerfile` arranca con `--host 0.0.0.0`**: la
   mitigación se pierde al desplegar. → Riesgo **HIGH**.
2. **`limit` sin tope superior** en los tres listados.
3. **Sin límite de tamaño** en `POST /transcriptions` (un cliente puede subir un
   fichero arbitrariamente grande; se lee entero en memoria con `await audio.read()`).
4. **Sin límite de conexiones SSE concurrentes.**
5. **`GET /health` cuenta hasta 1.000 filas** en cada llamada: una sonda barata que
   no lo es, y es el endpoint que un monitor llama cada pocos segundos.
6. **Sin cabeceras de seguridad** (`X-Content-Type-Options`, `X-Frame-Options`, CSP).
7. **Sin `TrustedHostMiddleware`.**

## 5. Estado global

**IMPLEMENTED_AND_VERIFIED** en lo funcional (12 endpoints, SSE con reconexión,
manejo de errores tipado, reserva atómica de reanudación). **NOT_IMPLEMENTED** en la
capa de seguridad de transporte (auth, límites, cabeceras).
