"""Read-only application discovery and explicit, bounded Windows launcher preparation."""

from __future__ import annotations

import ast
import hashlib
import os
import re
import subprocess
import sys
import webbrowser
from pathlib import Path

from pydantic import BaseModel, Field

from ai_swe.contracts import RunState


class LaunchGuide(BaseModel):
    available: bool = False
    kind: str = "unknown"
    summary_es: str = "No hay una aplicación promovida lista para abrir."
    launch_action: str = "none"
    command: str = ""
    instructions: list[str] = Field(default_factory=list)
    repo_path: str = ""
    entrypoint: str = ""
    prepared: bool = False
    launcher_path: str = ""


def approved_repository(state: RunState) -> Path:
    receipt = state.promotion_receipt
    if state.status != "completed" or not receipt or receipt.status != "promoted":
        raise ValueError("Primero termina y aprueba una aplicación con archivos guardados.")
    root = Path(state.options.repo_path or "").resolve()
    if not state.options.repo_path or not root.is_dir():
        raise ValueError("La carpeta de la aplicación ya no está disponible.")
    for change in state.artifacts.changed_files:
        path = root / change.path
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("La aplicación contiene una ruta no autorizada.")
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if hashlib.sha256(text.encode()).hexdigest() != change.sha256:
                raise ValueError(
                    "Los archivos cambiaron después de la revisión. Revisa antes de abrir."
                )
    return root


def _python_kind(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value.func
            if (
                (
                    (isinstance(call, ast.Name) and call.id == "FastAPI")
                    or (isinstance(call, ast.Attribute) and call.attr == "FastAPI")
                )
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                return "fastapi", node.targets[0].id
        if isinstance(node, ast.If) and "__name__" in ast.unparse(node.test):
            return "python_cli", ""
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            return "python_cli", ""
    return "python_library", ""


def describe(state: RunState) -> LaunchGuide:
    root = approved_repository(state)
    paths = [f.path for f in state.artifacts.changed_files if (root / f.path).is_file()]
    html = sorted(p for p in paths if p.endswith(".html"))
    python = sorted(p for p in paths if p.endswith(".py") and not Path(p).name.startswith("test_"))
    entry = "index.html" if "index.html" in html else html[0] if html else ""
    kind, app_name = ("web_static", "") if entry else ("unknown", "")
    if not entry:
        for candidate in sorted(
            python, key=lambda p: (Path(p).name not in {"main.py", "app.py"}, p)
        ):
            try:
                detected, app_name = _python_kind(root / candidate)
            except (SyntaxError, UnicodeError):
                continue
            kind, entry = detected, candidate
            if kind != "python_library":
                break
    if not entry or kind in {"unknown", "python_library"}:
        return LaunchGuide(
            kind=kind,
            repo_path=str(root),
            summary_es="Se guardó una biblioteca de código, sin pantalla ni programa de inicio.",
            instructions=[
                "Puedes usar sus funciones desde otro programa.",
                "Pide una pantalla o un programa principal para abrirlo con doble clic.",
            ],
        )
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", entry) or ".." in Path(entry).parts:
        raise ValueError("El nombre del archivo de inicio necesita revisión.")
    runtime = str(Path(sys.executable).resolve())
    if any(char in runtime + str(root) for char in '%!&|<>^"\r\n'):
        raise ValueError("La ruta contiene caracteres incompatibles con el iniciador de Windows.")
    if kind == "web_static":
        command = f'start "" "%~dp0{entry.replace("/", chr(92))}"'
    elif kind == "fastapi":
        module = entry[:-3].replace("/", ".")
        if not all(part.isidentifier() for part in module.split(".")):
            raise ValueError("El módulo de la aplicación necesita un nombre válido.")
        code = (
            "import sys;sys.path.insert(0,'.');import uvicorn;"
            f"uvicorn.run('{module}:{app_name}',host='127.0.0.1',port=8765)"
        )
        command = f'"{runtime}" -c "{code}"'
    else:
        code = (
            "import sys,runpy;sys.path.insert(0,'.');"
            "runpy.run_path(sys.argv[1],run_name='__main__')"
        )
        command = f'"{runtime}" -c "{code}" "{entry}"'
    launcher = root / "iniciar.bat"
    guide = LaunchGuide(
        available=True,
        kind=kind,
        summary_es="Tu aplicación está lista para usar.",
        launch_action="open_browser" if kind == "web_static" else "run_command",
        command=command,
        repo_path=str(root),
        entrypoint=entry,
        launcher_path=str(launcher),
        instructions=[
            f"Tu aplicación está guardada en {root}.",
            "Abre iniciar.bat con doble clic para usarla otra vez.",
            "Conserva la carpeta completa y esta instalación del sistema.",
        ],
    )
    if kind == "fastapi":
        guide.instructions.append(
            "Abre http://127.0.0.1:8765 después de iniciar. Cierra la ventana para detenerla."
        )
    guide.prepared = (
        launcher.is_file()
        and not launcher.is_symlink()
        and launcher.read_bytes() == launcher_bytes(guide)
    )
    return guide


def launcher_bytes(guide: LaunchGuide) -> bytes:
    return (
        "@echo off\r\nsetlocal DisableDelayedExpansion\r\nchcp 65001 >nul\r\n"
        "rem AI SWE - iniciador revisable; no contiene credenciales\r\n"
        'cd /d "%~dp0"\r\n'
        + guide.command
        + "\r\n"
        + ("pause\r\n" if guide.kind == "python_cli" else "")
    ).encode("utf-8")


def prepare(state: RunState) -> LaunchGuide:
    guide = describe(state)
    if not guide.available:
        return guide
    path = Path(guide.launcher_path)
    if path.is_symlink():
        raise ValueError("No se reemplazará un enlace llamado iniciar.bat.")
    if path.exists():
        if not guide.prepared:
            raise ValueError(
                "Ya existe iniciar.bat. Se conserva; cambia su nombre para preparar otro."
            )
    else:
        with path.open("xb") as file:
            file.write(launcher_bytes(guide))
    guide.prepared = True
    return guide


def launch(state: RunState) -> LaunchGuide:
    guide = prepare(state)
    if not guide.available:
        raise ValueError(guide.summary_es)
    if guide.kind == "web_static":
        if not webbrowser.open((Path(guide.repo_path) / guide.entrypoint).as_uri()):
            raise ValueError("No se pudo abrir el navegador; abre iniciar.bat con doble clic.")
    elif os.name == "nt":
        needed = {
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "HOME",
            "LOCALAPPDATA",
            "APPDATA",
            "PATHEXT",
            "NUMBER_OF_PROCESSORS",
            "PROCESSOR_ARCHITECTURE",
        }
        environment = {k: v for k, v in os.environ.items() if k.upper() in needed}
        subprocess.Popen(
            [
                os.path.join(os.environ["SYSTEMROOT"], "System32", "cmd.exe"),
                "/d",
                "/c",
                guide.launcher_path,
            ],
            cwd=guide.repo_path,
            env=environment,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    else:
        raise ValueError("Abre el iniciador en Windows o usa el comando indicado.")
    return guide
