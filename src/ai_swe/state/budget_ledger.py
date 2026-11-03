"""Transactional, per-profile reservations. Unknown usage retains its reservation."""

from __future__ import annotations

import math
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from pathlib import Path


class LedgerError(ValueError):
    pass


def _amount(value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise LedgerError("Importe invalido")
    return value


class BudgetLedger:
    @staticmethod
    def read_status(path: Path) -> dict:
        """Read readiness without creating/migrating a database or reserving money."""
        empty = {"available": 0.0, "hourly_used": 0.0}
        if not path.is_file():
            return empty
        try:
            with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
                limit = db.execute("SELECT limit_amount FROM profile_budget WHERE id=1").fetchone()
                used = db.execute(
                    "SELECT COALESCE(SUM(COALESCE(consumed,reserved)),0) FROM budget_reservations"
                ).fetchone()[0]
                hourly = db.execute(
                    "SELECT COALESCE(SUM(COALESCE(consumed,reserved)),0) FROM budget_reservations "
                    "WHERE consumed IS NULL OR COALESCE(settled_epoch,created_epoch)>=?",
                    (time.time() - 3600,),
                ).fetchone()[0]
                return {"available": max(0.0, limit[0] - used) if limit else 0.0,
                        "hourly_used": hourly}
        except sqlite3.Error:
            return empty

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS profile_budget (id INTEGER PRIMARY KEY CHECK(id=1),
                    limit_amount REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS budget_reservations (id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL, reserved REAL NOT NULL, consumed REAL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            """)
            db.execute("BEGIN IMMEDIATE")
            columns = {row[1] for row in db.execute("PRAGMA table_info(budget_reservations)")}
            for column in ("created_epoch", "settled_epoch"):
                if column not in columns:
                    db.execute(f"ALTER TABLE budget_reservations ADD COLUMN {column} REAL")
            if "dispatched" not in columns:
                # Legacy unknown reservations might already have reached a provider.
                db.execute("ALTER TABLE budget_reservations ADD COLUMN dispatched INTEGER NOT NULL DEFAULT 1")
            db.execute("UPDATE budget_reservations SET created_epoch="
                       "COALESCE(CAST(strftime('%s',created_at) AS REAL),?) "
                       "WHERE created_epoch IS NULL", (time.time(),))

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def set_limit(self, amount: float):
        amount = _amount(amount)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            used = db.execute(
                "SELECT COALESCE(SUM(COALESCE(consumed,reserved)),0) FROM budget_reservations"
            ).fetchone()[0]
            if amount < used:
                raise LedgerError("El limite no puede ser menor que consumo y reservas")
            db.execute(
                "INSERT INTO profile_budget VALUES(1,?) "
                "ON CONFLICT(id) DO UPDATE SET limit_amount=excluded.limit_amount",
                (amount,),
            )

    def reserve(self, run_id: str, amount: float, *, run_limit: float) -> str:
        amount, run_limit = _amount(amount), _amount(run_limit)
        if not run_id:
            raise LedgerError("Falta identificador de ejecucion")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            limit = db.execute("SELECT limit_amount FROM profile_budget WHERE id=1").fetchone()
            total = db.execute(
                "SELECT COALESCE(SUM(COALESCE(consumed,reserved)),0) FROM budget_reservations"
            ).fetchone()[0]
            run_total = db.execute(
                "SELECT COALESCE(SUM(COALESCE(consumed,reserved)),0) "
                "FROM budget_reservations WHERE run_id=?",
                (run_id,),
            ).fetchone()[0]
            if limit is None or total + amount > limit[0] or run_total + amount > run_limit:
                raise LedgerError("Presupuesto insuficiente para reservar la llamada")
            reservation = str(uuid.uuid4())
            db.execute(
                "INSERT INTO budget_reservations(id,run_id,reserved) VALUES(?,?,?)",
                (reservation, run_id, amount),
            )
            return reservation

    def reserve_call(self, run_id: str, *, run_limit: float, estimate: float,
                     hourly_limit: float | None = None) -> str:
        """Reserve all remaining run allowance before each attempt, including retries.

        This is a local spending guard, not a promise about third-party billing.
        Missing usage or an ambiguous transport error keeps the whole allowance.
        """
        run_limit, estimate = _amount(run_limit), _amount(estimate)
        if not run_id:
            raise LedgerError("Falta identificador de ejecucion")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            limit = db.execute("SELECT limit_amount FROM profile_budget WHERE id=1").fetchone()
            total = db.execute(
                "SELECT COALESCE(SUM(COALESCE(consumed,reserved)),0) FROM budget_reservations"
            ).fetchone()[0]
            used = db.execute(
                "SELECT COALESCE(SUM(COALESCE(consumed,reserved)),0) "
                "FROM budget_reservations WHERE run_id=?",
                (run_id,),
            ).fetchone()[0]
            remaining = run_limit - used
            unresolved_info = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(reserved),0) "
                "FROM budget_reservations WHERE run_id=? AND consumed IS NULL AND dispatched=1",
                (run_id,),
            ).fetchone()
            unresolved_count, unresolved_amount = (unresolved_info[0], unresolved_info[1]) if unresolved_info else (0, 0.0)
            unresolved_note = ""
            if unresolved_count > 0:
                unresolved_note = f" (atención: hay {unresolved_count} reserva(s) previa(s) de cobro incierto por ${unresolved_amount:.2f} retenida(s))"

            if limit is None:
                raise LedgerError(f"Sin saldo configurado en la bóveda del perfil; configure o aumente el límite en su bóveda{unresolved_note}")
            if remaining <= 0 or estimate > remaining:
                raise LedgerError(
                    f"Límite de coste por ejecución alcanzado: requiere estimación de ${estimate:.2f} pero solo restan ${max(0.0, remaining):.2f} "
                    f"del límite por ejecución (${run_limit:.2f}){unresolved_note}"
                )
            if total + remaining > limit[0]:
                disponible = max(0.0, limit[0] - total)
                raise LedgerError(
                    f"Saldo local insuficiente en la bóveda: disponible ${disponible:.2f}, requerido ${remaining:.2f} "
                    f"(límite de bóveda: ${limit[0]:.2f}, consumido/reservado: ${total:.2f}){unresolved_note}"
                )
            reservation = str(uuid.uuid4())
            from ai_swe.models.budget import assert_hourly_cost

            now = time.time()
            hourly = db.execute(
                "SELECT COALESCE(SUM(CASE WHEN consumed IS NULL THEN reserved "
                "ELSE consumed END),0) FROM budget_reservations "
                "WHERE consumed IS NULL OR COALESCE(settled_epoch,created_epoch)>=?",
                (now - 3600,),
            ).fetchone()[0]
            assert_hourly_cost(hourly, remaining, hourly_limit)
            db.execute(
                "INSERT INTO budget_reservations(id,run_id,reserved,created_epoch,dispatched) VALUES(?,?,?,?,0)",
                (reservation, run_id, remaining, now),
            )
            return reservation

    def mark_dispatched(self, reservation: str):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            result = db.execute(
                "UPDATE budget_reservations SET dispatched=1 WHERE id=? AND consumed IS NULL",
                (reservation,),
            )
            if result.rowcount != 1:
                raise LedgerError("La reserva ya se concilió; no se enviará la llamada")

    def reconcile_cancelled(self, run_id: str) -> dict:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            released = db.execute(
                "UPDATE budget_reservations SET consumed=0,settled_epoch=? "
                "WHERE run_id=? AND consumed IS NULL AND dispatched=0", (time.time(), run_id),
            ).rowcount
            unresolved = db.execute(
                "SELECT COUNT(*) FROM budget_reservations WHERE run_id=? AND consumed IS NULL",
                (run_id,),
            ).fetchone()[0]
            return {"released": released, "unresolved": unresolved}

    def settle(self, reservation: str, cost: float | None):
        if cost is None:
            # A settlement with missing usage cannot prove that no request was sent.
            self.mark_dispatched(reservation)
            return
        cost = _amount(cost)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT consumed FROM budget_reservations WHERE id=?", (reservation,)
            ).fetchone()
            if row is None or row[0] is not None:
                raise LedgerError("Reserva inexistente o ya contabilizada")
            # Preserve actual declared usage even if a provider exceeded our estimate.
            db.execute("UPDATE budget_reservations SET consumed=?,settled_epoch=? WHERE id=?",
                       (cost, time.time(), reservation))

    def summary(self) -> dict:
        with self._connect() as db:
            limit = db.execute("SELECT limit_amount FROM profile_budget WHERE id=1").fetchone()
            spent, reserved = db.execute(
                "SELECT COALESCE(SUM(consumed),0), "
                "COALESCE(SUM(CASE WHEN consumed IS NULL THEN reserved ELSE 0 END),0) "
                "FROM budget_reservations"
            ).fetchone()
        return {
            "limit": limit[0] if limit else None,
            "consumed": spent,
            "reserved": reserved,
            "available": max(0, limit[0] - spent - reserved) if limit else None,
        }

    def unresolved_reservations_for_run(self, run_id: str) -> dict:
        with self._connect() as db:
            row = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(reserved),0) "
                "FROM budget_reservations WHERE run_id=? AND consumed IS NULL AND dispatched=1",
                (run_id,),
            ).fetchone()
            return {"count": row[0] if row else 0, "amount": row[1] if row else 0.0}
