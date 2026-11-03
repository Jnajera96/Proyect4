"""Versioned, additive SQLite upgrades with consistent snapshots and atomic recovery."""

from __future__ import annotations

import hashlib
import inspect
import logging
import os
import shutil
import sqlite3
import uuid
from collections.abc import Callable
from contextlib import closing, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

LATEST_VERSION = 3
log = logging.getLogger(__name__)

BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    trace_id    TEXT NOT NULL,
    status      TEXT NOT NULL,
    intent      TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    error_count INTEGER NOT NULL DEFAULT 0,
    state_json  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_events (
    run_id TEXT NOT NULL,
    seq    INTEGER NOT NULL,
    at     TEXT NOT NULL,
    kind   TEXT NOT NULL,
    data   TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    repo_path  TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_updated ON runs(updated_at DESC);
"""

ASSOCIATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS file_cooccurrence(
                    owner TEXT NOT NULL, repository TEXT NOT NULL,
                    source TEXT NOT NULL, target TEXT NOT NULL, weight REAL NOT NULL,
                    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(owner,repository,source,target));
                CREATE TABLE IF NOT EXISTS file_observations(
                    owner TEXT NOT NULL, repository TEXT NOT NULL, observation TEXT NOT NULL,
                    PRIMARY KEY(owner,repository,observation));
"""

MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_documents (
                    id INTEGER PRIMARY KEY, owner TEXT NOT NULL, repository TEXT NOT NULL,
                    run_id TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL,
                    UNIQUE(owner, repository, run_id, kind));
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(text);
"""

CONTINUITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS worktree_snapshots (
                    owner TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    repo_path TEXT NOT NULL,
                    worktree_path TEXT NOT NULL,
                    base_commit_sha TEXT NOT NULL,
                    binary_diff_b64 TEXT NOT NULL,
                    inventory_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (owner, run_id)
                );
                CREATE TABLE IF NOT EXISTS continuity_config (
                    owner TEXT PRIMARY KEY,
                    backup_dir TEXT,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    deferred INTEGER NOT NULL DEFAULT 0,
                    last_backup_path TEXT,
                    last_backup_at TEXT,
                    last_backup_status TEXT NOT NULL DEFAULT 'not_configured',
                    last_backup_error TEXT
                );
"""


class MigrationError(RuntimeError):
    """Upgrade refused or restored; retained snapshots must not be deleted."""


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    up: Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class MigrationReport:
    old_version: int
    new_version: int
    backup_path: Path | None
    applied_versions: tuple[int, ...] = ()


def _execute(db, script):
    # executescript commits an open transaction, so execute each canonical DDL separately.
    for statement in script.split(";"):
        if statement.strip():
            db.execute(statement)


def _baseline(db):
    _execute(db, BASE_SCHEMA)
    _execute(
        db,
        """
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT NOT NULL, checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL, parent_checkpoint_id TEXT, type TEXT,
            checkpoint BLOB, metadata BLOB, PRIMARY KEY(thread_id,checkpoint_ns,checkpoint_id));
        CREATE TABLE IF NOT EXISTS writes (
            thread_id TEXT NOT NULL, checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL, task_id TEXT NOT NULL, idx INTEGER NOT NULL,
            channel TEXT NOT NULL, type TEXT, value BLOB,
            PRIMARY KEY(thread_id,checkpoint_ns,checkpoint_id,task_id,idx));
        CREATE TABLE IF NOT EXISTS profile_budget (
            id INTEGER PRIMARY KEY CHECK(id=1), limit_amount REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS budget_reservations (
            id TEXT PRIMARY KEY, run_id TEXT NOT NULL, reserved REAL NOT NULL,
            consumed REAL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    """,
    )
    columns = {row[1] for row in db.execute("PRAGMA table_info(budget_reservations)")}
    for name, definition in [
        ("created_epoch", "REAL"),
        ("settled_epoch", "REAL"),
        ("dispatched", "INTEGER NOT NULL DEFAULT 1"),
    ]:
        if name not in columns:
            db.execute(f"ALTER TABLE budget_reservations ADD COLUMN {name} {definition}")
    # Old releases use this marker; keep it compatible without deleting their runs.
    db.execute("INSERT OR REPLACE INTO meta VALUES ('esquema_version','2')")


def _memory(db):
    _execute(db, ASSOCIATION_SCHEMA)
    _execute(db, MEMORY_SCHEMA)


def _recovery(db):
    _execute(db, CONTINUITY_SCHEMA)
    db.execute("""CREATE TABLE IF NOT EXISTS schema_migrations_log (
        version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL,
        description TEXT NOT NULL, checksum TEXT NOT NULL)""")
    for table, field in [("projects", "last_launched_at"), ("runs", "cancellation_reason")]:
        if field not in {row[1] for row in db.execute(f"PRAGMA table_info({table})")}:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {field} TEXT")


MIGRATIONS = (
    Migration(1, "Esquema base compatible", _baseline),
    Migration(2, "Memoria asociativa y FTS5", _memory),
    Migration(3, "Auditoria y recuperacion operativa", _recovery),
)


class SchemaMigrator:
    def __init__(self, migrations=MIGRATIONS):
        self.migrations = tuple(migrations)
        if [m.version for m in self.migrations] != list(range(1, LATEST_VERSION + 1)):
            raise ValueError("Las migraciones deben ser secuenciales de v1 a v3")

    @staticmethod
    def get_user_version(conn):
        return conn.execute("PRAGMA user_version").fetchone()[0]

    @staticmethod
    def set_user_version(conn, version):
        if type(version) is not int or not 0 <= version <= LATEST_VERSION:
            raise ValueError("Version de esquema invalida")
        conn.execute(f"PRAGMA user_version={version}")

    @staticmethod
    def check_integrity(conn):
        return [row[0] for row in conn.execute("PRAGMA integrity_check")] == ["ok"]

    def create_backup(self, db_path):
        db_path = Path(db_path)
        with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as source:
            version = self.get_user_version(source)
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
            backup = db_path.with_name(
                f"{db_path.name}.bak.{stamp}-{uuid.uuid4().hex[:8]}.v{version}"
            )
            backup.touch(mode=0o600, exist_ok=False)
            wal = Path(str(db_path) + "-wal")
            if wal.exists() and wal.stat().st_size:
                with closing(sqlite3.connect(backup)) as target:
                    source.backup(target)
            else:
                shutil.copyfile(db_path, backup)
        with closing(sqlite3.connect(backup.resolve().as_uri() + "?mode=ro", uri=True)) as probe:
            if not self.check_integrity(probe):
                raise MigrationError("El respaldo no supera la verificacion de integridad")
        log.info("[Migraciones] Respaldo preventivo creado: %s", backup)
        with backup.open("r+b") as stream:
            os.fsync(stream.fileno())
        return backup

    @staticmethod
    def restore_backup(backup_path, target_path):
        backup_path, target_path = Path(backup_path), Path(target_path)
        temporary = target_path.with_name(target_path.name + ".restore-" + uuid.uuid4().hex)
        try:
            with temporary.open("xb") as destination, backup_path.open("rb") as source:
                os.chmod(temporary, 0o600)
                shutil.copyfileobj(source, destination)
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary, target_path)
            # All our SQLite handles are closed before replacement; stale WAL must not replay.
            for suffix in ("-wal", "-shm"):
                Path(str(target_path) + suffix).unlink(missing_ok=True)
        finally:
            temporary.unlink(missing_ok=True)

    def migrate_database(self, db_path):
        from ai_swe.state.operation_lock import operation_lock

        path = Path(db_path)
        if path.is_symlink():
            raise MigrationError("No se migra una base de datos mediante enlace")
        path.parent.mkdir(parents=True, exist_ok=True)
        version = None
        for attempt in range(5):
            try:
                with closing(sqlite3.connect(path, timeout=15)) as probe:
                    version = self.get_user_version(probe)
                break
            except sqlite3.OperationalError as exc:
                if attempt < 4:
                    time.sleep(0.05 * (attempt + 1))
                    continue
                raise MigrationError("No se puede leer la base de datos; no se modifica") from exc
            except sqlite3.Error as exc:
                raise MigrationError("No se puede leer la base de datos; no se modifica") from exc
        if version > LATEST_VERSION:
            raise MigrationError("Version futura no compatible; no se modifica la base de datos")
        if version == LATEST_VERSION:
            return MigrationReport(version, version, None)
        backup, db = None, None
        try:
            with operation_lock(Path(str(path) + ".migration.lock")):
                try:
                    db = sqlite3.connect(path, timeout=15)
                    version = self.get_user_version(db)
                    if version == LATEST_VERSION:
                        return MigrationReport(version, version, None)
                    if version > LATEST_VERSION:
                        raise MigrationError("Version futura no compatible")
                    db.execute("BEGIN IMMEDIATE")
                    if not self.check_integrity(db):
                        raise MigrationError("La base de datos de origen no supera integridad")
                    backup = self.create_backup(path)
                    pending = [m for m in self.migrations if m.version > version]
                    for migration in pending:
                        log.info(
                            "[Migraciones] Detectada version v%s. Aplicando v%s (%s)",
                            self.get_user_version(db),
                            migration.version,
                            migration.description,
                        )
                        migration.up(db)
                        self.set_user_version(db, migration.version)
                    for migration in pending:
                        schemas = {
                            1: BASE_SCHEMA,
                            2: ASSOCIATION_SCHEMA + MEMORY_SCHEMA,
                            3: CONTINUITY_SCHEMA,
                        }
                        checksum = hashlib.sha256(
                            (inspect.getsource(migration.up) + schemas[migration.version]).encode()
                        ).hexdigest()
                        db.execute(
                            "INSERT INTO schema_migrations_log VALUES(?, ?, ?, ?)",
                            (
                                migration.version,
                                datetime.now(UTC).isoformat(),
                                migration.description,
                                checksum,
                            ),
                        )
                    if not self.check_integrity(db):
                        raise MigrationError("El resultado no supera la verificacion de integridad")
                    db.commit()
                    if not self.check_integrity(db):
                        raise MigrationError("La verificacion final de integridad fallo")
                    log.info("[Migraciones] Base de datos actualizada a v%s", LATEST_VERSION)
                    return MigrationReport(
                        version, LATEST_VERSION, backup, tuple(m.version for m in pending)
                    )
                except Exception as exc:
                    if db is not None:
                        with suppress(sqlite3.Error):
                            db.rollback()
                        db.close()
                        db = None
                    if backup is not None:
                        self.restore_backup(backup, path)
                        log.error(
                            "[Migraciones] Actualizacion abortada; respaldo restaurado: %s", backup
                        )
                    raise MigrationError(
                        "Actualizacion abortada; no se inicia la base de datos"
                    ) from exc
                finally:
                    if db is not None:
                        db.close()
        except (OSError, sqlite3.Error) as exc:
            raise MigrationError("Base de datos ocupada o no accesible; no se actualiza") from exc
