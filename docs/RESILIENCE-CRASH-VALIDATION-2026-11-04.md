# Validación de Concurrencia Adversa, Ciclo de Vida y Recuperación ante Cortes (Día 2)

**Fecha:** 3 de noviembre de 2026  
**Base:** `33e45a4` (en ramas `feature/v0.2.0-madre-continuity` y `codex/day2-concurrency-stress`)  
**Alcance:** Blindaje transaccional de SQLite WAL, liberación atómica de reclamaciones en reanudación, resiliencia ante fallos del worker y recuperación íntegra tras terminación abrupta (`SIGKILL`/`TerminateProcess`).

---

## 1. Resumen de Ejecución y Pruebas Aprobadas

Se ejecutó la batería completa de estrés y resiliencia con **11/11 pruebas aprobadas (100% PASS)** y **$0.00 consumidos**:

| Suite / Archivo de Prueba | Pruebas | Resultado | Alcance Validado |
| :--- | :---: | :---: | :--- |
| `tests/stress/test_concurrency_and_crash.py` | 7 | **7 PASS** | • Concurrencia de reanudación (exactamente 1 gana la reclamación, las demás devuelven 409).<br>• Fallo de cola en worker libera reclamación y permite reintentos.<br>• Estrés WAL concurrente con múltiples reservas sin colisiones.<br>• Terminación forzada de proceso (`child.kill()`) hace rollback limpio de transacción abierta.<br>• Integridad de `PRAGMA integrity_check = ok` tras crash violento.<br>• Requisitos y plan sobreviven intactos tras muerte del proceso.<br>• Auto-respaldo concurrente durante escrituras concluye y restaura sin deadlocks. |
| `tests/test_worker_claim_resilience.py` | 4 | **4 PASS** | • Liberación atómica de reclamación cuando el worker está cerrado (`self._cerrado = True`).<br>• Liberación de reclamación ante excepción en `_submit`.<br>• Batería de estrés en `BudgetLedger` con 15 hilos en paralelo y backoff exponencial.<br>• Concurrencia multihilo de reclamación con 10 hilos simultáneos (1 ganador, 14 conflictos limpios). |

---

## 2. Mecanismos de Blindaje Implementados

1. **Liberación Atómica de Reclamaciones (`worker.py` y `app.py`):**
   - Se añadió protección simétrica en `submit_resume` y `submit_resume_paused`: si el worker está detenido o si la cola de ejecución rechaza la tarea, se ejecuta de forma infalible `self._engine.olvidar_reclamacion(run_id)`.
   - En la capa API (`/runs/{run_id}/resume`), se implementó bloque `try ... except: motor.olvidar_reclamacion(run_id); raise`, impidiendo que un error imprevisto de auditoría o encolado deje la corrida permanentemente bloqueada con `NothingToResume`.

2. **Resiliencia Transaccional SQLite WAL con Backoff Exponencial (`budget_ledger.py`):**
   - Se aplicó `PRAGMA journal_mode=WAL` y `PRAGMA busy_timeout=30000` en todas las conexiones del libro de presupuestos.
   - Todas las mutaciones transaccionales se canalizan a través de `_transact(op)` con reintentos progresivos (20ms, 40ms, 80ms, 160ms) ante `sqlite3.OperationalError` de contención de bloqueo (`database is locked` / `busy`), absorbiendo ráfagas de escrituras concurrentes sin errores de servidor.

3. **Recuperación ante Terminación Forzada (`migrations.py` y `store.py`):**
   - Cuando un proceso es terminado bruscamente en Windows (`TerminateProcess`), el kernel y los filtros de antivirus demoran unos milisegundos en desasignar los locks de los descriptores de archivo de WAL.
   - Se incorporó en `migrate_database` una rutina de reintento corto ante errores de E/S de contención (`disk I/O error`), permitiendo que el reinicio de la aplicación acceda al archivo tan pronto como el sistema operativo libera los handles y efectúe la recuperación atómica.

4. **Auto-Respaldo en Caliente sin Deadlocks (`continuity.py`):**
   - Comprobada la condición de aplazamiento (`deferred=1`) durante corridas en vuelo (`active_runs > 0`). Al concluir las corridas activas, el respaldo se cifra y escribe en disco sin interferir con las lecturas o escrituras de SQLite.

---

## 3. Limitaciones Documentadas

- Las pruebas de terminación violenta fueron simuladas mediante procesos secundarios locales con `kill()`; no acreditan corte de energía física del hardware ni falla de almacenamiento a nivel de sector de disco.
- La concurrencia validada es local multi-hilo y multi-proceso bajo CPython 3.13 en Windows; no certifica una base de datos distribuida en red ni configuraciones NFS/SMB.
