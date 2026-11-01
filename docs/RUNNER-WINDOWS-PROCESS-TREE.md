# Cierre del grupo de procesos en Windows

Fecha: 31 de octubre de 2026. Base: `6785a87`. Validación offline, sin inferencias
pagadas. Recuperación entre PC y piloto real GitHub continúan en pausa.

## Defecto y corrección

La prueba anterior a la corrección retuvo un handle del descendiente sintético:
después del timeout del runner, WaitForSingleObject todavía devolvía WAIT_TIMEOUT.
Evidencia local: `_tmp/windows-job-before-verified.xml`. Matar únicamente al padre
no confirmaba el cierre de sus descendientes.

`tools/windows_job.py` usa la API nativa mediante ctypes, sin dependencias nuevas.
El runner crea el hijo suspendido, lo asigna a un Job Object propio y sólo entonces
reanuda su único hilo inicial. KILL_ON_JOB_CLOSE queda activo y no se permiten
opciones de breakaway. Un fallo de preparación impide ejecutar código del target.

Al cerrar se impide crear más procesos en el grupo, se consulta su lista acotada
de PID y se retienen handles cuya pertenencia al Job Object se comprueba. Se
termina el grupo y se espera la señal de terminación de esos handles, además del
contador de procesos activos. El contador por sí solo no basta: en la calibración
real llegó a cero antes de que un handle del hijo estuviese señalado. No se matan
procesos por nombre ni mediante un recorrido global de PID.

El timeout conserva código 124. Si el padre termina normalmente pero deja hijos
activos tras una breve gracia, se limpian y el resultado es código 125, nunca una
prueba aprobada. Si no se puede confirmar el cierre se produce RunnerError. Los
plazos incluyen hasta cinco segundos adicionales para la terminación del grupo.
El snapshot admite hasta 1.024 procesos; si se supera o falla su consulta, se
rechaza el resultado y el cierre del handle conserva KILL_ON_JOB_CLOSE.

## Intérprete y entorno de validación

El alias AppExecutionAlias de Microsoft Store delegó la ejecución fuera del grupo
en la reproducción local. Se rechaza ese intérprete antes de lanzar el target,
con indicación de usar Python real o el portable firmado. No hay fallback sin
control de procesos. La modificación experimental de `.venv/pyvenv.cfg` hacia la
instalación Store real dio acceso denegado: se restauró su preimagen, sin cambiar
paquetes ni instalaciones globales. Los hashes y la preimagen están bajo
`_tmp/windows-job-venv/`.

Las pruebas focalizadas utilizan el CPython 3.13.14 firmado incluido en rc13,
cargando el código fuente actual. Esto no convierte rc13 en un paquete que ya
contenga la corrección. Para la regresión completa se prepara un entorno temporal
con los mismos bytes del archivo oficial de CPython, omitiendo su archivo `._pth`
para activar la configuración estándar; Lib/site-packages enlaza las dependencias
ya instaladas y se copia Ruff sin modificarlo. Firma Python válida y preimagen de
pyvenv.cfg restaurada verificadas. Preparación: `_tmp/native-test-python.py`.

Usar el runtime embebido como Python de desarrollo sin activar su worker deja
Ruff fuera de su ruta; activar globalmente `_ai_swe_bundle`, por el contrario,
cambia los defaults instalados de perfiles. Esas corridas se interrumpieron y se
conservan como fallidas/incompletas, no como regresiones aprobadas. El entorno
estándar temporal evita ambas diferencias sin cambiar pruebas ni código productivo.

La primera regresión bajo `_tmp/` heredó el addopts de pyproject.toml en los
repositorios sintéticos: tres afirmaciones del resumen de pytest fallaron por
doble `-q`. La repetición con temporales fuera del árbol del proyecto pasó sus
45 pruebas, sin modificar esas afirmaciones ni la configuración de producción.
Los temporales predeterminados del puente restringido dieron errores de permisos;
no se contabilizan como verificaciones aprobadas.

## Evidencia

- `_tmp/job-focused-final.xml`: 45 PASS, 0 fallos, 0 omitidas; cierre de
  descendientes tras timeout/salida normal, rechazo del alias, fallo de asignación,
  captura acotada, entorno y flujo real offline del grafo.
- Frontend: 39 PASS y `npm run build` aprobado, sin cambios de interfaz.
- Ruff del runner, módulo nativo y pruebas nuevas: aprobado.
- `_tmp/job-final-native.xml`: 5 PASS, incluida negativa de éxito cuando no se
  verifica el cierre.
- `_tmp/job-rc14-tests.xml`: 16 PASS, cargando ai_swe desde el ZIP extraído, sin
  cargar src: cinco pruebas nativas, ocho de salida acotada y tres de entorno.
- `_tmp/job-rc14-smoke-host/report.json`: 14/14 PASS, cero llamadas pagadas y ambos
  cierres ordenados. El primer smoke en el puente restringido falló por timeout de
  readiness sin logs; se conserva en `_tmp/job-rc14-smoke/report.json`.
- Regresión completa: 1.078 PASS / 4 SKIP, cero errores/fallos;
  `_tmp/job-standard-final.xml`. Duración: 573.203 s.
- Preflight: su fixture híbrido ahora declara hf_token vacío explícitamente;
  antes heredaba HF_TOKEN del host y fallaba la prueba de credencial ausente.
  Se conservan todas las afirmaciones. La corrida previa tuvo 1.077 PASS,
  4 SKIP y ese único fallo (`_tmp/job-standard-full.xml`); las 20 pruebas
  del archivo pasaron aisladas antes de repetir toda la suite.
- Rc14 queda como portable local verificado; rc13 y anteriores se conservan.

El puente Serena agotó su espera de 240 segundos para la regresión larga; el
proceso continuó y produjo después el log al 100% y el XML completo de 1.082 casos
en 573,203 segundos. El resultado se comprobó en esos archivos, no se interpretó
el timeout del puente como un PASS.

## Alcance y límites

La garantía se limita al linaje de procesos asociado al Job Object en Windows y
a los handles observados durante su cierre. No es una barrera contra procesos
creados mediante servicios externos o brokers, ni aislamiento de archivos, red,
credenciales accesibles por permisos del usuario, CPU o RAM. El límite de procesos
se aplica durante el cierre, no como cuota de ejecución. POSIX conserva su
comportamiento anterior y no recibe esta garantía. Falta validar en otro equipo
y cerrar el aislamiento fuerte antes de declarar producción pública. Las cuotas
nativas se verificaron posteriormente en rc15: `RUNNER-WINDOWS-RESOURCE-LIMITS.md`. La muerte
abrupta del supervisor se comprobó después del cierre de rc14, como se detalla abajo.

Referencias primarias: [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
[QueryInformationJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject)
y [ResumeThread](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-resumethread).


## Rc14 — cierre verificable de procesos en Windows

El runner asigna el hijo suspendido a un Job Object antes de ejecutarlo y verifica
el cierre mediante handles de sus procesos. Timeout conserva código 124; hijos
activos tras salida normal provocan código 125, nunca un aprobado. El alias de
Microsoft Store se rechaza explícitamente: usar el portable o Python real.

1.078 backend PASS / 4 SKIP, 39 frontend PASS y build aprobado, 16 pruebas desde
el ZIP extraído y 14/14 controles del smoke estándar. No hay inferencias nuevas.
Entrega local: `dist/windows-v0.2.0-rc14-process-tree-final/AISWESystem-windows-x64.zip`.
SHA-256: `28d53cfdff4ff915f44261cdee61207e5f182f38c7cc11516d11f6923ec75feb`.
Acta: `RUNNER-WINDOWS-PROCESS-TREE.md`. Rc13 y anteriores se conservan. El avance
global sigue en 84/100: faltan cuotas fuertes, aislamiento de archivos/red y matriz
Windows independiente. Recuperación entre PC y piloto GitHub continúan en pausa.

## Verificación adicional: muerte abrupta del supervisor

Base: `72fbf3a`. Se termina mediante TerminateProcess el supervisor sintético,
utilizando exclusivamente el handle retenido por Popen: no se ejecutan finally
de Python ni la limpieza explícita del runner. Antes se confirma que su hijo está
vivo mediante otro handle propio; después se verifica su terminación en cinco
segundos. El cierre del Job Object por Windows elimina ese hijo.

El control negativo desactiva KILL_ON_JOB_CLOSE sólo en el Job Object del fixture,
sin modificar archivos productivos. En ese caso el hijo debe seguir vivo; el test
lo termina después mediante su handle propio. Así se evita una prueba vacua que
aprobase por una salida natural o una causa distinta a la política del grupo.

- Fuente con CPython oficial firmado: **7/7 PASS**, incluyendo los cinco casos
  anteriores y los dos escenarios nuevos; `_tmp/job-supervisor-calibrated.xml`.
- Módulos y runtime de rc14 extraído, sin src de desarrollo: **7/7 PASS**;
  `_tmp/job-supervisor-rc14-calibrated.xml`.
- Ruff del archivo de pruebas y git diff --check: aprobados.

Sólo cambian pruebas y documentación. No se repiten la regresión completa ni el
build del frontend, ni se fabrica otro ZIP idéntico. La última regresión completa
sigue siendo 1.078 PASS / 4 SKIP, y el smoke previo del portable sigue en 14/14.
El paquete, su SHA-256 y el avance estimado de 84/100 se mantienen. Esta prueba no
demuestra aislamiento de archivos/red, cuotas de recursos ni resistencia contra
brokers externos o procesos con privilegios equivalentes al usuario.
