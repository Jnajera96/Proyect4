# Validación independiente de resiliencia y concurrencia — Día 2

**Ejecutada el 3 de noviembre de 2026 (America/Mexico_City).** Se conserva `2026-11-04` en el nombre por la planificación solicitada; no representa una ejecución futura.

## Dictamen y base

**22/22 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, en 27,060 segundos de pytest. Aprobado el alcance local del Día 2, no una certificación global 100/100. Se verificó la misma base `96f58bb44f5f4e3a62434c7869517033157557fd` antes y después de la corrida.

Suite de Codex integrada en `33e45a4`; blindaje de Antigravity en `6c5069f`, `4f0ecc3` y `36da66b`. Codex trabajó en `provider-preflight`: no editó core ni frontend, no hizo push, no reconstruyó ni modificó portables históricos y no realizó llamadas facturadas. El supervisor reproducible se encuentra en `tools/verify_day2_resilience.py`.

## Resultados reproducidos

| Suite | PASS | Verificación |
| --- | ---: | --- |
| `tests/stress/test_concurrency_and_crash.py` | 7 | HTTP simultáneo, fallo de despacho, WAL, corte de proceso y respaldo/restauración |
| `tests/test_budget_pause_and_recovery.py` | 5 | Pausa y recuperación simulada, preflight agotado, reclamación y reservas inciertas |
| `tests/test_continuity_m.py` | 6 | Snapshots, pausa, exportación cifrada, respaldo y recuperación con repositorio sintético |
| `tests/test_worker_claim_resilience.py` | 4 | Worker cerrado, rechazo del executor, ledger concurrente y reclamaciones |

Los identificadores completos y tiempos de cada caso provienen del JUnit y están en el JSON adjunto. No se contaron como aprobadas las corridas preliminares con cambios de base o colisiones de temporales.

### Reanudación adversa y despacho

Se lanzaron lotes de **10 y 20 peticiones HTTP simultáneas**, sincronizadas con una barrera, a la ruta real `POST /runs/{id}/resume` mediante TestClient sin sockets de red. En cada lote hubo exactamente **1 HTTP 200**, **9 o 19 HTTP 409** y **1 despacho encolado**. El stub mantiene la reclamación mientras se procesan los contendientes; no ejecuta agentes. El fixture es local con autenticación y rate limit desactivados para aislar la propiedad de exclusión, no valida la frontera autenticada por perfil.

Se provocó tanto el cierre del worker como una excepción de `ThreadPoolExecutor.submit`: la primera petición devolvió 500, dejó la corrida pausada y `worker.active == 0`; al corregir la condición, un nuevo intento pudo encolarse con HTTP 200. No se sustituyeron por xfail ni se debilitaron estas aserciones.

### Escritura WAL

**40 hilos**, 20 del ledger y 20 de checkpoints auténticos de LangGraph, iniciaron juntos. Cada uno realizó 6 iteraciones: **120 reservas conciliadas y 120 checkpoints** en la misma SQLite. El consumo final exacto fue **7,5** unidades sintéticas, reservas pendientes cero; se verificaron los checkpoints de cada escritor y `PRAGMA integrity_check = ok`. No se envolvieron las llamadas del test en reintentos propios que ocultaran errores del producto.

La suite complementaria de Antigravity añade 15 hilos del ledger y 15 intentos de reclamación. Este último caso verifica 1 ganador y 14 conflictos; se corrige la anterior descripción inconsistente de “10 hilos / 14 conflictos”.

### Corte abrupto

El hijo crea requisitos confirmados y un plan real `PLAN_ONLY`, los persiste y abre `BEGIN IMMEDIATE`. Escribe cambios no confirmados sobre el registro y una reserva, y avisa al padre mediante un archivo. Solo entonces el padre termina **su propio proceso hijo** con `kill()` (TerminateProcess en Windows), espera su salida y abre de nuevo RunStore/RunEngine. Integridad `ok`, reserva no confirmada ausente e interpretación/plan idénticos a la línea base confirmada.

La base inicial reveló un `disk I/O error` inmediatamente después del corte. Una apertura posterior recuperó datos íntegros. El backoff de Antigravity permitió aprobar el reinicio inmediato; **no se demuestra que el antivirus o un componente concreto fuese su causa**. No se borraron manualmente WAL/SHM ni se restauró una copia para hacer pasar el ensayo.

### Ciclo de vida y respaldo

Cuatro trabajos del RunWorker escribieron 10 checkpoints cada uno y terminaron. Sus callbacks reales invocaron auto_backup; `shutdown(wait=True)` concluyó, el contador activo quedó en cero y el estado final de respaldo fue `completed`. Se leyó el `.aiswe-vault`, se descifró/importó con una contraseña sintética mantenida en memoria y se comprobaron integridad, plan e interpretación restaurados. La contraseña no aparece en caplog y el archivo no expone la cabecera SQLite en claro.

Este ensayo cubre las carreras ejercitadas y el respaldo tras estabilización; no prueba que se exporte una instantánea de una tarea activa ni ausencia universal de deadlocks. El aplazamiento con tareas activas está cubierto por la suite de continuidad existente. No se usaron contraseñas ni bases reales del usuario.

## Reproducción y aislamiento del harness

Desde el worktree de Codex:

```powershell
.venv\Scripts\python.exe tools/verify_day2_resilience.py _tmp/day2-evidence-nueva
```

El destino debe ser nuevo. El supervisor impone **180 segundos**, usa un directorio temporal **corto y único** fuera de `pytest-of-jose_`, guarda log/JUnit/metadata y rechaza como no certificada una corrida cuyo HEAD cambie. Los fixtures fallidos pueden conservarse en el temporal indicado por el informe para diagnóstico; no deben publicarse como datos del usuario.

Esto evita dos interferencias observadas: borrado de temporales compartidos por otra sesión pytest y rutas excesivamente largas al colocar toda la base de pruebas dentro del worktree. La corrida final corta/exclusiva aprobó también la continuidad que falló bajo la ruta profunda; no se cambió la aserción de continuidad para conseguirlo.

## Evidencia y límites

[Reporte JSON](RESILIENCE-CRASH-EVIDENCE-2026-11-04.json): base estable, casos reales, conteos, parámetros, hashes JUnit/log y hashes de las cuatro suites. Crudos locales en `_tmp/day2-codex-independent/`. La comprobación Ruff del supervisor y suite adversa aprobó.

No se ejecutó regresión completa backend/frontend, pruebas de carga prolongada, conexiones remotas, Docker real, almacenamiento en red ni corte físico de energía. No se inyectaron errores de bloqueo directamente en vault.py. La carrera HTTP demuestra exclusión de despachos en la cola, no facturación exactamente una vez en un proveedor externo. RC26 no se reconstruyó con los commits del Día 2: ese empaquetado y su certificación son una actividad posterior.

## Seguimiento de seguridad del supervisor

Se eliminó el parser XML del supervisor tras el hallazgo `use-defused-xml-parse`. El resultado de pytest sigue siendo la autoridad; el JUnit se conserva como bytes opacos con ruta y SHA-256 calculado en streaming, sin resolver entidades ni cargar un árbol XML. No se añadió dependencia. Tres tests unitarios pasan con XML normal, una entidad externa y una declaración de expansión. Esta corrección de metadatos no reejecutó las 22 pruebas del acta ni altera su evidencia histórica.
