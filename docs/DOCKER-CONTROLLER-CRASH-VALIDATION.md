# Cierre abrupto del controlador Docker

Fecha: 1 de noviembre de 2026. Base: `7ead9d2`.
Sin cambios de runtime, llamadas pagadas, publicación ni modificaciones al ZIP rc17.

## Qué se comprobó

`tests/test_docker_controller_crash.py` lanza el ejecutor en otro proceso CPython
firmado y espera a que el código de prueba escriba una señal dentro del tmpfs del
contenedor. Después termina abruptamente el controlador mediante su handle propio
de `Popen`, no por un PID buscado. No se ejecutan los bloques `finally` del proceso
terminado. El objetivo usa una espera de 90 segundos y un plazo interno de 20.

- **Con watchdog:** el contenedor termina con código 124 tras perder el controlador.
  El límite dentro de la imagen funciona aunque desaparezca el cliente Docker.
- **Control negativo:** se reemplaza únicamente el supervisor por una espera
  confiable de prueba. No se ejecuta código del repositorio como root. Tras matar
  el controlador, el contenedor sigue activo durante los 23 segundos de observación.
  Esto comprueba que la desaparición del CLI por sí sola no detiene el contenedor.
- Ambas variantes verifican que el snapshot todavía existe tras la muerte del
  controlador. La prueba, como operador externo, elimina sólo el contenedor con
  su etiqueta propia y comprueba la limpieza. No se atribuye esa limpieza al
  proceso muerto ni se simulan reembolsos de presupuesto.

Se usan la imagen inmutable y las restricciones reales de rc17: snapshot de
lectura, red deshabilitada, rootfs de lectura, cuotas y UID separados. El control
negativo altera el comando sólo en el arnés de prueba; no añade opciones al producto.

## Resultados

- **20/20 PASS** en fuente: los dos controles nuevos y las 18 pruebas del runner;
  97,996 segundos, sin omisiones.
- **2/2 PASS** con CPython y módulos importados del ZIP rc17 extraído. Se comprueba
  que `ai_swe` se importe desde el bundle, no desde `src`.
- Ruff y `git diff --check` aprobados para el cambio.
- La primera ejecución falló porque Docker Desktop estaba cerrado, antes de crear
  contenedores. Se conservó el informe. Se verificó su firma y se inició la
  instalación existente; no se instaló software ni se modificaron protecciones.

Evidencia: `DOCKER-CONTROLLER-CRASH-EVIDENCE.json`. Reproducción con Docker Linux
local activo y la imagen del acta de integración:

```powershell
$env:AI_SWE_TEST_DOCKER_IMAGE = 'sha256:37b09beaaf4efae0e6c6fa63136577121b03ecbb3047a81e36489e932a59f4d8'
python -m pytest tests/test_docker_controller_crash.py tests/test_docker_runner.py
```

Sin la variable, los controles reales son opt-in y se omiten. Un motor detenido
con la prueba activada causa un fallo explícito; no se disimula como prueba aprobada.

## Entrega y límites

Se conserva como portable aprobado localmente:
`dist/windows-v0.2.0-rc17-docker-runner-final/AISWESystem-windows-x64.zip`.
SHA-256: `0491df0eb6d93220b9185584388f46f7fa5494c07cd906a975d4801d8f63b62c`.
No se repiten la regresión completa, build ni smoke: no cambió código del producto,
imagen ni paquete. Su baseline sigue siendo 1.121 backend PASS/4 SKIP, 39 frontend
PASS, 56 pruebas del ZIP y smoke 14/14. Las nuevas pruebas no se presentan como
una regresión completa de 1.123 casos.

El alcance es muerte del controlador **después de iniciar el objetivo**. No se
validan cortes eléctricos, muerte del daemon/VM, todas las ventanas de creación
ni recuperación automática tras reiniciar. Quedan pendientes el inventario y la
recuperación segura de contenedores detenidos/snapshots que deja un controlador
muerto, conservando ledger y trabajo del usuario. La limpieza externa de esta
prueba no implementa esa recuperación en la aplicación.

Avance estimado conservado: **86/100**. Los pilotos entre PC y GitHub siguen
pausados. La validación no equivale a aprobación para producción pública.
