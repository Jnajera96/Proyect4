"""Tests verifying atomic claim release on worker submission failure and SQLite WAL resilience."""

from __future__ import annotations

import concurrent.futures
import json
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_swe.config import Settings
from ai_swe.contracts import RunOptions, RunStatus
from ai_swe.graph.engine import NothingToResume, RunEngine
from ai_swe.graph.worker import RunWorker
from ai_swe.state.budget_ledger import BudgetLedger
from ai_swe.state.store import RunStore


def test_submit_resume_paused_releases_claim_on_closed_worker(tmp_path: Path):
    db_path = tmp_path / "state.sqlite3"
    settings = Settings(
        _env_file=None,
        state_db_path=db_path,
        workspace_base_dir=tmp_path / "workspaces",
    )
    store = RunStore(db_path)
    engine = RunEngine(store=store, settings=settings)
    worker = RunWorker(engine=engine, max_workers=2)

    state = engine.crear_estado(
        "Prueba resiliencia de reclamacion",
        options=RunOptions(execution_mode="INSPECT_ONLY"),
    )
    engine.create(state)
    run_id = state.run_id
    state.status = RunStatus.PAUSED
    state.next_step = "coder"
    store.create(state)

    # Claim the pause resume
    engine.reclamar_reanudacion_pausa(run_id)
    assert run_id in engine._reclamadas

    # Close worker to trigger submission failure
    worker.shutdown(wait=False)

    with pytest.raises(RuntimeError, match="el trabajador esta cerrado"):
        worker.submit_resume_paused(run_id)

    # Claim must be released
    assert run_id not in engine._reclamadas

    # Should be able to reclaim cleanly without NothingToResume
    engine.reclamar_reanudacion_pausa(run_id)
    assert run_id in engine._reclamadas
    engine.olvidar_reclamacion(run_id)


def test_submit_resume_paused_releases_claim_on_submission_failure(tmp_path: Path):
    db_path = tmp_path / "state.sqlite3"
    settings = Settings(
        _env_file=None,
        state_db_path=db_path,
        workspace_base_dir=tmp_path / "workspaces",
    )
    store = RunStore(db_path)
    engine = RunEngine(store=store, settings=settings)
    worker = RunWorker(engine=engine, max_workers=2)

    state = engine.crear_estado(
        "Prueba resiliencia de fallo de encolado",
        options=RunOptions(execution_mode="INSPECT_ONLY"),
    )
    engine.create(state)
    run_id = state.run_id
    state.status = RunStatus.PAUSED
    state.next_step = "coder"
    store.create(state)

    engine.reclamar_reanudacion_pausa(run_id)
    assert run_id in engine._reclamadas

    def failing_submit(op, *args):
        raise RuntimeError("Simulated threadpool queue error")

    worker._submit = failing_submit

    with pytest.raises(RuntimeError, match="Simulated threadpool queue error"):
        worker.submit_resume_paused(run_id)

    # Claim must be forgotten despite failure
    assert run_id not in engine._reclamadas


def test_budget_ledger_concurrent_wal_resilience(tmp_path: Path):
    db_path = tmp_path / "state.sqlite3"
    ledger = BudgetLedger(db_path)
    ledger.set_limit(50.0)

    errors = []

    def worker_task(thread_id: int):
        try:
            run_id = f"run-thread-{thread_id}"
            # Test concurrent reserve and summary
            for _ in range(5):
                res_id = ledger.reserve(run_id, 0.05, run_limit=2.0)
                ledger.settle(res_id, cost=0.04)
                summary = ledger.summary()
                assert summary["limit"] == 50.0
        except Exception as exc:
            errors.append(f"Thread {thread_id} failed: {type(exc).__name__}: {exc}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_task, i) for i in range(15)]
        concurrent.futures.wait(futures)

    assert not errors, f"Concurrent ledger transactions encountered errors: {errors}"
    summary = ledger.summary()
    assert summary["consumed"] > 0
    assert summary["reserved"] == 0


def test_concurrent_reclamar_reanudacion_pausa_exactly_one_wins(tmp_path: Path):
    db_path = tmp_path / "state.sqlite3"
    settings = Settings(
        _env_file=None,
        state_db_path=db_path,
        workspace_base_dir=tmp_path / "workspaces",
    )
    store = RunStore(db_path)
    engine = RunEngine(store=store, settings=settings)

    state = engine.crear_estado(
        "Prueba reclamacion concurrente",
        options=RunOptions(execution_mode="INSPECT_ONLY"),
    )
    engine.create(state)
    run_id = state.run_id
    state.status = RunStatus.PAUSED
    state.next_step = "coder"
    store.create(state)

    wins = []
    conflicts = []

    def try_claim():
        try:
            engine.reclamar_reanudacion_pausa(run_id)
            wins.append(True)
        except NothingToResume:
            conflicts.append(True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_claim) for _ in range(15)]
        concurrent.futures.wait(futures)

    assert len(wins) == 1, f"Expected exactly 1 claim winner, got {len(wins)}"
    assert len(conflicts) == 14, f"Expected 14 conflicts, got {len(conflicts)}"
    assert run_id in engine._reclamadas

    engine.olvidar_reclamacion(run_id)
    assert run_id not in engine._reclamadas

