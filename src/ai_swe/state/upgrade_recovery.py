"""Durable intent record for the installed-data directory switch; never delete data."""

import json
import logging
import os
import re
import uuid
from pathlib import Path

log = logging.getLogger(__name__)


def journal_path(root: Path) -> Path:
    return root.parent / f".{root.name}.upgrade-journal.json"


def write_journal(root: Path, previous: Path, state: str) -> None:
    journal = journal_path(root)
    temporary = journal.with_name(journal.name + "." + uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump({"state": state, "previous": previous.name}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, journal)
    finally:
        temporary.unlink(missing_ok=True)


def recover_upgrade(root: Path) -> bool:
    """Caller holds the server lease. Prepared -> rollback; committed -> keep new data."""
    journal = journal_path(root)
    if not journal.exists():
        return False
    if journal.is_symlink() or journal.is_junction():
        raise RuntimeError("Diario de actualizacion invalido")
    if journal.stat().st_size > 4096:
        raise RuntimeError("Diario de actualizacion demasiado grande")
    record = json.loads(journal.read_text(encoding="utf-8"))
    if (
        not isinstance(record, dict)
        or record.get("state") not in {"prepared", "committed"}
        or not isinstance(record.get("previous"), str)
        or not re.fullmatch(re.escape(root.name) + r"\.pre-upgrade-[0-9a-f-]+", record["previous"])
    ):
        raise RuntimeError("Diario de actualizacion invalido; no se mueve ningun dato")
    previous = root.parent / record["previous"]
    if any(p.is_symlink() or p.is_junction() for p in (root, previous)):
        raise RuntimeError("Ruta de recuperacion invalida")
    restored = False
    if record["state"] == "prepared" and previous.exists():
        if root.exists():
            quarantine = root.with_name(root.name + ".interrupted-" + uuid.uuid4().hex)
            os.replace(root, quarantine)
        os.replace(previous, root)
        restored = True
        log.warning("[Migraciones] Actualizacion interrumpida; datos anteriores restaurados")
    if not root.is_dir():
        raise RuntimeError("No se encuentran los datos; conserva el diario y el respaldo")
    journal.unlink()
    return restored
