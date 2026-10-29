# Ruta 3, entrega 2 — Workflow, consulta visible y baja de proyectos

Fecha de corte: 28 de octubre de 2026. Base: `91b3043`, descendiente del motor corregido `0e29fe0`. El árbol estaba limpio al comenzar. Se incorporaron los commits existentes `4b05eb3` (proveedores/contexto) y `91b3043` (baja de proyectos); no se duplicó su implementación.

## Cambios de esta entrega

- **Workflow de la vista general:** «Ver evidencia» en cada etapa abre el inspector existente con el estado y los eventos de la ejecución seleccionada. El inspector se actualiza desde las mismas fuentes que el flujo, se cierra al dejar de corresponder al run y permite ir al detalle si hay una puerta humana pendiente. Escape cierra el diálogo y devuelve el foco al control de origen. Abrir evidencia no ejecuta modelos, pruebas ni aprobaciones.
- **Releer del servidor:** mantiene la consulta real de estado/historial, muestra carga y bloquea doble pulsación. Al completar muestra la hora local de consulta; si cualquiera de las lecturas falla muestra el error en lugar de un éxito ficticio. Releer no reanuda una ejecución detenida ni repite inferencia. Los errores se devuelven desde el refresco real de App; no se deducen mediante un temporizador.
- **Baja de registros:** se conserva DELETE ya implementado en la base, limitado al registro en SQLite del perfil. La confirmación explica que se conservan archivos, repositorio e historial. La UI muestra espera y confirmación de éxito, limpia el proyecto seleccionado cuando corresponde y cierra/oculta un detalle que ya no pertenece a la lista. No borra carpetas, Git, remotos, ejecuciones ni worktrees.
- **Contrato:** se añadió la descripción de DELETE a `tools/export_contracts.py` y se regeneró `frontend/contracts.json`.

## Evidencia

- TypeScript y Vite: compilación aprobada.
- Frontend existente: **32 PASS**.
- API focalizada: **8 PASS, 0 omitidas, 0 errores, 0 fallos**. Incluye alta/listado/detalle, baja repetida 404, rol administrador en modo clave, rechazo sin autenticación, rechazo reader/operator, CSRF, origen ajeno, aislamiento entre Alice/Bob, historial conservado y comparación de los bytes de todos los archivos del repositorio antes/después.
- Navegador: **9 comprobaciones aprobadas**, con React App real y HTTP local simulado. Se verificaron carga/lectura/éxito, error de servidor sin falso éxito, recuperación de consulta, inspector con error del run seleccionado, Escape/foco, cancelar sin DELETE, baja confirmada/detalle obsoleto, historial visible y ausencia de errores de React.
- Ruff de prueba nueva/exportador y `git diff --check`: aprobados.

Reproducir navegador: `node tools/verify_workflow_interactions.cjs`. Usa Playwright/esbuild ya disponibles y un Chromium local; se puede indicar `AI_SWE_BROWSER_EXECUTABLE`. No usa servicios externos ni credenciales. El informe de navegador se conserva en `docs/evidence/workflow-ui/browser-report.json`; capturas adicionales en `_tmp/workflow-interactions/`.

Reproducir API: `.venv/Scripts/python.exe -m pytest tests/test_project_deregistration.py tests/test_f10_api.py -q -k "project or proyecto"`. XML local: `_tmp/workflow-project-api.xml`. Pruebas con perfiles y repositorios temporales, sin proveedor remoto.

No se repitió toda la suite del producto. La evidencia de esta entrega es focalizada en los cambios; no se suma al resultado histórico de 889 aprobadas/4 omitidas ni a las 91 del motor como una supuesta suite única.

## Portable

Nuevo candidato: `dist/windows-v0.2.0-workflow-rc1/AISWESystem-windows-x64.zip`. Carpeta ejecutable: `dist/windows-v0.2.0-workflow-rc1/dist/AISWESystem/AISWESystem.cmd`. Incluye el motor corregido y el frontend de esta entrega.

SHA256 del ZIP: `1d163af98956e0a3ba61bc7abb4f5f6712bffbe652d3e01b9630b83cdef1ed64`.

El smoke portable utiliza un perfil temporal, PATH sin Python/Node de desarrollo, manifiesto de hashes, ausencia de archivos de secretos/estado de desarrollo, frontend integrado, registro, confirmación humana, persistencia de perfil/SQLite/checkpoint y reinicio. Informe local: `_tmp/workflow-portable-smoke/report.json`; se preserva su resultado final en `docs/evidence/workflow-ui/portable-smoke.json`.

Resultado final del smoke: **14 comprobaciones aprobadas**. Integridad ZIP: 4745 entradas, ninguna dañada. La verificación de navegador corresponde a las fuentes; el smoke del portable comprueba sus estáticos integrados y hashes, sin repetir allí las nueve interacciones de fixture.

Antes de probar, cerrar el servidor de un ZIP anterior y extraer la carpeta completa. El puerto que abra el launcher corresponde a la instancia iniciada; una pestaña antigua puede seguir consultando otro servidor. Las ejecuciones históricas conservan su resultado. Esta entrega no requiere introducir otra vez una contraseña o token en el chat.

## Límites y siguiente paso

Las pruebas UI usan respuestas HTTP de fixture; las de API ejercitan backend real temporal; el smoke comprueba el paquete. No hay una nueva inferencia Qwen acreditada. El presupuesto del laboratorio permanece sin renovar; no hubo llamadas pagadas. La prueba remota de una petición nueva requiere nueva autorización de gasto.

La baja es una operación de organización de la lista, no un mecanismo para revocar la autorización general de una ruta. No se ofrece edición de rutas ni limpieza automática de disco. La comprobación con otra PC y la revisión independiente final siguen pendientes.

El siguiente hito funcional es verificar una petición nueva con Coder/Reviewer reales y revisar el producto generado según requisitos concretos. Los defectos conocidos de continuidad/importación/auto-respaldo y los límites de aislamiento de procesos siguen abiertos; este acta no acredita producción.
