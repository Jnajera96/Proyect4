# Acta independiente de RC26 — 3 de noviembre de 2026

## Dictamen y alcance

**Aprobado como candidato portable para el entorno local y el alcance de empaquetado probado.** Se cierra la auditoría de empaquetado del Día 1; no equivale a certificación global 100/100 ni a cierre de concurrencia, resiliencia o pilotos físicos. Base auditada: `3879148`, recuperación de presupuesto en `17c7c4e`. Codex trabajó en `provider-preflight`, sin editar core/frontend, reconstruir el ZIP, hacer push ni realizar llamadas facturadas.

## Artefacto e integridad

- ZIP: `C:/Users/jose_/Desktop/repo_proyect/proyecto4-ai-swe/dist/windows-v0.2.0-rc26/AISWESystem-windows-x64.zip`.
- SHA-256: `d213a4086a85f55a9420a74a181910587c2e9d9859c68ed1fecf41826d7949ad`.
- Tamaño: **127809964 bytes**.
- Manifiesto: **4862 archivos**, ZIP: **4863 archivos**.
- SHA-256 de `BUNDLE-MANIFEST.json`: `74ed0c478889084899b2ac084c00eaac80453fcf161b7f72aa5789f134cdf754`.
- CRC, nombres únicos, inventario exacto y hashes de cada archivo tanto dentro del ZIP como en la extracción: aprobados. No se reutilizó como prueba el informe del empaquetador.
- 94 archivos de fuente/recurso coinciden con el worktree tras normalizar únicamente CRLF/LF. En 43 la diferencia de bytes es exclusivamente de fin de línea; **no** se afirma igualdad binaria entre checkouts. Los hashes del artefacto se comprobaron sin normalización.
- La extracción incluye `unresolved_reservations_for_run` y la captura de `BudgetExceededError` en el motor.

## Runtime y frontend

CPython **3.13.14**. Firmas Authenticode de `python.exe` y `pythonw.exe`: **Valid**, Python Software Foundation, consultadas en esta auditoría. Esto no afirma que todas las DLL de terceros estén firmadas. `sys.frozen=False` es normal: el marcador del bundle activa Settings instalado.

Vite **5.4.21**, React **18.3.1** según dependencias locales; verificador con Node **24.22.1**. `index.html` referencia `index-DMoZfdcG.js` y `index-PhWDwN8O.css`. No se recompiló el frontend durante la auditoría. Hay 100 archivos en assets, incluidos históricos no referenciados por el índice: residuo de empaquetado pendiente de limpieza por su responsable y nueva generación de hashes si se cambia el ZIP.

## Resultados independientes

| Verificación | Resultado | Alcance |
| --- | --- | --- |
| Smoke portable | 14/14 PASS | Arranque aislado, perfiles, puerta humana, SQLite/checkpoint, reinicio y cierre ordenado |
| Harness de capacidades | 15/15 PASS | Imports desde extracción, STT CPU/int8 e imports nativos, MCP stdio/redacción/confinamiento, AST, Node estático y rechazo nativo de red estricta |
| Integridad, sandbox, promoción, presupuesto y continuidad | 68 PASS / 1 SKIP / 0 FAIL | CPython y todos los módulos ai_swe importados desde la extracción |
| Capacidades locales, red y Node | 68 PASS / 0 FAIL | Módulos ai_swe extraídos; sin marcador instalado para las aserciones de modo desarrollo de la suite MCP |
| Frontend | 44/44 PASS | Suite existente de contratos/estados del source |
| Navegador con fixtures locales | 8/8 PASS | React real y voces/exportador simulados; no prueba el JS del portable ni audio físico |

La omisión es el vector de enlaces simbólicos: Windows no concedió privilegio para construirlo (WinError 1314). No se contó como pase. No existe `tests/test_portable_bundle.py` en esta base; se reutilizaron las suites equivalentes existentes de integridad/sandbox/promoción y continuidad. Los scripts temporales de ejecución verificaron que todos los imports `ai_swe.*` provinieran del bundle, sin permitir `src` en pythonpath. PATH del proceso objetivo: Windows y Git, sin Python/Node de desarrollo. Las suites de desarrollo usan Python del bundle; no son una instalación en otra PC.

## Presupuesto: qué se demuestra y qué falta

Los cinco tests empaquetados de recuperación pasan: pausa en Coder, conservación de plan/requisitos, rechazo con ledger agotado, reclamación duplicada secuencial y reservas de cobro incierto. La recuperación exitosa usa un adaptador simulado que cambia de fallo a respuesta; **no demuestra** recarga real del ledger a través del endpoint. El test de reclamación no es un ensayo de peticiones HTTP concurrentes.

Para el Día 2 siguen pendientes: comprobar importe completo de reserva y límite horario antes de reanudar (el preflight actual solo rechaza saldo no positivo), liberar la reclamación si falla el envío al worker, recuperar una pausa de presupuesto tras reinicio y validar pausa/reanudación en Reviewer. Las reservas despachadas inciertas no se liberaron. No se modificaron límites ni datos reales.

## Límites de certificación

Docker `network=host` se rechaza y el comando empaquetado declara `--network=none`, pero no se probó conectividad de un contenedor real. El runner nativo deniega la ejecución estricta: **no** se afirma que aplique bloqueo físico a sockets del host. Node es detección/preflight estático, sin npm ni scripts de aplicaciones ejecutados en host.

MCP HEAD-only está cubierto por la suite local empaquetada; el harness stdio ejercita lectura y rechazo de escape. TTS se probó con Web Speech simulado y voces locales, no físicamente. Sin micrófono real, inferencia Whisper, modelos remotos, Langfuse real, segunda PC física ni regresión backend completa en esta ejecución. Los pilotos de GitHub y continuidad física permanecen pausados.

## Evidencias

[RELEASE-RC26-EVIDENCE-2026-11-03.json](RELEASE-RC26-EVIDENCE-2026-11-03.json) contiene resultados, hashes JUnit y límites de cada comprobación. Informes crudos y procedencia de imports en `_tmp/evidence-rc26-codex*`; fixtures de navegador en `_tmp/local-capabilities-browser/`. Estos directorios son locales ignorados por Git. No se suman controles y tests como si fueran una única suite homogénea.
