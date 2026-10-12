# 32 — Preparación para el diseño del frontend

> ¿Está el sistema listo para rediseñar el frontend? Commit `065db452`.

## 1. ¿Qué se puede visualizar ya?

**22 capacidades** (ver `31-…`) tienen sus datos disponibles en el backend **hoy**:

- Todo el ciclo de ejecución: crear → seguir → confirmar requisitos → aprobar → informe.
- Plan, timeline, diff, evidencia de pruebas, veredicto, errores.
- Presupuesto (tokens/coste/ciclos), aprobaciones, estado por subtarea.
- Voz (backend completo), política, salud.

## 2. Qué datos faltan en la API

| # | Falta | Para qué | Impacto |
|---|---|---|---|
| 1 | `GET /config` (o `/models`) | Mostrar y elegir el modelo en uso | Sin él, la pantalla de ajustes no existe |
| 2 | Endpoint del registro de eventos crudo | Vista de desarrollador | Bajo (el SSE ya cubre el caso normal) |
| 3 | Endpoint de evaluación | Dashboard de `EXP-01` | Bajo (es un documento) |
| 4 | Coste real | Panel de coste con datos | **No es API: es configuración** (`AI_SWE_MODEL_PRICING`) |
| 5 | Estado por subtarea | `Subtask.status` existe en el contrato, pero **los nodos nunca lo actualizan** | **Requiere cambio en el grafo**, no solo API |

> **Hallazgo**: `Subtask.status` y `Subtask.attempts` están en el contrato y **nadie
> los escribe**. `plan_index` sí avanza. Mostrar el estado por subtarea exigiría que
> los nodos lo actualizaran.

## 3. Qué eventos faltan

| Falta | Por qué |
|---|---|
| Evento de inicio de nodo | Solo hay hitos de **finalización** (`*.completed`). No se puede mostrar «el Coder está trabajando» con honestidad |
| Evento de progreso de pruebas | `tests.completed` llega al terminar |
| Evento de presupuesto | El `Budget` cambia y no se emite |

**Nota**: la ausencia de un evento de inicio es **deliberada y correcta** — el motor
lee el grafo con `stream_mode="updates"`, que entrega el resultado cuando el nodo ya
terminó; emitir un `started` mentiría sobre el instante. **Un indicador de «en
curso» debe inferirse de `next_step`**, no inventarse.

## 4. Qué contratos requieren ajuste

| Ajuste | Motivo | Riesgo |
|---|---|---|
| `ApproveRequest.decision` obligatorio | Hoy `{}` aprueba (`SEC-03`) | Bajo |
| `Subtask.status` que alguien actualice | Para la vista de plan | Medio (toca el grafo) |
| `RunOptions.dry_run`: implementar o retirar | Campo muerto con descripción falsa | Bajo |
| `TestRun.reproducible`: implementar o retirar | Idem | Bajo |
| Añadir `EventKind` de presupuesto | Si se quiere ver el coste en vivo | Bajo (aditivo) |

## 5. Qué NO debe exponerse

| Dato | Motivo |
|---|---|
| Credenciales de proveedor | Secreto del operador |
| Rutas absolutas de la máquina | Revela estructura (`repo_path`, `worktree_path`) |
| `stderr`/`stdout` sin redactar | Riesgo de fuga; el backend ya redacta, no deshacer |
| Trazas de excepción | El backend ya devuelve `error_class` |
| Contenido de la BD | No es una capacidad |

## 6. Estado actual del frontend frente al objetivo

| Dimensión | Hoy | Objetivo |
|---|---|---|
| Pantallas | 1 (`App.tsx`) | 5-8 con router |
| URLs | Ninguna | Una por recurso |
| Estado | 16 `useState` locales | Por pantalla + caché de consultas |
| Componentes | 5 | 20-30 |
| Tests en pytest | 0 (`AUD-07`) | Los flujos críticos |
| Accesibilidad | No verificada | Foco gestionado, `aria-*`, navegación por teclado |
| Design system | `estilos.css` (699 líneas) | Tokens + componentes |
| Voz | No existe | Grabar → transcribir → confirmar |

## 7. Veredicto de preparación

| Pregunta | Respuesta | Por qué |
|---|---|---|
| ¿Se puede rediseñar **sin tocar el backend**? | **SÍ, en un 80 %** | 22 de 28 capacidades ya tienen datos |
| ¿Hay datos simulados que limpiar? | **NO** | El frontend no tiene mocks; todo viene de la API |
| ¿Hay que arreglar algo **antes** de diseñar? | **SÍ, tres cosas** | (1) `ApproveRequest.decision` obligatorio; (2) `README`/`__init__` dicen «fase M0»; (3) decidir si se muestra coste (requiere tarifas) |
| ¿El backend es estable como contrato? | **SÍ** | `contracts.json` GENERATED y verificado por una prueba |
| ¿Falta algún endpoint bloqueante? | **Solo `GET /config`** | Y solo para la pantalla de ajustes |

## 8. Recomendación

**FRONTEND_REDESIGN_READY = YES**, con tres condiciones previas pequeñas:

1. Corregir `ApproveRequest.decision` (sin default).
2. Corregir las dos contradicciones de documentación.
3. Decidir si el panel de coste mostrará datos reales (requiere `AI_SWE_MODEL_PRICING`)
   o se marcará como «no configurado».

**No hace falta esperar** a MCP, observabilidad ni autenticación para rediseñar el
frontend de las capacidades existentes. **Sí** hace falta decidir el alcance de la
entrega (¿prototipo local o producto?), porque eso determina si el rediseño incluye
pantallas de autenticación y de administración.
