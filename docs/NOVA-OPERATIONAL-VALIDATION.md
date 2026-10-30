# Preparación, recuperación SSE y cancelación cooperativa

Fecha: 30 de octubre de 2026. Rama: `feature/v0.2.0-madre-continuity`.
Base: `9fe10cb`. Adaptación de conceptos de la revisión Nova, sin copiar módulos
ni cambiar LangGraph, Pydantic, worktrees o las puertas humanas.

## Fase 1 — preparación antes de ejecutar

- `GET /projects/{id}/readiness?mode=FULL_PROPOSAL`: autenticado, confinado al
  proyecto/perfil; verifica Git en PATH, raíz Git exacta y HEAD, proveedor/modelos,
  roles Coder/Reviewer, tarifas y saldo local suficiente para la reserva por ejecución
  y el límite horario. Los modos de inspección/plan no exigen inferencia remota.
- `BudgetLedger.read_status` abre SQLite de solo lectura; no crea tablas, cambia
  límites ni reserva dinero. La configuración presente no acredita permisos,
  disponibilidad del modelo o saldo del proveedor. No realiza peticiones externas.
- `POST /projects/{id}/initialize-head`: administrador y protecciones de mutación
  existentes. Requiere raíz Git válida, HEAD ausente y ausencia de trabajadores activos.
  Crea solo un commit vacío, sin añadir archivos ni consumir el índice del usuario.
  Desactiva hooks/firma/helpers usando el entorno Git restringido existente y audita
  la operación. Es idempotente si HEAD ya existe.
- Compositor muestra causas y acciones, bloquea Ejecutar durante la comprobación o
  ante fallos y vuelve a consultar inmediatamente antes de crear el run. Seleccionar
  otra carpeta/configuración invalida el resultado anterior. La creación de HEAD
  requiere el clic explícito de la persona, con el efecto explicado junto al botón.

El control de preparación complementa las guardas de runtime. No sustituye la
validación de HEAD al crear el worktree ni la reserva transaccional antes de inferir.

## Fase 2 — recuperar el estado sin repetir acciones

`useEventosRun` escucha todos los eventos del contrato, incluidos arranque/creación:
omitirlos habría generado falsos huecos. Descarta secuencias ya recibidas y detecta
saltos. Al encontrar uno, limpia actividad parcial antigua y consulta `GET /runs/{id}`;
el callback de App actualiza el estado seleccionado desde ese snapshot.

La recuperación es de solo lectura, de una consulta a la vez; un nuevo hueco durante
la lectura exige otra consulta. Fallos son visibles y permiten reintento. Respuestas
tardías de otra ejecución/conexión/credencial no reemplazan la selección actual.
No ejecuta ni reanuda agentes, aprobaciones, herramientas o promociones. No inventa
los eventos que faltan: recupera estado, no una reproducción completa del historial.

## Fase 3 — cancelación solicitada y parada confirmada

`POST /runs/{id}/cancel` deja de devolver 501. Requiere operador y audita la solicitud:

- 202 + recibo `requested`: el trabajo activo todavía no ha confirmado la parada.
- 200 + recibo `confirmed`: el stream del motor terminó y el estado es `cancelled`.
- `too_late`: una promoción ya iniciada terminó o la operación ya había finalizado;
  los cambios no se revierten por cancelar. Pedir cancelar un run ya terminal devuelve
  409, salvo repetición idempotente de una cancelación ya completada.

Los tokens son locales a la ejecución y sus nodos; los comprueban las fronteras de
nodo y los intentos del gateway. No se confirma parada dentro del bucle de updates:
LangGraph puede haber iniciado el siguiente nodo por anticipado. Se espera el cierre
del stream y luego se consulta el checkpoint definitivo. Esto evita confirmar una
cancelación y borrar un worktree mientras un nodo ya admitido sigue trabajando.

Una promoción admitida antes de la señal se trata como operación atómica: si termina,
se conserva y se informa `too_late`; no se simula un rollback. Las ejecuciones canceladas
no se reanudan ni aceptan aprobaciones posteriores.

La limpieza utiliza el helper existente, solo para la ruta propia esperada
`workspace_root/run_id`, nunca para la raíz del repositorio ni una ruta arbitraria.
Comprueba la desaparición del worktree. Si falla, el recibo lo indica y conserva los
archivos para revisión; no declara limpieza exitosa.

### Reconciliación de dinero

Se añade una marca de despacho a las reservas: los registros anteriores se migran
conservadoramente como posiblemente enviados. El gateway marca el intento antes
de invocar al adaptador. Al cancelar se liberan solo reservas sin despacho probado.
El consumo declarado se conserva; un despacho sin consumo conocido retiene su reserva.
`settle(None)` tampoco acredita ausencia de despacho. No se renueva ningún presupuesto.

El recibo informa reservas liberadas y no resueltas. La UI diferencia solicitud de
parada, confirmación, promoción demasiado avanzada, limpieza fallida y saldo incierto.

## Evidencia offline

- Nuevas pruebas: preparación/commit vacío, permisos, preservación del índice y
  lectura pura del ledger; cancelación en cola, en llamada FakeModelAdapter, en
  aprobación y durante promoción; limpieza confinada y reservas inciertas/antiguas.
- La carrera con promoción detectó un defecto de confirmación prematura por prefetch
  del grafo: corregido esperando el cierre del stream, sin relajar la prueba.
- Se actualizó únicamente la expectativa obsoleta del test que exigía 501 al cancelar.
  La primera regresión también detectó un cambio de texto 409; se conservó la aserción
  existente y se restauró su compatibilidad.
- Navegador: 10 controles nuevos en `tools/verify_operational_nova.cjs`, 11 controles
  de entrega y 9 de interacción existentes aprobados (30 en total). HTTP/SSE locales
  y publicaciones simuladas.
- Frontend existente: 32 PASS; build TypeScript/Vite aprobado.
- Regresión backend final: **973 PASS, 4 SKIP, 0 fallos y 0 errores** (977 casos).
  Verificación focalizada final: 37 PASS; readiness revalidado tras ajustar la
  declaración de dependencias de autenticación. Ruff de módulos/pruebas nuevas aprobado.

Informes locales: `_tmp/nova-operational-full-final.xml`,
`_tmp/nova-operational-focused.xml`, `_tmp/nova-operational-browser/report.json`
y `_tmp/intuitive-browser/report.json`. Contrato exportado regenerado.

## Límites explícitos

- La cancelación implementada es cooperativa en frontera de nodo/intento. **No fuerza
  el cierre de un HTTP ya enviado** ni mata un hilo/proceso en ejecución; la llamada
  actual puede acabar o agotar su timeout antes de confirmar parada. No acredita
  detener facturación del proveedor (`remote_stop_confirmed=false`).
- La preparación usa configuración y ledger locales, sin validar identidad, crédito
  ni disponibilidad de un servicio remoto. Toda la validación se realizó offline.
- El worktree no es aislamiento fuerte de procesos/red; esta entrega no cierra
  producción pública ni recuperación completa entre equipos.
- No se generó un nuevo ZIP, no se reemplazó el servidor abierto ni se hicieron
  llamadas pagadas o publicaciones remotas. Falta verificar el nuevo paquete y otra PC.
