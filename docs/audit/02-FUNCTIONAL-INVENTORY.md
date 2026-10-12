# 02 — Inventario funcional

> Árbol de **funcionalidades**, no de carpetas. Cada una con estado real y la
> evidencia que lo sostiene. Commit `065db452`.

Leyenda de estado: `IMPLEMENTED_AND_VERIFIED` · `PARTIAL` · `PLANNED` ·
`PLACEHOLDER` · `ORPHANED` · `SUPERSEDED` · `NOT_IMPLEMENTED` · `NOT_VERIFIED` ·
`DEAD_CODE` · `GENERATED` · `DEPENDENCY` · `UNKNOWN`

---

## 1. Gestión de proyectos

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| Alta de proyecto (valida el repositorio en el alta) | IMPLEMENTED_AND_VERIFIED | `POST /projects` → `validar_repositorio()` exige `.git`; `tests/test_f10_api.py` |
| Listado de proyectos | IMPLEMENTED_AND_VERIFIED | `GET /projects`; `state/store.py` tabla `projects` |
| Consulta de un proyecto | IMPLEMENTED_AND_VERIFIED | `GET /projects/{id}`; 404 tipado |
| Aislamiento entre proyectos | **PARTIAL** | Existe `project_id`, pero **no hay usuario**: cualquier cliente ve todos los proyectos. No hay multi-tenencia (`AUD-06`) |

## 2. Ejecuciones (runs)

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| Crear ejecución sin bloquear (202 + `run_id`) | IMPLEMENTED_AND_VERIFIED | `POST /runs` encola en `RunWorker`; `tests/test_api.py::test_crear_responde_antes_de_ejecutar` |
| Ejecutar el grafo | IMPLEMENTED_AND_VERIFIED | `RunEngine.execute` / `RunWorker` |
| Consultar estado | IMPLEMENTED_AND_VERIFIED | `GET /runs/{id}` lee el checkpoint |
| Listar ejecuciones | IMPLEMENTED_AND_VERIFIED | `GET /runs` → `RunSummary` |
| Progreso en vivo (SSE) | IMPLEMENTED_AND_VERIFIED | `GET /runs/{id}/events`, `Last-Event-ID`, cierra en `run.done` |
| Pausar en puerta humana | IMPLEMENTED_AND_VERIFIED | `interrupt()` de LangGraph; estados `awaiting_*` |
| Reanudar | IMPLEMENTED_AND_VERIFIED | `reclamar_reanudacion` + `reanudar_reclamada` (reserva atómica) |
| Cancelar una ejecución en curso | **NOT_IMPLEMENTED** | `POST /runs/{id}/cancel` devuelve **501** explícito (`RF-16`) |
| Reanudación tras caída del proceso | IMPLEMENTED_AND_VERIFIED | checkpoint SQLite; recuperación de huérfanas → `run.failed` |
| `GET /runs/{id}/trace` | PLANNED | Declarado para M6 (observabilidad); no existe la ruta |

## 3. Puertas humanas (HITL)

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| Puerta 1: confirmar/corregir requisitos | IMPLEMENTED_AND_VERIFIED | `confirm_requirements_gate` + `POST /runs/{id}/confirm-requirements` |
| Puerta 2: aprobar / pedir cambios / rechazar | IMPLEMENTED_AND_VERIFIED | `approval_gate` + `POST /runs/{id}/approve`; F12 añadió `comments` |
| Promoción del cambio aprobado al repo del usuario | IMPLEMENTED_AND_VERIFIED | `tools/promoter.py`; `git apply` + integridad SHA256 |
| Trazabilidad de la decisión (`Approval`) | IMPLEMENTED_AND_VERIFIED | `RunState.approvals` con actor, fecha, hash de contenido y decisión |

## 4. Inteligencia artificial (Model Gateway)

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| Gateway único (ningún agente importa SDK de proveedor) | IMPLEMENTED_AND_VERIFIED | `models/gateway.py`; verificado en `10-MODEL-INFRASTRUCTURE-AUDIT.md` |
| Salida estructurada validada contra Pydantic | IMPLEMENTED_AND_VERIFIED | `generate_structured` inyecta el JSON Schema del contrato |
| Proveedor `openai-compatible` | IMPLEMENTED_AND_VERIFIED | `models/providers/openai_compatible.py` |
| Proveedor `fake` determinista | IMPLEMENTED_AND_VERIFIED | `models/providers/fake.py`; sostiene toda la suite offline |
| Fallback determinista por nodo | IMPLEMENTED_AND_VERIFIED | Cada nodo cae a su versión determinista y **lo declara** con `MODEL_FALLBACK` |
| Contabilidad de tokens y coste | IMPLEMENTED_AND_VERIFIED | `models/budget.py`; F14 añadió el desglose entrada/salida |
| Tarifas por modelo | IMPLEMENTED_AND_VERIFIED | `models/pricing.py`; vacío por defecto ⇒ coste `None` («no se sabe») |
| Enrutado de modelo por rol | IMPLEMENTED_AND_VERIFIED | `reviewer_model` separado de `model_name` |
| Reintentos / backoff | **NOT_VERIFIED** | Existe `timeout_s`; no se localizó política de reintentos explícita |
| *Hugging Face* como proveedor | **NOT_IMPLEMENTED** | No hay `HuggingFaceAdapter`. El proyecto usa un proveedor compatible con OpenAI |

> **Precisión importante.** El enunciado de la auditoría menciona «Hugging Face».
> En el código **no existe** ningún adaptador de Hugging Face: `config.py` declara
> `PROVEEDORES_CON_CLAVE = {openai, anthropic, azure, openrouter, mistral}` y el
> único adaptador real es `OpenAICompatibleAdapter`. Ver `10-…` y `28-…`.

## 5. Agentes

| Agente | Estado | Naturaleza real |
|---|---|---|
| Requirements Analyst (`interpret`) | IMPLEMENTED_AND_VERIFIED | **Modelo + fallback determinista** |
| Supervisor (`plan`) | IMPLEMENTED_AND_VERIFIED | **Modelo + fallback determinista** |
| Researcher (`researcher`) | IMPLEMENTED_AND_VERIFIED | **Determinista** (enumera y lee ficheros; no llama al modelo) |
| Coder (`coder`) | IMPLEMENTED_AND_VERIFIED | **Modelo + fallback vacío** (nunca inventa parche) |
| Reviewer (`reviewer`) | IMPLEMENTED_AND_VERIFIED | **Modelo + veredicto determinista** + 2 guardas |
| `src/ai_swe/agents/` | **PLACEHOLDER** | Solo docstring; 0 importadores; los agentes viven en `graph/nodes.py` |

## 6. Herramientas y política

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| Catálogo cerrado de 11 herramientas | IMPLEMENTED_AND_VERIFIED | `tools/registry.py`; `run_shell` y `git_push` **no existen** |
| Matriz de permisos por rol | IMPLEMENTED_AND_VERIFIED | `ROLE_TOOLS` / `ROLE_APPROVAL_TOOLS`; `tests/test_policy.py` afirma los conjuntos exactos |
| Policy Engine puro y determinista | IMPLEMENTED_AND_VERIFIED | `tools/policy.py::decide`; 6 reglas en orden |
| Ejecución real de pruebas (targets cerrados) | IMPLEMENTED_AND_VERIFIED | `tools/runner.py`; `shell=False`, tabla `TARGET_COMMANDS` |
| Aplicación de parches confinada | IMPLEMENTED_AND_VERIFIED | `tools/patcher.py`; 4 barreras por escritura |
| Promoción al repositorio del usuario | IMPLEMENTED_AND_VERIFIED | `tools/promoter.py` (F12) |

## 7. Sandbox y ejecución de código

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| `git worktree` aislado por ejecución | IMPLEMENTED_AND_VERIFIED | `sandbox.py::crear`; `--detach` |
| Confinamiento de rutas (sintáctico + físico) | IMPLEMENTED_AND_VERIFIED | `resolver_destino`; `tests/test_f7_sandbox.py` |
| Limpieza del worktree (`teardown`) | IMPLEMENTED_AND_VERIFIED | `destruir` + `_limpiar_sandbox` en `finalize` (F12) |
| Límites de recursos (CPU / memoria / disco) | **NOT_IMPLEMENTED** | Solo hay límite de tiempo (`_TIEMPO_GIT_S`, timeout del runner). Ver `13-…` |
| Aislamiento de red del subproceso | **PARTIAL** | `network_egress_enabled` declarado en `Settings` pero **nunca leído** (`25-…`) |
| Aislamiento por proceso/usuario | **NOT_IMPLEMENTED** | El sandbox es un worktree, no un contenedor: comparte el proceso y el usuario del servidor |

## 8. Speech-to-Text

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| Transcripción local (`faster-whisper`) | IMPLEMENTED_AND_VERIFIED | `stt/base.py` (F13); 24 pruebas herméticas + 1 opt-in |
| Contrato `STTAdapter` + `FakeAdapter` | IMPLEMENTED_AND_VERIFIED | `stt/base.py` |
| Endpoint de transcripción | IMPLEMENTED_AND_VERIFIED | `POST /transcriptions`; 503 si falta el extra `voice` |
| El audio crudo nunca llega al Supervisor (`RF-03`) | IMPLEMENTED_AND_VERIFIED | El adaptador devuelve solo `Transcript`; `Instruction` de origen `voice` **exige** confirmación (validador Pydantic) |
| UI de voz en el frontend | **NOT_IMPLEMENTED** | No hay `MediaRecorder` ni componente de grabación |
| TTS | PLANNED | `tts_enabled` declarado, sin implementación |

## 9. Persistencia y estado

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| Checkpoint LangGraph en SQLite | IMPLEMENTED_AND_VERIFIED | `state/store.py::checkpointer` |
| Índice de ejecuciones + registro de eventos | IMPLEMENTED_AND_VERIFIED | tablas `runs`, `events`, `projects` |
| Migración de esquema | **PARTIAL** | `ESQUEMA_VERSION` existe; no hay sistema de migraciones. Ver `07-…` |
| Purga / retención | **NOT_IMPLEMENTED** | Nada se borra nunca; los eventos crecen sin límite |

## 10. Seguridad

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| Redacción de secretos (centralizada) | IMPLEMENTED_AND_VERIFIED | `security/redaction.py`; `tests/test_redaction.py` + mutaciones propias |
| Filtro de logging con redacción | IMPLEMENTED_AND_VERIFIED | `security/logging.py` |
| Redacción en el flujo SSE | IMPLEMENTED_AND_VERIFIED | `store.append_event` redacta; mutación F10 lo protege |
| `SecretStr` para credenciales | IMPLEMENTED_AND_VERIFIED | `config.py` |
| Autenticación | **NOT_IMPLEMENTED** | `AUD-06`; binding fijo a 127.0.0.1 como mitigación |
| Autorización / multi-tenencia | **NOT_IMPLEMENTED** | Sin usuarios ⇒ sin autorización |
| Lista blanca de repositorios | **NOT_IMPLEMENTED (declarada y no aplicada)** | `authorized_repos` no se lee en ningún sitio (`25-…`) |

## 11. Evaluación

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| Catálogo de 13 tareas controladas | IMPLEMENTED_AND_VERIFIED | `evaluation/tasks.py` |
| Arnés comparativo single/multi | IMPLEMENTED_AND_VERIFIED | `evaluation/runner.py`; `tests/test_f14_evaluation.py` (43 casos) |
| Informe comparativo generado | IMPLEMENTED_AND_VERIFIED (GENERATED) | `docs/06-EVALUATION.md` + `var/evaluation_results.json` |
| `EXP-02`..`EXP-08` (Reviewer, MCP, WER, guardrails…) | **NOT_IMPLEMENTED** | Solo `EXP-01` está cubierto |

## 12. Frontend

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| Dashboard de una sola pantalla | IMPLEMENTED_AND_VERIFIED | `frontend/src/App.tsx` (476 líneas) |
| Alta de proyecto y lanzamiento de ejecución | IMPLEMENTED_AND_VERIFIED | `App.tsx` + `lib/api.ts` |
| Línea de tiempo de hitos | IMPLEMENTED_AND_VERIFIED | `components/Timeline.tsx` |
| Puerta de requisitos (confirmar/corregir) | IMPLEMENTED_AND_VERIFIED | `components/PuertaRequisitos.tsx` |
| Puerta de aprobación (diff + evidencia + veredicto) | IMPLEMENTED_AND_VERIFIED | `components/PuertaAprobacion.tsx` + `Diff.tsx` |
| SSE en vivo + sondeo de respaldo | IMPLEMENTED_AND_VERIFIED | `hooks/useEventosRun.ts` + intervalo de 900 ms |
| Enrutado / múltiples pantallas | **NOT_IMPLEMENTED** | No hay router: todo vive en `App.tsx` |
| UI de voz, ajustes de modelo, coste/tokens, historial | **NOT_IMPLEMENTED** | Ver `16-…` y `31-…` |
| Verificación en motor real | IMPLEMENTED_AND_VERIFIED | `tools/verify_frontend.py` (15/15), **arnés aparte** de pytest (`AUD-07`) |

## 13. Módulos presentes pero sin función

| Módulo | Estado | Evidencia |
|---|---|---|
| `src/ai_swe/agents/` | **PLACEHOLDER** | 13 líneas, solo docstring, 0 importadores |
| `src/ai_swe/mcp/` | **PLACEHOLDER** | 13 líneas, solo docstring, 0 importadores |
| `src/ai_swe/observability/` | **PLACEHOLDER** | 13 líneas, solo docstring, 0 importadores |
| `data/tasks/README.md` | **ORPHANED** | 2.838 bytes; ninguna referencia desde `src/` |
| `docs/05-graphify-evaluacion.md` | **SUPERSEDED** (propuesta) | Marcada `[PROP]`, nunca implementada |
