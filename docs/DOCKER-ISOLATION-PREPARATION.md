# Preparación del aislamiento con Docker Desktop

Fecha: 1 de noviembre de 2026. Elección explícita del usuario: validar en este
equipo Windows con Docker Desktop. **Preparación verificada; backend de la aplicación
todavía no integrado.** No se declara seguro el runner local por esta prueba.

## Entorno observado

Docker no estaba en PATH ni en Program Files, pero ya estaba instalado por usuario
en `%LOCALAPPDATA%/Programs/DockerDesktop`. CLI con firma válida de Docker Inc;
cliente/servidor consultados: 29.9.2. Se confirmó motor Linux local por el pipe
`npipe:////./pipe/dockerDesktopLinuxEngine`. WSL 2.7.3, Ubuntu predeterminada en WSL2,
Windows 11 Pro x64, aproximadamente 16 GB de RAM e hipervisor presente.

No se instaló Docker, WSL ni software de sistema, ni se cambió PATH, BIOS,
Smart App Control, configuración de usuario o características de Windows. No hubo
reinicios. Se usaron las [opciones oficiales de Docker para Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
para localizar la instalación por usuario; no se concluyó que el motor faltase
sólo por no encontrarlo en PATH. Esta observación no certifica otros equipos.

## Imagen preparada

- Base oficial fijada: `python:3.13.14-slim-bookworm@sha256:67a1e1f215ccda113cfc024e8639049257e88f273898f595b61476d128d387e8`.
- Imagen local construida: `sha256:55c177ad698e01456dec9f3d86c06f54b6c6a42b74b1c0e6844696b1fbbced60`.
- Receta: `packaging/docker-runner/Dockerfile`. El contexto de build contiene sólo
  receta y requisitos; no se envían el proyecto, perfiles, bóvedas o archivos .env.
- Pytest 9.1.1, Ruff 0.16.10, iniconfig 2.3.1, packaging 26.3, pluggy 1.6.0 y
  pygments 2.21.0: versiones y hashes de ruedas Linux amd64 extraídos de uv.lock.
  Pip exige hashes y ruedas binarias; no hay resolución a versiones flotantes ni
  compilación de dependencias desde fuente. Las descargas ocurren sólo en el build.
- El build instala dependencias como root dentro de la imagen y después fija
  USER 65532:65532. Eso no habilita root para código generado ni instala paquetes
  en el Python del host.

El primer pull falló al buscar docker-credential-desktop fuera de PATH. Se repitió
con configuración Docker temporal anónima, sin modificar la configuración del
usuario. El build usó el constructor legado y emitió su aviso de deprecación:
preparar descubrimiento de buildx/BuildKit antes de automatizar la construcción
definitiva. No se instaló ni se desactivó ningún componente para ocultar el aviso.

## Prueba real, no mock

`tools/verify_docker_isolation.py` exige un ID local inmutable, fuerza el endpoint
local y usa configuración Docker anónima y captura de salida acotada del proyecto.
No descarga imágenes durante la prueba (`--pull=never`). Sólo monta una carpeta
recién creada con canarios y un test sintético, en modo de lectura. No monta el
repositorio real, el socket Docker ni directorios del usuario.

Resultado: **20/20 controles aprobados**, incluyendo:

- UID no root, capacidades efectivas cero, no-new-privileges y seccomp activo.
- Canario de entrada legible; canario exterior no montado; escrituras sobre entrada
  y raíz rechazadas, permitiendo escritura temporal sólo en el contenedor.
- Egreso a IP externa rechazado con ENETUNREACH; socket local permitido como control.
- Cgroups efectivos: 512 MiB, un CPU y límite de 32 PID/hilos. Son controles Linux
  distintos del tiempo de CPU acumulado de los Job Objects de Windows.
- Pytest y Ruff ejecutados de verdad sobre los mismos bytes del fixture.
- Limpieza y comprobación de ausencia de contenedores propios por ID y etiqueta
  aleatoria, sin prune, borrado de imágenes ni modificaciones a otros contenedores.

También se comprobaron tres rechazos previos a crear recursos: imagen mutable,
directorio de salida ocupado y Python con optimizaciones que desactivarían asserts.
El directorio ocupado y su informe conservaron su hash.

La primera prueba falló en Ruff EXE002: el bind mount Windows mostraba como
ejecutable un test sin shebang. El diagnóstico y su fallo se conservaron. Se
copió el fixture dentro del tmpfs Linux, normalizando a 0644 y comprobando sus bytes;
no se añadió una exclusión de lint ni se debilitó el montaje de lectura.

Evidencia durable: `DOCKER-ISOLATION-PREPARATION-EVIDENCE.json`. Informes locales:
`_tmp/docker-proof-20261101/report.json` y `_tmp/docker-proof-diagnostic-20261101/report.json`
son fallidos; `_tmp/docker-proof-final-20261101/report.json` es el aprobado.
La imagen se conserva localmente para el siguiente incremento; no se publicó.

## Qué falta integrar

1. Snapshot aprobado, con exclusión de secretos/.git, rechazo de enlaces y reparse
   points, protección frente a carreras de lectura y manifiesto de integridad.
2. Backend de ejecución con targets cerrados, imagen local inmutable, límites y
   sólo snapshot desechable; sin comandos, flags o montajes elegidos por el modelo.
3. Preflight/API/UI explícitos para motor/imagen faltantes: sin fallback silencioso
   al runner local cuando se haya solicitado aislamiento.
4. Cancelación y timeout sobre el contenedor real, no sólo el CLI; confirmar cierre,
   limpiar recursos propios y conservar evidencia/ledger aun ante errores del motor.
5. E2E desde la aplicación y ataques sintéticos: escapes de rutas/enlaces, acceso
   a canarios, red, tormentas de procesos, salida masiva y fallos durante limpieza.

La prueba actual usa datos controlados, no código hostil ni un repositorio arbitrario.
La aplicación y el ZIP rc16 siguen usando el runner local con cuotas Windows.
El script pertenece al repositorio; Docker no se incluye en el ZIP. No se acredita
aislamiento de extremo a extremo, independencia del kernel ni producción pública.
Los pilotos de recuperación entre PC y publicación real GitHub continúan pausados.

Referencias primarias: [ejecución y restricciones](https://docs.docker.com/engine/containers/run/)
y [creación de contenedores](https://docs.docker.com/reference/cli/docker/container/create/).
