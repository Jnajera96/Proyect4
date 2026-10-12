# 16 — Mapa backend → frontend

> **El documento clave para el rediseño.** Qué capacidad real del backend puede
> convertirse en interfaz. Commit `065db452`. **No se diseña nada aquí.**

Leyenda de `CURRENT UI`: ✅ ya existe · ⚠️ parcial · ❌ no existe.

---

## 1. Proyectos

| BACKEND CAPABILITY | ENDPOINT | CONTRACT | EVENT | USER ACTION | CURRENT UI | MISSING UI | RECOMMENDED SCREEN |
|---|---|---|---|---|---|---|---|
| Alta de proyecto (valida repo) | `POST /projects` | `ProjectRequest` → `Project` | — | Nombrar + indicar ruta | ⚠️ en `<details>` dentro de «Nueva ejecución» | Pantalla propia; lista de repositorios; estado de validación | **Projects** |
| Listar proyectos | `GET /projects?limit` | `[Project]` | — | Ver mis repositorios | ❌ (se llama, no se pinta) | Lista con `repo_path`, fecha, nº de ejecuciones | **Projects** |
| Consultar proyecto | `GET /projects/{id}` | `Project` | — | Abrir un proyecto | ❌ | Ficha del proyecto | **Project detail** |
| Ejecuciones por proyecto | `GET /runs` (filtrando en cliente) | `[RunSummary]` | — | Ver historial del proyecto | ❌ | Historial | **Project detail** |

## 2. Ejecuciones

| BACKEND CAPABILITY | ENDPOINT | CONTRACT | EVENT | USER ACTION | CURRENT UI | MISSING UI | RECOMMENDED SCREEN |
|---|---|---|---|---|---|---|---|
| Crear ejecución | `POST /runs` (202) | `RunRequest` → `RunState` | `run.created` | Escribir instrucción + ejecutar | ✅ | Elección de **alcance** (`allowed_paths`, `protected_paths`) — existe en el contrato y no se expone | **New run** |
| Estado autoritativo | `GET /runs/{id}` | `RunState` | — | Ver dónde está | ✅ | — | **Run detail** |
| Listar ejecuciones | `GET /runs?limit` | `[RunSummary]` | — | Ver historial | ❌ | **Tabla de historial** con estado, intención, fecha y errores | **Runs** |
| Progreso en vivo | `GET /runs/{id}/events` (SSE) | `RunEvent` | todos | Seguir el avance | ✅ | — | **Run detail** |
| Plan propuesto | (en `RunState.plan`) | `RunPlan` | `plan.completed` | Ver las subtareas | ✅ | Estado por subtarea (hoy solo se listan) | **Run detail** |
| **Presupuesto consumido** | (en `RunState.budget`) | `Budget` | — | Ver tokens, coste, ciclos | ❌ | **Panel de coste**: tokens in/out, coste, llamadas, ciclos usados/máx | **Run detail** |
| Informe final | (en `RunState.final_report`) | `FinalReport` | `run.completed` | Leer el resultado | ✅ | — | **Run detail** |
| Errores tipados | (en `RunState.errors`) | `[RunError]` | `run.failed` | Entender qué falló | ✅ | Acción sugerida por `error_class` | **Run detail** |
| **Aprobaciones registradas** | (en `RunState.approvals`) | `[Approval]` | — | Auditar quién decidió qué | ❌ | Trazabilidad visible (actor, fecha, hash) | **Run detail → Audit** |
| Cancelar | `POST /runs/{id}/cancel` | — | — | Parar una ejecución | ❌ | **Devuelve 501**: no se puede ofrecer hasta que exista | — |

## 3. Puertas humanas (HITL)

| BACKEND CAPABILITY | ENDPOINT | CONTRACT | EVENT | USER ACTION | CURRENT UI | MISSING UI | RECOMMENDED SCREEN |
|---|---|---|---|---|---|---|---|
| Confirmar requisitos | `POST .../confirm-requirements` | `ConfirmRequirementsRequest` | `run.awaiting_human` | Confirmar / corregir / rechazar | ✅ | Resaltar qué campos se corrigieron | **Gate 1** |
| Corregir interpretación | idem (`intent`, `constraints`, `rationale`) | — | — | Editar la interpretación | ✅ | Vista de diferencias antes/después | **Gate 1** |
| Aprobar cambio | `POST .../approve` `{decision:"approved"}` | `ApproveRequest` | `run.awaiting_human` | Aprobar y **promover** | ✅ | Aviso explícito de que **escribe en el repositorio** | **Gate 2** |
| Pedir cambios | idem `{decision:"modified", comments}` | — | — | Devolver al Coder con instrucciones | ✅ | — | **Gate 2** |
| Rechazar | idem `{decision:"rejected"}` | — | — | Cerrar sin promover | ✅ | — | **Gate 2** |
| Evidencia de pruebas | (en `RunState.evidence.test_runs`) | `[TestRun]` | `tests.completed` | Ver qué se ejecutó | ✅ | Salida completa (`stdout`), `argv`, duración | **Gate 2** |
| Veredicto del Reviewer | (en `outputs.reviewer_output`) | `ReviewVerdict` | — | Leer el juicio y los hallazgos | ✅ | Hallazgos con severidad y evidencia | **Gate 2** |
| Diff del cambio | (en `artifacts.diff`) | `CodeChange` | `coder.completed` | Revisar el parche | ✅ | — | **Gate 2** |

## 4. Modelo / IA

| BACKEND CAPABILITY | ENDPOINT | CONTRACT | EVENT | USER ACTION | CURRENT UI | MISSING UI | RECOMMENDED SCREEN |
|---|---|---|---|---|---|---|---|
| Proveedor y modelo en uso | — (solo `Settings`) | — | — | Ver qué modelo responde | ❌ | **No hay endpoint**: habría que crear `GET /config` | **Settings → Models** |
| Modelo del Reviewer | — (`AI_SWE_REVIEWER_MODEL`) | — | — | Elegir modelo de revisión | ❌ | Sin endpoint | **Settings → Models** |
| Fallback determinista | `RunState.errors` (`MODEL_FALLBACK`) | `RunError` | — | Saber si el modelo no se usó | ⚠️ (aparece como error genérico) | Aviso destacado: «esta ejecución no usó el modelo» | **Run detail** |
| Coste y tarifas | — (`AI_SWE_MODEL_PRICING`) | `PricingTable` | — | Ver coste | ❌ | Sin endpoint; hoy el coste es `None` | **Settings → Cost** |

## 5. Voz

| BACKEND CAPABILITY | ENDPOINT | CONTRACT | EVENT | USER ACTION | CURRENT UI | MISSING UI | RECOMMENDED SCREEN |
|---|---|---|---|---|---|---|---|
| Transcribir audio | `POST /transcriptions` | `Transcript` | — | **Dictar** la instrucción | ❌ | **Todo**: `MediaRecorder`, subida, previsualización del texto | **New run → Voice** |
| Confirmar transcripción | (contrato `Instruction`) | `TranscriptMeta` | — | Confirmar antes de ejecutar | ❌ | Confirmación explícita (obligatoria por contrato) | **New run → Voice** |
| Estado del STT | `GET /health` → `stt` | — | — | Saber si la voz está disponible | ⚠️ (solo el chip global) | Indicador en el control de voz | **New run → Voice** |

## 6. Seguridad y política

| BACKEND CAPABILITY | ENDPOINT | CONTRACT | EVENT | USER ACTION | CURRENT UI | MISSING UI | RECOMMENDED SCREEN |
|---|---|---|---|---|---|---|---|
| Violaciones de política | `RunState.errors` (`POLICY_*`, `SANDBOX_PATH_DENIED`) | `RunError` | — | Ver si se bloqueó algo | ⚠️ (como error) | Panel de seguridad con la regla que denegó | **Run detail → Security** |
| Alcance declarado | `RunOptions.allowed_paths` / `protected_paths` | `RunOptions` | — | Declarar dónde puede escribir | ❌ | **Formulario de alcance** (capacidad real, invisible hoy) | **New run → Scope** |
| Rutas protegidas | idem | — | — | Proteger rutas | ❌ | idem | **New run → Scope** |
| Redacción de secretos | `security/redaction.py` | — | — | (transparente) | ✅ | — | — |

## 7. Evaluación

| BACKEND CAPABILITY | ENDPOINT | CONTRACT | EVENT | USER ACTION | CURRENT UI | MISSING UI | RECOMMENDED SCREEN |
|---|---|---|---|---|---|---|---|
| Resultados de evaluación | — (artefacto `var/evaluation_results.json`) | — | — | Ver la comparativa | ❌ | **No hay endpoint**: hoy es un documento, no una capacidad de la API | **Evaluation** (futuro) |

## 8. Resumen: capacidad real vs UI actual

| Capacidad del backend | ¿Visible hoy? |
|---|---|
| Crear proyecto | ⚠️ (oculto en un `<details>`) |
| Listar proyectos / ejecuciones | ❌ |
| Crear y seguir ejecución | ✅ |
| Puertas HITL completas | ✅ |
| Diff, evidencia, veredicto | ✅ |
| Informe final y errores | ✅ |
| **Presupuesto (tokens, coste, ciclos)** | ❌ |
| **Alcance declarado (`allowed_paths`)** | ❌ |
| **Aprobaciones (trazabilidad)** | ❌ |
| **Voz** | ❌ |
| **Modelo en uso** | ❌ |
| **Política / denegaciones** | ⚠️ |
| Evaluación | ❌ |

**Cuatro capacidades reales del backend no tienen ninguna representación en la UI:
presupuesto, alcance, trazabilidad de aprobaciones y voz.** Son las de mayor valor
para el rediseño, porque **ya funcionan** y no requieren backend nuevo.

**Una capacidad requeriría backend nuevo**: la selección de modelo (no hay
`GET /config`).
