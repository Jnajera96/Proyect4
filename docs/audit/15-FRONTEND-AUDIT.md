# 15 — Auditoría del frontend

> `frontend/` — React 18 + TypeScript + Vite. 12 ficheros fuente, 2.311 líneas.
> Commit `065db452`.

## 1. Inventario

| Fichero | Líneas | Función | Estado |
|---|---|---|---|
| `index.html` | 12 | Punto de entrada de Vite (`<div id="root">`) | IMPLEMENTED_AND_VERIFIED |
| `src/main.tsx` | 18 | `createRoot`; falla si no existe `#root` | IMPLEMENTED_AND_VERIFIED |
| `src/App.tsx` | 476 | **Toda la aplicación**: estado, efectos, SSE, sondeo, render | IMPLEMENTED_AND_VERIFIED |
| `src/components/PuertaRequisitos.tsx` | 224 | Puerta 1: ver, confirmar, corregir, rechazar | IMPLEMENTED_AND_VERIFIED |
| `src/components/PuertaAprobacion.tsx` | 188 | Puerta 2: diff + evidencia + veredicto; aprobar / pedir cambios / rechazar | IMPLEMENTED_AND_VERIFIED |
| `src/components/Diff.tsx` | 69 | Visor de diffs (no reescribe el diff) | IMPLEMENTED_AND_VERIFIED |
| `src/components/Timeline.tsx` | 69 | Línea de tiempo de hitos canónicos | IMPLEMENTED_AND_VERIFIED |
| `src/components/ui.tsx` | 55 | `Chip`, `Panel`, `Fila`, `Vacio`, `hora` | IMPLEMENTED_AND_VERIFIED |
| `src/hooks/useEventosRun.ts` | 138 | `EventSource`, cierre en `run.done` | IMPLEMENTED_AND_VERIFIED |
| `src/lib/api.ts` | 133 | Cliente HTTP tipado con `ErrorApi` | IMPLEMENTED_AND_VERIFIED |
| `src/lib/contracts.ts` | 260 | Tipos derivados de `contracts.json` | IMPLEMENTED_AND_VERIFIED |
| `src/estilos.css` | 699 | Sistema de diseño (variables CSS, claro/oscuro) | IMPLEMENTED_AND_VERIFIED |
| `src/vite-env.d.ts` | 21 | Tipado de módulos JSON | IMPLEMENTED_AND_VERIFIED |
| `contracts.json` | — | **GENERATED** por `tools/export_contracts.py` | GENERATED |

## 2. Arquitectura

- **Sin router.** No hay `react-router`: **una sola pantalla** con paneles
  condicionales. Todo el estado de la aplicación vive en `App.tsx` (16 `useState`).
- **Sin gestor de estado** (Redux/Zustand/Context): estado local + `useMemo`.
- **Sin librería de componentes**: UI propia (`ui.tsx`, 55 líneas).
- **SSE** con `EventSource` + **sondeo de respaldo a 900 ms** mientras la ejecución
  no es terminal (una ejecución puede cambiar de estado sin emitir evento).
- **Sin dependencias de UI de terceros**: `package.json` solo tiene `react`,
  `react-dom` y tipos. **Superficie de ataque mínima** — es una decisión acertada.

## 3. Pantallas / áreas funcionales

| Área | Qué muestra | Backend | Estado |
|---|---|---|---|
| Cabecera | Chip de salud con **fase leída de `/health`** | `GET /health` | COMPLETO |
| Nueva ejecución | Instrucción, selector de proyecto, botón «Ejecutar» | `POST /runs` | COMPLETO |
| Nuevo proyecto (`<details>`) | Nombre + ruta; valida al registrar | `POST /projects` | COMPLETO |
| Progreso | `run_id`, chips de estado, conexión | `GET /runs/{id}`, SSE | COMPLETO |
| Detalles | Estado, intención, contadores | `GET /runs/{id}` | COMPLETO |
| Plan | Lista de subtareas con agente | `RunState.plan` | COMPLETO |
| Línea de tiempo | Hitos canónicos (alcanzados vs pendientes) | SSE | COMPLETO |
| Puerta 1 | Interpretación; confirmar / corregir / rechazar | `POST .../confirm-requirements` | COMPLETO |
| Puerta 2 | Diff, pruebas, veredicto; aprobar / pedir cambios / rechazar | `POST .../approve` | COMPLETO |
| Informe final | Cambios, pruebas, pendiente, revisión | `RunState.final_report` | COMPLETO |
| Errores | Lista de `RunError` | `RunState.errors` | COMPLETO |
| Historial de ejecuciones | — | `GET /runs` | **NO HAY UI** (se llama, no se muestra lista) |
| Selección de modelo | — | — (no hay endpoint) | **NO EXISTE** |
| Tokens / coste / presupuesto | — | `RunState.budget` | **NO SE MUESTRA** |
| Voz (`MediaRecorder`) | — | `POST /transcriptions` | **NO EXISTE** |
| Aprobaciones registradas | — | `RunState.approvals` | **NO SE MUESTRA** |
| Cancelar ejecución | — | `POST .../cancel` (501) | **NO EXISTE** (y el backend devuelve 501) |

## 4. Problemas de UX / completitud

| # | Problema | Severidad |
|---|---|---|
| 1 | **Todo en una pantalla de 476 líneas**: a medida que crezca, es insostenible | MEDIA |
| 2 | **Sin router ni URLs**: no se puede enlazar a una ejecución concreta; recargar pierde el estado | MEDIA |
| 3 | El **historial de ejecuciones se pide pero no se pinta** (`GET /runs` se llama; no hay lista visible) | MEDIA |
| 4 | **El presupuesto no se muestra**: tokens, coste y ciclos existen en el estado y no se ven | MEDIA |
| 5 | **No hay estados vacíos** para «aún no hay ejecuciones» (sí existe el componente `Vacio`) | BAJA |
| 6 | El error de acción se muestra en un `<p role="alert">`; no hay recuperación guiada | BAJA |
| 7 | **Sin accesibilidad verificada**: no hay `aria-*` sistemáticos, ni foco gestionado al abrir una puerta | MEDIA |
| 8 | **Sin manejo de errores por código**: `ErrorApi` expone `errorClass` pero la UI muestra el mensaje | BAJA |
| 9 | `estilos.css` de 699 líneas en un solo fichero | BAJA |
| 10 | **Sin tests en pytest** (arnés aparte, `AUD-07`) | MEDIA |

## 5. Componentes muertos

**Ninguno.** Verificado componente a componente:

| Componente | Importado por |
|---|---|
| `Diff` + `CabeceraFichero` | `PuertaAprobacion.tsx` (import relativo `./Diff`) |
| `PuertaRequisitos` | `App.tsx` |
| `PuertaAprobacion` | `App.tsx` |
| `Timeline` | `App.tsx` |
| `ui` (`Chip`/`Panel`/`Fila`/`Vacio`/`hora`) | `App.tsx` |
| `useEventosRun` | `App.tsx` |
| `api` | `App.tsx`, ambas puertas |
| `contracts` | 8 ficheros |

> **Nota de método.** Una primera pasada con `grep "components/Diff"` sugirió que
> `Diff.tsx` era huérfano. Era un **falso positivo**: el import es relativo
> (`from "./Diff"`). Se documenta porque es el error que la Fase 39 pide evitar.

## 6. Seguridad del frontend

| Comprobación | Resultado |
|---|---|
| `dangerouslySetInnerHTML` | **No se usa** |
| `innerHTML` | **No se usa** |
| `localStorage` / `sessionStorage` | **No se usan** |
| Tokens en el cliente | **No hay** (no hay auth) |
| Scripts de terceros | **Ninguno** (`package.json` sin dependencias de UI) |
| Dependencias npm | 3 de runtime + 5 de desarrollo; `npm audit` **no ejecutado** (requiere red) |
| CSP | **No hay** cabecera CSP |
| `index.html` | Sin `<meta http-equiv>` de seguridad |
| Servido desde | El **mismo origen** que la API (`/app`) ⇒ sin CORS y sin `file://` |

## 7. Conclusión

**IMPLEMENTED_AND_VERIFIED** como dashboard funcional de una sola pantalla: cubre el
ciclo completo (crear proyecto → lanzar → seguir → confirmar requisitos → aprobar →
ver informe) y lo hace sin dependencias de UI.

**No está listo para ser «el frontend definitivo»**: falta router, historial
visible, presupuesto/tokens, UI de voz, accesibilidad y tests dentro de pytest. Ver
`16-…`, `17-…` y `31-…`.
