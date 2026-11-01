# Roadmap vigente de cierre y experimentación

## Plan maestro hasta la entrega funcional — actualización del 1 de noviembre de 2026

Meta inmediata: entrega Windows local que una persona no técnica pueda configurar,
usar para construir una aplicación, revisar y abrir, con recuperación comprobada.
La producción pública requiere además el último control de seguridad de esta lista.
La validación fuente no equivale a actualizar el portable instalado.
El estado ponderado actual (86/100) y la adopción real de patrones están en
`PROJECT-STATUS-2026-10-30.md`. La generalización del Analyst se verifica en
`UNIVERSAL-REQUIREMENTS-VALIDATION.md`; mantiene las mismas puertas humanas.
La preparación integral, recuperación SSE y cancelación cooperativa adaptadas de
Nova se incorporan en fuente: `NOVA-OPERATIONAL-VALIDATION.md`. Se incluyen en rc9; sigue pendiente el
piloto integral en otra PC, sin declarar producción aprobada.

| Orden | Trabajo y estado | Criterio para avanzar |
| --- | --- | --- |
| 1 | **Completado y validado en fuente:** Analyst como Product Manager, síntesis por familias/núcleo nominal para productos nuevos, revisión editable y chips de inicio rápido. | Confirmación humana obligatoria, confianza de intención clara >=0,85 y exclusiones preservadas; backend962 PASS/4 SKIP, frontend32 PASS y build aprobado. Actas: `PRODUCT-REQUIREMENTS-VALIDATION.md` y `UNIVERSAL-REQUIREMENTS-VALIDATION.md`. |
| 2 | **Rc18 aprobado localmente; rc17 y anteriores conservados.** | Recuperación Docker al arrancar, 1.137 backend PASS/4 SKIP, 72 pruebas del ZIP y smoke 14/14. Acta vigente: `DOCKER-RESOURCE-RECOVERY.md`. |
| 3 | **Uso en otra PC confirmado por el usuario; matriz detallada pendiente.** | Falta identificar versión/hash, Windows y recorrido: protecciones activas, reinicio, voz y promoción. No se infiere recuperación entre equipos. Cualquier inferencia pagada exige presupuesto explícito. |
| 4 | **Pendiente:** cierre de continuidad K/L/M y recuperación. | Exportación/importación cifrada, contraseña/clave de rescate, separación entre usuarios y reconstrucción del trabajo pausado en otro equipo sin pérdida de datos. |
| 5 | **Selección por contenido e historial FTS5 medidos offline; calidad/publicación/tokens reales pendientes.** | Consultas sin rutas: 50% de cobertura en frío y 100% con asociaciones sintéticas. Historial probado en Python/JS/TS/SQL: añade ~10% de bytes; no demuestra ahorro facturado ni calidad del modelo. Actas: `CONTEXT-MEMORY-MEASUREMENT.md` y `FTS-HISTORY-MEASUREMENT.md`. Faltan repositorios reales, tokenizer correcto y publicación voluntaria real. |
| 6 | **Docker opt-in y muerte del controlador durante tarea validados localmente; operación pública pendiente.** | Recuperación al arrancar de sesiones propias detenidas validada; los casos inciertos requieren revisión manual. Faltan fallos reales del daemon, matriz Windows independiente y controles de secretos, TLS, auditoría, copias/restauración y política de datos para producción pública. |

### Flujo de pendientes de la mejora de requisitos

- [x] Reproducir offline las peticiones concisas que se clasificaban como inspección.
- [x] Proponer bases editables para calculadora, calendario y contador de calorías en la ruta local.
- [x] Actualizar el prompt remoto, sin sustituir permisos ni confirmación humana por confianza.
- [x] Mostrar funciones con viñetas y enviar ajustes al contexto confirmado que recibe Coder.
- [x] Añadir sugerencias que rellenan el compositor sin ejecutar automáticamente.
- [x] Registrar cierre de la regresión completa en el acta y el progreso.
- [x] Incluir estos cambios en el portable rc3 y verificar perfiles/SQLite.
- [ ] Validar en otra PC; guía: `PORTABLE-SECOND-PC-PILOT.md`.

### Seguimiento de continuidad

- [x] Medir solicitudes reales con FakeModelAdapter y controles sin poda/léxico/asociativo.
- [x] Corregir selección arbitraria sin anclas, exceso de archivos explícitos y cierre SQLite.
- [x] Cerrar rc8 corregido con dos smokes estándar aprobados sin instrumentación.
- [x] Incorporar historical_context FTS5 al Coder con redacción, límites y separación de usuarios/repositorios verificada.

Evidencia: `CONTEXT-MEMORY-MEASUREMENT.md`.

- [x] Mostrar decisiones humanas en Flujo, enfocar progreso tras Ejecutar y ofrecer continuar desde las demás vistas.

Acta UX: `HUMAN-GATES-INTUITIVE-UX-VALIDATION.md`.

- [x] Prueba local para bibliotecas Python y ficha de decisión postgeneración.
- [x] Incluir la mejora de lanzador en rc5; 14 controles portable aprobados (rc4 se conserva).

Acta de esta mejora: `UNIVERSAL-LOCAL-LAUNCH-VALIDATION.md`.

- [x] Revalidar 17 pruebas de memoria/recuperación en desarrollo y con módulos del portable.
- [x] Reproducir y corregir Base64 incompatible al subir respaldos desde la UI.
- [x] Verificar carga binaria en navegador: 4 controles offline aprobados.
- [ ] Validar de extremo a extremo la recuperación desde la UI en una PC independiente.
- [x] Exponer restauración de perfil desde la pantalla de acceso y validar API/ UI offline.
- [x] Añadir lectura previa y asignación guiada de múltiples repositorios al restaurar un perfil.

Acta: `MULTI-REPOSITORY-RESTORE-VALIDATION.md`. La lectura no crea perfiles ni repositorios.

Evidencia y límites: `CONTINUITY-FOLLOWUP-2026-10-30.md`.
Recuperación desde acceso y reporte de otra PC: `PROFILE-IMPORT-UI-VALIDATION.md`.

## Antecedentes y líneas posteriores

Este documento distingue trabajo futuro de capacidades implementadas. Los planes
de `docs/history/` son referencias históricas.

1. **Fase A:** garantías de redacción y estados del frontend. Preservación del
   rediseño en `f095729`; correcciones en `245a4a8`.
2. **Fase B:** experiencia de frontend para entrega sobre endpoints existentes.
   Shell, alcance, errores, voz, evidencia, temas y responsive. Resultado y
   límites de comprobación en `BASELINE-FRONTEND-DELIVERY.md`.
3. **Fase C — ejecutada:** candidato local verificado, tres defectos corregidos,
   690 pruebas Python aprobadas y tres omitidas; navegador y promoción con checkpoint
   real verificados. Alcance, evidencia y límites en `RELEASE-CANDIDATE-PHASE-C.md`.
4. **Jupyter / Hugging Face Agent Model Lab — PLANNED:** laboratorio externo con
   Inference Providers o GPU cloud y modelos del Hub. Descubrimiento de modelos y
   proveedores, pruebas reproducibles de structured output/tool calling/contexto,
   latencia, tokens, coste fiable, errores y fallbacks. Comparación por rol y futura
   exportación JSON de resultados y recomendaciones para ModelGateway. El notebook
   no forma parte del runtime; no hay interfaz ni endpoint de laboratorio todavía.
5. **Posterior a entrega:** evaluar MCP, Graphify/Knowledge Graph y observabilidad
   con criterios de adopción medibles, sin presentar placeholders como funciones.
6. **Antes de producción:** TD-02, TLS, secretos, rate limiting operativo,
   auditoría persistente, aislamiento de ejecución/red/recursos, backups y retención.

El laboratorio no requiere un HuggingFaceAdapter de antemano: primero se comprobará
el adapter OpenAI-compatible existente. No se descargan modelos ni se consume un
proveedor real en la fase de frontend.

## Cierre del pendiente de actualización operativa — 31 de octubre

- [x] Versionado SQLite v1/v2/v3 y eliminación de recreación destructiva.
- [x] Snapshot previo, rollback, reservas conservadas y auditoría de migraciones.
- [x] Actualizador portable con datos de preparación y respaldo ZIP privado.
- [x] Recuperación tras terminación abrupta antes de preparar rutas o crear API.
- [x] Actualización real rc9→rc10, compatibilidad de lectura de rc9 y retorno al snapshot.
- [x] Regresión 1.022 PASS/4 SKIP, comando solicitado 28 PASS y smoke 14/14.

Acta: `SAFE-UPGRADE-MIGRATIONS.md`. El cierre es local. Continúan recuperación
por UI entre PC, matriz independiente, calidad/tokenizer/modelos reales, publicación
autorizada y aislamiento/operación de producción pública.

## Medición exacta de tokens — tarea de prioridad 4 solicitada

- [x] Contador local cl100k_base/o200k_base con hashes, fallback marcado y sin red.
- [x] Benchmark de 15 archivos y tres tareas, con historia fija previa y oráculos
  de rutas/funciones comprobados en los bloques de código.
- [x] Evidencia reproducible: ahorro total 28,293361% / 30,075671%; solo código
  66,208948% / 66,428003%, según encoding. 1.030 backend PASS/4 SKIP y 34 frontend PASS.
- [ ] Alcanzar 40–70% en todos los mensajes, conservando garantías y suficiencia.
- [ ] Verificar el tokenizer del modelo servido y ahorro facturado/efecto en calidad.

Acta: `MEMORY-TOKEN-SAVINGS-EVIDENCE.md`. Se cierra la instrumentación y medición
de referencia; la meta global 40–70% no se declara alcanzada. El pendiente de
publicación GitHub se conserva: esta tarea no lo implementa ni lo valida.


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


## Evaluación real de modelos y prioridades activas — 31 de octubre

Por instrucción del usuario se mantienen en pausa recuperación entre PC y piloto
GitHub. Se completaron 36 sondas reales de contrato sobre las diez rutas del
selector: ocho con 4/4 y dos sin esquema nativo con 2/2 en modo JSON. Todas
aprobaron los casos asignados, sin ejecutar código generado. No son diez E2E ni
una clasificación universal. El selector muestra evidencia por rol; sólo Qwen2.5
Coder 32B conserva la validación histórica de aplicación completa.

Acta: `MODEL-ROUTE-VALIDATION-2026-10-31.md`; métricas en el JSON adjunto.
Autorización nueva hasta 2 USD dentro de 5 acumulados, respaldada por captura
4,96 USD de créditos/0,04 USD de uso. Ledger histórico intacto, sesión separada
con 1,967842 USD reservados. Estimación por uso/tarifas: 0,01962210 USD, no factura;
no liberar reservas ni repetir llamadas basándose sólo en ese cálculo.

Siguen activos calidad E2E con otros productos/modelos, optimización global del
contexto, tokenizer específico y diseño de aislamiento fuerte. Las sondas no
cierran esos trabajos. Rc11 se conserva; este cambio no genera otro portable.

Verificación de este cierre: 1.059 backend PASS/4 SKIP, 31 focalizadas offline
PASS y 39 frontend PASS/build. Los pilotos pausados permanecen sin ejecutar.

## Compactación de evidencia para Coder

Implementada deduplicación sin borrar auditoría, conservación de hallazgos distintos
y redacción antes del recorte. Ahorro incremental exacto de 3,24–3,34% en fixtures;
no cierra la meta global 40–70% ni valida calidad con un proveedor remoto.
Acta: `CODER-CONTEXT-COMPACTION.md`. No hay nuevas llamadas pagadas ni nuevo ZIP;
los pilotos 1 y 2 permanecen pausados. Continúan optimización de selección,
calidad E2E, tokenizer del proveedor y aislamiento fuerte de procesos/red.

Cierre de compactación: 1.062 backend PASS/4 SKIP, 39 frontend PASS y build;
cero inferencias nuevas. Detalles y límites en `CODER-CONTEXT-COMPACTION.md`.


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

Verificación posterior, sin cambios del ejecutable: muerte abrupta del supervisor
comprobada con TerminateProcess y control negativo. 7/7 pruebas nativas en fuente
y 7/7 sobre rc14; acta `RUNNER-WINDOWS-PROCESS-TREE.md`. Quedan por implementar
cuotas fuertes y aislamiento de archivos/red; esta evidencia no cierra esos puntos.


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


## Seguimiento: muerte abrupta del controlador Docker

1 de noviembre de 2026. 20 pruebas focalizadas PASS en fuente y 2 PASS con
el runtime y los módulos del ZIP rc17 sin modificar. El watchdog termina el
contenedor con 124 después de matar el controlador; el control negativo sin
watchdog sigue activo y requiere limpieza externa. Acta y límites:
`DOCKER-CONTROLLER-CRASH-VALIDATION.md`, evidencia JSON asociada.
No se repiten build, smoke ni regresión completa porque el producto no cambió.
Sigue pendiente recuperación automática de residuos al reiniciar y fallos reales
del daemon/VM. Se mantiene 86/100 y los pilotos entre PC/GitHub pausados.


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
