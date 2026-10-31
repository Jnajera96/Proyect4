"""Offline maintenance: stop the app, snapshot user data, stage upgrades, then publish."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

from ai_swe.runtime_paths import user_paths
from ai_swe.state.migrations import MigrationError, SchemaMigrator
from ai_swe.state.operation_lock import operation_lock
from ai_swe.state.upgrade_recovery import journal_path, recover_upgrade, write_journal


class UpgradeError(RuntimeError):
    pass


def _bundle(root):
    matches = [
        p
        for p in (root, root / "AISWESystem", root / "dist/AISWESystem")
        if (p / "runtime/python.exe").is_file() and (p / "start.py").is_file()
    ]
    if len(matches) != 1:
        raise UpgradeError("Selecciona una distribucion signed-python completa y no ambigua")
    return matches[0]


def assert_server_stopped(source, target):
    """Legacy packages have no lease: inspect command lines locally and fail closed."""
    if os.name == "nt":
        powershell = (
            Path(os.environ["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        result = subprocess.run(
            [
                str(powershell),
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-CimInstance Win32_Process -ErrorAction Stop | "
                "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        processes = json.loads(result.stdout or "[]")
        if isinstance(processes, dict):
            processes = [processes]
        for process in processes:
            name = (process.get("Name") or "").lower()
            command = (process.get("CommandLine") or "").lower()
            if name.startswith("python") and not command:
                raise UpgradeError(
                    "No se pudo inspeccionar un proceso Python; cierra la aplicacion"
                )
            if name == "aiswesystem.exe" or (
                name.startswith(("python", "uvicorn"))
                and any(
                    token in command
                    for token in (
                        "start.py",
                        "ai_swe.api",
                        "ai_swe.launcher",
                        "ai_swe.__main__",
                        " -m ai_swe",
                    )
                )
            ):
                raise UpgradeError("El servidor esta en ejecucion; cierralo antes de actualizar")
    else:
        # shortcut: legacy process discovery is Windows-only; the portable targets Windows.
        raise UpgradeError("El preflight de procesos requiere Windows")


def _safe_tree(root):
    for path in [root, *root.rglob("*")] if root.is_dir() else [root]:
        if path.is_symlink() or path.is_junction():
            raise UpgradeError("No se actualizan datos mediante enlaces o uniones")


def _payload(root):
    names = {"userdata", "data", "users", "config", "var", "logs", "worktrees", ".env"}
    return [p for p in root.iterdir() if p.name in names or p.suffix == ".aiswe-vault"]


def _databases(copied, root_name):
    if not copied.is_dir():
        return []
    result = []
    for path in copied.rglob("state.sqlite3"):
        parts = path.relative_to(copied).parts
        if root_name in {"users", "data", "var"}:
            parts = (root_name, *parts)
        if parts[0] == "AISWESystem":
            parts = parts[1:]
        if (
            parts in (("state.sqlite3",), ("data", "state.sqlite3"), ("var", "state.sqlite3"))
            or (len(parts) == 3 and parts[0] == "users")
            or (len(parts) == 4 and parts[:2] == ("data", "users"))
        ):
            result.append(path)
    return result


def upgrade(
    source: Path,
    target: Path,
    *,
    backup_dir: Path | None = None,
    data_dir: Path | None = None,
    dry_run: bool = False,
) -> dict:
    source, target = source.resolve(), target.resolve()
    if not source.is_dir() or not target.is_dir():
        raise UpgradeError("Las dos instalaciones deben existir")
    if source.is_relative_to(target) or target.is_relative_to(source):
        raise UpgradeError("Origen y destino deben ser directorios separados")
    old_bundle, new_bundle = _bundle(source), _bundle(target)
    _safe_tree(old_bundle)
    _safe_tree(new_bundle)
    local = [(item, target / item.relative_to(source)) for item in _payload(source)]
    if old_bundle != source:
        local += [
            (item, new_bundle / item.relative_to(old_bundle)) for item in _payload(old_bundle)
        ]
    external = (data_dir or user_paths().root).resolve()
    if external.exists() and any(
        external.is_relative_to(p) or p.is_relative_to(external) for p in (source, target)
    ):
        raise UpgradeError("Los datos instalados deben estar fuera de ambos paquetes")
    if any(destination.exists() for _, destination in local):
        raise UpgradeError(
            "El destino ya contiene datos; no se sobrescriben perfiles o configuraciones"
        )
    for item, _ in local:
        _safe_tree(item)
    if external.exists():
        _safe_tree(external)
    backup_dir = (backup_dir or target.parent / "upgrade-backups").resolve()
    if any(backup_dir.is_relative_to(p) for p in (source, target, external)):
        raise UpgradeError("El respaldo debe estar fuera de instalaciones y datos")
    runtime_hashes = {
        p: hashlib.sha256(p.read_bytes()).hexdigest() for p in new_bundle.rglob("*") if p.is_file()
    }
    assert_server_stopped(source, target)
    token = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid.uuid4().hex[:8]
    backup = None
    published = []
    previous_external = external.with_name(external.name + ".pre-upgrade-" + token)
    external_replaced = False
    with ExitStack() as leases:
        for path in sorted(
            {
                source.parent / f".{source.name}.upgrade.lock",
                target.parent / f".{target.name}.upgrade.lock",
                user_paths().root.parent / f".{user_paths().root.name}.server.lock",
                external.parent / f".{external.name}.server.lock",
            }
        ):
            leases.enter_context(operation_lock(path))
        assert_server_stopped(source, target)
        if dry_run and journal_path(external).exists():
            raise UpgradeError(
                "Hay una actualizacion interrumpida; recupera los datos antes del dry-run"
            )
        if not dry_run:
            recover_upgrade(external)
        with tempfile.TemporaryDirectory(prefix="aiswe-upgrade-", dir=target.parent) as temporary:
            stage = Path(temporary)
            copies = []
            for index, (item, destination) in enumerate(local):
                copied = stage / str(index)
                if item.is_dir():
                    shutil.copytree(item, copied)
                else:
                    shutil.copy2(item, copied)
                copies.append((item, copied, destination))
            staged_external = stage / "installed"
            if external.exists():
                external_stage = Path(
                    leases.enter_context(
                        tempfile.TemporaryDirectory(prefix=".aiswe-upgrade-", dir=external.parent)
                    )
                )
                staged_external = external_stage / "installed"
                shutil.copytree(external, staged_external)
                copies.append((external, staged_external, external))
            if not dry_run:
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup = backup_dir / f"aiswe_userdata_backup_{token}.zip"
                with backup.open("xb") as stream:
                    os.chmod(backup, 0o600)
                    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                        for index, (original, copied, _) in enumerate(copies):
                            paths = list(copied.rglob("*")) if copied.is_dir() else [copied]
                            for path in paths:
                                if path.is_file() and not path.name.endswith(".lock"):
                                    relative = (
                                        path.relative_to(copied)
                                        if copied.is_dir()
                                        else Path(original.name)
                                    )
                                    archive.write(path, f"{index}/{relative.as_posix()}")
                        archive.writestr(
                            "upgrade-backup-manifest.json",
                            json.dumps(
                                [
                                    {
                                        "entry": str(i),
                                        "original": str(original),
                                        "target": str(destination),
                                        "directory": copied.is_dir(),
                                    }
                                    for i, (original, copied, destination) in enumerate(copies)
                                ],
                                indent=2,
                            ),
                        )
                    stream.flush()
                    os.fsync(stream.fileno())
                with zipfile.ZipFile(backup) as archive:
                    if archive.testzip() is not None:
                        raise UpgradeError(
                            "El respaldo ZIP no supera CRC; no se aplica la actualizacion"
                        )
            databases = [
                p for original, copied, _ in copies for p in _databases(copied, original.name)
            ]
            for database in databases:
                SchemaMigrator().migrate_database(database)
            try:
                if not dry_run:
                    for _, copied, destination in copies:
                        if destination == external:
                            write_journal(external, previous_external, "prepared")
                            os.replace(external, previous_external)
                            external_replaced = True
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(copied, destination)
                        published.append((destination, copied))
                if any(
                    hashlib.sha256(p.read_bytes()).hexdigest() != digest
                    for p, digest in runtime_hashes.items()
                ):
                    raise UpgradeError("Cambio inesperado en el paquete de destino")
                if external_replaced:
                    write_journal(external, previous_external, "committed")
                    journal_path(external).unlink()
            except Exception:
                for destination, copied in reversed(published):
                    os.replace(destination, copied)
                if external_replaced:
                    os.replace(previous_external, external)
                if journal_path(external).exists():
                    recover_upgrade(external)
                raise
    return {
        "success": True,
        "dry_run": dry_run,
        "databases": len(databases),
        "backup": str(backup) if backup else None,
        "previous_data": str(previous_external) if external_replaced else None,
        "source_unchanged": True,
        "runtime_unchanged": True,
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", "--source-dir", type=Path, required=True)
    parser.add_argument("--target", "--target-dir", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument(
        "--data-dir", type=Path, help="Datos externos; por defecto LOCALAPPDATA/AISWESystem"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                upgrade(
                    args.source,
                    args.target,
                    backup_dir=args.backup_dir,
                    data_dir=args.data_dir,
                    dry_run=args.dry_run,
                ),
                indent=2,
            )
        )
        return 0
    except (UpgradeError, MigrationError) as exc:
        print(f"Actualizacion abortada: {exc}")
        return 1
    except (OSError, subprocess.SubprocessError, ValueError):
        print(
            "Actualizacion abortada. Conserva el respaldo y cierra el servidor antes de reintentar."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
