# Rc11 — publicación guiada y vista previa de borradores

Fecha: 31 de octubre de 2026. Rama `feature/v0.2.0-madre-continuity`.
Base recibida: `46499c9`, posterior al cierre de tokens `32816a0`.

## Alcance y decisiones

Se conserva la corrección de Antigravity para evitar pruebas web dependientes de
js2py y permitir revisar un borrador cuando el motor escala a una persona. La
vista previa acepta needs_human/awaiting_approval con archivos registrados e
integridad válida. No autoriza publicar ni declara pruebas exitosas. Un run activo
no puede abrir su worktree mientras los agentes escriben.

Se separa esa autorización de approved_repository: publicar requiere completed y
recibo promoted, rutas dentro del repositorio y hashes coincidentes. La tarjeta
advierte que el borrador no está verificado y ejecuta código en el propio equipo;
el botón de publicación queda deshabilitado hasta la promoción.

## Flujo de publicación

1. Comprobaciones locales antes de cualquier petición HTTP: proyecto autorizado,
   promoción aprobada, ausencia de remoto y de cambios preparados ajenos, archivos
   permitidos, historial inicial acotado y búsqueda de credenciales reconocibles.
   También se inspecciona el commit inicial, para no filtrar un secreto que ya fue
   eliminado de la copia de trabajo.
2. GET https://api.github.com/user valida identidad y exige X-OAuth-Scopes con repo.
   El asistente requiere PAT clásico. Rechaza scopes insuficientes o ausentes;
   no atribuye permisos a un token fine-grained por su formato.
3. POST /user/repos o /orgs/{organization}/repos crea el repositorio con la
   visibilidad elegida, privada por defecto. La organización es opcional y su
   nombre se valida; GitHub verifica los derechos efectivos de creación allí.
4. Se confirma únicamente el conjunto aprobado más README, se agrega origin sin
   credenciales y se ejecuta push -u origin sobre la rama local, sin force y con
   hooks, configuración global y ayudas de credenciales deshabilitados.
5. Sólo tras el retorno exitoso de Git se presenta el enlace de publicación.

El endpoint POST /projects/{project_id}/publish-github mantiene la respuesta JSON
para clientes anteriores. Con ?stream=true entrega NDJSON con las fases reales
validating, creating, uploading y la confirmación final; los errores son eventos
explícitos. El frontend conserva autenticación/CSRF y procesa bloques UTF-8
fragmentados. Un stream incompleto no se transforma en éxito ni se reintenta solo.

## Protección del PAT

SecretStr, registro en el redactor central y uso efímero por petición. No se
persiste en SQLite, configuración Git, URL remota, eventos ni archivos del bundle.
Git recibe la autorización por entorno de proceso, no por argumentos ni URL.
Las excepciones de HTTP y Git no incluyen cuerpos remotos, stderr ni cabeceras.
Los 422 del endpoint tampoco devuelven el cuerpo de entrada con el PAT.
El modal lo oculta, deshabilita cambios durante la operación y lo vacía al terminar.

## Verificación

Regresión completa: **1.050 PASS, 4 SKIP, 0 fallos**, 476,10 segundos.
Se conservan las 1.030 pruebas previas. Evidencia de ejecución:

- `_tmp/rc11-focused.xml`: pruebas focalizadas de publicación y lanzadores.
- `_tmp/rc11-backend.xml`: regresión completa offline.
- `_tmp/rc11-bundle-focused.xml`: módulos del ZIP con CPython firmado, sin src local.
- `_tmp/rc11-portable-smoke/report.json`: perfiles/reinicio/SQLite del ZIP extraído.
- `dist/windows-v0.2.0-rc11/build-report.json`: dependencias y firmas de CPython.

## Límites y recuperación

El cierre de esta tarea es de implementación y verificación offline. GET/POST de
GitHub y push de publicación se sustituyen por mocks; no hubo repositorio remoto
real creado ni se usó un PAT real. El piloto autorizado con una cuenta de GitHub
continúa pendiente. Las comprobaciones no acreditan permisos efectivos de una
organización externa ni sustituyen una prueba en otra PC o VM Windows.

La publicación sencilla sigue reservada a proyectos nuevos con un único commit
base, sin remoto existente ni historial ajeno. No reemplaza conexiones previas ni
ofrece publicación incremental. GitHub aloja el código; no despliega la aplicación.

Si falla después de crear el repositorio remoto, el mensaje conserva su enlace y
los archivos locales. Puede quedar un commit y origin sin push final: se debe
revisar antes de reintentar, sin borrar automáticamente el repositorio remoto ni
resetear el Git local. Cerrar la pestaña no garantiza cancelar un push ya iniciado.

El PAT es efímero a nivel de aplicación, no memoria protegida del sistema operativo.
La redacción y el detector de formatos conocidos no prueban ausencia de todo
secreto arbitrario dentro de código generado: el usuario debe revisar los archivos.
El worktree sigue sin aislar procesos ni red. No se declara producción pública ni
se consume inferencia pagada. Se preservan los portables anteriores y v0.1.0.

## Candidato rc11 verificado localmente

ZIP: `dist/windows-v0.2.0-rc11/AISWESystem-windows-x64.zip`.
SHA-256: `e57a3e87e37059f52691e644d0ed741215cd5e50165e019982439739204fee60`.
Tamaño: 121.285.054 bytes. Manifiesto: 4.735 archivos; CRC, hashes y correspondencia
de todos los módulos Python con la fuente verificados en la extracción.

- 38 pruebas focalizadas PASS en desarrollo y 38 PASS con el CPython/módulos del ZIP.
- Frontend: 38 PASS, TypeScript/Vite aprobado.
- Smoke portable estándar: 14/14 PASS; ambos procesos cierran con código 0.
- CPython 3.13.14: python.exe/pythonw.exe con firmas válidas de Python Software Foundation.
- Autocomprobación adicional `_tmp/rc11-local-push-report.json`: push real por
  transporte file a un bare descartable, upstream y contenido remoto verificados;
  HTTPS bloqueado, creación/identidad de GitHub simuladas. No se usó el remoto del proyecto.

El push HTTP de las pruebas unitarias es simulado. La autocomprobación Git local
complementa esas pruebas, pero no acredita autenticación ni permisos reales de
GitHub. Fuente y paquete incluyen la misma implementación; los informes y este
acta quedan en el commit de cierre. Los portables anteriores se conservan.

Referencias de contrato: [Repositorios REST de GitHub](https://docs.github.com/en/rest/repos/repos)
y [Scopes OAuth](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps).
