# Captura acotada de salida del ejecutor

Fecha: 31 de octubre de 2026. Base: `cc32844`.
Se mantienen pausados recuperación entre PC y piloto GitHub. No se hacen llamadas
pagadas ni se modifican los ledgers de autorización.

## Defecto reproducido

El runner usaba subprocess.run(capture_output=True) y recortaba stdout/stderr
cuando el proceso ya había terminado. El límite de 200.000 caracteres del contrato
no protegía la memoria durante la captura. Un hijo sintético escribió 16 MiB en
cada canal, 32 MiB en total: tracemalloc registró 67.135.777 bytes de pico de
asignaciones Python en el padre. La prueba falló con el código anterior.

## Cambio

Popen con pipes binarios no bloqueantes; lectura alternada de stdout y stderr en
bloques de hasta 65.536 bytes. Se conservan sólo los últimos 200.000 bytes por
canal. No se usan archivos de spool, communicate con captura completa ni hilos
lectores que puedan quedar bloqueados. Se añade un marcador de recorte, se decodifica
UTF-8 con reemplazo de bytes inválidos y se respeta además el máximo de caracteres
de TestRun. El hijo Python recibe PYTHONIOENCODING=utf-8 como valor fijo seguro.

La cola en bytes puede retener menos de 200.000 caracteres con texto multibyte;
no se afirma lo contrario. El comienzo de un carácter cortado se reemplaza y la
salida se declara recortada; el final útil de la evidencia se mantiene.

El deadline se comprueba incluso si ambos canales producen salida continuamente.
Se rechazan plazos no positivos, NaN e infinitos antes de crear el hijo. Un timeout
sigue produciendo exit_code=124, nunca un aprobado. El mensaje de timeout ahora va
al final de stderr para que un canal lleno no lo elimine durante el recorte.

En salida normal se espera el EOF de ambos canales y el código real del hijo. En
error/timeout se mata y espera al proceso directo (hasta 5 s de gracia) y se cierran
los descriptores. Si falla la configuración de captura segura o no se confirma el
cierre, hay RunnerError explícito: no se degrada a captura sin límite ni se inventa
un TestRun aprobado. La creación del proceso sigue dependiendo del sistema operativo;
no se promete que pueda interrumpirse dentro del deadline de lectura.

Se mantienen shell=False, stdin=DEVNULL, argumentos de lista, targets cerrados,
entorno mínimo y directorio del worktree. Los dos tests observadores existentes
ahora inspeccionan Popen en vez de run; sus afirmaciones de shell/argv/PYTHONPATH
se conservan. Se adapta el anclaje de mutación de shell=False al lugar nuevo.
No se ejecutaron mutaciones; sólo se verificaron los anclajes únicos.

## Evidencia

- Mismo caso de 32 MiB: pico medido aproximadamente 1,4 MB (1.401.697 y 1.402.793
  bytes en repeticiones locales), conservando FINAL_STDOUT/FINAL_STDERR. Son
  asignaciones Python medidas, no RSS total, memoria del hijo ni una garantía
  general de uso de RAM. La prueba exige menos de 8 MiB, no un número exacto.
- Salida continua: código 124 y aviso de timeout conservado; lectura no bloqueada.
- Unicode/bytes inválidos, plazos inválidos y fallo de preparación con cierre del
  hijo cubiertos por ocho pruebas nuevas. Los scripts son fixtures cerrados, no
  comandos elegidos por un modelo.
- Regresión focalizada: 41 PASS, `_tmp/runner-output-final.xml`.
- Evidencia de fallo anterior: `_tmp/runner-output-before.xml`. Las ejecuciones
  intermedias fallidas se conservan como tales, no se presentan como aprobadas.
- Ruff del runner y tests nuevos aprobado. El archivo F8 conserva ocho avisos
  previos idénticos a cc32844; cero nuevos. `_tmp/check-runner-observers.py`.

Reproducción offline:

```powershell
uv run pytest -s tests/test_runner_output_limits.py tests/test_runner_environment.py tests/test_f8_test_runner.py
```

Se usa os.set_blocking sobre pipes, disponible en Windows desde Python 3.12 y
verificado con el CPython 3.13 firmado de este proyecto. Fuente primaria:
[documentación de Python](https://docs.python.org/3/library/os.html#os.set_blocking).

## Límites que siguen abiertos

Esto limita la memoria de captura del padre, no CPU/RAM del hijo ni todos sus
procesos descendientes. Los hijos que retengan descriptores no pueden prolongar
indefinidamente la lectura: se aplica el deadline y se cierran los pipes. Eso no
prueba que hayan terminado esos descendientes. Quedan control del árbol de procesos,
cuotas fuertes y aislamiento de archivos/red; no se declara producción pública.
Los tiempos incluyen la espera de cierre directo y pueden exceder el timeout de
lectura por esa gracia; no se aumenta el plazo estándar de los smokes del portable.

El diseño de aislamiento fuerte sigue en `RUNNER-ENVIRONMENT-HARDENING.md`.
No se instala Docker/Podman ni se hace un fallback silencioso a un modo pretendidamente
seguro. La plataforma comprobada es este host Windows, no Linux ni otra PC.


## Cierre y portable rc13

- Backend completo: **1.073 PASS, 4 SKIP, 0 fallos**, 641,46 s;
  `_tmp/runner-output-full.xml`. Se conservan las 1.065 pruebas anteriores.
- Focalizadas: **41 PASS**, `_tmp/runner-output-final.xml`.
- Frontend: **39 PASS**, TypeScript/Vite aprobado durante la construcción.
- ZIP extraído: **11 PASS**, `_tmp/runner-rc13-embedded.xml`, CPython y módulos
  del paquete sin src de desarrollo. Ocho pruebas estresan la captura con scripts
  fijos y tres verifican el entorno/worker embebido real. Pico medido en el caso
  de salida masiva: 1.402.393 bytes de asignaciones Python del padre.
- Smoke estándar: **14/14 PASS**, ambos cierres código 0, perfiles y SQLite
  persistentes; `_tmp/runner-rc13-portable-smoke/report.json`.
- Firmas válidas de Python Software Foundation en python.exe/pythonw.exe, CRC,
  4.735 hashes de manifiesto y correspondencia de todos los módulos con fuente
  verificados. No se añadieron dependencias ni ejecutables PE nuevos.

Portable local verificado: `dist/windows-v0.2.0-rc13-output-limits/AISWESystem-windows-x64.zip`.
SHA-256: `865c67e27d45a1d7d93f7cf79cec1ca29ecf6e919febc6cc2327ffcff79e36ad`.
Tamaño: 121.286.812 bytes. Se conservan rc12 y todos los paquetes anteriores.
No se declara validación en otro equipo ni aislamiento fuerte. No hubo inferencias
pagadas nuevas, push ni cambios al tag v0.1.0. Los dos pilotos siguen pausados.
