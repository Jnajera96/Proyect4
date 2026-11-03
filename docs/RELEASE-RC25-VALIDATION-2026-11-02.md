# Certificación local del portable rc25

## RC25 — candidato recomendado para pruebas locales

Fecha: 2 de noviembre de 2026. Base de producto `f2554d2`: corrige integridad de
diffs multiarchivo, EOF, LF/CRLF, hash de bytes escritos y promoción autocrlf;
Seguridad distingue errores del motor de resultados de pruebas.

- ZIP: `dist/Windows-v0.2.0-rc25/AISWESystem-windows-x64.zip`.
- SHA-256: `323e3d97ded9b35fbd3dfcd09d6f5d3ebdea4ca6a704bb25098ecdd00833766c`.
- Tamaño: **121319619 bytes**.
- Archivos ZIP: **4746**; manifiesto: **4745** (excluye su propio JSON).
- CRC, fuentes Python, frontend construido y hashes de manifiesto: aprobados.
- Runtime CPython 3.13.14: firmas PSF válidas de python.exe y pythonw.exe.
- Smoke estándar: **14/14**, con perfiles, persistencia, reinicio y cierres ordenados.
- Integridad/sandbox/promoción desde el bundle: **57 PASS / 1 SKIP**.
- Frontend: **41 PASS** y build TypeScript/Vite con Node 24.22.1, offline.

Acta: [RELEASE-RC25-VALIDATION-2026-11-02.md](RELEASE-RC25-VALIDATION-2026-11-02.md).
Evidencia: [RELEASE-RC25-EVIDENCE-2026-11-02.json](RELEASE-RC25-EVIDENCE-2026-11-02.json).
Rc23 y rc24 conservan sus hashes como historia; no contienen el arreglo de integridad
de f2554d2. Pilotos físicos y publicación real GitHub siguen pausados, sin APIs pagadas.

## Construcción y verificación

Por solicitud posterior del usuario se leyó el README público de GitHub para
conciliar pendientes. Esa lectura documental es una excepción explícita al trabajo
offline: no participa en el build, no descarga dependencias ni invoca modelos.
La conciliación queda en `README-PENDING-RECONCILIATION-2026-11-02.md`.

Se normalizaron los errores tipográficos del documento de encargo: `tools` en lugar
de `tolos` y guiones/comillas ASCII para PowerShell. Se usó el archivo CPython
fijado localmente, UV_OFFLINE=1 y npm_config_offline=true, sin descargas ni npm install.
Los binarios oficiales se conservan: no se genera un bootloader PE sin firma.
No se altera Smart App Control, SmartScreen ni configuración privada.

El build se guardó en un directorio nuevo. Sólo `dist/AISWESystem` entra al ZIP,
no el directorio de compilación exterior. Se inspeccionaron .env, .sqlite3, .gguf,
bóvedas/identidades, cachés y residuos del proyecto antes de comprimir. Los binarios
y la biblioteca estándar empaquetada son partes necesarias del runtime, no residuos.
Tras comprimir se verificó CRC, se extrajo el ZIP y se contrastaron todos los
hashes del manifiesto y cada fuente Python con el árbol actual. También coincide
el frontend construido. Se conserva la receta Docker y su detector canónico.

Los tests adicionales importan ai_swe desde el bundle y usan su propio CPython;
comprueban archivos válidos, hashes exactos, EOF/CRLF, corrupción inyectada y promoción
bajo autocrlf. El único SKIP requiere privilegios Windows para crear symlinks:
no se concede ese privilegio ni se debilita la prueba para evitar la omisión.

Se ejecutó `tools/verify_portable_profiles.py` desde .venv sobre la extracción,
con sus plazos originales y PATH de Windows sin Python/Node de desarrollo.
Los 14 controles incluyen registro cifrado, perfil sin token heredado, ejecución
determinista, puerta humana, SQLite/checkpoints, reinicio y dos cierres limpios.
Los datos del smoke están en carpetas temporales, no en perfiles personales.

## Evidencia previa y alcance

La regresión de fuente de f2554d2 ya registró 1.196 PASS / 18 SKIP y 22 PASS
suplementarios Windows Job con CPython no-Store. Se referencia su acta; no se
presenta como una nueva ejecución completa durante este empaquetado. Los conjuntos
de pruebas comparten casos y no deben sumarse como pruebas distintas.

No se ejecutaron modelos remotos, la calculadora del usuario, micrófono físico,
Whisper real, importación en otra PC física ni publicación GitHub. El smoke no
acredita calidad general de software generado ni producción pública; tampoco
convierte los controles Node en un runtime npm disponible offline.

Para usar el arreglo: cerrar el servidor anterior, extraer rc25 completo en una
carpeta nueva y abrir su AISWESystem.cmd. No sobrescribir la única copia de datos.
La actualización no repara automáticamente archivos o corridas ya corruptos,
no borra historial y no inicia otra inferencia por sí sola.

## Pendientes y siguiente ruta

Se conserva 91/100 como estimación técnica informada, no porcentaje certificado.
El cierre local del paquete no sustituye el piloto funcional completo en destino.
La recomendación es estabilizar este candidato y validar un recorrido completo
con criterios de aceptación antes de agregar funciones: idea, confirmación,
código, pruebas, revisión, aprobación, promoción y apertura de la app.

Después: matriz Windows/SAC/voz, continuidad física, publicación del asistente,
calidad de modelos con productos distintos y control de tokens real. Los pilotos
pausados requieren autorización nueva; cualquier API pagada necesita presupuesto
explícito. La disponibilidad de paquetes Node y TLS/operación pública conservan
sus criterios independientes. No se declara 100 % ni despliegue público aprobado.
