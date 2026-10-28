"""Explicit, local-only bootstrap of a new Git project."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

from ai_swe.config import Settings, repositorio_autorizado
from ai_swe.sandbox import SandboxError


def _checked_path(raw: str, settings: Settings) -> Path:
    path = Path(raw)
    components = path.parts[1:] if path.anchor else path.parts
    if any(part.rstrip(" .").casefold() == ".git" for part in components):
        raise SandboxError("crear_proyecto", "La ruta no puede estar dentro de metadatos .git.")
    if any(part.endswith((".", " ")) or ":" in part for part in components):
        raise SandboxError("crear_proyecto", "La ruta contiene componentes locales ambiguos.")
    if not path.is_absolute() or ".." in path.parts or raw.startswith(("\\\\", "//")):
        raise SandboxError("crear_proyecto", "Indica una ruta local absoluta, sin enlaces ni '..'.")
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise SandboxError(
                "crear_proyecto", "No se permiten enlaces o junctions en la ruta del proyecto."
            )
    path = path.resolve()
    if any(part.rstrip(" .").casefold() == ".git" for part in path.parts):
        raise SandboxError("crear_proyecto", "La ruta no puede estar dentro de metadatos .git.")
    private_roots = [
        settings.profiles_root or settings.state_db_path.parent / "users",
        settings.workspace_root,
        settings.state_db_path.parent,
        *[
            p
            for p in (settings.log_dir, settings.cache_dir, settings.stt_download_root)
            if p is not None
        ],
    ]
    if any(
        path == p.resolve() or p.resolve() in path.parents or path in p.resolve().parents
        for p in private_roots
    ):
        raise SandboxError(
            "crear_proyecto", "La ruta coincide con datos privados o internos del sistema."
        )
    if not repositorio_autorizado(settings, path):
        raise SandboxError("crear_proyecto", "La ruta queda fuera de AI_SWE_AUTHORIZED_REPOS.")
    if not path.parent.is_dir():
        raise SandboxError(
            "crear_proyecto",
            "La carpeta padre debe existir; elige una nueva carpeta dentro de ella.",
        )
    return path


def crear_proyecto_git(raw: str, name: str, settings: Settings) -> Path:
    """Create README and HEAD; preserve partial output on failure for inspection."""
    path = _checked_path(raw, settings)
    if shutil.which("git") is None:
        raise SandboxError("crear_proyecto", "Git no está instalado o no se encuentra en PATH.")
    # Exclusive directory creation prevents two requests from sharing a new target.
    # Existing empty directories use an exclusive claim and a second content check.
    try:
        path.mkdir()
    except FileExistsError:
        if not path.is_dir() or any(path.iterdir()):
            raise SandboxError(
                "crear_proyecto", "Nuevo proyecto requiere una carpeta nueva o vacía."
            ) from None
    claim = path / ".aiswe-bootstrap-lock"
    try:
        claim.mkdir()
    except FileExistsError:
        raise SandboxError(
            "crear_proyecto", "Ya hay una creación de proyecto en esta carpeta."
        ) from None
    try:
        _checked_path(raw, settings)
        if any(item != claim for item in path.iterdir()):
            raise SandboxError(
                "crear_proyecto", "La carpeta dejó de estar vacía; no se modificó su contenido."
            )
        env = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
        }
        env.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0",
            GIT_ATTR_NOSYSTEM="1",
        )

        def git(*args: str) -> None:
            result = subprocess.run(
                [
                    "git",
                    "-c",
                    "core.hooksPath=" + str(claim / "no-hooks"),
                    "-c",
                    "commit.gpgSign=false",
                    "-c",
                    "user.name=AI SWE",
                    "-c",
                    "user.email=ai-swe@localhost",
                    *args,
                ],
                cwd=path,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                shell=False,
                timeout=30,
            )
            if result.returncode:
                raise SandboxError(
                    "crear_proyecto",
                    "Git no pudo completar la creación; revisa la carpeta parcial.",
                )

        git("init", "--quiet", "--template=")
        with (path / "README.md").open("x", encoding="utf-8") as readme:
            readme.write(f"# {name.replace(chr(10), ' ').replace(chr(13), ' ')}\n\n")
        git("add", "--", "README.md")
        git("commit", "--quiet", "-m", "Initial project")
        git("rev-parse", "--verify", "HEAD")
        return path
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandboxError(
            "crear_proyecto", "No se completó la creación; revisa la carpeta parcial."
        ) from exc
    finally:
        # Only remove our own empty claim; never sweep a partially initialized repo.
        claim.rmdir()
