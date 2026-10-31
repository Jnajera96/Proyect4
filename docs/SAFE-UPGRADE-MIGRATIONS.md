# Actualización segura y recuperación operativa

Fecha: 31 de octubre de 2026. Base: `203bc70`. Prioridad 6 cerrada para el entorno
local validado. Referencia de diseño: `HANDOFF-CODEX-SAFE-UPGRADE-MIGRATIONS.md`
proporcionado por Antigravity. Este documento describe la implementación real.

## Esquema canónico y arranque

`SchemaMigrator` usa PRAGMA user_version; la versión actual es **3**.

| Paso | Esquema |
| --- | --- |
| v1 | projects, runs, run_events, meta, checkpoints y writes de LangGraph; profile_budget y budget_reservations con campos de reservas conservadoras. |
| v2 | file_cooccurrence, file_observations, memory_documents y memory_fts FTS5, con sus columnas actuales y separación por propietario/repositorio. |
| v3 | schema_migrations_log con fecha y checksum; last_launched_at en projects y cancellation_reason en runs; tablas actuales de snapshots y configuración de continuidad. |

Los nombres reales son run_events, profile_budget y budget_reservations.
Una tabla antigua llamada budget_ledger se preserva sin renombrarla ni vaciarla.
Se conserva la estructura real de file_observations, no la estructura hipotética
de la propuesta. No se borra ninguna tabla ni se reinicia el presupuesto.
Las reservas de coste desconocido conservan su importe; las heredadas sin marca
de despacho se consideran despachadas de forma conservadora.

RunStore migra antes de abrir su conexión de trabajo. Se elimina su antigua
recreación destructiva por cambios de meta.esquema_version. El marcador meta se
mantiene en 2 para que rc9 pueda leer el esquema aditivo nuevo; el versionado real
es user_version=3. ESQUEMA_VERSION sigue exportándose y ahora vale 3.
Un fallo impide inicializar ese almacén y su aplicación privada.

El migrador obtiene BEGIN IMMEDIATE, comprueba el origen y crea el snapshot antes
del primer cambio de esquema. Usa sentencias individuales, sin executescript
dentro de la transacción. Aplica pasos secuenciales, registra sus checksums,
verifica integridad antes y después del commit y cierra todas las conexiones.
Ante un fallo ejecuta rollback y restaura el snapshot mediante reemplazo atómico.
Los WAL comprometidos se incorporan al respaldo con SQLite backup; no se copian
solo los bytes del archivo principal cuando hay un WAL pendiente.

Los respaldos se llaman `state.sqlite3.bak.<timestamp>-<id>.v<version>` y se retienen.
Un bloqueo de sistema operativo serializa migraciones y se libera incluso al
terminar abruptamente el proceso. Se rechazan versiones futuras y archivos
corruptos; no se intenta reparar una base desconocida creando un almacén vacío.

En 200 aperturas de una base ya actualizada: mediana **0,948 ms**, p95 **1,331 ms**,
máximo **2,010 ms**. No hay escaneo completo de integridad ni respaldo en esa ruta.
Es una medición del host validado, no un SLA para cualquier disco o antivirus.

## Uso del actualizador

Cierra la aplicación y conserva la instalación anterior. Extrae el paquete nuevo
en otra carpeta; no sobrescribas el anterior. Desde el proyecto:

```powershell
uv run python tools/upgrade_portable.py --source <instalacion_anterior> --target <instalacion_nueva> --dry-run
uv run python tools/upgrade_portable.py --source <instalacion_anterior> --target <instalacion_nueva> --backup-dir <carpeta_privada>
```

Sin Python de desarrollo, utiliza el intérprete **del paquete nuevo**:

```powershell
& '<nuevo>/runtime/python.exe' -B '<nuevo>/tools/upgrade_portable.py' --source '<anterior>' --target '<nuevo>'
```

Se aceptan --source-dir/--target-dir como alias. La instalación puede indicarse
como raíz AISWESystem, carpeta que la contiene o raíz de build con dist/AISWESystem.
--data-dir selecciona una ubicación externa explícita; por defecto se usa
%LOCALAPPDATA%/AISWESystem, compartida entre versiones instaladas actuales.
No debe ubicarse dentro de ninguno de los paquetes. Las rutas de repositorios
registradas se conservan; no se clonan, publican ni cambian sus commits.

La herramienta conserva también archivos locales heredados (.env, .aiswe-vault,
config, data, users, userdata, var, logs, worktrees) copiándolos a un destino vacío
equivalente. No activa una nueva modalidad de datos locales ni reescribe overrides
absolutos de configuración; las instalaciones actuales siguen usando los datos
externos. No sobrescribe datos preexistentes en el destino. No migra bases de
aplicaciones generadas dentro de worktrees ni bases SQLite arbitrarias.

El preflight consulta procesos locales mediante PowerShell de Windows por su
ruta absoluta y falla de forma cerrada si no puede comprobarlos. No necesita
Python, Node, Git ni PowerShell en el PATH de la aplicación. El launcher nuevo
mantiene una reserva exclusiva sobre los datos instalados mientras está abierto;
el actualizador usa esa misma reserva y comprueba también portables anteriores.
Las versiones antiguas deben permanecer cerradas durante toda la operación.

Antes de migrar se crea un ZIP consolidado con CRC verificado. Todas las bases se
migran primero en copias de preparación. Solo entonces se publican los datos;
los originales instalados quedan retenidos en .pre-upgrade-<id>. Se verifica que
los archivos originales del paquete de destino no hayan cambiado. Si falla una
base posterior o la publicación, se revierten los cambios ya publicados.
La preparación de datos externos está en su mismo volumen para que los renombres
no dependan de que el portable y LOCALAPPDATA estén en la misma unidad.

El JSON final indica backup y previous_data. El ZIP puede contener credenciales
de .env y datos privados: **no está cifrado**, debe guardarse en una carpeta
privada y no debe publicarse. No se añade ningún respaldo al ZIP distribuible ni
al repositorio. No hay eliminación automática de respaldos.

## Interrupciones y retorno a la versión anterior

Un diario pequeño, sincronizado a disco antes del intercambio, distingue prepared
y committed. El siguiente launcher nuevo recupera los datos anteriores antes de
preparar directorios, leer la configuración definitiva o crear la API. Si ya había
datos nuevos, los aparta en .interrupted-<id> y los conserva. Un diario inválido
detiene el proceso sin seguir rutas arbitrarias. Dry-run rechaza un diario pendiente
y no realiza esa recuperación ni cambia datos de usuario.

Después de una interrupción usa primero el launcher nuevo para completar la
recuperación; los binarios antiguos no conocen este diario. Para un retorno manual
tras una actualización exitosa, con todos los servidores cerrados, conserva los
datos actuales con otro nombre y devuelve previous_data a su ruta original. No
mezcles archivos ni sobrescribas una carpeta con otra. Después abre la versión
anterior. El respaldo ZIP conserva un manifiesto con las rutas de procedencia.

## Evidencia

- `uv run pytest tests/test_migrations.py tests/test_upgrade_portable.py`:
  **28 PASS**, UV_OFFLINE=1, `_tmp/safe-upgrade-requested.xml`.
- Regresión completa: **1.022 PASS, 4 SKIP, 0 fallos**, 678,560 s;
  `_tmp/safe-upgrade-all-verified.xml`. Se conservan las 994 pruebas previas.
- 60 pruebas focalizadas de recuperación, launcher y configuración instaladas
  aprobadas antes de la última corrección del preflight; esta corrección queda
  cubierta por la suite final y la actualización real.
- Falla SQL parcial, fallo de integridad posterior al commit, base corrupta,
  versión futura, WAL pendiente y fallo de publicación comprobados.
- Terminaciones reales con os._exit: rollback SQLite, liberación del bloqueo y
  recuperación del directorio ausente o ya sustituido. No se borran los datos nuevos.
- Actualización real con runtimes firmados rc9→rc10, PATH=System32 y datos sintéticos:
  dry-run, esquema 0→3, login de bóveda, checkpoint pausado, memoria y reserva de
  0,75 intactos. Rc9 lee el esquema actualizado; retorno al snapshot original v0
  probado con rc9. Ambos paquetes y el repositorio Git permanecen idénticos.
  `_tmp/safe-upgrade-real-verified/report.json`.
- Frontend 34 PASS y TypeScript/Vite aprobado; no hay cambios de interfaz.
- Portable nuevo: 14/14 controles estándar PASS, ambos cierres código 0,
  `_tmp/safe-upgrade-rc10-smoke/report.json`.
- Cero inferencias pagadas, sin push y sin alterar v0.1.0 → b158d9b.

## Distribución y límites

Paquete: `dist/windows-v0.2.0-safe-upgrade-rc10-verified/AISWESystem-windows-x64.zip`.
SHA-256: `01d0fe77d4f75fc866f92798b26f549cd34191d2742bda6a58f23397c96c1854`.
118.808.072 bytes, 4.730 archivos de manifiesto, CRC y correspondencia de fuente
verificados. Incluye tools/upgrade_portable.py. CPython 3.13.14 con firmas válidas;
no se generan ni se modifican ejecutables PE. Rc9 se conserva. Los directorios
rc10 y rc10-final son candidatos intermedios no aprobados, identificados como tales.

El cierre corresponde a este host Windows con datos sintéticos y runtimes reales.
No acredita cortes físicos de energía, una VM independiente, actualización con
enlaces/junctions ni recuperación completa por UI entre dos equipos. La producción
pública y el aislamiento fuerte de procesos/red siguen pendientes.
