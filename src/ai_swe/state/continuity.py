"""Portable checkpoints, worktree snapshots, encrypted .aiswe-vault export/import, and lost-device recovery."""

from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import uuid

from ai_swe.contracts import RunState
from ai_swe.security.vault import (
    VaultError,
    _aad,
    _decode,
    _encode,
    open_sealed,
    seal,
    unwrap_key,
    wrap_key,
)
from ai_swe.tools.policy import normalize_rel_path

MAX_WORKTREE_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_CONTENT_BYTES = 256 * 1024 * 1024
ARCHIVE_FORMAT = "aiswe-vault"
ARCHIVE_VERSION = 1


class ContinuityError(RuntimeError):
    """Error tipado de continuidad, portabilidad o recuperacion de sesion."""


@contextmanager
def _sqlite_conn(path: Path | str, timeout: int = 30):
    con = sqlite3.connect(path, timeout=timeout)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()


def _git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(key, None)
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            env=env,
            input=data,
            capture_output=True,
            timeout=60,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ContinuityError(f"Fallo al ejecutar git en '{repo}': {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or b"").decode("utf-8", errors="replace").strip()[:300]
        raise ContinuityError(f"Operacion git rechazada ({' '.join(args[:2])}): {detail}")
    return result.stdout


def _is_link(path: Path) -> bool:
    try:
        return path.is_symlink() or path.is_junction()
    except OSError:
        return True


def _validate_no_links_in_tree(root: Path) -> None:
    if _is_link(root):
        raise ContinuityError("No se permiten enlaces simbolicos ni junctions en la raiz")
    resolved_root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current_dir = Path(dirpath)
        if _is_link(current_dir) or not current_dir.resolve().is_relative_to(resolved_root):
            raise ContinuityError("Enlace externo detectado en el arbol de trabajo")
        if ".git" in dirnames:
            dirnames.remove(".git")
        for name in [*dirnames, *filenames]:
            if name == ".git":
                continue
            candidate = current_dir / name
            if _is_link(candidate):
                raise ContinuityError(f"Enlace no permitido en el worktree: '{name}'")
            if not candidate.resolve().is_relative_to(resolved_root):
                raise ContinuityError(f"Ruta escapa del worktree: '{name}'")


def _validate_rel_Worktree_path(root: Path, rel_path: str) -> Path:
    normalized = normalize_rel_path(rel_path)
    parts = rel_path.split("/")
    if (
        normalized is None
        or normalized != rel_path
        or not normalized
        or any(p in ("", ".", "..") for p in parts)
        or any(p.casefold() == ".git" or ":" in p for p in parts)
    ):
        raise ContinuityError(f"Ruta relativa invalida o no confinada: '{rel_path}'")
    resolved_root = root.resolve()
    current = root
    for part in parts:
        current = current / part
        if _is_link(current):
            raise ContinuityError(f"Enlace no permitido en '{rel_path}'")
    resolved = current.resolve()
    if resolved == resolved_root or not resolved.is_relative_to(resolved_root):
        raise ContinuityError(f"La ruta '{rel_path}' escapa de la raiz autorizada")
    return current


def _atomic_write_bytes(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".aiswe-cont-", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(tmp_path, stat.S_IMODE(mode))
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


class ContinuityStore:
    """Gestiona capturas de worktree, exportacion/importacion .aiswe-vault y auto-respaldo."""

    def __init__(
        self,
        database: Path | str,
        owner: str,
        *,
        profile_name: str | None = None,
        worktrees_root: Path | str | None = None,
    ) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.owner = owner
        self.profile_name = profile_name or owner
        self.worktrees_root = Path(worktrees_root) if worktrees_root else self.database.parent / "worktrees"
        self._profile_key: bytes | None = None
        self._profile_header: dict | None = None
        self._password: str | None = None
        with self.connection() as con:
            con.executescript(
                """
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
            )

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.database, timeout=30)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()

    # ------------------------------------------------- 1. Captura de worktree
    def capture_worktree(
        self,
        run_id: str,
        repo_path: str | Path,
        worktree_path: str | Path,
        base_commit: str = "",
    ) -> dict:
        wt = Path(worktree_path)
        if not wt.exists():
            raise ContinuityError(f"El worktree '{wt}' no existe")
        _validate_no_links_in_tree(wt)
        wt_resolved = wt.resolve()
        repo_resolved = str(Path(repo_path).resolve())
        head_sha = _git(wt_resolved, "rev-parse", "HEAD").decode("utf-8").strip()
        effective_base = base_commit.strip() or head_sha

        tracked_raw = _git(wt_resolved, "diff", "--name-only", "-z", "HEAD").split(b"\0")
        untracked_raw = _git(
            wt_resolved, "ls-files", "--others", "--exclude-standard", "-z"
        ).split(b"\0")
        candidate_paths = sorted(
            {p.decode("utf-8") for p in (*tracked_raw, *untracked_raw) if p}
        )
        if len(candidate_paths) > 500:
            raise ContinuityError("El inventario del worktree supera 500 archivos")

        inventory: list[dict] = []
        total_bytes = 0
        for rel_name in candidate_paths:
            target = _validate_rel_Worktree_path(wt_resolved, rel_name)
            if not target.exists():
                inventory.append(
                    {
                        "path": rel_name,
                        "status": "deleted",
                        "sha256": None,
                        "size": 0,
                        "mode": None,
                        "content_b64": None,
                    }
                )
                continue
            if not target.is_file():
                raise ContinuityError(f"La ruta '{rel_name}' no es un archivo regular")
            raw = target.read_bytes()
            total_bytes += len(raw)
            if total_bytes > MAX_WORKTREE_BYTES:
                raise ContinuityError("El inventario del worktree supera 64 MiB")
            inventory.append(
                {
                    "path": rel_name,
                    "status": "present",
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "size": len(raw),
                    "mode": stat.S_IMODE(target.stat().st_mode),
                    "content_b64": _encode(raw),
                }
            )

        _git(wt_resolved, "add", "-N", "--", ".")
        binary_diff = _git(wt_resolved, "diff", "HEAD", "--binary", "--no-color")
        if len(binary_diff) > MAX_WORKTREE_BYTES:
            raise ContinuityError("El diff binario del worktree supera 64 MiB")

        now = datetime.now(UTC).isoformat()
        snapshot = {
            "owner": self.owner,
            "run_id": run_id,
            "repo_path": repo_resolved,
            "worktree_path": str(wt_resolved),
            "base_commit_sha": effective_base,
            "binary_diff_b64": _encode(binary_diff),
            "inventory": inventory,
            "updated_at": now,
        }
        with self.connection() as con:
            con.execute(
                """
                INSERT INTO worktree_snapshots(
                    owner, run_id, repo_path, worktree_path, base_commit_sha,
                    binary_diff_b64, inventory_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(owner, run_id) DO UPDATE SET
                    repo_path=excluded.repo_path,
                    worktree_path=excluded.worktree_path,
                    base_commit_sha=excluded.base_commit_sha,
                    binary_diff_b64=excluded.binary_diff_b64,
                    inventory_json=excluded.inventory_json,
                    updated_at=excluded.updated_at
                """,
                (
                    self.owner,
                    run_id,
                    repo_resolved,
                    str(wt_resolved),
                    effective_base,
                    snapshot["binary_diff_b64"],
                    json.dumps(inventory, ensure_ascii=False),
                    now,
                ),
            )
        return snapshot

    def capture_run(self, state: RunState) -> dict | None:
        wt_path = state.artifacts.worktree_path
        if not wt_path:
            return None
        wt = Path(wt_path)
        if not wt.exists():
            return None
        repo_path = (
            state.interpretation.scope.repo_path
            if state.interpretation is not None and state.interpretation.scope.repo_path
            else state.options.repo_path
        )
        if not repo_path:
            return None
        return self.capture_worktree(
            state.run_id,
            repo_path,
            wt,
            base_commit=state.artifacts.base_commit or "",
        )

    def snapshot_for(self, run_id: str) -> dict | None:
        with self.connection() as con:
            row = con.execute(
                "SELECT * FROM worktree_snapshots WHERE owner=? AND run_id=?",
                (self.owner, run_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "owner": row["owner"],
            "run_id": row["run_id"],
            "repo_path": row["repo_path"],
            "worktree_path": row["worktree_path"],
            "base_commit_sha": row["base_commit_sha"],
            "binary_diff_b64": row["binary_diff_b64"],
            "inventory": json.loads(row["inventory_json"]),
            "updated_at": row["updated_at"],
        }

    def set_checkpoint_status(self, run_id: str, status) -> None:
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
        from ai_swe.state.store import msgpack_allowlist

        serde = JsonPlusSerializer(allowed_msgpack_modules=list(msgpack_allowlist()))
        now = datetime.now(UTC).isoformat()
        status_val = status.value if hasattr(status, "value") else str(status)
        with self.connection() as con:
            row = con.execute(
                "SELECT state_json FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is not None:
                state_dict = json.loads(row["state_json"])
                state_dict["status"] = status_val
                state_dict["updated_at"] = now
                con.execute(
                    "UPDATE runs SET status=?, updated_at=?, state_json=? WHERE run_id=?",
                    (status_val, now, json.dumps(state_dict, ensure_ascii=False), run_id),
                )
            has_cp = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'"
            ).fetchone()
            if has_cp:
                cp_row = con.execute(
                    """
                    SELECT thread_id, checkpoint_ns, checkpoint_id, type, checkpoint
                    FROM checkpoints WHERE thread_id=?
                    ORDER BY checkpoint_id DESC LIMIT 1
                    """,
                    (run_id,),
                ).fetchone()
                if cp_row is not None:
                    cp_obj = serde.loads_typed((cp_row["type"], cp_row["checkpoint"]))
                    if isinstance(cp_obj, dict) and isinstance(cp_obj.get("channel_values"), dict):
                        cp_obj["channel_values"]["status"] = status
                        new_type, new_blob = serde.dumps_typed(cp_obj)
                        con.execute(
                            """
                            UPDATE checkpoints SET type=?, checkpoint=?
                            WHERE thread_id=? AND checkpoint_ns=? AND checkpoint_id=?
                            """,
                            (
                                new_type,
                                new_blob,
                                cp_row["thread_id"],
                                cp_row["checkpoint_ns"],
                                cp_row["checkpoint_id"],
                            ),
                        )
                    w_type, w_blob = serde.dumps_typed(status)
                    con.execute(
                        """
                        UPDATE writes SET type=?, value=?
                        WHERE thread_id=? AND checkpoint_ns=? AND checkpoint_id=? AND channel='status'
                        """,
                        (
                            w_type,
                            w_blob,
                            cp_row["thread_id"],
                            cp_row["checkpoint_ns"],
                            cp_row["checkpoint_id"],
                        ),
                    )

    def reconstruct_worktree(
        self,
        run_id: str,
        repo_path: str | Path,
        worktrees_root: str | Path | None = None,
        *,
        snapshot: dict | None = None,
    ) -> Path:
        snap = snapshot or self.snapshot_for(run_id)
        if snap is None:
            raise ContinuityError(f"No existe captura de worktree para '{run_id}'")
        repo = Path(repo_path)
        if _is_link(repo) or not repo.exists():
            raise ContinuityError(f"Repositorio invalido para reconstruir worktree: '{repo}'")
        repo_resolved = repo.resolve()
        wt_base = Path(worktrees_root or self.worktrees_root)
        if _is_link(wt_base):
            raise ContinuityError("Raiz de worktrees enlazada no permitida")
        wt_base.mkdir(parents=True, exist_ok=True)
        wt_root = wt_base.resolve()
        if wt_root == repo_resolved or repo_resolved in wt_root.parents:
            raise ContinuityError("La raiz de worktrees no puede estar dentro del repositorio")

        wt_path = (wt_root / run_id).resolve()
        if not wt_path.is_relative_to(wt_root):
            raise ContinuityError("Identificador de ejecucion invalido para worktree")

        if wt_path.exists():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(wt_path)],
                cwd=str(repo_resolved),
                capture_output=True,
                shell=False,
            )
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=str(repo_resolved),
                capture_output=True,
                shell=False,
            )
            if wt_path.exists():
                shutil.rmtree(wt_path, ignore_errors=True)

        base_commit = snap["base_commit_sha"]
        _git(repo_resolved, "cat-file", "-e", f"{base_commit}^{{commit}}")
        _git(repo_resolved, "worktree", "add", "--detach", str(wt_path), base_commit)

        for item in snap["inventory"]:
            rel_name = item["path"]
            dest = _validate_rel_Worktree_path(wt_path, rel_name)
            status = item.get("status")
            if status == "deleted":
                dest.unlink(missing_ok=True)
            elif status == "present":
                raw = _decode(item["content_b64"])
                if (
                    hashlib.sha256(raw).hexdigest() != item["sha256"]
                    or len(raw) != int(item["size"])
                ):
                    raise ContinuityError(
                        f"Integridad fallida al reconstruir '{rel_name}' en '{run_id}'"
                    )
                _atomic_write_bytes(dest, raw, mode=item.get("mode"))
            else:
                raise ContinuityError(f"Estado de archivo desconocido en inventario: {status!r}")

        _git(wt_path, "add", "-N", "--", ".")
        return wt_path

    # ------------------------------------------------- 2. Auto-backup config
    def configure_backup(
        self, folder: str | Path | None, *, enabled: bool = True
    ) -> dict:
        if folder is None or str(folder).strip() == "":
            with self.connection() as con:
                con.execute(
                    """
                    INSERT INTO continuity_config(owner, backup_dir, enabled, deferred, last_backup_status, last_backup_error)
                    VALUES (?, NULL, 0, 0, 'not_configured', NULL)
                    ON CONFLICT(owner) DO UPDATE SET
                        backup_dir=NULL, enabled=0, deferred=0,
                        last_backup_status='not_configured', last_backup_error=NULL
                    """,
                    (self.owner,),
                )
            return self.backup_status()

        target = Path(folder)
        if _is_link(target):
            raise ContinuityError("La carpeta de respaldo no puede ser un enlace simbolico")
        if any(p.casefold() == ".git" for p in target.parts):
            raise ContinuityError("La carpeta de respaldo no puede estar dentro de .git")
        try:
            target.mkdir(parents=True, exist_ok=True)
            resolved = target.resolve()
        except OSError as exc:
            raise ContinuityError(f"No se pudo preparar la carpeta de respaldo: {exc}") from exc
        if _is_link(resolved):
            raise ContinuityError("La carpeta de respaldo resuelta no es valida")

        with self.connection() as con:
            con.execute(
                """
                INSERT INTO continuity_config(owner, backup_dir, enabled, deferred, last_backup_status, last_backup_error)
                VALUES (?, ?, ?, 0, 'configured', NULL)
                ON CONFLICT(owner) DO UPDATE SET
                    backup_dir=excluded.backup_dir,
                    enabled=excluded.enabled,
                    last_backup_status=CASE
                        WHEN excluded.enabled=1 THEN 'configured'
                        ELSE 'disabled'
                    END,
                    last_backup_error=NULL
                """,
                (self.owner, str(resolved), 1 if enabled else 0),
            )
        return self.backup_status()

    def backup_status(self) -> dict:
        with self.connection() as con:
            row = con.execute(
                "SELECT * FROM continuity_config WHERE owner=?", (self.owner,)
            ).fetchone()
        if row is None:
            return {
                "enabled": False,
                "backup_dir": None,
                "deferred": False,
                "last_backup_path": None,
                "last_backup_at": None,
                "status": "not_configured",
                "error": None,
            }
        return {
            "enabled": bool(row["enabled"]),
            "backup_dir": row["backup_dir"],
            "deferred": bool(row["deferred"]),
            "last_backup_path": row["last_backup_path"],
            "last_backup_at": row["last_backup_at"],
            "status": row["last_backup_status"],
            "error": row["last_backup_error"],
        }

    # ------------------------------------------------- 3. Exportacion cifrada
    def _has_inflight_runs(self, active_runs: int = 0) -> bool:
        if active_runs > 0:
            return True
        with self.connection() as con:
            has_runs = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
            ).fetchone()
            if not has_runs:
                return False
            row = con.execute(
                "SELECT count(*) AS n FROM runs WHERE status IN ('running', 'planned')"
            ).fetchone()
            return bool(row and row["n"] > 0)

    def _refresh_open_snapshots(self) -> None:
        with self.connection() as con:
            has_runs = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
            ).fetchone()
            if not has_runs:
                return
            rows = con.execute("SELECT run_id FROM runs").fetchall()
            has_cp = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'"
            ).fetchone()
        if not rows:
            return
        from ai_swe.state.store import RunStore
        from ai_swe.graph.engine import RunEngine

        with RunStore(self.database) as store:
            engine = RunEngine(store)
            for row in rows:
                try:
                    st = engine.get(row["run_id"])
                    if st.artifacts.worktree_path and Path(st.artifacts.worktree_path).exists():
                        self.capture_run(st)
                except Exception:
                    continue

    def _collect_repo_bundles(self) -> tuple[list[dict], int]:
        repos: dict[str, set[str]] = {}
        with self.connection() as con:
            for table, col in (
                ("projects", "repo_path"),
                ("worktree_snapshots", "repo_path"),
                ("promotion_receipts", "root"),
            ):
                exists = con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if not exists:
                    continue
                for r in con.execute(f"SELECT {col} AS p FROM {table}").fetchall():
                    if r["p"]:
                        repos.setdefault(str(Path(r["p"]).resolve()), set())

            has_snaps = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='worktree_snapshots'"
            ).fetchone()
            if has_snaps:
                for r in con.execute(
                    "SELECT repo_path, base_commit_sha FROM worktree_snapshots WHERE owner=?",
                    (self.owner,),
                ).fetchall():
                    if r["repo_path"] and r["base_commit_sha"]:
                        repos.setdefault(str(Path(r["repo_path"]).resolve()), set()).add(
                            r["base_commit_sha"]
                        )

            has_runs = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
            ).fetchone()
            if has_runs:
                for r in con.execute("SELECT state_json FROM runs").fetchall():
                    try:
                        st = json.loads(r["state_json"])
                        rp = (
                            (st.get("interpretation") or {}).get("scope", {}).get("repo_path")
                            or (st.get("options") or {}).get("repo_path")
                        )
                        if rp:
                            resolved_rp = str(Path(rp).resolve())
                            repos.setdefault(resolved_rp, set())
                            bc = (st.get("artifacts") or {}).get("base_commit")
                            if bc:
                                repos[resolved_rp].add(bc)
                    except Exception:
                        continue

        bundles: list[dict] = []
        total_bundle_bytes = 0
        for repo_str, base_commits in sorted(repos.items()):
            repo_path = Path(repo_str)
            if not (repo_path / ".git").exists():
                continue
            head_sha = _git(repo_path, "rev-parse", "HEAD").decode("utf-8").strip()
            all_commits = sorted({head_sha, *base_commits})
            with tempfile.TemporaryDirectory(prefix="aiswe-bundle-") as tmpdir:
                bundle_file = Path(tmpdir) / "repo.bundle"
                _git(repo_path, "bundle", "create", str(bundle_file), "HEAD", "--all")
                bundle_bytes = bundle_file.read_bytes()
            total_bundle_bytes += len(bundle_bytes)
            if total_bundle_bytes > MAX_ARCHIVE_CONTENT_BYTES:
                raise ContinuityError("Los objetos Git superan el presupuesto de 256 MiB")
            bundles.append(
                {
                    "repo_path": repo_str,
                    "head_sha": head_sha,
                    "base_commits": all_commits,
                    "bundle_sha256": hashlib.sha256(bundle_bytes).hexdigest(),
                    "bundle_size": len(bundle_bytes),
                    "bundle_b64": _encode(bundle_bytes),
                }
            )
        return bundles, total_bundle_bytes

    def _sqlite_backup_bytes(self) -> bytes:
        with tempfile.TemporaryDirectory(prefix="aiswe-sqlite-bkp-") as tmpdir:
            backup_path = Path(tmpdir) / "state.sqlite3"
            with _sqlite_conn(self.database, timeout=30) as src_con:
                with _sqlite_conn(backup_path) as dst_con:
                    src_con.backup(dst_con)
            with _sqlite_conn(backup_path) as dst_con:
                dst_con.execute("PRAGMA journal_mode=DELETE")
                check = dst_con.execute("PRAGMA integrity_check").fetchone()
                if not check or check[0] != "ok":
                    raise ContinuityError("Fallo de integridad en la copia SQLite")
            return backup_path.read_bytes()

    def _build_payload_bytes(self, *, active_runs: int = 0) -> bytes:
        if self._has_inflight_runs(active_runs):
            raise ContinuityError(
                "Hay una ejecucion en curso; solicita una pausa antes de exportar"
            )
        self._refresh_open_snapshots()
        bundles, bundle_bytes = self._collect_repo_bundles()
        sqlite_bytes = self._sqlite_backup_bytes()
        if len(sqlite_bytes) + bundle_bytes > MAX_ARCHIVE_CONTENT_BYTES:
            raise ContinuityError(
                "El contenido del respaldo supera el presupuesto de 256 MiB"
            )
        payload = {
            "schema": "aiswe-continuity-v1",
            "owner": self.owner,
            "profile_name": self.profile_name,
            "exported_at": datetime.now(UTC).isoformat(),
            "sqlite_sha256": hashlib.sha256(sqlite_bytes).hexdigest(),
            "sqlite_size": len(sqlite_bytes),
            "sqlite_b64": _encode(sqlite_bytes),
            "repositories": bundles,
        }
        return json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")

    def export_archive(self, password: str, *, active_runs: int = 0) -> bytes:
        payload_bytes = self._build_payload_bytes(active_runs=active_runs)
        try:
            dek = os.urandom(32)
            header = wrap_key(self.owner, password, dek)
            ciphertext = seal(dek, payload_bytes, _aad(self.owner, "continuity-backup"))
        except VaultError as exc:
            raise ContinuityError(str(exc)) from exc
        envelope = {
            "format": ARCHIVE_FORMAT,
            "version": ARCHIVE_VERSION,
            "owner": self.owner,
            "profile_name": self.profile_name,
            "created_at": datetime.now(UTC).isoformat(),
            "header": header,
            "ciphertext": _encode(ciphertext),
        }
        return json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode("utf-8")

    def export_with_profile_key(
        self, key: bytes, header: dict, *, active_runs: int = 0
    ) -> bytes:
        payload_bytes = self._build_payload_bytes(active_runs=active_runs)
        try:
            ciphertext = seal(key, payload_bytes, _aad(self.owner, "continuity-backup"))
        except VaultError as exc:
            raise ContinuityError(str(exc)) from exc
        envelope = {
            "format": ARCHIVE_FORMAT,
            "version": ARCHIVE_VERSION,
            "owner": self.owner,
            "profile_name": self.profile_name,
            "created_at": datetime.now(UTC).isoformat(),
            "header": header,
            "ciphertext": _encode(ciphertext),
        }
        return json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode("utf-8")

    def export_to_file(
        self, path: str | Path, password: str, *, active_runs: int = 0
    ) -> Path:
        target = Path(path)
        if _is_link(target):
            raise ContinuityError("El destino de exportacion no puede ser un enlace")
        archive_bytes = self.export_archive(password, active_runs=active_runs)
        _atomic_write_bytes(target, archive_bytes)
        return target

    def set_credentials(
        self,
        key: bytes | None = None,
        header: dict | None = None,
        password: str | None = None,
    ) -> None:
        """Configura credenciales para auto-respaldo silencioso en el ciclo de vida."""
        self._profile_key = key
        self._profile_header = header
        self._password = password

    def auto_backup(
        self,
        password: str | None = None,
        *,
        profile_key: bytes | None = None,
        profile_header: dict | None = None,
        active_runs: int = 0,
    ) -> Path | None:
        cfg = self.backup_status()
        if not cfg["enabled"] or not cfg["backup_dir"]:
            return None
        if self._has_inflight_runs(active_runs):
            with self.connection() as con:
                con.execute(
                    "UPDATE continuity_config SET deferred=1, last_backup_status='deferred' WHERE owner=?",
                    (self.owner,),
                )
            return None

        eff_pwd = password if password is not None else self._password
        eff_key = profile_key if profile_key is not None else self._profile_key
        eff_hdr = profile_header if profile_header is not None else self._profile_header

        backup_dir = Path(cfg["backup_dir"])
        try:
            if _is_link(backup_dir):
                raise ContinuityError("La carpeta de auto-respaldo es un enlace no permitido")
            backup_dir.mkdir(parents=True, exist_ok=True)
            if eff_pwd is not None:
                archive_bytes = self.export_archive(eff_pwd, active_runs=0)
            elif eff_key is not None and eff_hdr is not None:
                archive_bytes = self.export_with_profile_key(
                    eff_key, eff_hdr, active_runs=0
                )
            else:
                return None

            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            filename = f"aiswe-{self.owner[:8]}-{stamp}-{uuid.uuid4().hex[:8]}.aiswe-vault"
            dest = backup_dir / filename
            _atomic_write_bytes(dest, archive_bytes)
            now = datetime.now(UTC).isoformat()
            with self.connection() as con:
                con.execute(
                    """
                    UPDATE continuity_config SET
                        deferred=0,
                        last_backup_path=?,
                        last_backup_at=?,
                        last_backup_status='completed',
                        last_backup_error=NULL
                    WHERE owner=?
                    """,
                    (str(dest), now, self.owner),
                )
            return dest
        except Exception as exc:
            msg = str(exc)[:500]
            with self.connection() as con:
                con.execute(
                    """
                    UPDATE continuity_config SET
                        last_backup_status='error',
                        last_backup_error=?
                    WHERE owner=?
                    """,
                    (msg, self.owner),
                )
            raise ContinuityError(f"Fallo en auto-respaldo: {msg}") from exc

    # ------------------------------------------------- 4. Importacion y Rebind
    @staticmethod
    def _open_archive_bytes(archive_bytes: bytes, password: str) -> dict:
        if not archive_bytes or len(archive_bytes) > MAX_ARCHIVE_CONTENT_BYTES * 2:
            raise ContinuityError("Archivo de respaldo vacio o demasiado grande")
        try:
            outer = json.loads(archive_bytes.decode("utf-8"))
        except Exception as exc:
            raise ContinuityError("Formato de respaldo corrupto o invalido") from exc
        if (
            not isinstance(outer, dict)
            or outer.get("format") != ARCHIVE_FORMAT
            or outer.get("version") != ARCHIVE_VERSION
            or not isinstance(outer.get("owner"), str)
            or not isinstance(outer.get("header"), dict)
            or not isinstance(outer.get("ciphertext"), str)
        ):
            raise ContinuityError("Cabecera de respaldo invalida o version no soportada")

        source_owner = outer["owner"]
        try:
            dek = unwrap_key(source_owner, password, outer["header"])
            plaintext = open_sealed(
                dek,
                _decode(outer["ciphertext"]),
                _aad(source_owner, "continuity-backup"),
            )
            payload = json.loads(plaintext.decode("utf-8"))
        except (VaultError, ValueError, KeyError, TypeError) as exc:
            raise ContinuityError("Contraseña incorrecta o respaldo alterado") from exc

        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "aiswe-continuity-v1"
            or payload.get("owner") != source_owner
            or not isinstance(payload.get("sqlite_b64"), str)
            or not isinstance(payload.get("sqlite_sha256"), str)
            or not isinstance(payload.get("sqlite_size"), int)
            or not isinstance(payload.get("repositories"), list)
        ):
            raise ContinuityError("Estructura interna del respaldo invalida")

        try:
            sqlite_bytes = _decode(payload["sqlite_b64"])
        except Exception as exc:
            raise ContinuityError("Base de datos del respaldo corrupta") from exc

        if (
            len(sqlite_bytes) != payload["sqlite_size"]
            or len(sqlite_bytes) > MAX_ARCHIVE_CONTENT_BYTES
            or hashlib.sha256(sqlite_bytes).hexdigest() != payload["sqlite_sha256"]
        ):
            raise ContinuityError("El hash o tamaño de la base SQLite no coincide")

        payload["_sqlite_bytes"] = sqlite_bytes
        return payload

    @staticmethod
    def _prepare_repository(
        bundle_info: dict, target_repo: Path
    ) -> Path:
        if _is_link(target_repo):
            raise ContinuityError(f"La ruta de repositorio '{target_repo}' es un enlace no permitido")
        for parent in target_repo.parents:
            if parent.exists() and _is_link(parent):
                raise ContinuityError("Un directorio padre del repositorio es un enlace no permitido")

        bundle_bytes = _decode(bundle_info["bundle_b64"])
        if (
            len(bundle_bytes) != int(bundle_info["bundle_size"])
            or hashlib.sha256(bundle_bytes).hexdigest() != bundle_info["bundle_sha256"]
        ):
            raise ContinuityError("El paquete de objetos Git del respaldo esta dañado")

        head_sha = bundle_info["head_sha"]
        base_commits = bundle_info.get("base_commits") or [head_sha]

        if not target_repo.exists() or (
            target_repo.is_dir() and not any(target_repo.iterdir())
        ):
            target_repo.mkdir(parents=True, exist_ok=True)
            resolved = target_repo.resolve()
            _git(resolved, "init", "-q")
            with tempfile.TemporaryDirectory(prefix="aiswe-unbundle-") as tmpdir:
                bundle_file = Path(tmpdir) / "repo.bundle"
                bundle_file.write_bytes(bundle_bytes)
                _git(resolved, "bundle", "unbundle", str(bundle_file))
            for sha in base_commits:
                _git(resolved, "cat-file", "-e", f"{sha}^{{commit}}")
            _git(resolved, "update-ref", "refs/heads/main", head_sha)
            _git(resolved, "symbolic-ref", "HEAD", "refs/heads/main")
            _git(resolved, "-c", "core.autocrlf=false", "checkout", "-f", head_sha)
            return resolved

        if not target_repo.is_dir():
            raise ContinuityError(f"El destino '{target_repo}' no es un directorio")
        resolved = target_repo.resolve()
        if not (resolved / ".git").exists():
            raise ContinuityError(
                f"El directorio destino '{resolved}' no esta vacio y no es un repositorio Git"
            )
        actual_top = Path(
            _git(resolved, "rev-parse", "--show-toplevel").decode("utf-8").strip()
        ).resolve()
        if actual_top != resolved:
            raise ContinuityError("La ruta autorizada no es la raiz del repositorio Git")
        status_out = _git(resolved, "status", "--porcelain", "--untracked-files=normal").strip()
        if status_out:
            raise ContinuityError(
                "El repositorio existente tiene cambios sin confirmar; no se fuerza ni sobrescribe"
            )
        for sha in base_commits:
            try:
                _git(resolved, "cat-file", "-e", f"{sha}^{{commit}}")
            except ContinuityError as exc:
                raise ContinuityError(
                    f"Faltan objetos Git para la base '{sha[:12]}' en el repositorio existente"
                ) from exc
        current_head = _git(resolved, "rev-parse", "HEAD").decode("utf-8").strip()
        if current_head != head_sha:
            raise ContinuityError(
                "El HEAD del repositorio existente no coincide con la base del respaldo"
            )
        return resolved

    def import_archive(
        self,
        archive_bytes: bytes,
        password: str,
        *,
        repo_mapping: dict[str, str | Path] | None = None,
        worktrees_root: str | Path | None = None,
    ) -> dict:
        payload = self._open_archive_bytes(archive_bytes, password)
        sqlite_bytes: bytes = payload["_sqlite_bytes"]
        wt_root = Path(worktrees_root or self.worktrees_root)
        if _is_link(wt_root):
            raise ContinuityError("La raiz de worktrees no puede ser un enlace")
        wt_root.mkdir(parents=True, exist_ok=True)
        wt_root_resolved = wt_root.resolve()

        with tempfile.TemporaryDirectory(prefix="aiswe-import-") as tmpdir:
            staged_db = Path(tmpdir) / "staged.sqlite3"
            staged_db.write_bytes(sqlite_bytes)

            try:
                with _sqlite_conn(staged_db) as con:
                    integrity = con.execute("PRAGMA integrity_check").fetchone()
                    if not integrity or integrity[0] != "ok":
                        raise ContinuityError("La base SQLite del respaldo no supero integrity_check")
                    tables = {
                        r["name"]
                        for r in con.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                    }
                    if not {"runs", "checkpoints", "writes"}.issubset(tables):
                        raise ContinuityError("La base SQLite del respaldo no contiene las tablas requeridas")
            except sqlite3.Error as exc:
                raise ContinuityError(f"Base SQLite invalida en el respaldo: {exc}") from exc

            # Check existing target database safety: never overwrite existing runs or roll back ledger spend
            if self.database.exists():
                with self.connection() as dest_con:
                    dest_tables = {
                        r["name"]
                        for r in dest_con.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                    }
                    if "runs" in dest_tables:
                        existing_runs = dest_con.execute("SELECT count(*) FROM runs").fetchone()[0]
                        if existing_runs > 0:
                            raise ContinuityError(
                                "El perfil destino ya tiene ejecuciones; no se sobrescribe un perfil en uso"
                            )
                    if "budget_reservations" in dest_tables:
                        dest_spent = dest_con.execute(
                            "SELECT COALESCE(SUM(COALESCE(consumed,reserved)),0) FROM budget_reservations"
                        ).fetchone()[0]
                        with _sqlite_conn(staged_db) as src_con:
                            src_tables = {
                                r[0]
                                for r in src_con.execute(
                                    "SELECT name FROM sqlite_master WHERE type='table'"
                                ).fetchall()
                            }
                            src_spent = (
                                src_con.execute(
                                    "SELECT COALESCE(SUM(COALESCE(consumed,reserved)),0) FROM budget_reservations"
                                ).fetchone()[0]
                                if "budget_reservations" in src_tables
                                else 0.0
                            )
                        if dest_spent > src_spent:
                            raise ContinuityError(
                                "No se permite importar un ledger con menor gasto acumulado"
                            )

            # Resolve repository mapping
            raw_mapping = repo_mapping or {}
            normalized_mapping: dict[str, Path] = {}
            for k, v in raw_mapping.items():
                dest_path = Path(v)
                if _is_link(dest_path):
                    raise ContinuityError(f"Ruta de repositorio enlazada no permitida: '{dest_path}'")
                normalized_mapping[k] = dest_path
                try:
                    normalized_mapping[str(Path(k).resolve())] = dest_path
                except OSError:
                    pass

            authorized_targets: dict[str, Path] = {}
            for bundle_info in payload["repositories"]:
                old_repo = bundle_info["repo_path"]
                target_repo = normalized_mapping.get(old_repo)
                if target_repo is None and len(payload["repositories"]) == 1 and len(raw_mapping) == 1:
                    target_repo = Path(next(iter(raw_mapping.values())))
                if target_repo is None:
                    raise ContinuityError(
                        f"Debes autorizar una ruta local para el repositorio '{old_repo}'"
                    )
                if not target_repo.is_absolute():
                    raise ContinuityError("Autoriza una ruta absoluta para cada repositorio")
                if any(_is_link(p) for p in [target_repo, *target_repo.parents]):
                    raise ContinuityError("No se permiten enlaces en las carpetas autorizadas")
                resolved = target_repo.resolve()
                for previous in [wt_root_resolved, *authorized_targets.values()]:
                    if (resolved == previous or resolved in previous.parents
                            or previous in resolved.parents):
                        raise ContinuityError(
                            "Los repositorios y worktrees deben usar carpetas separadas "
                            "sin solaparse"
                        )
                authorized_targets[old_repo] = resolved

            resolved_repo_map: dict[str, str] = {}
            for bundle_info in payload["repositories"]:
                old_repo = bundle_info["repo_path"]
                target_repo = authorized_targets[old_repo]
                prepared_repo = self._prepare_repository(bundle_info, target_repo)
                if prepared_repo == wt_root_resolved or prepared_repo in wt_root_resolved.parents or wt_root_resolved in prepared_repo.parents:
                    raise ContinuityError("El repositorio autorizado y los worktrees deben estar en directorios separados")
                resolved_repo_map[old_repo] = str(prepared_repo)

            def map_repo(path_str: str | None) -> str | None:
                if not path_str:
                    return path_str
                if path_str in resolved_repo_map:
                    return resolved_repo_map[path_str]
                try:
                    res = str(Path(path_str).resolve())
                    if res in resolved_repo_map:
                        return resolved_repo_map[res]
                except OSError:
                    pass
                if path_str in normalized_mapping:
                    return str(normalized_mapping[path_str].resolve())
                if len(resolved_repo_map) == 1:
                    return next(iter(resolved_repo_map.values()))
                raise ContinuityError(f"Repositorio no autorizado en la importacion: '{path_str}'")

            # Reconstruct worktrees for all snapshots in staged_db
            worktree_map: dict[str, str] = {}
            staged_continuity = ContinuityStore(
                staged_db, payload["owner"], worktrees_root=wt_root_resolved
            )
            with staged_continuity.connection() as con:
                snap_rows = con.execute("SELECT * FROM worktree_snapshots").fetchall()
                run_statuses = {
                    r["run_id"]: r["status"]
                    for r in con.execute("SELECT run_id, status FROM runs").fetchall()
                }
            for srow in snap_rows:
                rid = srow["run_id"]
                status = run_statuses.get(rid, "")
                if status in {"completed", "failed", "needs_human", "cancelled"}:
                    continue
                new_repo_str = map_repo(srow["repo_path"])
                assert new_repo_str is not None
                snap_dict = {
                    "owner": srow["owner"],
                    "run_id": rid,
                    "repo_path": srow["repo_path"],
                    "worktree_path": srow["worktree_path"],
                    "base_commit_sha": srow["base_commit_sha"],
                    "binary_diff_b64": srow["binary_diff_b64"],
                    "inventory": json.loads(srow["inventory_json"]),
                    "updated_at": srow["updated_at"],
                }
                new_wt = staged_continuity.reconstruct_worktree(
                    rid, new_repo_str, wt_root_resolved, snapshot=snap_dict
                )
                worktree_map[rid] = str(new_wt)

            # Rebind paths in staged_db without touching run IDs, pending gates, approvals, or budgets
            self._rebind_sqlite_database(
                staged_db,
                target_owner=self.owner,
                map_repo=map_repo,
                worktree_map=worktree_map,
            )

            # Copy staged_db into self.database using SQLite Backup API
            with _sqlite_conn(staged_db) as src_con:
                with _sqlite_conn(self.database, timeout=30) as dst_con:
                    src_con.backup(dst_con)

        with self.connection() as con:
            restored_runs = [
                {"run_id": r["run_id"], "status": r["status"]}
                for r in con.execute("SELECT run_id, status FROM runs ORDER BY updated_at DESC").fetchall()
            ]
        return {
            "restored_runs": restored_runs,
            "rebound_repositories": resolved_repo_map,
            "reconstructed_worktrees": worktree_map,
        }

    @staticmethod
    def _rebind_sqlite_database(
        db_path: Path,
        *,
        target_owner: str,
        map_repo,
        worktree_map: dict[str, str],
    ) -> None:
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
        from ai_swe.state.store import msgpack_allowlist

        serde = JsonPlusSerializer(allowed_msgpack_modules=list(msgpack_allowlist()))

        def rebind_value(thread_id: str, channel: str, val):
            if val is None:
                return val
            if channel == "options":
                if hasattr(val, "repo_path") and val.repo_path:
                    return val.model_copy(update={"repo_path": map_repo(val.repo_path)})
                if isinstance(val, dict) and val.get("repo_path"):
                    return {**val, "repo_path": map_repo(val["repo_path"])}
            elif channel == "interpretation":
                if hasattr(val, "scope") and val.scope and val.scope.repo_path:
                    new_scope = val.scope.model_copy(
                        update={"repo_path": map_repo(val.scope.repo_path)}
                    )
                    return val.model_copy(update={"scope": new_scope})
                if isinstance(val, dict) and isinstance(val.get("scope"), dict) and val["scope"].get("repo_path"):
                    return {
                        **val,
                        "scope": {
                            **val["scope"],
                            "repo_path": map_repo(val["scope"]["repo_path"]),
                        },
                    }
            elif channel == "artifacts" and thread_id in worktree_map:
                if hasattr(val, "worktree_path") and val.worktree_path:
                    return val.model_copy(update={"worktree_path": worktree_map[thread_id]})
                if isinstance(val, dict) and val.get("worktree_path"):
                    return {**val, "worktree_path": worktree_map[thread_id]}
            return val

        with _sqlite_conn(db_path) as con:
            tables = {
                r["name"]
                for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }

            if "projects" in tables:
                for row in con.execute("SELECT project_id, repo_path FROM projects").fetchall():
                    con.execute(
                        "UPDATE projects SET repo_path=? WHERE project_id=?",
                        (map_repo(row["repo_path"]), row["project_id"]),
                    )

            if "memory_documents" in tables:
                for row in con.execute("SELECT id, repository FROM memory_documents").fetchall():
                    con.execute(
                        "UPDATE memory_documents SET owner=?, repository=? WHERE id=?",
                        (target_owner, map_repo(row["repository"]), row["id"]),
                    )

            if "promotion_receipts" in tables:
                for row in con.execute("SELECT receipt_id, root FROM promotion_receipts").fetchall():
                    new_root = map_repo(row["root"])
                    new_git_dir = (
                        _git(Path(new_root), "rev-parse", "--absolute-git-dir")
                        .decode("utf-8")
                        .strip()
                        if new_root and (Path(new_root) / ".git").exists()
                        else row["root"]
                    )
                    con.execute(
                        "UPDATE promotion_receipts SET owner=?, root=?, git_dir=? WHERE receipt_id=?",
                        (target_owner, new_root, new_git_dir, row["receipt_id"]),
                    )

            if "worktree_snapshots" in tables:
                for row in con.execute("SELECT owner, run_id, repo_path, worktree_path FROM worktree_snapshots").fetchall():
                    rid = row["run_id"]
                    con.execute(
                        "UPDATE worktree_snapshots SET owner=?, repo_path=?, worktree_path=? WHERE owner=? AND run_id=?",
                        (
                            target_owner,
                            map_repo(row["repo_path"]),
                            worktree_map.get(rid, row["worktree_path"]),
                            row["owner"],
                            rid,
                        ),
                    )

            if " continuity_config" in tables or "continuity_config" in tables:
                con.execute("DELETE FROM continuity_config")

            if "runs" in tables:
                for row in con.execute("SELECT run_id, state_json FROM runs").fetchall():
                    rid = row["run_id"]
                    state_dict = json.loads(row["state_json"])
                    if isinstance(state_dict.get("options"), dict) and state_dict["options"].get("repo_path"):
                        state_dict["options"]["repo_path"] = map_repo(state_dict["options"]["repo_path"])
                    if (
                        isinstance(state_dict.get("interpretation"), dict)
                        and isinstance(state_dict["interpretation"].get("scope"), dict)
                        and state_dict["interpretation"]["scope"].get("repo_path")
                    ):
                        state_dict["interpretation"]["scope"]["repo_path"] = map_repo(
                            state_dict["interpretation"]["scope"]["repo_path"]
                        )
                    if (
                        isinstance(state_dict.get("artifacts"), dict)
                        and state_dict["artifacts"].get("worktree_path")
                        and rid in worktree_map
                    ):
                        state_dict["artifacts"]["worktree_path"] = worktree_map[rid]
                    validated = RunState.model_validate(state_dict)
                    con.execute(
                        "UPDATE runs SET state_json=? WHERE run_id=?",
                        (validated.model_dump_json(), rid),
                    )

            if "checkpoints" in tables:
                cp_rows = con.execute(
                    "SELECT thread_id, checkpoint_ns, checkpoint_id, type, checkpoint FROM checkpoints"
                ).fetchall()
                for row in cp_rows:
                    tid = row["thread_id"]
                    cp_obj = serde.loads_typed((row["type"], row["checkpoint"]))
                    if isinstance(cp_obj, dict) and isinstance(cp_obj.get("channel_values"), dict):
                        cv = cp_obj["channel_values"]
                        for ch in ("options", "interpretation", "artifacts"):
                            if ch in cv:
                                cv[ch] = rebind_value(tid, ch, cv[ch])
                        new_type, new_blob = serde.dumps_typed(cp_obj)
                        con.execute(
                            """
                            UPDATE checkpoints SET type=?, checkpoint=?
                            WHERE thread_id=? AND checkpoint_ns=? AND checkpoint_id=?
                            """,
                            (
                                new_type,
                                new_blob,
                                tid,
                                row["checkpoint_ns"],
                                row["checkpoint_id"],
                            ),
                        )

            if "writes" in tables:
                w_rows = con.execute(
                    """
                    SELECT thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value
                    FROM writes WHERE channel IN ('options', 'interpretation', 'artifacts')
                    """
                ).fetchall()
                for row in w_rows:
                    tid = row["thread_id"]
                    ch = row["channel"]
                    val_obj = serde.loads_typed((row["type"], row["value"]))
                    new_val = rebind_value(tid, ch, val_obj)
                    new_type, new_blob = serde.dumps_typed(new_val)
                    con.execute(
                        """
                        UPDATE writes SET type=?, value=?
                        WHERE thread_id=? AND checkpoint_ns=? AND checkpoint_id=? AND task_id=? AND idx=?
                        """,
                        (
                            new_type,
                            new_blob,
                            tid,
                            row["checkpoint_ns"],
                            row["checkpoint_id"],
                            row["task_id"],
                            row["idx"],
                        ),
                    )


def import_vault_to_profile(
    profile_store,
    archive_bytes: bytes,
    archive_password: str,
    *,
    new_name: str | None = None,
    new_password: str | None = None,
    repo_mapping: dict[str, str | Path],
    conflict_strategy: str = "error",
):
    """Restaura un archivo .aiswe-vault creando un perfil nuevo sin sobrescribir perfiles existentes."""
    payload = ContinuityStore._open_archive_bytes(archive_bytes, archive_password)
    target_name = new_name or payload.get("profile_name") or "restored"
    target_password = new_password or archive_password

    if conflict_strategy == "rename" and hasattr(profile_store, "_find"):
        base_name = target_name
        counter = 1
        while profile_store._find(target_name) is not None:
            target_name = f"{base_name}-restored" if counter == 1 else f"{base_name}-restored-{counter}"
            counter += 1

    try:
        profile = profile_store.create(target_name, target_password)
    except ValueError as exc:
        raise ContinuityError(f"No se puede crear el perfil de destino: {exc}") from exc

    continuity = ContinuityStore(
        profile.paths.database,
        profile.user_id,
        profile_name=profile.name,
        worktrees_root=profile.paths.worktrees,
    )
    try:
        continuity.import_archive(
            archive_bytes,
            archive_password,
            repo_mapping=repo_mapping,
            worktrees_root=profile.paths.worktrees,
        )
    except Exception:
        profile_store.rollback_creation(profile)
        raise
    return profile
