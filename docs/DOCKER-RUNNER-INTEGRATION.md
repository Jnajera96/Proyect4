# Ejecutor Docker opcional para pruebas generadas

Fecha: 1 de noviembre de 2026. Rama `feature/v0.2.0-madre-continuity`.
Base: `d0fadb4`. Implementación sin inferencias pagadas ni publicación Git.

## Alcance

Se conserva LangGraph, los contratos, el worktree para editar y las dos puertas
humanas. Cuando `runner_docker` está configurado, sólo los objetivos cerrados
`pytest.unit`, `pytest.integration` y `ruff.check` se ejecutan en Docker Desktop
Linux local. Un motor detenido, imagen ausente o protocolo incorrecto bloquean
la construcción; no se descarga una imagen ni se vuelve silenciosamente al host.
La preparación muestra la causa en el compositor. El Coder repite la comprobación
antes de pedir una propuesta al modelo, incluso si se elude el preflight de la UI.

El valor predeterminado sigue siendo el ejecutor Windows con Job Objects.
No se modificó el `.env` privado. La integración opcional no afirma que todas
las instalaciones anteriores queden aisladas automáticamente.

## Datos y fronteras

1. Se crea una carpeta temporal nueva por objetivo. La copia Windows mantiene
   handles que impiden escritura/borrado mientras se leen las entradas, rechaza
   dispositivos, hardlinks, junctions y otros reparse points y verifica rutas
   finales. Límites: 64 MiB, 2.000 archivos, 4.000 entradas y profundidad 32.
2. Se excluyen `.git`, entornos, cachés, carpetas privadas conocidas, `.env*`,
   `*.aiswe-vault`, `credentials.json`, `secrets.json` y claves SSH conocidas.
   Esto no detecta todos los secretos que alguien incruste en código arbitrario.
3. Se monta exclusivamente esa copia, en lectura. No se monta el repositorio
   original, la bóveda, el perfil ni el socket Docker. Un manifiesto SHA-256
   identifica los bytes; el worker comprueba inventario y hashes antes de ejecutar.
4. El worker copia el código a un tmpfs y normaliza archivos a 0644. La raíz es
   de lectura, la red está deshabilitada, seccomp está activo y no se permiten
   privilegios nuevos. El entorno no hereda credenciales del servidor.
5. El PID 1 de la imagen empieza con UID 0 y **sólo** SETUID/SETGID para crear el
   worker UID 65532. Después se reduce a UID 65533. El código del proyecto nunca
   corre como root; no puede detener el watchdog de otro UID. El supervisor
   limita tiempo y CPU de usuario acumulada del cgroup, y sale si quedan huérfanos.
   Al morir el PID 1, el kernel termina el espacio de procesos del contenedor.
6. Cuotas Docker propias: 512 MiB RAM/swap total idéntico, 1 CPU de velocidad,
   600 s de CPU de usuario acumulada, 32 procesos/hilos, tmpfs `/tmp` 64 MiB y
   `/workspace` 256 MiB. No se reinterpretan las cuotas Windows como cuotas Linux.
7. La limpieza sólo elimina IDs cuya etiqueta aleatoria pertenece al objetivo.
   Comprueba su desaparición antes de devolver el resultado o confirmar cancelar.
   Una creación de resultado incierto o fallo de limpieza conserva snapshot y
   `recovery.json`; se requiere intervención. No se anuncia cancelación confirmada,
   no se borra el worktree y no se liberan reservas como si el proceso hubiera parado.

No hay `prune` global, montajes arbitrarios ni flags o comandos elegidos por el LLM.
Los resultados que terminan conservan el comando de preparación, imagen y hash
del snapshot en `TestRun.argv`. Un timeout conserva el comando Docker que agotó
el plazo, nunca un comando Python nativo que no se ejecutó.
Códigos: 124 plazo, 125 descendientes, 126 CPU; otros fallos mantienen la salida real.
La captura conserva colas acotadas de 200.000 caracteres por canal.

## Activación deliberada

Requiere Docker Desktop con contenedores Linux, disponible en su ruta por usuario
o en `C:/Program Files/Docker/Docker/resources/bin/docker.exe`. Se utiliza el
endpoint local `npipe:////./pipe/dockerDesktopLinuxEngine`; no un contexto remoto.

Construir `packaging/docker-runner` (o `tools/docker-runner` del portable) con
Docker y obtener su ID con `docker image inspect`. La receta fija la base oficial
Python 3.13.14 slim por digest y seis ruedas con hashes. La construcción inicial
necesita acceso a los registros; ejecutar pruebas no requiere red ni descarga.

En el archivo de configuración instalado
`%LOCALAPPDATA%/AISWESystem/config/.env`, añadir y reiniciar:

```dotenv
AI_SWE_RUNNER_DOCKER={"image":"sha256:ID_LOCAL_COMPLETO_DE_64_HEXADECIMALES","memory_mb":512,"cpus":1.0,"cpu_seconds":600,"pids_limit":32}
```

Sustituir el ID de ejemplo. Para esta validación, imagen local:
`sha256:37b09beaaf4efae0e6c6fa63136577121b03ecbb3047a81e36489e932a59f4d8`.
Otra compilación puede producir otro ID. La imagen debe declarar
`io.aiswe.runner-protocol=1`; la antigua imagen de preparación no basta.
El ZIP incluye la receta, no Docker Desktop ni la imagen Linux ya construida.

## Validación reproducible

Ejecutar con CPython oficial firmado, sin credenciales, y el ID local:

```powershell
$env:AI_SWE_TEST_DOCKER_IMAGE = 'sha256:ID_LOCAL_COMPLETO'
python -m pytest tests/test_execution_snapshot.py tests/test_docker_runner.py tests/test_cooperative_cancellation.py tests/test_project_readiness.py
```

Los tests Docker reales son opt-in y se saltan sin esa variable. El caso E2E usa
`BuilderAdapter`/`FakeModelAdapter`, Git descartable, pruebas reales dentro del
contenedor y confirmaciones humanas simuladas. No demuestra calidad de un LLM remoto.
La primera corrida focalizada pasó 34/34 en 65,237 s. La regresión final y el
portable se registran en `DOCKER-RUNNER-INTEGRATION-EVIDENCE.json` al cerrar.

La prueba reforzada de salida masiva detectó evidencia incorrecta del comando
en timeout. Se corrigió el runner y se agregó una prueba de regresión. El fixture
también pasó a desactivar explícitamente la captura interna de pytest para enviar
300.000 caracteres a la tubería real. Los fallos intermedios se conservan.
El primer candidato `windows-v0.2.0-rc17-docker-runner` queda retenido; el candidato
de cierre es `windows-v0.2.0-rc17-docker-runner-final`.

## Límites y pendientes

- Docker comparte el kernel de su VM Linux y depende del daemon y de una imagen
  confiables. No equivale a una VM dedicada por tarea ni certifica código hostil.
- Sólo están preinstalados pytest/Ruff y sus dependencias fijadas. FastAPI, Node,
  navegadores o paquetes adicionales no aparecen automáticamente; se informan
  fallos reales, sin instalar dependencias durante las pruebas.
- «Probar en local» puede ejecutar la aplicación generada en el host por decisión
  del usuario. Este incremento aísla el runner de pruebas, no ese lanzador.
- Sin validar corte eléctrico, caída abrupta del controlador Docker, fallos reales
  del daemon, todas las carreras posibles o una matriz independiente de Windows.
  El rechazo ante limpieza fallida sí se prueba mediante inyección de fallos.
- Continúan pausados los pilotos de continuidad entre PC y publicación GitHub real.
  Siguen pendientes calidad con modelos reales, ahorro global de tokens 40–70%
  y aprobación para producción pública.


## Rc17 — ejecutor Docker opcional integrado y verificado

1 de noviembre de 2026. Snapshot Windows con handles bloqueados y SHA-256,
rechazo de enlaces, worker Linux sin privilegios, red deshabilitada, cuotas y
watchdog dentro de la imagen. Preflight antes del Coder y limpieza del contenedor
real en cancelación/timeout. Si no se verifica el cierre, se conservan diario,
worktree y reservas; no se declara cancelación confirmada.

**1.121 backend PASS / 4 SKIP**, **39 frontend PASS/build**, **56 pruebas desde
el ZIP PASS** y **14/14 controles del smoke estándar PASS**, ambos cierres 0.
Se valida promoción con FakeModelAdapter y Docker real, sin llamadas pagadas.
Portable aprobado localmente:
`dist/windows-v0.2.0-rc17-docker-runner-final/AISWESystem-windows-x64.zip`.
SHA-256: `0491df0eb6d93220b9185584388f46f7fa5494c07cd906a975d4801d8f63b62c`.
121.301.245 bytes; CRC y 4.742 hashes aprobados. CPython oficial firmado 3.13.14.
El primer candidato `windows-v0.2.0-rc17-docker-runner` está retenido; rc16 se conserva.

Acta: `DOCKER-RUNNER-INTEGRATION.md`; evidencia JSON del mismo nombre.
Docker es opt-in y requiere motor/imagen locales. Sin configuración sigue el
runner Windows; no se editó el `.env` privado. El ZIP incluye receta, no Docker
ni una imagen Linux. El lanzador de la aplicación generada puede correr en el host.

Avance estimado: **86/100** (85,85 ponderado; distribución y operación 80→88).
No es aprobación de producción pública. Pendientes: robustez ante caída real del
daemon/controlador, matriz Windows/SAC independiente, dependencias por proyecto,
calidad con modelos y ahorro global de tokens 40–70%. Los pilotos de recuperación
entre PC y publicación real GitHub continúan pausados.


## Seguimiento: muerte abrupta del controlador Docker

1 de noviembre de 2026. 20 pruebas focalizadas PASS en fuente y 2 PASS con
el runtime y los módulos del ZIP rc17 sin modificar. El watchdog termina el
contenedor con 124 después de matar el controlador; el control negativo sin
watchdog sigue activo y requiere limpieza externa. Acta y límites:
`DOCKER-CONTROLLER-CRASH-VALIDATION.md`, evidencia JSON asociada.
No se repiten build, smoke ni regresión completa porque el producto no cambió.
Sigue pendiente recuperación automática de residuos al reiniciar y fallos reales
del daemon/VM. Se mantiene 86/100 y los pilotos entre PC/GitHub pausados.
