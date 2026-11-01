# Cierre del portable operativo — 30 de octubre de 2026

## RC10 — actualización segura verificada localmente

Entrega del área: `dist/windows-v0.2.0-safe-upgrade-rc10-verified/AISWESystem-windows-x64.zip`.
SHA-256: `01d0fe77d4f75fc866f92798b26f549cd34191d2742bda6a58f23397c96c1854`.
118.808.072 bytes; 4.730 archivos de manifiesto y CRC verificados. Incluye migrador
v1/v2/v3 y CLI ejecutable con el runtime firmado del paquete nuevo.

**1.022 backend PASS/4 SKIP**, **28 pruebas solicitadas PASS**, **34 frontend PASS**,
build aprobado y **14/14 controles estándar del portable PASS**, ambos cierres 0.
Actualización real rc9→rc10, checkpoint/bóveda/reserva conservados y retorno al
snapshot original con rc9 comprobados, usando datos sintéticos y PATH=System32.
Firmas CPython válidas. Cero gasto de API y sin cambios al tag v0.1.0 (b158d9b).

Acta: `SAFE-UPGRADE-MIGRATIONS.md`. Se conserva rc9. Los directorios rc10 y
rc10-final son candidatos intermedios no aprobados. Aprobación local, sin certificar
cortes físicos de energía, matriz independiente ni producción pública.

## RC9 — candidato local aprobado anterior

Entrega canónica: `dist/windows-v0.2.0-operational-rc9/AISWESystem-windows-x64.zip`.
SHA-256: `56f1fd866d079eb5d29714c6cea739aa5ceaf3e3f7c8e9f64f65946391d25c99`.
Tamaño: 118798364 bytes; manifiesto de 4726 archivos y CRC verificados.
Fuente `8b1ff87`, con búsqueda por contenido y bloques de código del cierre `3100e3c`.

**994 backend PASS / 4 SKIP**, **34 frontend PASS**, build TypeScript/Vite
aprobado, **30 focalizadas PASS**, **11 pruebas con módulos del ZIP PASS** y
**14/14 smoke estándar PASS**. Ambos cierres terminaron con código 0; perfiles,
SQLite y checkpoint persisten tras reiniciar. CPython oficial firmado 3.13.14.

Acta y límites: `RC9-CONTEXT-HISTORY-CLOSURE.md`. Sin inferencia pagada, publicación
ni tag; no equivale a validación independiente entre equipos ni producción pública.
Se conserva rc8 corregido como respaldo verificado.

## RC8 corregido — aprobado anterior

Entrega canónica local: `dist/windows-v0.2.0-operational-rc8-fixed/AISWESystem-windows-x64.zip`.
SHA-256: `f27bf21c14cb8c47f8c75be52592e70deada90632713c4069cc369300183429b`.
Tamaño: 118.796.881 bytes; manifiesto de 4.726 archivos; CRC y hashes aprobados.
Fuente base `8adcb0e` más cierre Uvicorn acotado, conexión cliente cerrada y
historial FTS5 redactado en Coder (3 entradas / 800 caracteres totales).

Regresión completa: **990 PASS, 4 SKIP, 0 fallos**, 741,654 s. Frontend: **34 PASS**,
TypeScript/Vite aprobado. Pruebas launcher/historial con runtime empaquetado:
**18 PASS**. Dos ejecuciones estándar sin instrumentación del verificador sobre
el ZIP extraído: **14/14 PASS cada una**, con plazos originales y cuatro cierres
código 0. SQLite y checkpoint persisten tras reiniciar; logs sin WinError 10054
ni traceback. Evidencia y alcance: `RC8-SHUTDOWN-FTS-CLOSURE.md`.

Se aprueba este candidato corregido para el host local validado, sin inferencia
pagada ni publicación. rc7 y el rc8 original retenido se conservan. La aprobación
no sustituye piloto en destino, calidad con modelos reales ni producción pública.

## Seguimiento rc8 — contexto conservador y cierre SQLite

**CANDIDATO ORIGINAL NO APROBADO (histórico).** En este checkpoint se mantuvo rc7;
el cierre corregido posterior y su ZIP distinto se documentan arriba.

ZIP: `dist/windows-v0.2.0-operational-rc8/AISWESystem-windows-x64.zip`.
SHA-256: `9d33e1aa6edcc1df237440e85c6c1a9fba0926cf4f701d9ebd834678f49ddea6`.
Tamaño: 118.796.348 bytes; 4.726 archivos en manifiesto. Base `e299ed6` más
selección conservadora sin anclas, guardia de más de 20 archivos explícitos del
inventario y cierre determinista de conexiones SQLite. rc7 se conserva intacto.

Regresión completa **986 PASS, 4 SKIP, 0 fallos**, 353,91 s. Focalizada: 48 PASS.
Frontend: 34 PASS; compilación TypeScript/Vite aprobada. Las cinco pruebas de
memoria pasan también con módulos y CPython del rc8 (`_tmp/memory-rc8.xml`).
Se comprobaron CRC del ZIP, hashes y correspondencia de todos los módulos con
fuente antes de empaquetar. Métricas sintéticas agregadas sin secretos:
`dist/windows-v0.2.0-operational-rc8/context-memory-report.json`.

El resultado de ~16 % menos bytes en tres fixtures con anclas no se presenta
como ahorro de tokens facturados. Sin anclas no hubo reducción ni recuperación
suficiente de archivos relevantes. Historial FTS5 en prompt Coder sigue pendiente.
Acta: `CONTEXT-MEMORY-MEASUREMENT.md`. Sin inferencias pagadas ni publicación.

El smoke estándar falló dos veces por TimeoutExpired al esperar un cierre
automático (105 s para procesos con `--exit-after 90`). Informes preservados:
`_tmp/operational-rc8-profiles/report.json` y
`_tmp/operational-rc8-profiles-recheck/report.json`. El primero llegó a comprobar
persistencia e integridad tras reinicio; el segundo agotó el plazo en el primer
cierre. Se observó además WinError 10054 en el log del segundo intento, sin causa
raíz confirmada ni atribución demostrada a las correcciones de memoria.

Dos repeticiones instrumentadas completaron 14 controles: temporizador de 15 s
y traceback de 30 s; luego temporizador estándar de 90 s con traceback periódico.
Informes: `_tmp/operational-rc8-shutdown-diagnostic/` y
`_tmp/operational-rc8-shutdown-traced-90/`. El paquete y el verificador fuente no se
modificaron. Estas repeticiones no sustituyen un smoke estándar reproducible.
No se ocultó el fallo, no se aumentaron los plazos estándar y no se parcheó el
launcher sin evidencia suficiente. Pendiente prioritario: aislar el cierre y
reverificar antes de recomendar rc8.

## Seguimiento rc7 — flujo accionable y progreso visible

ZIP: `dist/windows-v0.2.0-operational-rc7/AISWESystem-windows-x64.zip`.
SHA-256: `f1f26017d64672f0193370aa0931cb8e82c24f2f487e4bfe6d1a068092ecfb7f`.
Tamaño: 118.796.148 bytes; manifiesto de 4.726 archivos y CRC verificado.
Base `8cd0b39` más cambios de frontend para puertas accionables en Flujo,
transición/foco al ejecutar, botón compartido para continuar y mensajes humanos.
rc6 se conserva intacto. El éxito de construcción se condiciona a una promoción
confirmada; los identificadores técnicos quedan en detalles desplegables.

Suite completa: **982 PASS, 4 SKIP, 0 fallos**, 425,22 s. Frontend: **34 PASS**;
navegador offline: **34 controles PASS**; TypeScript/Vite aprobado. Sin llamadas
pagadas ni publicación real. Acta: `HUMAN-GATES-INTUITIVE-UX-VALIDATION.md`.
Portable extraído: **14 controles PASS**, salida 0, CPython autónomo, perfiles,
dos arranques y SQLite/checkpoint íntegros/persistentes. Frontend cotejado con
la compilación final. Informe: `dist/windows-v0.2.0-operational-rc7/portable-profiles-report.json`.

## Seguimiento rc6 — restauración de múltiples repositorios

ZIP: `dist/windows-v0.2.0-operational-rc6/AISWESystem-windows-x64.zip`.
SHA-256: `06d366b7fa7a1b6c98d8246f32c27ed7c9cafd2ee92eb221239c8e37267b701a`.
Tamaño: 118.795.627 bytes; manifiesto de 4.726 archivos. Base `d9d691d` más
lectura previa de respaldo, mapeo de destinos y liberación segura de identidades
nuevas tras fallar una importación. Se conserva rc5.

38 pruebas backend focalizadas, 32 frontend y 7 controles de navegador PASS;
TypeScript/Vite y Ruff focalizado aprobados. CRC del ZIP y cotejo del backend con
fuente aprobados. Acta: `MULTI-REPOSITORY-RESTORE-VALIDATION.md`.
Las pruebas API de lectura/importación de uno y dos repositorios pasan también
con CPython y módulos empaquetados: 2 PASS, `_tmp/profile-import-rc6.xml`.
Smoke del ZIP rc6 extraído: **14 controles PASS**, salida 0, sin llamadas pagadas;
arranque autónomo, perfiles y SQLite tras reinicio aprobados. Informe:
`dist/windows-v0.2.0-operational-rc6/portable-profiles-report.json`.
No se presenta una nueva suite backend completa ni validación entre equipos.

## Seguimiento rc5 — recuperar perfil sin registro previo

ZIP: `dist/windows-v0.2.0-operational-rc5/AISWESystem-windows-x64.zip`.
SHA-256: `d1247f75c2201cc997ec4a00a8dcecfe7b5272fad594c2cb782fa3b0f014729b`.
Tamaño: 118.794.712 bytes; manifiesto de 4.726 archivos, CRC del ZIP comprobado.
Base `33fc64c` más `ProfileRoot.tsx`/`RestaurarPerfil.tsx`: recuperar desde acceso.
Incluye el lanzador y decisiones postgeneración; rc4 y rc3 quedan intactos.

Validación fuente focalizada: 36 backend PASS, 32 frontend PASS y 5 controles
de navegador PASS; TypeScript/Vite y Ruff aprobados. No se declara una nueva
regresión completa. Acta: `PROFILE-IMPORT-UI-VALIDATION.md`.
Portable rc5 extraído: **14 controles PASS**, salida 0 y cero llamadas pagadas,
con PATH reducido, perfil aislado, dos arranques y SQLite íntegro/persistente.
La prueba HTTP nueva pasó también con CPython y módulos empaquetados del rc5.
Informe: `dist/windows-v0.2.0-operational-rc5/portable-profiles-report.json`.
El reporte del usuario de funcionamiento en otra PC se conserva con sus límites;
no sustituye el recorrido de recuperación por UI en destino ni acredita producción.

## Seguimiento rc4 — restauración desde la interfaz

Nueva entrega: `dist/windows-v0.2.0-operational-rc4/AISWESystem-windows-x64.zip`.
SHA-256: `512bd67c625fb004e6eddda07b746fe6db5ace2120984f8ee7537fa74b86ecec`.
Tamaño: 118.793.386 bytes; manifiesto con 4.726 archivos. Conserva rc3 intacto.
Base documental `3d20867` más la corrección de `VistaSesion.tsx` que conserva
Base64 estándar al subir respaldos. Backend sin cambios respecto a rc3.

El fallo fue reproducido antes de corregirlo. Tras la corrección: 4 controles
de navegador, 32 pruebas frontend y compilación TypeScript/Vite aprobados.
Además, 17 pruebas de continuidad/memoria pasan en desarrollo y otras 17 con
CPython y módulos del portable rc3, incluida recuperación simulada sin repetir
Coder/Runner/Reviewer. No se suman las repeticiones a la regresión de 973 casos.
Integridad CRC del ZIP rc4 y sus hashes comprobados tras extraerlo, así como
identidad del backend y presencia del frontend corregido.

Smoke sobre el ZIP rc4 extraído: **14 controles PASS**, salida 0, cero llamadas
pagadas. Registro, autenticación, API protegida, UI, puerta humana, reinicio y
persistencia SQLite aprobados con PATH reducido y LOCALAPPDATA temporal.
Informe: `dist/windows-v0.2.0-operational-rc4/portable-profiles-report.json`.

Acta: `CONTINUITY-FOLLOWUP-2026-10-30.md`. Guía para el hito que requiere otro
equipo: `PORTABLE-SECOND-PC-PILOT.md`. La recuperación completa por UI en otra
PC y la producción pública no se dan por cerradas.

## Entrega

Rama: `feature/v0.2.0-madre-continuity`.
Código empaquetado: `4703934f2a16072c2df0b9c0059fd3d79497056f`.
Se conserva rc2 y se construye un directorio rc3 nuevo.

- ZIP: `dist/windows-v0.2.0-operational-rc3/AISWESystem-windows-x64.zip`.
- SHA-256: `f3f5b06944e3551c4645c610bd7bde6c4add3a01051b13abbc5ebb1fa023304d`.
- Tamaño: 118.793.405 bytes.
- Manifiesto: `AISWESystem/BUNDLE-MANIFEST.json`, 4.726 archivos indexados.
- Inicio: extraer el ZIP y abrir `AISWESystem/AISWESystem.cmd`.

CPython 3.13.14 oficial, con firmas Authenticode válidas de Python Software
Foundation para `python.exe` y `pythonw.exe`. No se genera un ejecutable nuevo
sin firma. Las ruedas oficiales se conservan sin modificar; no se afirma que
todas sus DLL tengan firma Authenticode. No requiere Python ni Node de desarrollo
en destino. Git sigue siendo requisito para trabajar con repositorios.

## Verificación

`npm run build` terminó sin errores de TypeScript. El constructor compiló además
el frontend hacia una carpeta nueva. Un `_captura.html` residual de la salida de
desarrollo quedó excluido; no forma parte de la aplicación distribuida.

Se comprobó la integridad CRC del ZIP, se extrajo y se compararon sus 74 módulos
Python con el código fuente, además de los estáticos de la compilación nueva.
Los hashes del manifiesto corresponden a los archivos extraídos.

Regresión fuente ya cerrada, sin cambios de código posteriores: **973 PASS,
4 SKIP, 0 fallos**, informe `_tmp/nova-operational-full-final.xml`.
Frontend: **32 PASS**; verificaciones de navegador: **30 PASS**. Estos resultados
corresponden a la validación fuente documentada en
`NOVA-OPERATIONAL-VALIDATION.md`; no se presentan como una repetición completa
desde el ZIP. En este cierre se repitió la compilación y la verificación portable.

Comando del verificador sobre la extracción del ZIP:

```powershell
.venv/Scripts/python.exe tools/verify_portable_profiles.py _tmp/operational-rc3-zip-extracted/AISWESystem _tmp/operational-rc3-profiles
```

Resultado portable: **14 controles PASS**, salida 0, `success: true` y
`paid_calls: 0`. Se verificaron arranque con PATH limitado a System32,
LOCALAPPDATA temporal, registro y autenticación cifrada, API privada protegida,
UI integrada, ejecución determinista pausada ante la puerta humana, reinicio,
checkpoint y SQLite persistentes con `PRAGMA integrity_check = ok`.
El informe queda en `_tmp/operational-rc3-profiles/report.json` y su copia sin
datos de usuario en `dist/windows-v0.2.0-operational-rc3/portable-profiles-report.json`.
Evidencia de construcción y cotejo:
`build-report.json`, `artifact-report.json` y `source-verification.json` en el
directorio rc3. No compartir los directorios temporales de datos de prueba como
parte de la entrega.

## Capacidades incluidas

- Síntesis de requisitos para productos nuevos, con propuesta editable y
  confirmación humana obligatoria antes de construir.
- Preparación previa: Git, repositorio con HEAD, configuración de modelos y
  disponibilidad del ledger local. Inicialización explícita de commit base vacío.
- Recuperación de huecos SSE mediante estado autoritativo, sin repetir agentes.
- Cancelación cooperativa con recibo verificable y limpieza acotada del worktree;
  solo se liberan reservas demostrablemente no despachadas.
- UX de entrega, guía de ejecución, memoria asociativa y control horario de gasto
  incorporados al portable, conservando contratos y puertas humanas.

## Límites y siguiente paso

No hubo llamadas de inferencia pagadas ni publicaciones reales en GitHub. El
servidor abierto anteriormente y los datos del usuario no se reemplazaron.
La verificación local con PATH reducido y LOCALAPPDATA aislado no sustituye una
PC o VM independiente. Falta ese piloto y el cierre integral de continuidad y
recuperación entre equipos; no se declara aprobación de producción pública.

La preparación no comprueba saldo remoto ni permisos reales del token. La
cancelación no garantiza interrumpir una petición HTTP ya despachada ni detener
su facturación. Un worktree no proporciona aislamiento fuerte de procesos/red.

El host de compilación reportó Node 24.13.0 afectado por CVE-2026-111497; la
herramienta recomienda actualizar a 24.22.1 o posterior. Node no se incluye ni
se necesita para ejecutar este portable.


## Rc11 — publicación guiada y entrega de borradores (31 de octubre)

Implementados validación de identidad/scopes de PAT clásico, creación pública o
privada en cuenta/organización, origin seguro y push con upstream, y progreso real
en el modal. Se conserva la vista previa sin aprobar una publicación de borrador.
Regresión: 1.050 backend PASS/4 SKIP, 38 frontend PASS/build, 38 focalizadas usando
el ZIP y 14/14 smoke estándar. Se verifica push Git sólo a bare local descartable;
la API de GitHub permanece simulada. El piloto remoto real sigue pendiente.

Candidato local: `dist/windows-v0.2.0-rc11/AISWESystem-windows-x64.zip`.
SHA-256: `e57a3e87e37059f52691e644d0ed741215cd5e50165e019982439739204fee60`.
Acta y límites: `RC11-GITHUB-PUBLISH-AND-UNLOCKED-DELIVERY.md`. Se preservan rc10
y las distribuciones previas. No se declara producción pública ni se consumen APIs
pagadas; no cambia la evidencia pendiente de recuperación entre equipos y calidad
remota.


## Rc12 — entorno mínimo del ejecutor

Corregida herencia de credenciales y configuración del servidor por el proceso
de pruebas: lista mínima de entorno y PYTHONPATH del worktree. 1.065 backend
PASS/4 SKIP, 33 focalizadas PASS, 39 frontend PASS/build, 3 pruebas del worker
embebido PASS desde el ZIP y 14/14 smoke estándar. No hay inferencias nuevas.

Portable local verificado: `dist/windows-v0.2.0-rc12-security/AISWESystem-windows-x64.zip`.
SHA-256: `0b6c1e2d77eefa79c6d39f26f896a5989db03c13184aa044df62127a65e837cd`.
Acta y plan de aislamiento: `RUNNER-ENVIRONMENT-HARDENING.md`. Incluye también
compactación de contexto y evidencia real por modelo del selector. Rc11 y los
paquetes anteriores se conservan. No existe todavía aislamiento fuerte de archivos,
red y descendientes: no se declara producción pública. Los pilotos entre PC y
GitHub siguen pausados. No se detectó motor Docker/Podman en este host.


## Rc13 — captura de salida acotada

Corregida la acumulación completa de stdout/stderr antes del recorte. Captura
no bloqueante con colas de 200.000 bytes por canal, UTF-8 tolerante a bytes
inválidos, timeout no suprimible por salida continua y cierre del proceso directo.
Caso sintético de 32 MiB: pico de asignaciones Python del padre ~67,1 MB antes
y ~1,4 MB después; no es un límite de memoria del hijo ni del RSS total.

1.073 backend PASS/4 SKIP, 41 focalizadas PASS, 39 frontend PASS/build, 11 pruebas
desde el ZIP y 14/14 smoke estándar. Cero inferencias nuevas.
Entrega local: `dist/windows-v0.2.0-rc13-output-limits/AISWESystem-windows-x64.zip`.
SHA-256: `865c67e27d45a1d7d93f7cf79cec1ca29ecf6e919febc6cc2327ffcff79e36ad`.
Acta: `RUNNER-OUTPUT-BOUNDS.md`. Rc12 y anteriores se conservan. Siguen pendientes
cuotas de CPU/RAM del hijo, control verificable de descendientes y aislamiento
de archivos/red; los pilotos entre PC y GitHub permanecen pausados.


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

Verificación posterior de caída abrupta del supervisor, sin cambio de ejecutable:
7/7 pruebas nativas en fuente y 7/7 sobre rc14, incluyendo control negativo.
No se repitió la suite completa ni el build; rc14 y su hash permanecen vigentes.
Acta: `RUNNER-WINDOWS-PROCESS-TREE.md`. El avance global continúa en 84/100.


## Rc15 — cuotas nativas del ejecutor Windows

Se aplican por objetivo 16 procesos, 1.024 MiB de memoria comprometida y 600 s de
CPU de usuario acumulada, configurables con `AI_SWE_RUNNER_LIMITS`. La limpieza
preserva el reloj de CPU y las cuotas de memoria; no hay fallback sin cuotas en
Windows. No se modifica el `.env` privado ni se añaden dependencias.

1.095 backend PASS / 4 SKIP, 39 frontend PASS y build aprobado, 33 pruebas desde
el ZIP y 14/14 controles del smoke estándar. Cero llamadas pagadas.
Entrega local: `dist/windows-v0.2.0-rc15-resource-limits/AISWESystem-windows-x64.zip`.
SHA-256: `d16dfd57986f1fd8618da99033b52efb68b6c104915138465f6b8df1cc31bc30`.
Acta: `RUNNER-WINDOWS-RESOURCE-LIMITS.md`. Rc14 y anteriores se conservan.
Avance estimado: 85/100 (84,65 ponderado; operación segura 75→80). Siguen pendientes
aislamiento de archivos/red, calidad/ahorro con modelos y matriz Windows independiente.
Los pilotos de recuperación entre PC y publicación real GitHub continúan pausados.


## Rc16 — código relevante conservado y preparación Docker

1 de noviembre de 2026. Corregida la pérdida de la función solicitada cuando
líneas largas de contexto previo consumían el fragmento. No aumentan los límites
ni se modifica el prompt de sistema, la redacción o las puertas humanas.

1.097 backend PASS / 4 SKIP, 39 frontend PASS/build, 35 pruebas desde el ZIP y
smoke estándar 14/14. Cero inferencias pagadas. Entrega local:
`dist/windows-v0.2.0-rc16-context-window/AISWESystem-windows-x64.zip`.
SHA-256: `43a2616ab0256edcd66ebfe0635af0b2ccc8ff7d9bd7bec3965bd9bf4bf316a8`.
Acta: `CODER-CONTEXT-WINDOW-SUFFICIENCY.md`. Rc15 y anteriores se conservan.

Docker Desktop ya estaba instalado por usuario, fuera de PATH. Motor Linux local
e imagen inmutable preparados; 20 controles reales y 3 rechazos de CLI aprobados.
Ver `DOCKER-ISOLATION-PREPARATION.md` y su evidencia JSON. **La aplicación sigue
usando el runner local**: faltan snapshot seguro, integración Docker, preflight
y cancelación sobre el contenedor. No se afirma aislamiento integrado.
Avance: 85/100, sin cambiar ponderaciones ni dar por cumplido el ahorro global
40–70% (benchmark completo sigue en 28,127385% / 29,916601%). Los pilotos de
recuperación entre PC y publicación real GitHub permanecen pausados.


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
