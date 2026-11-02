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
