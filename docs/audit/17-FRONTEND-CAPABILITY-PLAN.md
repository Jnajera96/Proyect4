# 17 — Plan de capacidad del frontend

> **FRONTEND CAPABILITY PLAN.** Qué debe poder hacer el frontend, basado
> **exclusivamente** en capacidades verificadas del backend. **No es un diseño.**

## 1. Estado actual: qué falla

| Problema | Evidencia |
|---|---|
| Una sola pantalla de 476 líneas | `App.tsx` |
| Sin router: no hay URLs, recargar pierde todo | No hay `react-router` en `package.json` |
| El historial se pide y no se pinta | `GET /runs` se llama en `App.tsx`; no hay lista |
| Cuatro capacidades del backend invisibles | Presupuesto, alcance, aprobaciones, voz (ver `16-…`) |
| Sin tests en pytest | `AUD-07` |
| Sin accesibilidad verificada | Sin `aria-*` sistemáticos |

## 2. Capacidades que el frontend debe representar

Ordenadas por **valor demostrable** (capacidad ya existente ÷ esfuerzo).

### Prioridad 1 — capacidad ya existente, solo hay que mostrarla

| # | Capacidad | Por qué primero |
|---|---|---|
| 1 | **Presupuesto de la ejecución** | `RunState.budget` ya trae tokens in/out, coste, llamadas y ciclos. Es la métrica `MET-06` y hoy **no se ve**. Coste de frontend: bajo |
| 2 | **Historial de ejecuciones** | `GET /runs` ya devuelve `RunSummary[]`. Hoy se pide y se descarta |
| 3 | **Alcance declarado** | `RunOptions.allowed_paths` / `protected_paths` existen y son una **restricción de seguridad**; el usuario no puede ejercerla desde la UI |
| 4 | **Trazabilidad de aprobaciones** | `RunState.approvals` registra actor, fecha, hash y decisión. Es `RNF-T2` y no se muestra |
| 5 | **Evidencia de pruebas completa** | `TestRun` incluye `stdout`, `stderr`, `argv`, `duration_s`. Hoy se resume |

### Prioridad 2 — capacidad existente, requiere UI nueva de verdad

| # | Capacidad | Nota |
|---|---|---|
| 6 | **Dictado por voz** | `POST /transcriptions` funciona; falta `MediaRecorder` + confirmación obligatoria |
| 7 | **Panel de seguridad** | Errores `POLICY_*` / `SANDBOX_PATH_DENIED` merecen un panel propio, no la lista genérica de errores |
| 8 | **Estado por subtarea del plan** | `Subtask.status` existe en el contrato y hoy no se pinta |
| 9 | **Aviso de fallback del modelo** | `MODEL_FALLBACK` significa «esta ejecución no usó el modelo». Hoy aparece como un error más |

### Prioridad 3 — requiere backend nuevo

| # | Capacidad | Qué falta |
|---|---|---|
| 10 | **Selección de modelo** | `GET /config` (o `/models`). Hoy solo existe en `Settings` |
| 11 | **Coste real** | `AI_SWE_MODEL_PRICING` vacío ⇒ coste `None`. Es configuración, no código |
| 12 | **Cancelar ejecución** | El endpoint devuelve **501** |
| 13 | **Purga de ejecuciones** | No hay `DELETE` |
| 14 | **Vista de evaluación** | `var/evaluation_results.json` no se sirve por API |

## 3. Acciones que hoy no dan retroalimentación

| Acción | Problema |
|---|---|
| Ejecutar | El botón se deshabilita mientras lanza; después no hay estado de «encolado» hasta que llega el primer evento |
| Registrar proyecto | Éxito silencioso: el `<details>` no se cierra ni confirma |
| Aprobar | **No avisa de que promueve al repositorio del usuario.** Es la acción de mayor impacto del sistema |
| Rechazar | No explica que la ejecución quedará `cancelled` |
| Pedir cambios | No explica que gastará un ciclo de revisión |
| Cancelar | No existe |

## 4. Datos simulados / mocks

**Ninguno en el frontend.** Verificado: no hay datos de ejemplo, ni `TODO`, ni
constantes de relleno. Todo lo que se pinta viene de la API o del SSE. Es un punto
fuerte y conviene conservarlo en el rediseño.

## 5. Endpoints no consumidos por la UI

| Endpoint | Estado |
|---|---|
| `GET /projects` | Se llama; **no se pinta** |
| `GET /projects/{id}` | **No se usa** |
| `GET /runs` | Se llama; **no se pinta** |
| `POST /runs/{id}/cancel` | No se usa (y devuelve 501) |
| `GET /health` | Sí (chip) |
| `POST /transcriptions` | **No se usa** |

## 6. SSE no visualizado

| Evento | ¿Visualizado? |
|---|---|
| `run.created`, `run.started` | Indirecto |
| `requirements.completed`, `plan.completed`, `coder.completed`, `tests.completed` | ✅ (línea de tiempo) |
| `run.awaiting_human` | ✅ (abre la puerta correspondiente) |
| `run.completed`, `run.failed` | ✅ (chip de estado) |
| `run.done` | ✅ (cierra el flujo) |

**El SSE está bien aprovechado.** El único hueco es que los hitos no muestran la
**duración** entre ellos.

## 7. Estados que la UI no contempla

| Estado | Situación |
|---|---|
| `planned` | El chip lo pinta, pero la UI asume que tras crear ya está `running` |
| `needs_human` (por escalada, no por puerta) | Aparece como chip; **no hay pantalla de escalada** |
| `cancelled` | Existe el tono, pero no hay flujo que lo produzca visiblemente |
| `failed` | Chip; sin pantalla de diagnóstico |
| Sin proyectos registrados | No hay estado vacío guiado |
| STT no disponible (503) | No se contempla |

## 8. Plan de capacidad (resumen ejecutable)

| Fase | Contenido | Requiere backend |
|---|---|---|
| **A** | Router + URL por ejecución; historial visible; panel de presupuesto | No |
| **B** | Formulario de alcance; panel de trazabilidad de aprobaciones; estado por subtarea | No |
| **C** | Voz (grabar → transcribir → confirmar); panel de seguridad | No |
| **D** | Pantallas de escalada/fallo/cancelado; estados vacíos; accesibilidad | No |
| **E** | Selección de modelo; coste real; cancelar; purga | **Sí** |

**Conclusión operativa.** Las fases A-D **no necesitan tocar el backend**. Es decir:
la mayor parte del rediseño se puede hacer sobre capacidades ya verificadas.
