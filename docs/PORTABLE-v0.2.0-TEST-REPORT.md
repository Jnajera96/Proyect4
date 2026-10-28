# Portable experimental v0.2.0 — revisión del 27 de octubre de 2026

**Estado: apto para prueba controlada en otra PC; NO aprobado para lanzamiento.**

Se revisaron los commits de Antigravity hasta `5f230f4`: memoria FTS5, modos,
rollback por rutas, continuidad cifrada y frontend Nebula/Cosmic. Se conservaron
el tag `v0.1.0` y su distribución. No se hicieron llamadas de pago, push ni cambios
al control de integridad de Windows.

## Descarga y uso

Archivo: `dist/windows-v0.2.0-portable-review1/AISWESystem-v0.2.0-PRUEBA.zip`.
SHA256: `f9b8866307c8e0292cada24c9d24a6b0c4712e8ce9300991036ce536ce95cbc4`.
Tamaño: 118753070 bytes. ZIP comprobado mediante CRC (`testzip`).
Carpeta: `dist/windows-v0.2.0-portable-review1/dist/AISWESystem`.

Windows 10/11 x64: descomprimir todo, abrir `AISWESystem/AISWESystem.cmd`,
crear un perfil con contraseña de al menos 12 caracteres y configurar proveedor
propio si se desea inferencia remota. Python y Node no hacen falta. Para operar
repositorios se necesita Git para Windows en PATH; Git no va incluido.
Los modelos de voz tampoco se incluyen: la descarga inicial requiere Internet.
Los datos se alojan bajo `%LOCALAPPDATA%/AISWESystem`. Cerrar con Ctrl+C.

Usar repositorios descartables. Respaldar el proyecto completo por separado.
No depender todavía de la importación ni del auto-respaldo para conservar trabajo.
No ejecutar simultáneamente copias del mismo perfil en varias máquinas.
Las credenciales/configuración remota no viajan dentro del archivo de continuidad:
se deben configurar otra vez en el destino.

## Evidencia obtenida en esta revisión

- Build TypeScript/Vite aprobado; coincide con assets del handoff.
- 24/24 pruebas frontend aprobadas.
- Suite Python: 833 recolectadas, 828 PASS, 3 SKIP, 2 FAIL, 380.837 s.
  Ambos fallos cuentan secretos y heredan configuración privada del host.
  Repetidas solo esas dos sin dotenv ni variables de credencial: 2 PASS.
  No se presenta esto como una suite completa limpia; queda corregir el aislamiento
  del fixture y repetir la regresión final.
- Paquete real: 14 comprobaciones aprobadas, incluidos manifiesto completo,
  ausencia de archivos privados de desarrollo, arranque con PATH solo Windows,
  perfiles por defecto, autenticación, cifrado, ejecución determinista, puerta humana,
  reinicio y persistencia/integridad SQLite. Sin llamadas remotas.
- Chromium contra el paquete: registro, espacio cósmico, bóveda y logout aprobados;
  sin errores JS. Captura `_tmp/v020-packaged-browser/workspace.png`.
- Voz desde el Python embebido y dependencias del paquete: modelo local small,
  CPU/int8, español, sin descargar. Transcripción: «Analiza el proyecto y muestra
  un resumen. No modifiques archivos. Quiero revisar el texto antes de ejecutar».
  Los pesos y audio usados eran fixtures externos al ZIP.
- Python oficial 3.13.14: Authenticode Valid, Python Software Foundation.
  SAC permanece en estado 1. El arranque y el cifrado no produjeron WinError4551.
  No se afirma que todos los PE de dependencias tengan firma ni admisión universal.
- No se ejecutó una VM ni otra PC. Tampoco se verificó promoción E2E contra este
  nuevo paquete; no se reutiliza la evidencia de v0.1.0 para atribuírsela a v0.2.0.

## Bloqueadores de lanzamiento

Véase `ANTIGRAVITY-v0.2.0-AUDIT.md` para evidencia por archivo/línea.

1. Conectar auto-respaldo al ciclo real de checkpoints: ahora solo guarda configuración.
2. Corregir base64 de importación UI, error NameError del backend y probar recorrido
   completo de importación en perfil nuevo desde navegador.
3. Preservar cambios promovidos sin commit y objetos Git de rollback en el respaldo;
   probar recuperación posterior a promoción en un repositorio nuevo.
4. Liberar la reserva de nombre al fallar una importación para permitir reintentar.
5. Endurecer validación/límites del archivo y esquema SQLite importados.
6. Alinear versiones internas (todavía 0.1.0), corregir aislamiento de pruebas y
   completar suite limpia, promoción E2E del paquete y prueba en Windows independiente.

No se corrigieron silenciosamente estos problemas al empaquetar. El ZIP contiene
el código revisado de Antigravity en `5f230f4`, con advertencias externas; no es un
release v0.2.0 final ni se creó ese tag.



## Detalle de auditoría conservado

# Revision focalizada Antigravity L/M — 1df64f2..5f230f4

Revision de solo lectura frente a docs/SPEC-v0.2.0-MADRE-USER-CONTINUITY.md. No se modifico fuente, no se ejecutaron llamadas remotas ni suite completa. Herramientas Serena no disponibles en ALL_TOOLS de este agente. Estado recomendado: candidato para probar, NO entrega v0.2.0 lista para lanzamiento.

## Bloqueadores concretos

1. **P1 — Auto-respaldo anunciado pero nunca ejecutado.** `src/ai_swe/state/continuity.py:749` define `auto_backup`; busqueda en `src` confirma cero llamadas productivas. `api/app.py:1169` solo guarda la configuracion, y `graph/engine.py:428-459` captura snapshots sin programar backup. `frontend/src/views/VistaSesion.tsx:72` informa que esta activado. Reproduccion: elegir carpeta, terminar/pausar una ejecucion; ningun codigo llama al escritor de archivos, por lo que la carpeta no obtiene respaldos. Conecta el ciclo estable y la clave de perfil, con diferimiento y errores reales, antes de prometer recuperacion automatica.

2. **P1 — Importacion desde la UI usa codificacion incompatible.** `frontend/src/views/VistaSesion.tsx:114` convierte a base64 URL-safe y elimina padding; `frontend/src/lib/api.ts:320` envia la cadena sin normalizar; `src/ai_swe/api/app.py:1208` decodifica con base64 estandar `validate=True`. Un archivo valido cuyo largo no sea multiplo de tres falla por padding; los caracteres URL-safe tambien fallan. Ademas la rama de error de `app.py:1210` usa `ContinuityError` fuera de su alcance: la unica importacion esta dentro de otra funcion (`_registrar_manejadores`), por lo que genera NameError/500 en vez del error previsto. Prueba faltante: exportar por UI y volver a cargar el archivo por UI.

3. **P1 — El traslado posterior a una promocion pierde el resultado aplicado y los objetos de rollback.** `src/ai_swe/state/continuity.py:647` crea bundle de `HEAD --all`. La promocion escribe bytes sin commit; no entran al bundle. Los arboles de recibo de `tools/rollback.py:143-146` quedan sin referencias y tampoco entran. `continuity.py:1073` omite reconstruir snapshots de runs completados. Reproduccion: promocionar app.py, exportar, importar en una carpeta vacia: el nuevo repo materializa el HEAD anterior, no los bytes promovidos, mientras el historial sigue diciendo completed/promoted. No existen los objetos antes/despues necesarios para rollback. Incluso en el equipo original, git gc puede eventualmente eliminar esos objetos sin referencia. Debe preservarse explicitamente el estado promovido y la clausura de objetos de recibos; no presentar el bundle como respaldo completo de ese estado.

4. **P2 — Fallar una importacion deja reservado para siempre el nombre del nuevo perfil.** `src/ai_swe/state/continuity.py:1307` crea perfil y el bloque `:1325` solo borra su directorio. `state/profiles.py:190-195` mantiene la reclamacion exclusiva en `users/.names/<hash>`. Reproduccion: importar con un nombre nuevo a un destino ocupado; corregir el destino y reintentar el mismo nombre: create rechaza Nombre ya registrado aunque el perfil ya no exista. Hace falta revertir la reclamacion de nombre junto al perfil, bajo el bloqueo del almacen.

## Limites adicionales que deben comunicarse/verificarse

- La UI solo llama `/continuity/import` sobre el perfil autenticado; nunca llama `/auth/import-vault`, que es el flujo de crear perfil nuevo. El perfil destino con ejecuciones se rechaza. El flujo real de perdida de equipo no tiene prueba de navegador.
- El payload de `continuity.py:688-699` incluye SQLite y Git, pero no `vault.json` ni datos de credenciales/configuracion. `import_vault_to_profile` crea una boveda vacia. HF_TOKEN/modelos/tarifas no se recuperan y deben configurarse otra vez; no afirmar portabilidad completa del perfil sin esta salvedad.
- La validez SQLite se reduce a integrity_check y presencia de tres tablas (`continuity.py:962-974`); no valida esquema esperado, triggers/views ni coherencia de checkpoint/run/owner. Un archivo cifrado correcto no demuestra estructura segura. No se confirmo ejecucion arbitraria: la version local de JsonPlusSerializer tiene pickle_fallback=False por defecto y allowlist msgpack explicita, por lo que NO reporto un exploit pickle.
- El limite de importacion verifica 512 MiB de envelope y 256 MiB SQLite, pero no suma bytes de todos los bundles como si hace exportacion. Tampoco hay limite de request antes de cargar/decodear todo el JSON base64. Son carencias de limites y disponibilidad, no evidencia de perdida remota de datos.
- Rebind conserva checkpoints y reescribe solo campos de ruta conocidos. La prueba existente `test_lost_device_e2e_recovery_at_review_gate_without_rerunning_coder_or_reviewer` cubre la puerta de aprobacion con modelos/pruebas simulados; no cubre post-promocion, la UI, auto-backup real ni importacion concurrente.

## Aspectos favorables observados

Memoria FTS parametrizada y filtrada por propietario/repositorio; modos limitados en nodos del grafo; cifrado autenticado de archivos; Backup API SQLite; importacion no aprueba automaticamente; rollback local verifica identidad, HEAD y bytes posteriores y restringe rutas. No se encontro bypass de cookie/CSRF en los endpoints autenticados nuevos durante esta revision focalizada.
