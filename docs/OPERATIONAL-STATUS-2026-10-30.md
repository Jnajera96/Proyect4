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
