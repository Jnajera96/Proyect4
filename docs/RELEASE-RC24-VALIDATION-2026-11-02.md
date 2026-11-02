# Certificación local del candidato rc24

Fecha: 2 de noviembre de 2026. Alcance: Windows local, sin servicios remotos.

## RC24 — validación local offline (2 de noviembre de 2026)

Fuentes de `e47c40f`, incluidas recuperación `67e6fef`, integración Node/seguridad
`a5e7e7e` y autorización npm `e47c40f`. Sin cambios de lógica de producto en este
cierre: se añaden comprobaciones y documentación.

- Backend desde `.venv`: **1185 PASS / 18 SKIP**.
- Frontend: **39 PASS**, TypeScript/Vite aprobados con Node 24.22.1 y npm offline.
- Seguridad y respaldo: **11 PASS**; paquete: **47 PASS**.
- Suplemento Windows Job con CPython oficial: **22 PASS / 0 SKIP**.
- Smoke portable estándar: **14/14**, con reinicio y ambos cierres ordenados.
- ZIP: `dist/windows-v0.2.0-rc24/AISWESystem-windows-x64.zip`.
- SHA-256: `10794bd86428bfcde983a0ed353e73e17285ca157bd8ec5bb6a926aa1d94c480`.
- Tamaño: **121318903 bytes**; manifiesto: **4745 archivos**.

Acta: [RELEASE-RC24-VALIDATION-2026-11-02.md](RELEASE-RC24-VALIDATION-2026-11-02.md).
Evidencia: [RELEASE-RC24-EVIDENCE-2026-11-02.json](RELEASE-RC24-EVIDENCE-2026-11-02.json).
Rc23 conserva su hash. Cero consumo de API y ningún push; pilotos GitHub y dos
PC físicas pausados. La estimación 91/100 no se convierte en 100 % por este smoke.

## Seguridad y auto-respaldo

La prueba se ejecuta en la aplicación de perfiles real, no únicamente en el
backend hijo. `/auth/login` es la ruta implementada; no existe `/profiles/auth`.
Se comprueba HSTS en `/health` y `/auth/status` con archivos de certificado/clave
configurados, y ausencia de HSTS cuando no hay configuración. Es una prueba de
cabeceras: los archivos son fixtures sintéticos, no certificados TLS válidos.
No se certifica terminación TLS, validez de certificados ni exposición pública.

Diez intentos incorrectos obtienen 401; el siguiente obtiene 429 con
`Retry-After: 60`, `Cache-Control: no-store` y auditoría `RATE_LIMIT_EXCEEDED`.
La contraseña sintética no aparece en respuesta ni logs capturados.

La prueba autenticada registra un perfil y comprueba que ContinuityStore recibe
su clave y header en memoria, sin almacenar contraseña en su campo `_password`.
Configura respaldo, crea una inspección y espera que el worker llegue a puerta
humana y produzca el `.aiswe-vault`; no llama manualmente a auto_backup.
Verifica ausencia de contraseña en archivo/logs INFO, rechazo de contraseña
incorrecta, descifrado/restauración en otro directorio y conservación de run_id y
puerta pendiente. No representa recuperación en una PC física distinta.

## Empaquetado reproducible y límites

La suite de `.venv` omite 14 casos Windows Job por su intérprete base Store.
Se ejecutan por separado con CPython oficial firmado; los resultados se registran
sin sumar casos duplicados ni alterar guards. Las otras cuatro omisiones son
proveedor remoto, STT real y dos casos de symlink sin privilegios. No se elevan
privilegios ni se descargan modelos para forzar su ejecución.

Build sin descarga: frontend propio, CPython oficial 3.13.14 ya disponible y
dependencias de `.venv` contrastadas con el lock y hashes RECORD. UV_OFFLINE y
npm_config_offline activos. No se ejecuta npm install ni scripts de apps generadas.
Se comprueban firmas PSF de python.exe/pythonw.exe; no se afirma que todas las DLL
de ruedas oficiales estén firmadas. No se modifica ni desactiva Smart App Control.

El ZIP se crea en directorio nuevo, se comprueba CRC, se extrae y se contrastan
todos los hashes del manifiesto y cada fuente Python con el árbol de trabajo,
además de la receta Docker. El conteo de manifiesto excluye su propio archivo;
el ZIP contiene ese archivo adicional. El smoke comprueba ausencia de archivos
privados, perfiles sin token heredado, checkpoint, SQLite, reinicio y cierre.

Las fixtures de API mono-perfil del runtime empaquetado reciben
AI_SWE_PROFILE_MODE=false; las de perfiles lo solicitan explícitamente. El smoke
usa el modo instalado de perfiles predeterminado y no necesita Python/Node del
PATH. La prueba de cabecera HSTS no equivale a un navegador con HTTPS real.

Las autorizaciones Node ya están integradas y empaquetadas: lista vacía deniega,
imports requieren declaración, y el bloqueo detiene Coder/runner antes de targets.
No se instala ni acredita disponibilidad de paquetes npm o ejecución Node aislada.
Los pilotos físicos y de publicación siguen pausados. La guía de segunda PC
prepara voz offline, importación de bóveda y evidencia SAC/SmartScreen sin ejecutarlos.
