# Recuperación conservadora de recursos Docker al arrancar

Fecha: 1 de noviembre de 2026. Base: `52ffe40`.
Este incremento recupera recursos temporales del ejecutor; no reanuda ni aprueba
automáticamente el trabajo de un agente.

## Comportamiento

Las nuevas sesiones guardan sus recursos en
`%TEMP%/AISWESystem-docker/aiswe-docker-xxxxxxxx/`. El directorio contiene copia
del proyecto, configuración Docker anónima y `execution.json`. Un bloqueo del
sistema operativo en un archivo vecino `.lock` permanece adquirido durante
la sesión. Se libera incluso si el controlador muere; no se confía en un PID.

El diario se escribe por reemplazo atómico, con flush/fsync antes de enviar una
creación al daemon. Registra versión, propietario aleatorio, fase, ID del
contenedor e imagen inmutable; no contiene tokens ni rutas de otros proyectos.

| Fase | Interpretación | Recuperación automática |
| --- | --- | --- |
| `prepared` | Todavía no se envió una creación. | Sólo elimina el temporal si no hay contenedores con su etiqueta. |
| `creating` | Puede existir una solicitud cuyo resultado no se confirmó. | Conserva diario y recursos para revisión manual. |
| `created` | El daemon devolvió un ID válido y se registró. | Verifica ID, propietario, imagen y etiqueta de sesión. Limpia únicamente si el contenedor está detenido o ya no existe. |

Se ejecuta un barrido al iniciar la API con Docker solicitado, tanto en modo
perfiles como en modo directo. Se ejecuta fuera del bucle async y mantiene la
salud de la aplicación si Docker está detenido. Sin `runner_docker`, no consulta
Docker ni barre directorios. La activación sigue siendo explícita.

Cada barrido tiene un presupuesto de cinco segundos para sus comandos y examina
como máximo cien entradas. El cierre/verificación del proceso CLI puede agregar
su propio tiempo de limpieza; no se afirma un tiempo total absoluto de cinco
segundos. Lo que no alcance a comprobar queda pendiente para otro arranque.

## Barreras de seguridad

- Se ignoran carpetas ajenas y sesiones sin diario. Se rechazan reparse points,
  diarios enlazados o mayores de 4 KiB y bloqueos no regulares o con hardlinks.
- Si el bloqueo está ocupado, no consulta ni elimina el contenedor de esa sesión.
- Las etiquetas aleatorias, el ID completo y la imagen deben coincidir con el
  diario. La etiqueta adicional de sesión impide aceptar una copia del diario
  colocada en otro directorio.
- Si el contenedor está ejecutándose, se conserva. El watchdog continúa siendo
  responsable del timeout; este barrido no mata objetivos activos.
- La limpieza verifica la desaparición del contenedor antes de borrar el temporal.
  Los errores, identidad inconsistente o un plazo agotado conservan los recursos.
- No lee ni modifica SQLite, ledger, bóveda, repositorios o worktrees. No libera
  reservas, confirma cancelaciones, promueve cambios ni reinicia agentes. La
  recuperación de corridas huérfanas que ya existía en la API sigue siendo aparte.
- No hay `prune` global ni limpieza por antigüedad o por coincidencia de PID.

El resumen se conserva en el estado interno de la aplicación y se registra en
los logs. Los contadores distinguen eliminados, activos, en ejecución, inciertos
y no resueltos. No se añaden credenciales al log ni un endpoint público nuevo.

## Verificación

La corrida focalizada inicial pasó **34/34** en 129,436 segundos. Incluye diarios
inválidos, hardlinks de diario/bloqueo, sesión ajena, motor ausente, salud de ambas
APIs y exclusión cuando Docker no está solicitado. Con Docker real también se
verifica que el proceso hijo mantiene el lease, que el watchdog sobrevive a su
muerte y que después el barrido retira sólo su contenedor detenido y su copia.
Las pruebas usan datos sintéticos y FakeModelAdapter, sin inferencias pagadas.

Reproducción en Windows con la imagen de `DOCKER-RUNNER-INTEGRATION.md`:

```powershell
$env:AI_SWE_TEST_DOCKER_IMAGE = 'sha256:37b09beaaf4efae0e6c6fa63136577121b03ecbb3047a81e36489e932a59f4d8'
python -m pytest tests/test_docker_recovery.py tests/test_docker_controller_crash.py tests/test_docker_runner.py
```

La regresión completa, las pruebas con módulos del ZIP y el smoke se registran
al cerrar en `DOCKER-RESOURCE-RECOVERY-EVIDENCE.json`. No se cambia la imagen
Linux, el runtime oficial firmado ni las dependencias del proyecto.

## Límites vigentes

- No hay barrido periódico: si se reinicia antes de que venza el watchdog, los
  recursos aún activos quedan para otro arranque. No se declara limpieza completa.
- Una creación incierta exige intervención; no se deduce éxito de una lista vacía.
- Los temporales antiguos de rc17, sin este diario y fuera del nuevo directorio,
  requieren revisión manual. No se adoptan automáticamente como recursos propios.
- No se prueban cortes eléctricos ni caída/reinicio real del daemon o la VM.
  El manejo del daemon ausente se valida offline con fallos inyectados.
- Un usuario o administrador que controle el daemon y los archivos del host sigue
  siendo de confianza. El aislamiento de pruebas no cubre el lanzador de la app.
- Permanecen pausados los pilotos entre PC y publicación real GitHub. Siguen
  pendientes matriz Windows/SAC, dependencias por proyecto, calidad de modelos,
  ahorro global de tokens y controles de producción pública.


## Rc18 — recuperación de recursos Docker al arrancar

1 de noviembre de 2026. Se añaden diario atómico previo a la creación, lease del
sistema operativo y barrido acotado al arrancar con Docker solicitado. Sólo se
limpian sesiones propias confirmadas y detenidas. Activas, en ejecución, inciertas
o sin identidad válida se conservan; no se modifican ledger, bóveda ni repositorios.

**1.137 backend PASS / 4 SKIP**, **39 frontend PASS/build**, **72 pruebas del ZIP
PASS** (57 de integración y 15 del launcher), **14/14 smoke PASS**, ambos cierres 0.
Se verifica recuperación tras matar el controlador y esperar al watchdog con
Docker real, CPython firmado y datos sintéticos. Cero llamadas pagadas.

Portable aprobado localmente:
`dist/windows-v0.2.0-rc18-docker-recovery/AISWESystem-windows-x64.zip`.
SHA-256: `8eada0dfd22aaa45585c4b8cfd63ef67ebdf700f0b72cac0d964e44e52b3c50a`.
121.303.057 bytes; CRC y 4.742 hashes verificados. Rc17 y anteriores se conservan.
La imagen Linux y las dependencias no cambian. El ajuste del fixture de CPU sólo
separa el fallo pytest intencional de la cuota de 1 s; no relaja límites del producto.

Acta: `DOCKER-RESOURCE-RECOVERY.md`; evidencia:
`DOCKER-RESOURCE-RECOVERY-EVIDENCE.json`. Se mantiene **86/100**.
No se prueba caída real del daemon/VM ni corte eléctrico. Los recursos todavía
activos quedan para otro arranque; creaciones inciertas y restos antiguos rc17
necesitan revisión manual. Siguen pendientes dependencias por proyecto, matriz
Windows/SAC, calidad con modelos y ahorro global de tokens. Los pilotos entre PC
y publicación GitHub permanecen pausados; producción pública no aprobada.
