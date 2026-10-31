import sqlite3
from contextlib import closing

import pytest

from ai_swe.state.migrations import MIGRATIONS, Migration, MigrationError, SchemaMigrator
from ai_swe.state.operation_lock import operation_lock


def legacy(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        MIGRATIONS[0].up(db)
        db.execute("PRAGMA user_version=1")
        db.execute("INSERT INTO projects VALUES('p','Demo','C:/repos/demo','now')")
        db.execute(
            "INSERT INTO runs VALUES('r','t','awaiting_approval','modify','now','now',0,'{}')"
        )
        db.execute("INSERT INTO profile_budget VALUES(1,5)")
        db.execute(
            "INSERT INTO budget_reservations(id,run_id,reserved,consumed) VALUES('b','r',0.5,NULL)"
        )
        db.execute("CREATE TABLE budget_ledger(id TEXT PRIMARY KEY, amount REAL)")
        db.execute("INSERT INTO budget_ledger VALUES('legacy',1.25)")
    return path


def version(path):
    with closing(sqlite3.connect(path)) as db:
        return SchemaMigrator.get_user_version(db)


def test_fresh_database_initializes_at_latest_version(tmp_path):
    path = tmp_path / "state.sqlite3"
    result = SchemaMigrator().migrate_database(path)
    assert result.applied_versions == (1, 2, 3) and result.backup_path.is_file()
    with closing(sqlite3.connect(path)) as db:
        assert version(path) == 3 and SchemaMigrator.check_integrity(db)
        assert [
            r[0] for r in db.execute("SELECT version FROM schema_migrations_log ORDER BY version")
        ] == [1, 2, 3]
        assert all(
            len(r[0]) == 64 for r in db.execute("SELECT checksum FROM schema_migrations_log")
        )


def test_incremental_migration_preserves_existing_data(tmp_path):
    path = legacy(tmp_path / "state.sqlite3")
    report = SchemaMigrator().migrate_database(path)
    assert report.applied_versions == (2, 3)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT name,repo_path FROM projects").fetchall() == [
            ("Demo", "C:/repos/demo")
        ]
        assert db.execute("SELECT state_json,status FROM runs").fetchall() == [
            ("{}", "awaiting_approval")
        ]
        assert db.execute("SELECT * FROM budget_ledger").fetchall() == [("legacy", 1.25)]
        assert db.execute("SELECT reserved,consumed FROM budget_reservations").fetchall() == [
            (0.5, None)
        ]
        assert db.execute("SELECT limit_amount FROM profile_budget").fetchone()[0] == 5
        assert "last_launched_at" in {r[1] for r in db.execute("PRAGMA table_info(projects)")}
        assert "cancellation_reason" in {r[1] for r in db.execute("PRAGMA table_info(runs)")}
        db.execute("INSERT INTO memory_fts(text) VALUES('memoria de prueba')")
        assert (
            db.execute(
                "SELECT count(*) FROM memory_fts WHERE memory_fts MATCH 'memoria'"
            ).fetchone()[0]
            == 1
        )


def test_migration_failure_triggers_automatic_rollback_and_restores_backup(tmp_path, monkeypatch):
    path = legacy(tmp_path / "state.sqlite3")
    before = path.read_bytes()
    restored = []
    original = SchemaMigrator.restore_backup

    def restore(backup, target):
        restored.append(backup)
        original(backup, target)

    def broken(db):
        db.execute("CREATE TABLE must_rollback(value TEXT)")
        db.execute("INVALID SQL")

    monkeypatch.setattr(SchemaMigrator, "restore_backup", staticmethod(restore))
    migrator = SchemaMigrator(
        (MIGRATIONS[0], Migration(2, "Fallo simulado", broken), MIGRATIONS[2])
    )
    with pytest.raises(MigrationError):
        migrator.migrate_database(path)
    assert restored and restored[0].read_bytes() == before == path.read_bytes()
    assert version(path) == 1


def test_integrity_check_failure_aborts_migration(tmp_path, monkeypatch):
    path = legacy(tmp_path / "state.sqlite3")
    before = path.read_bytes()
    original = SchemaMigrator.check_integrity

    def integrity(db):
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations_log'").fetchone():
            return False
        return original(db)

    monkeypatch.setattr(SchemaMigrator, "check_integrity", staticmethod(integrity))
    with pytest.raises(MigrationError):
        SchemaMigrator().migrate_database(path)
    assert version(path) == 1 and path.read_bytes() == before


def test_latest_version_is_noop_without_backup_or_integrity_scan(tmp_path, monkeypatch):
    path = tmp_path / "state.sqlite3"
    SchemaMigrator().migrate_database(path)
    before = path.read_bytes()
    monkeypatch.setattr(
        SchemaMigrator, "check_integrity", lambda *_: pytest.fail("No full scan on hot path")
    )
    assert SchemaMigrator().migrate_database(path).backup_path is None
    assert path.read_bytes() == before and len(list(tmp_path.glob("*.bak.*"))) == 1


def test_future_schema_refused_without_writes(tmp_path):
    path = legacy(tmp_path / "state.sqlite3")
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA user_version=99")
    before = path.read_bytes()
    with pytest.raises(MigrationError, match="futura"):
        SchemaMigrator().migrate_database(path)
    assert path.read_bytes() == before and not list(tmp_path.glob("*.bak.*"))


def test_wal_snapshot_includes_committed_data(tmp_path):
    path = legacy(tmp_path / "state.sqlite3")
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("INSERT INTO budget_ledger VALUES('wal',2)")
        db.commit()
        report = SchemaMigrator().migrate_database(path)
        with closing(sqlite3.connect(report.backup_path)) as snapshot:
            assert (
                snapshot.execute("SELECT amount FROM budget_ledger WHERE id='wal'").fetchone()[0]
                == 2
            )
        assert version(path) == 3


def test_concurrent_migration_lock_refuses_without_writes(tmp_path):
    path = legacy(tmp_path / "state.sqlite3")
    before = path.read_bytes()
    with operation_lock(tmp_path / "state.sqlite3.migration.lock"), pytest.raises(MigrationError):
        SchemaMigrator().migrate_database(path)
    assert path.read_bytes() == before


def test_unversioned_legacy_store_does_not_delete_runs(tmp_path):
    from ai_swe.state import RunStore

    path = legacy(tmp_path / "state.sqlite3")
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("PRAGMA user_version=0")
        db.execute("UPDATE meta SET valor='1'")
    with RunStore(path):
        assert version(path) == 3
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT run_id,state_json FROM runs").fetchall() == [("r", "{}")]


def test_store_aborts_before_opening_on_migration_failure(tmp_path, monkeypatch):
    from ai_swe.state import RunStore

    def fail(*args):
        raise MigrationError("Fallo simulado")

    monkeypatch.setattr(SchemaMigrator, "migrate_database", fail)
    with pytest.raises(MigrationError):
        RunStore(tmp_path / "state.sqlite3")


def test_v2_preserves_memory_checkpoints_and_associations(tmp_path):
    path = legacy(tmp_path / "state.sqlite3")
    with closing(sqlite3.connect(path)) as db, db:
        MIGRATIONS[1].up(db)
        db.execute("PRAGMA user_version=2")
        db.execute("INSERT INTO file_cooccurrence VALUES('alice','repo','a.py','b.py',2,'now')")
        db.execute("INSERT INTO memory_documents VALUES(1,'alice','repo','old','note','historial')")
        db.execute("INSERT INTO memory_fts(rowid,text) VALUES(1,'historial')")
        db.execute(
            "INSERT INTO checkpoints(thread_id,checkpoint_id,checkpoint) VALUES('r','c',?)",
            (b"checkpoint",),
        )
    assert SchemaMigrator().migrate_database(path).applied_versions == (3,)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT weight FROM file_cooccurrence").fetchone()[0] == 2
        assert db.execute("SELECT checkpoint FROM checkpoints").fetchone()[0] == b"checkpoint"
        assert db.execute(
            "SELECT rowid FROM memory_fts WHERE memory_fts MATCH 'historial'"
        ).fetchall() == [(1,)]


def test_post_commit_integrity_failure_restores_original(tmp_path, monkeypatch):
    path = legacy(tmp_path / "state.sqlite3")
    before = path.read_bytes()
    checks = []
    original = SchemaMigrator.check_integrity

    def check(db):
        checks.append(True)
        return False if len(checks) == 4 else original(db)

    monkeypatch.setattr(SchemaMigrator, "check_integrity", staticmethod(check))
    with pytest.raises(MigrationError):
        SchemaMigrator().migrate_database(path)
    assert len(checks) == 4 and path.read_bytes() == before and version(path) == 1


def test_corrupt_database_is_not_modified(tmp_path):
    path = tmp_path / "state.sqlite3"
    path.write_bytes(b"not a sqlite database")
    with pytest.raises(MigrationError):
        SchemaMigrator().migrate_database(path)
    assert path.read_bytes() == b"not a sqlite database"


def test_process_crash_rolls_back_sqlite_and_releases_lease(tmp_path):
    import subprocess
    import sys

    path = legacy(tmp_path / "state.sqlite3")
    script = """
import os, sys
from ai_swe.state.migrations import SchemaMigrator, Migration, MIGRATIONS
def crash(db):
    db.execute('CREATE TABLE half_applied(value TEXT)')
    os._exit(73)
migrator = SchemaMigrator((MIGRATIONS[0], Migration(2, 'Crash fixture', crash), MIGRATIONS[2]))
migrator.migrate_database(sys.argv[1])
"""
    result = subprocess.run([sys.executable, "-c", script, str(path)], check=False, timeout=30)
    assert result.returncode == 73 and version(path) == 1
    with closing(sqlite3.connect(path)) as db:
        assert SchemaMigrator.check_integrity(db)
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='half_applied'").fetchone()
    assert SchemaMigrator().migrate_database(path).new_version == 3
