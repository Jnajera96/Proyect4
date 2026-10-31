# Restauración de varios repositorios — 30 de octubre de 2026

## Contrato y experiencia

La pantalla «Restaurar desde un respaldo» permite leer el archivo antes de crear
el perfil. Una vez comprobada la contraseña muestra cada repositorio de origen,
con un campo de carpeta autorizada de destino independiente. Cambiar archivo o
contraseña descarta la lectura previa y bloquea restaurar hasta volver a leerlo.
Los respaldos sin repositorios no exigen inventar una ruta de destino.

Nuevo endpoint: `POST /auth/inspect-vault`.

- Entrada JSON: `archive_b64` (Base64 estándar) y `password` (secreto, 8–1024 caracteres).
- Salida 200: `profile_name` y `repositories` (lista de rutas originales).
- 400: archivo, autenticidad, contraseña o metadatos inválidos; mensaje genérico.
- 422: contrato de entrada inválido; no devuelve la contraseña recibida.
- Conserva rechazo de origen externo, limitación de intentos y `Cache-Control: no-store`.
- No crea perfil/sesión, no materializa repositorios, no ejecuta agentes y no
  devuelve SQLite, contenido de archivos, claves ni tokens.

No se añade caché del descifrado en servidor: la importación vuelve a verificar
el archivo. El navegador conserva sus datos de envío solo durante el asistente.

## Seguridad y defecto corregido

Antes de reconstruir repositorios se resuelven todas las asignaciones y se
rechazan rutas faltantes, relativas, duplicadas, anidadas o solapadas con los
worktrees. Se conservan rechazos de enlaces, destinos ocupados y repositorios
incompatibles. Las comprobaciones de mapeo no implican una transacción global de
sistema de archivos: un fallo posterior de Git puede dejar carpetas nuevas ya
creadas; no se eliminan automáticamente destinos autorizados por el usuario.

La prueba de reintento reprodujo un defecto previo: una importación fallida
borraba la carpeta del perfil recién creado pero dejaba su reserva en `.names`.
Esto impedía corregir el mapeo y reutilizar el nombre. Ahora la reversión comprueba
la raíz confinada y la propiedad de la reserva antes de eliminar ese perfil nuevo
y liberar su nombre. No existe una nueva API para borrar perfiles existentes.
Se prueba que otro almacén no puede revertir una identidad ajena y que otro perfil
conserva su acceso y bóveda.

## Evidencia offline

- **38 pruebas backend PASS**, regresión de perfiles, recuperación y continuidad:
  `_tmp/multi-repo-regression.xml`.
- API real: respaldos de uno/dos repositorios, lectura sin crear destinos,
  contraseña/origen/entrada inválidos, rechazo de asignación incompleta,
  duplicada y anidada sin crear los repositorios, reintento con mismo nombre,
  importación correcta y conservación de puertas y rutas después de reiniciar.
- UI real con API de fixture: **7 controles PASS**,
  `_tmp/profile-restore-browser/report.json`. No acredita descifrado de su archivo
  sintético; el descifrado se verifica por separado en las pruebas API reales.
- **32 frontend PASS** y TypeScript/Vite aprobado.
- Pruebas de lectura/importación repetidas con CPython y módulos de rc6:
  **2 PASS**, `_tmp/profile-import-rc6.xml` (sin sumar repeticiones a los 38 casos).
- ZIP rc6 extraído: **14 controles portable PASS**, salida 0, cero llamadas
  pagadas; perfiles, dos arranques, checkpoint y SQLite persistente/íntegro.
- Ruff focalizado (API, perfiles y pruebas) y `git diff --check` aprobados.
  `state/continuity.py` conserva deuda de estilo previa, sin refactor general.

Los fallos intermedios por reserva de nombre quedaron reproducidos y corregidos.
También se corrigió una aserción añadida en el bloque de prueba equivocado; no se
eliminaron ni relajaron las comprobaciones existentes.

## Límites

Sin inferencias pagadas, publicación en GitHub ni perfiles reales del usuario.
No se afirma cierre de producción pública ni recuperación real entre dos equipos.
La comprobación completa de esa experiencia sigue en el piloto documentado.
rc5 se conserva; este cambio se prepara en rc6, con hash/evidencia en el acta
operativa y en sus informes de distribución.
