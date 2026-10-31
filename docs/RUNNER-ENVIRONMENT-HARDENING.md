# Entorno mínimo del ejecutor y plan de aislamiento

Fecha: 31 de octubre de 2026. Base: `a8be2ee`.
Los pilotos de recuperación entre PC y publicación GitHub permanecen pausados.
No se hacen inferencias ni consultas de saldo en esta tarea.

## Defecto reproducido y cerrado

_entorno copiaba os.environ completo. Una prueba pytest generada podía leer
HF_TOKEN, AI_SWE_HF_TOKEN, OPENAI_API_KEY y cualquier contraseña de nombre arbitrario
heredada del servidor. Se reprodujo con valores sintéticos y un proceso pytest
real, sin exponer tokens reales. También se heredaban PYTHONHOME, proxies y
opciones/plugins de pytest definidos por el padre.

Ahora el hijo recibe una lista cerrada de variables operativas: PATH, SYSTEMROOT,
WINDIR, COMSPEC, SYSTEMDRIVE, PATHEXT, TEMP, TMP, LANG, LC_ALL, LC_CTYPE y TZ.
Se añade PYTHONDONTWRITEBYTECODE=1 y se reconstruye PYTHONPATH sólo desde src del
worktree cuando existe. Si no existe src, no se restaura la ruta del padre.
No se mantiene una lista de nombres de secretos: toda variable no permitida se
excluye, incluidas credenciales con nombres personalizados y configuración AI_SWE.

Se conservan los targets cerrados, shell=False, el intérprete del proyecto, cwd
del worktree, timeout y evidencia TestRun. La ejecución no recibe nuevas órdenes
del modelo ni cambia el registro completo de evidencia.

## Verificación local

- Antes del cambio: 2 pruebas nuevas fallaron y reprodujeron la herencia.
- Después: 33 pruebas focalizadas PASS, incluidas 3 nuevas de entorno.
- Se usa Git/worktree y un subproceso pytest reales para comprobar que las
  credenciales sintéticas no aparecen en el hijo ni en su salida.
- Se comprueba la eliminación de controles Python/pytest/proxy del padre y la
  ausencia de PYTHONPATH original cuando el worktree no tiene src.
- Ruff focalizado aprobado y diff sin errores.
- Evidencia local: _tmp/runner-environment-before.xml y
  _tmp/runner-environment-focused.xml. El primero es evidencia histórica de fallo,
  no un resultado aprobado. El código del test no vuelca el entorno del equipo.

## Lo que esta corrección no protege

El proceso sigue ejecutándose con los permisos del usuario. Puede leer archivos
accesibles de ese usuario, abrir red, crear hijos o consumir recursos. El worktree
no es aislamiento de ejecución. PATH/TEMP y las variables operativas permitidas
siguen siendo visibles. Las credenciales en archivos tampoco quedan protegidas
por limpiar el entorno. No se declara aptitud para ejecutar código hostil ni para
ofrecer el sistema como servicio público.

El timeout y el recorte de TestRun actuales no son límites fuertes: la captura se
acumula antes de recortarse y el cierre del hijo directo no demuestra que hayan
terminado todos sus descendientes. Esas garantías forman parte del trabajo siguiente.

## Próximo incremento: Runner aislado

No se detectó docker ni podman en PATH ni en las rutas estándar comprobadas de
Windows. No se instaló software ni se modificó la protección de Windows. Por tanto
no se implementa ni se declara probado un backend de contenedor ficticio.

El siguiente incremento debe cerrar, en orden:

1. Preparar en un host de prueba un motor de contenedores y una imagen local
   confiable fijada por digest, con Python/pytest/ruff y dependencias autorizadas.
   Sin descargas ni instalación de dependencias durante una ejecución generada.
2. Copiar únicamente el snapshot aprobado para pruebas a un espacio desechable.
   No montar el repositorio real, .git, perfiles, bóvedas, .env del servidor,
   directorios de usuario ni el socket del motor. Validar enlaces y junctions.
3. Ejecutar como usuario sin privilegios, raíz de sólo lectura, red desactivada,
   sin capacidades extra y con límites de CPU, RAM, procesos, tiempo y salida.
   Reservar únicamente el espacio temporal necesario para pruebas y sus archivos.
4. Mantener los targets de la tabla cerrada. El modelo no elige imágenes, montajes,
   variables, flags del motor ni comandos libres.
5. Cancelar y comprobar el término de todo el contenedor y descendientes antes de
   emitir evidencia terminal. Recoger sólo resultados acotados y limpiar únicamente
   recursos propios, preservando logs y recibos verificables sin secretos.
6. Si el modo aislado fue solicitado y el motor/imagen no está disponible, fallar
   de forma explícita: nunca degradar silenciosamente a ejecución local ni registrar
   pruebas aprobadas sin ejecutarlas. La UI debe explicar el requisito faltante.
7. Probar ataques reales en datos sintéticos: lectura de canarios fuera del
   snapshot, variables del servidor, salida a red, enlaces, escritura fuera del
   área de trabajo, tormenta de procesos, salida masiva y cancelación. Comprobar
   también pytest/ruff positivos, persistencia de evidencias y fallos del motor.

Las pruebas con mocks pueden verificar construcción de comandos y fallos, pero no
sustituyen esas pruebas de aislamiento con un motor real. Los contenedores comparten
el kernel del host: una entrega pública requiere revisar además el despliegue y
los límites de su plataforma, no sólo añadir un comando docker al runner.

## Distribución

Se conserva rc11 y se prepara rc12 en un directorio nuevo para verificar el worker
embebido con el entorno mínimo y repetir el smoke del ZIP extraído. Los paquetes
anteriores no adquieren esta corrección por actualizar únicamente el repositorio.
La matriz Windows independiente continúa pendiente.

Referencias para el incremento de contenedores:
[Seguridad de Docker Engine](https://docs.docker.com/engine/security/) y
[ejecución y límites de contenedores](https://docs.docker.com/engine/containers/run/).
Estas referencias orientan el diseño; no prueban aislamiento en este host.

## Candidato rc12

Se construyó en directorio nuevo con CPython oficial firmado y se verificó la
extracción del ZIP: CRC, 4.735 hashes del manifiesto y correspondencia de todos los
módulos Python con la fuente actual. Incluye también la compactación de contexto
y el selector con evidencia real de las diez rutas de modelos.

Las tres pruebas nuevas de entorno aprobaron ejecutadas por el CPython y módulos
del ZIP, con sys._ai_swe_bundle activo: el subproceso usó start.py y el worker
embebido, no el intérprete ni src de desarrollo. Informe:
`_tmp/runner-rc12-embedded.xml`. Se usaron únicamente
repositorios y credenciales sintéticos.

Paquete: `dist/windows-v0.2.0-rc12-security/AISWESystem-windows-x64.zip`.
SHA-256: `0b6c1e2d77eefa79c6d39f26f896a5989db03c13184aa044df62127a65e837cd`.
Tamaño: 121.286.030 bytes. rc11 y anteriores se conservan.

Smoke estándar del ZIP extraído: **14/14 PASS**, ambos cierres código 0,
SQLite/checkpoint y perfil persistentes. Informe:
`_tmp/runner-rc12-portable-smoke/report.json`. **Rc12 aprobado en este host local**;
no acredita aislamiento fuerte ni una VM o PC independiente.


## Regresión completa

1.065 backend PASS, 4 SKIP, 0 fallos, 545,81 s. Se conservan las 1.062 pruebas
previas. Informe: `_tmp/runner-environment-full.xml`. Frontend: 39 PASS y
compilación TypeScript/Vite aprobada; Ruff de runner y tests aprobado.
Cero inferencias nuevas, sin push y sin alteración del tag histórico v0.1.0.
