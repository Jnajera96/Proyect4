# Continuidad y restauración — seguimiento del 30 de octubre de 2026

## Defecto reproducido y corrección

La vista de sesión convertía el archivo seleccionado a Base64 URL-safe y quitaba
el relleno `=`. `POST /continuity/import` exige Base64 estándar mediante
`base64.b64decode(..., validate=True)`. Por ello podía rechazar un respaldo válido
antes de descifrarlo. Se corrigió exclusivamente el emisor: conservar `btoa(binary)`.
No se relajó la validación del backend ni se modificó el formato cifrado.

`tools/verify_continuity_upload.cjs` monta la vista React real en Chromium y usa
una API sintética estricta. Antes del cambio la restauración fue rechazada; tras
el cambio pasan cuatro comprobaciones: alfabeto/relleno estándar, bytes binarios
intactos, ruta autorizada preservada y contraseña borrada tras el éxito.
El archivo de prueba es sintético: esta prueba no acredita por sí sola descifrado
ni importación del backend. Informe: `_tmp/continuity-upload/report.json`.

## Recuperación del backend

Se ejecutaron `tests/test_continuity_m.py` y `tests/test_continuity_l.py`:

- Entorno de desarrollo: **17 PASS**, `_tmp/continuity-followup.xml`.
- CPython y módulos del portable rc3: **17 PASS**, `_tmp/continuity-portable.xml`.
  Se anuló `pythonpath=src` de pytest y se comprobó que `continuity.__file__`
  corresponde a `dist/windows-v0.2.0-operational-rc3/dist/AISWESystem/app/ai_swe/`.
- Frontend: **32 PASS** y `npm run build` aprobado.
- Sin cambios de backend: continúa vigente la regresión previa de 973 PASS/4 SKIP;
  no se presenta como una nueva ejecución completa en este seguimiento.

La cobertura incluye captura de archivos modificados/binarios/nuevos/borrados,
pausa y reanudación, cifrado y rechazo de alteraciones/contraseña incorrecta,
auto-respaldo diferido y escritura atómica, memoria por usuario y repositorio,
modos y rollback. La recuperación simulada usa perfil y repositorio nuevos,
preserva gasto/memoria/puerta pendiente y permite promover tras aprobación sin
repetir Coder, Runner ni Reviewer. Rechaza destinos ocupados y repositorios sucios.
Son pruebas offline con fixtures y nodos sustituidos, no inferencias reales.

## Distribución y piloto

El arreglo de frontend se distribuye en un rc4 nuevo; rc3 se conserva inmutable.
Hash y resultado del smoke se registran en el acta operativa del día:
**14 controles portable PASS**, salida 0, cero llamadas pagadas, sobre el ZIP
rc4 extraído con PATH reducido y datos temporales aislados.
Guía del piloto independiente: `PORTABLE-SECOND-PC-PILOT.md`.

No se usaron credenciales reales ni se alteraron repositorios o perfiles del
usuario. La simulación en dos directorios del mismo host no cierra la validación
entre equipos. Tampoco acredita la recuperación de perfil perdido desde toda la
UI, la sincronización cloud, una publicación real o aislamiento fuerte de código.
