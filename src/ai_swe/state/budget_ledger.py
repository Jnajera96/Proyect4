"""Transactional, per-profile reservations. Unknown usage retains its reservation."""

from __future__ import annotations

import math
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class LedgerError(ValueError):
    pass


def _amount(value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise LedgerError("Importe invalido")
    return value


class BudgetLedger:
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
            if (
                limit is None
                or remaining <= 0
                or estimate > remaining
                or total + remaining > limit[0]
            ):
                raise LedgerError("Presupuesto insuficiente para reservar la llamada")
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
                "INSERT INTO budget_reservations(id,run_id,reserved,created_epoch) VALUES(?,?,?,?)",
                (reservation, run_id, remaining, now),
            )
            return reservation

    def settle(self, reservation: str, cost: float | None):
        if cost is None:
            return  # Never interpret missing usage as zero.
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
