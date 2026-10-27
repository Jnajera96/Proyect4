# Integración del frontend de Antigravity

Fecha: 27 de octubre de 2026. Baseline: `bbddf91`.

## Fuente revisada y adaptación

Implementación aportada por el usuario en
`C:/Users/jose_/Desktop/AI-Software-Engineering/ai-software-engineering-system/frontend/src`.
Handoff: `docs/07-FRONTEND-REDESIGN-HANDOFF.md` en ese proyecto externo. Se revisaron
WorkflowPipeline, AppShell, StageDetailDrawer, DiffViewer y los tokens de index.css.
El proyecto externo se conserva sin modificaciones.

Su implementación parte de otro backend: estados de Fase 0, rutas `/api/v1/*`,
proyectos con `workspace_path` y promoción mediante endpoint separado. Esos
contratos no se importaron al runtime actual. Se adaptaron sus patrones de
interacción a los datos reales y componentes existentes:

| Propuesta de Antigravity | Integración actual |
| --- | --- |
| WorkflowPipeline secuencial | `SecuenciaAgentes.tsx`: ocho filas con rol, contrato/evidencia y estado calculado por el mapeador actual |
| StageDetailDrawer | `InspectorEtapa.tsx`: diálogo lateral modal con evidencia real, Escape y restauración de foco |
| RealTimeActivityPanel | `VistaActividad.tsx`: conexión SSE independiente del estado de ejecución, eventos canónicos y filtros |
| HistoryPage | Historial existente con búsqueda local por ID/trace/intención/estado y orden por fecha o errores |
| AppShell contraíble | Barra lateral compacta en escritorio; navegación accesible y drawer móvil existentes |
| CodeReviewPage / DiffViewer | Se reutilizan las puertas, diffs y paneles de pruebas/reviewer ya validados |
| ProjectsPolicyPage | Se conservan Proyectos, Seguridad y presupuesto real de la ejecución |

No se añade BrowserRouter ni una segunda API, ni se reemplaza la grabación real
por reconocimiento del navegador. Se conservan selector de proyecto, alcance,
autenticación y controles/etiquetas críticos. Las aprobaciones siguen en las
puertas existentes; el inspector no aprueba ni promueve. No se introduce el
endpoint `/promote` ni la confirmación ficticia «PROMOVER». Se conserva claro/
oscuro, contraste evaluado y movimiento reducido.

La consola muestra secuencia, tipo y fecha de eventos reales; no vuelca payloads
privados ni fabrica severidades ausentes del contrato. La búsqueda actúa sobre la
página cargada, no promete búsqueda global. No se añade importación de JSON como
si fuera una ejecución del servidor. Contratos Pydantic/backend permanecen intactos.

## Verificación

- 24/24 pruebas frontend existentes PASS, sin modificar sus archivos.
- TypeScript y Vite PASS.
- 134 comprobaciones reales de navegador PASS: local/auth, gates/SSE/voz,
  promoción fallida, búsqueda/orden, inspector, Escape/foco, sidebar compacta,
  móvil sin overflow y contraste AA evaluado entre 390 y 1920 px en ambos temas.
- Configuración instalada: 8 PASS; sin credencial se bloquea antes de encolar.
- Voz española real small CPU/int8: 16 PASS, captura sintética MediaRecorder,
  edición, confirmación sin ejecución y ejecución explícita. No nueva prueba física.
- Se inspeccionaron capturas de actividad e inspector móvil/escritorio.

Las primeras corridas detectaron restauración de foco defectuosa y pérdida del
selector canónico de promoción al adaptar el pipeline. Se corrigieron ambos y
se reverificó sin retirar aserciones existentes. Evidencia final:
`_tmp/antigravity-browser-04/1793113106328/report.json`.

No se repite la suite Python completa porque no se cambió backend; el resultado
785 PASS/3 SKIP anterior sigue siendo histórico. No hubo inferencia de pago.

## Paquete construido, validación bloqueada

Build final: `_tmp/antigravity-build-03/`, con frontend recién construido dentro
de `_internal/frontend/dist`. Instalador generado:
`dist/windows-antigravity-rc1/AISWESystem-v0.1.0-setup.exe`.

**No es una entrega validada.** El smoke del EXE falló antes de ejecutar controles:
`WinError 4551: Una directiva de Control de aplicaciones bloqueó este archivo`.
Authenticode informa `NotSigned`; no se atribuye el bloqueo a una causa más
específica sin evidencia. No se deshabilitó ni eludió la protección de Windows.
No se ejecutó instalación/desinstalación del paquete bloqueado. El acta
`ANTIGRAVITY-EVIDENCE.json` conserva hashes y resultado negativo del smoke.

La entrega premium anterior permanece separada e intacta y no incluye estas
vistas nuevas. Para ver la integración actual usar el frontend compilado del
checkout principal con el backend de desarrollo. El nuevo ejecutable requiere
resolver su distribución/firma o validarlo en un entorno autorizado compatible;
no repetirlo como PASS ni desactivar protecciones automáticamente.

Sin tag final ni push. Documentos académicos pendientes preservados.
