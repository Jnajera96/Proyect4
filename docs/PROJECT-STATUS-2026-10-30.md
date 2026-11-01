# Estado hacia la entrega funcional y adopción de patrones

Fecha: 1 de noviembre de 2026. Evaluación del código fuente de
`feature/v0.2.0-madre-continuity`, actualizada con rc18 y conservando las distribuciones anteriores.
Última validación fuente: backend1.137 PASS/4 SKIP, frontend39 PASS y compilación
TypeScript/Vite aprobada; sin nuevas inferencias pagadas.

## Avance estimado

**86/100 hacia v0.2.0 Windows local, confiable y recuperable.** Es una estimación
técnica ponderada (85,85 redondeado), no una métrica derivada del número de pruebas.
La aprobación de una plataforma pública de producción sigue pendiente.

Se conserva el método del acta `OPERATIONAL-STATUS-2026-10-29.md`.
Frente a 84,65, distribución y operación segura pasa de 80 a 88 por el runner
Docker opt-in validado de extremo a extremo. Las demás puntuaciones se conservan.
No se eleva voz, calidad de modelos ni recuperación entre PC sin su piloto.
La producción pública y una matriz independiente de Windows siguen pendientes.

| Objetivo | Peso | Estimación actual | Cierre pendiente |
| --- | ---: | ---: | --- |
| Perfiles y bóveda | 15 % | 95 | Recuperación/actualización en otro equipo. |
| Agentes y promoción | 30 % | 88 | Otros productos con modelos reales y revisión independiente de calidad. |
| UI, actividad y proyectos | 10 % | 95 | UX y puertas accionables incluidas en rc9; validar recorrido en destino. |
| Voz | 5 % | 90 | Micrófono/audio en el equipo de destino. |
| Memoria, modos y rollback | 10 % | 90 | Calidad con modelos reales y tokens facturados. Consultas sin rutas e historial multilenguaje ya medidos offline. |
| Continuidad y respaldo | 15 % | 60 | Recuperación por UI entre dos equipos, auto-backup, conflictos y pérdida de equipo. |
| Distribución y operación segura | 15 % | 88 | Matriz Windows/SAC, fallos reales del daemon/VM y casos inciertos. Docker opt-in, muerte del controlador durante tarea, cuotas y migración/retorno local verificados. |

## Qué se adoptó de MADRE

Conceptos adaptados a nuestra arquitectura, no sustitución de LangGraph:

- Preflight de configuración/proveedores sin inferencia: `preflight.py` y
  `models/providers/diagnostics.py`. Acta: `PREFLIGHT-PROVIDERS.md`.
- Modos `INSPECT_ONLY`, `PLAN_ONLY` y `FULL_PROPOSAL` impuestos en el grafo.
- Memoria contextual SQLite FTS5 por usuario/repositorio (`state/memory.py`) y
  consulta histórica en el contexto de trabajo.
  Ya llega al prompt del Coder: máximo tres entradas, 800 caracteres totales,
  redacción de secretos y bloque no confiable. Aislamiento comprobado con FTS5
  real y solicitud capturada por FakeModelAdapter; calidad con modelo real pendiente.
- Recibos y reversión de promoción acotada a los archivos aprobados
  (`tools/rollback.py`), con acción en la UI, sin reset destructivo global.
- Auditoría de propuesta de Coder frente a veredicto de Reviewer y pruebas.
- En la evolución asociada K/L/M: perfiles/bóveda aislados y base de pausa,
  checkpoints, archivos `.aiswe-vault` y reconstrucción (`state/continuity.py`).
  **Tener estas piezas no acredita recuperación completa de equipo:** su cierre
  integral sigue pendiente.

## Qué existe respecto a Nova

`NOVA-COMPARATIVE-REVIEW.md` registra una revisión estática del repositorio de referencia.
**No se copiaron módulos de Nova ni se incorporó su motor conversacional.** Ya existen
en AI SWE estos patrones coincidentes, algunos implementados antes de la comparación:

- Diagnóstico de repositorio/Git y comprobación específica de HEAD antes de Coder.
- Releer del servidor con estados visibles de carga, éxito y error.
- SSE con cursor y relectura, y actividad basada en eventos del servidor.
- Distinción entre nodo terminado, propuesta producida, prueba y promoción comprobada.
- Timeout y reintentos acotados del gateway, sin agregar un bucle externo de gasto.

Actualización operativa: ya se implementan preparación integral, reconciliación de
huecos SSE por snapshot y cancelación cooperativa con recibo de parada, según
`NOVA-OPERATIONAL-VALIDATION.md`. No se copian módulos de Nova ni se fuerza el corte
de un HTTP activo. El paquete actualizado rc3 ya se verificó; la validación en
destino sigue pendiente. El seguimiento de continuidad y el arreglo de carga de
respaldos constan en `CONTINUITY-FOLLOWUP-2026-10-30.md`.

## Neuromapa se registra por separado

La co-ocurrencia de archivos (`state/memory_graph.py`), selección de contexto y
`max_cost_per_hour` se inspiran en Neuromapa. No se atribuyen a MADRE ni a Nova.
No se ha demostrado ahorro de 50–70 % de tokens facturados.
La medición `CONTEXT-MEMORY-MEASUREMENT.md` obtiene ~15 % menos bytes de mensajes
en fixtures con contenido recuperable. FTS5 añade ~10 % de bytes en cuatro casos
multilenguaje; no hay tokenizer ni cargos reales medidos.

## Ruta restante

1. Paquete rc3 construido y verificado; rc4 incorpora el arreglo de carga de respaldos.
2. Completar la matriz de otra PC tras la confirmación de funcionamiento del usuario: versión, reinicio, voz y promoción.
3. Cerrar recuperación y respaldo de principio a fin entre equipos; acceso de restauración y múltiples rutas implementados, falta piloto integral por UI.
4. Evaluar más productos/modelos y publicación voluntaria con presupuesto explícito.
5. Resolver aislamiento de procesos/red y controles operativos antes de producción pública.

Plan maestro y cola de pendientes: `ROADMAP.md`. Actas fuente:
`INTUITIVE-UX-NEUROMAPA-VALIDATION.md`, `PRODUCT-REQUIREMENTS-VALIDATION.md` y
`UNIVERSAL-REQUIREMENTS-VALIDATION.md`. Los resultados offline no actualizan por sí
solos el ZIP ni el servidor que el usuario tenga abierto.

Actualización rc9: portable nuevo aprobado localmente, con 14/14 controles y 11
pruebas de memoria desde el ZIP. Acta `RC9-CONTEXT-HISTORY-CLOSURE.md`.
Se mantiene 81/100: las nuevas pruebas no sustituyen los cierres externos pendientes.


Actualización del 31 de octubre: estimación 83,90 → **84/100**. Continuidad 55→60
por respaldo y retorno de los datos instalados; distribución 60→75 por actualizador
portable, transacciones, recuperación tras interrupciones y prueba rc9→rc10 con
runtimes reales. Los valores 81/100 anteriores son históricos. Las demás áreas
no cambian; no se incrementa calidad de modelos ni recuperación entre PC sin piloto.
Evidencia: `SAFE-UPGRADE-MIGRATIONS.md`. La producción pública continúa pendiente.


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
