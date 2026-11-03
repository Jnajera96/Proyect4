"""Bounded read-only file boundary, shared by MCP and the local context graph."""

import os
import stat
from contextlib import ExitStack
from pathlib import Path

from ai_swe.security import redact
from ai_swe.state.memory_graph import usable_path
from ai_swe.tools.policy import DecisionContext, decide, normalize_rel_path, path_within_scope


def read_source(root, path, allowed_paths=()):
    relative = normalize_rel_path(path)
    if (
        not relative
        or ':' in relative
        or relative != path.replace("\\", "/")
        or not usable_path(relative)
        or any(
            p.startswith(".")
            or p.casefold() in {"secrets.json", "credentials.json"}
            or p.casefold().endswith((".pem", ".key", ".aiswe-vault"))
            for p in Path(relative).parts
        )
    ):
        raise ValueError("Ruta de lectura no permitida.")
    decision = decide(
        "read_file",
        {"path": relative},
        DecisionContext(run_id="mcp-read", agent="researcher", allowed_paths=tuple(allowed_paths)),
    )
    if decision.effect != "allow" or not path_within_scope(relative, tuple(allowed_paths)):
        raise ValueError("Lectura fuera del alcance autorizado.")
    root = Path(root).absolute()
    if root.resolve() != root or not root.is_dir():
        raise ValueError("La raíz de lectura debe ser una carpeta real autorizada.")
    target = root / relative
    with ExitStack() as stack:
        current = root
        for part in ("", *Path(relative).parts):
            current = current / part
            if os.name == "nt":
                from ai_swe.tools.execution_snapshot import _open_entry

                _, info, actual = stack.enter_context(_open_entry(current))
                if not actual.is_relative_to(root):
                    raise ValueError("La lectura escapó de la raíz autorizada.")
            elif current.is_symlink():
                raise ValueError("No se permiten enlaces en las lecturas.")
        metadata = target.stat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError("Solo se permiten archivos regulares sin enlaces duros.")
        with target.open("rb") as stream:
            raw = stream.read(32769)
    if b"\x00" in raw:
        raise ValueError("El archivo no es texto.")
    return {
        "path": relative,
        "text": redact(raw[:32768].decode("utf-8-sig", errors="replace")),
        "truncated": len(raw) > 32768,
    }
