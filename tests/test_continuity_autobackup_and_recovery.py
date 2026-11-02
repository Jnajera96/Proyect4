"""Pruebas de auto-respaldo en el ciclo de vida, resolución de conflictos y recuperación de cortes."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path
import pytest

from ai_swe.contracts import Instruction, InstructionSource, RunState
from ai_swe.graph.engine import RunEngine
from ai_swe.graph.worker import RunWorker
from ai_swe.state.continuity import ContinuityError, ContinuityStore, import_vault_to_profile
from ai_swe.state.profiles import ProfileStore
from ai_swe.state.store import RunStore


def test_auto_backup_in_worker_lifecycle(tmp_path: Path) -> None:
    db_path = tmp_path / "test_store.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    store = RunStore(db_path)
    engine = RunEngine(store)
    worker = RunWorker(engine)

    # Configurar respaldo automático con contraseña
    engine.continuity.configure_backup(str(backup_dir), enabled=True)
    engine.continuity.set_credentials(password="SuperSecret12345!")

    # Crear una ejecución simple
    ahora = datetime.now(UTC)
    st = RunState(
        run_id="run-autobackup-test",
        trace_id="trace-autobackup-test",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(text="hazme un script", source=InstructionSource.TEXT, confirmed_by_user=True),
    )
    store.create(st)

    # Enviar al trabajador para que se ejecute y dispare el auto-respaldo en el finally
    worker.submit(st.run_id)
    worker.shutdown(wait=True)

    # Verificar que el auto-respaldo se completó
    status = engine.continuity.backup_status()
    assert status["enabled"] == 1
    assert status["status"] == "completed"
    assert status["last_backup_path"] is not None

    backup_file = Path(status["last_backup_path"])
    assert backup_file.exists()
    assert backup_file.name.endswith(".aiswe-vault")
    assert backup_file.stat().st_size > 0


def test_import_vault_conflict_resolution_rename(tmp_path: Path) -> None:
    users_dir = tmp_path / "users"
    profile_store = ProfileStore(users_dir)

    # Crear un perfil existente con nombre 'pedro'
    profile_orig = profile_store.create("pedro", "Password123456!")
    # Inicializar el RunStore para que la base contenga las tablas requeridas
    rs = RunStore(profile_orig.paths.database)
    rs.close()

    # Exportar una bóveda con profile_name 'pedro'
    continuity = ContinuityStore(
        profile_orig.paths.database,
        profile_orig.user_id,
        profile_name="pedro",
        worktrees_root=profile_orig.paths.worktrees,
    )
    archive = continuity.export_archive("Password123456!")

    # Caso 1: con conflict_strategy="error" debe lanzar ContinuityError
    with pytest.raises(ContinuityError, match="No se puede crear el perfil"):
        import_vault_to_profile(
            profile_store,
            archive,
            "Password123456!",
            repo_mapping={},
            conflict_strategy="error",
        )

    # Caso 2: con conflict_strategy="rename" debe renombrar y tener éxito
    restored_profile = import_vault_to_profile(
        profile_store,
        archive,
        "Password123456!",
        repo_mapping={},
        conflict_strategy="rename",
    )
    assert restored_profile.name == "pedro-restored"
    assert restored_profile.user_id != profile_orig.user_id

    # Caso 3: importar una segunda vez debe generar 'pedro-restored-2'
    second_restored = import_vault_to_profile(
        profile_store,
        archive,
        "Password123456!",
        repo_mapping={},
        conflict_strategy="rename",
    )
    assert second_restored.name == "pedro-restored-2"


def test_store_recover_from_crash(tmp_path: Path) -> None:
    db_path = tmp_path / "crash_test.sqlite3"
    store = RunStore(db_path)

    # Crear una ejecucion para poblar la base
    ahora = datetime.now(UTC)
    st = RunState(
        run_id="run-crash-test",
        trace_id="trace-crash-test",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(text="test", source=InstructionSource.TEXT, confirmed_by_user=True),
    )
    store.create(st)

    # Ejecutar recuperacion de corte
    resultado = store.recover_from_crash()
    assert resultado["integrity_ok"] is True
    assert resultado["wal_checkpoint"] is not None


def test_import_long_profile_name_renames_without_overwriting(tmp_path):
    profiles = ProfileStore(tmp_path / "users")
    original = profiles.create("a" * 64, "Password123456!")
    with RunStore(original.paths.database):
        pass
    continuity = ContinuityStore(original.paths.database, original.user_id,
                                 profile_name=original.name)
    archive = continuity.export_archive("Password123456!")
    restored = import_vault_to_profile(
        profiles, archive, "Password123456!", repo_mapping={}, conflict_strategy="rename"
    )
    assert len(restored.name) <= 64
    assert restored.name.endswith("-restored")
    assert restored.user_id != original.user_id
    assert profiles.unlock(original.name, "Password123456!").user_id == original.user_id


def test_failed_integrity_does_not_checkpoint_wal(tmp_path):
    import sqlite3

    class DamagedConnection:
        def __init__(self):
            self.commands = []

        def execute(self, command):
            self.commands.append(command)
            return self

        def fetchone(self):
            return ("simulated damaged page",)

        def commit(self):
            pytest.fail("No debe modificar una base con integridad fallida")

    with RunStore(tmp_path / "state.sqlite3") as store:
        original = store._conn
        damaged = DamagedConnection()
        store._conn = damaged
        try:
            with pytest.raises(sqlite3.DatabaseError, match="integridad"):
                store.recover_from_crash()
            assert damaged.commands == ["PRAGMA integrity_check"]
        finally:
            store._conn = original


def test_server_rejects_failed_integrity_before_orphan_cleanup(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from ai_swe.api import crear_app
    from ai_swe.config import Settings

    with RunStore(tmp_path / "state.sqlite3") as store:
        monkeypatch.setattr(store, "recover_from_crash", lambda: {"integrity_ok": False})
        monkeypatch.setattr(store, "orphan_open_runs",
                            lambda: pytest.fail("No debe modificar ejecuciones"))
        app = crear_app(store=store, settings=Settings(_env_file=None, stt_provider="fake"))
        with pytest.raises(RuntimeError, match="integridad"), TestClient(app):
            pytest.fail("No debe iniciar con integridad fallida")


def test_invalid_backup_input_returns_explained_error(tmp_path):
    from fastapi.testclient import TestClient

    from ai_swe.api import crear_app
    from ai_swe.config import Settings

    with RunStore(tmp_path / "state.sqlite3") as store:
        app = crear_app(store=store, settings=Settings(_env_file=None, stt_provider="fake"))
        with TestClient(app) as client:
            response = client.post("/continuity/import", json={
                "archive_b64": "%%%invalid%%%", "password": "Password123456!", "repo_mapping": {}
            })
        assert response.status_code == 409
        assert "base64" in response.text
        assert "CONTINUITY_ERROR" in response.text


def test_authenticated_worker_backup_can_restore_pending_requirements(tmp_path):
    import time

    from fastapi.testclient import TestClient

    from ai_swe.api import crear_app
    from ai_swe.config import Settings

    password = "Synthetic backup password"
    app = crear_app(settings=Settings(
        _env_file=None, profile_mode=True, profiles_root=tmp_path / "users",
        stt_provider="fake",
    ))
    with TestClient(app) as client:
        response = client.post("/auth/register", json={"name": "backup-user", "password": password})
        assert response.status_code == 201
        headers = {"X-CSRF-Token": response.json()["csrf_token"]}
        assert client.post("/continuity/backup-config", json={
            "folder": str(tmp_path / "backups"), "enabled": True,
        }, headers=headers).status_code == 200
        response = client.post("/runs", json={
            "instruction": "Explica el proyecto sin modificar archivos",
            "options": {"execution_mode": "INSPECT_ONLY"},
        }, headers=headers)
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        deadline = time.monotonic() + 20
        while True:
            status = client.get("/continuity/status").json()
            if status["status"] == "completed":
                break
            assert time.monotonic() < deadline, status
            time.sleep(0.02)
        assert client.get(f"/runs/{run_id}").json()["status"] == (
            "awaiting_human_requirements_confirmation"
        )
        archive = Path(status["last_backup_path"]).read_bytes()
        assert password.encode() not in archive
        with pytest.raises(ContinuityError):
            ContinuityStore._open_archive_bytes(archive, "wrong-password")

    profiles = ProfileStore(tmp_path / "restored-users")
    restored = import_vault_to_profile(profiles, archive, password, repo_mapping={})
    with RunStore(restored.paths.database) as store:
        summaries = store.list_summaries()
        assert [(s.run_id, s.status) for s in summaries] == [
            (run_id, "awaiting_human_requirements_confirmation")
        ]
