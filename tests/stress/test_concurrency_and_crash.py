"""Offline adversarial HTTP, WAL, crash and worker-backup contracts.

Only synthetic temporary databases are killed; no application process is touched.
Run this suite in its own process with a bounded supervisor for deadlock detection.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.base import empty_checkpoint

from ai_swe.api import crear_app
from ai_swe.config import Settings
from ai_swe.contracts import RunOptions, RunStatus
from ai_swe.graph import RunEngine
from ai_swe.graph.worker import RunWorker
from ai_swe.state import RunStore
from ai_swe.state.budget_ledger import BudgetLedger
from ai_swe.state.continuity import ContinuityStore


def settings_at(path: Path) -> Settings:
    return Settings(
        _env_file=None, profile_mode=False, state_db_path=path / "state.sqlite3",
        workspace_root=path / "worktrees", remote_model_roles=[], stt_provider="fake",
        api_keys={}, rate_limit_enabled=False, network_egress_enabled=False,
    )


def seed_completed(engine: RunEngine):
    state = engine.crear_estado(
        "Crea un calendario de prueba", options=RunOptions(mode="PLAN_ONLY"))
    state = state.model_copy(update={"instruction": state.instruction.model_copy(
        update={"confirmed_by_user": True})})
    result = engine.start(state)
    if result.status is RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION:
        result = engine.resume(state.run_id, "approved")
    assert result.status is RunStatus.COMPLETED
    assert result.interpretation is not None and result.plan is not None
    return result


def checkpoint_write(saver, writer: int, iteration: int):
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {"writer": writer, "iteration": iteration}
    return saver.put(
        {"configurable": {"thread_id": f"stress-{writer}", "checkpoint_ns": ""}},
        checkpoint, {"source": "update", "step": iteration, "parents": {}}, {},
    )


@pytest.fixture
def paused_api(tmp_path):
    settings = settings_at(tmp_path)
    with RunStore(settings.state_db_path) as store:
        app = crear_app(store=store, settings=settings)
        with TestClient(app, raise_server_exceptions=False) as client:
            engine = app.state.engine
            state = engine.crear_estado("PeticiÃƒÆ’Ã‚Â³n sintÃƒÆ’Ã‚Â©tica para reanudar")
            state = state.model_copy(update={"status": RunStatus.PAUSED, "next_step": "coder"})
            engine.create(state)
            yield client, engine, app.state.worker, state.run_id


@pytest.mark.parametrize("requests", [10, 20])
def test_simultaneous_http_resume_dispatches_exactly_once(paused_api, monkeypatch, requests):
    client, engine, worker, run_id = paused_api
    dispatched = []
    lock = threading.Lock()

    def enqueue(identifier):
        with lock:
            dispatched.append(identifier)
        # Hold the claim as a queued worker would; never execute any agent here.

    monkeypatch.setattr(worker, "submit_resume_paused", enqueue)
    barrier = threading.Barrier(requests)

    def request(_):
        barrier.wait(timeout=15)
        response = client.post(f"/runs/{run_id}/resume")
        return response.status_code

    try:
        with ThreadPoolExecutor(max_workers=requests) as pool:
            codes = list(pool.map(request, range(requests), timeout=40))
        assert codes.count(200) == 1, codes
        assert codes.count(409) == requests - 1, codes
        assert dispatched == [run_id]
        assert engine.get(run_id).status is RunStatus.PAUSED
    finally:
        engine.olvidar_reclamacion(run_id)


@pytest.mark.parametrize("failure", ["closed_worker", "executor"])
def test_failed_worker_submission_releases_claim_for_http_retry(paused_api, monkeypatch, failure):
    client, engine, worker, run_id = paused_api

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic submission failure")

    if failure == "closed_worker":
        monkeypatch.setattr(worker, "_cerrado", True)
    else:
        monkeypatch.setattr(worker._pool, "submit", fail)
    try:
        first = client.post(f"/runs/{run_id}/resume")
        assert first.status_code == 500
        assert engine.get(run_id).status is RunStatus.PAUSED
        assert worker.active == 0
        accepted = []
        monkeypatch.setattr(worker, "_cerrado", False)
        monkeypatch.setattr(worker, "submit_resume_paused", accepted.append)
        retry = client.post(f"/runs/{run_id}/resume")
        assert retry.status_code == 200, retry.text
        assert accepted == [run_id]
    finally:
        engine.olvidar_reclamacion(run_id)


def test_forty_wal_writers_preserve_reservations_and_langgraph_checkpoints(tmp_path):
    settings = settings_at(tmp_path)
    with RunStore(settings.state_db_path) as store:
        ledgers = [BudgetLedger(settings.state_db_path) for _ in range(20)]
        ledgers[0].set_limit(100)
        savers = [store.checkpointer() for _ in range(20)]
        for saver in savers:
            saver.setup()
        barrier = threading.Barrier(40)

        def write(index):
            barrier.wait(timeout=15)
            for iteration in range(6):
                if index < 20:
                    reservation = ledgers[index].reserve(
                        f"ledger-{index}", 0.125, run_limit=10)
                    ledgers[index].settle(reservation, 0.0625)
                else:
                    checkpoint_write(savers[index - 20], index, iteration)

        with ThreadPoolExecutor(max_workers=40) as pool:
            list(pool.map(write, range(40), timeout=90))
        with sqlite3.connect(settings.state_db_path) as db:
            assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert db.execute("SELECT COUNT(*) FROM budget_reservations").fetchone()[0] == 120
            assert db.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 120
        assert ledgers[0].summary()["consumed"] == 7.5
        assert ledgers[0].summary()["reserved"] == 0
        for index, saver in enumerate(savers, 20):
            saved = saver.get_tuple({"configurable": {"thread_id": f"stress-{index}"}})
            assert saved.checkpoint["channel_values"] == {"writer": index, "iteration": 5}


def _crash_writer(directory: Path):
    settings = settings_at(directory)
    with RunStore(settings.state_db_path) as store:
        state = seed_completed(RunEngine(store, settings=settings))
        BudgetLedger(settings.state_db_path).set_limit(10)
        baseline = {"run_id": state.run_id,
                    "interpretation": state.interpretation.model_dump(mode="json"),
                    "plan": state.plan.model_dump(mode="json")}
        (directory / "committed.json").write_text(json.dumps(baseline), encoding="utf-8")
        with sqlite3.connect(settings.state_db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE runs SET state_json='uncommitted corruption'")
            db.execute("INSERT INTO budget_reservations(id,run_id,reserved) VALUES(?,?,?)",
                       ("uncommitted-crash", state.run_id, 9))
            (directory / "transaction-open").write_text("ready", encoding="ascii")
            threading.Event().wait(90)
            raise AssertionError("Parent failed to kill the crash fixture")


def test_forced_process_termination_rolls_back_and_preserves_requirements_plan(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    environment = {k: v for k, v in os.environ.items()
                   if k.upper() in {"SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
                                    "PATHEXT", "TEMP", "TMP", "USERPROFILE"}}
    environment["PATH"] = str(Path(os.environ["SYSTEMROOT"]) / "System32")
    environment.update(PYTHONPATH=str(repo / "src"), HF_HUB_OFFLINE="1",
                       LOCALAPPDATA=str(tmp_path / "user-data"), PYTHONDONTWRITEBYTECODE="1")
    with (tmp_path / "child.log").open("wb") as log:
        child = subprocess.Popen(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--crash-writer", str(tmp_path)],
            cwd=tmp_path, env=environment, stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            deadline = time.monotonic() + 30
            while not (tmp_path / "transaction-open").exists():
                assert child.poll() is None, (tmp_path / "child.log").read_text(errors="replace")
                assert time.monotonic() < deadline, "Crash writer never reached open transaction"
                time.sleep(0.02)
            child.kill()
            child.wait(timeout=10)
            assert child.returncode != 0
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
    baseline = json.loads((tmp_path / "committed.json").read_text(encoding="utf-8"))
    settings = settings_at(tmp_path)
    with RunStore(settings.state_db_path) as store:
        assert store.recover_from_crash()["integrity_ok"]
        recovered = RunEngine(store, settings=settings).get(baseline["run_id"])
        assert recovered.interpretation.model_dump(mode="json") == baseline["interpretation"]
        assert recovered.plan.model_dump(mode="json") == baseline["plan"]
        with sqlite3.connect(settings.state_db_path) as db:
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert db.execute("SELECT COUNT(*) FROM budget_reservations").fetchone()[0] == 0


def test_worker_auto_backup_during_checkpoint_writes_finishes_and_restores(tmp_path, caplog):
    settings = settings_at(tmp_path)
    password = "synthetic-day2-backup-password"
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        baseline = seed_completed(engine)
        engine.continuity.configure_backup(tmp_path / "backups")
        engine.continuity.set_credentials(password=password)
        savers = [store.checkpointer() for _ in range(4)]
        for saver in savers:
            saver.setup()
        barrier = threading.Barrier(4)
        done = [threading.Event() for _ in range(4)]
        errors = []

        def write(index):
            try:
                barrier.wait(timeout=15)
                for iteration in range(10):
                    checkpoint_write(savers[index], index, iteration)
            except Exception as exc:
                errors.append(exc)
            finally:
                done[index].set()

        worker = RunWorker(engine, max_workers=4)
        try:
            for index in range(4):
                worker._submit(write, index)
            assert all(event.wait(timeout=30) for event in done), "Checkpoint writers deadlocked"
        finally:
            worker.shutdown(wait=True)
        assert not errors
        assert worker.active == 0
        status = engine.continuity.backup_status()
        assert status["status"] == "completed", status
        archive = Path(status["last_backup_path"]).read_bytes()
        assert b"SQLite format 3" not in archive
        assert password not in caplog.text
    restored_path = tmp_path / "restored.sqlite3"
    restored = ContinuityStore(restored_path, "restored", worktrees_root=tmp_path / "restore-wt")
    restored.import_archive(archive, password)
    with RunStore(restored_path) as store:
        assert store.recover_from_crash()["integrity_ok"]
        recovered = RunEngine(store).get(baseline.run_id)
        assert recovered.plan == baseline.plan
        assert recovered.interpretation == baseline.interpretation


if __name__ == "__main__":
    assert len(sys.argv) == 3 and sys.argv[1] == "--crash-writer"
    _crash_writer(Path(sys.argv[2]))
