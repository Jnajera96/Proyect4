"""Read-only application discovery and explicit, bounded Windows launcher preparation."""

from __future__ import annotations

import ast
import hashlib
import keyword
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
    dependency_modules: list[str] = Field(default_factory=list)
    missing_modules: list[str] = Field(default_factory=list)
    suggested_requirements: str = ""
    installation_command: str = ""


def approved_repository(state: RunState) -> Path:
    """Publication requires a promotion; preview permission must not weaken this gate."""
    receipt = state.promotion_receipt
    if state.status == "completed" and receipt and receipt.status == "promoted":
        root = Path(state.options.repo_path or "").resolve()
        if not state.options.repo_path or not root.is_dir():
            raise ValueError("La carpeta de la aplicación ya no está disponible.")
        _verify_files(state, root)
        return root
    raise ValueError("Primero termina y aprueba una aplicación con archivos guardados.")


def _verify_files(state: RunState, root: Path) -> None:
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


def _preview_repository(state: RunState) -> Path:
    if state.status in {"needs_human", "awaiting_approval"} and state.artifacts.worktree_path:
        root = Path(state.artifacts.worktree_path).resolve()
        if root.is_dir() and state.artifacts.changed_files:
            _verify_files(state, root)
            return root
    return approved_repository(state)


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
    root = _preview_repository(state)
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
    if not paths:
        return LaunchGuide(
            repo_path=str(root),
        )
    if entry and (not re.fullmatch(r"[A-Za-z0-9_./-]+", entry) or ".." in Path(entry).parts):
        raise ValueError("El nombre del archivo de inicio necesita revisión.")
    runtime = str(Path(sys.executable).resolve())
    if any(char in runtime + str(root) for char in '%!&|<>^"\r\n'):
        raise ValueError("La ruta contiene caracteres incompatibles con el iniciador de Windows.")
    python_paths = repr([".", "src", Path(entry).parent.as_posix()])
    python_setup = f"import sys;sys.path[:0]={python_paths};"
    if kind == "web_static":
        command = f'start "" "%~dp0{entry.replace("/", chr(92))}"'
    elif kind == "python_library":
        module = entry[:-3].replace("/", ".")
        importable = all(p.isidentifier() and not keyword.iskeyword(p) for p in module.split("."))
        load = (
            f"from {module} import *"
            if importable
            else f"import runpy;globals().update(runpy.run_path('{entry}'))"
        )
        code = (
            python_setup + load + ";"
            "print('Módulo cargado con éxito. Prueba tus funciones aquí:')"
        )
        command = f'"{runtime}" -i -c "{code}"'
    elif kind == "fastapi":
        module = entry[:-3].replace("/", ".")
        if not all(part.isidentifier() for part in module.split(".")):
            raise ValueError("El módulo de la aplicación necesita un nombre válido.")
        code = (
            python_setup + "import uvicorn;"
            f"uvicorn.run('{module}:{app_name}',host='127.0.0.1',port=8765)"
        )
        command = f'"{runtime}" -c "{code}"'
    elif kind == "python_cli":
        code = (
            python_setup + "import runpy;"
            "runpy.run_path(sys.argv[1],run_name='__main__')"
        )
        command = f'"{runtime}" -c "{code}" "{entry}"'
    else:
        command = 'start "" "%~dp0"'
    launcher = root / "iniciar.bat"
    is_promoted = bool(
        state.status == "completed"
        and state.promotion_receipt
        and state.promotion_receipt.status == "promoted"
    )
    summary_text = (
        "Tu aplicación está lista para usar."
        if is_promoted
        else "Borrador de tu aplicación listo para probar en tu computadora."
    )
    first_instruction = (
        f"Tu aplicación está guardada en {root}."
        if is_promoted
        else f"Borrador generado en el entorno de pruebas ({root})."
    )
    guide = LaunchGuide(
        available=True,
        kind=kind,
        summary_es=summary_text,
        launch_action="open_browser" if kind == "web_static" else "run_command",
        command=command,
        repo_path=str(root),
        entrypoint=entry,
        launcher_path=str(launcher),
        instructions=[
            first_instruction,
            "Abre iniciar.bat con doble clic para usarla otra vez.",
            "Conserva la carpeta completa y esta instalación del sistema.",
        ],
    )
    if kind == "fastapi":
        guide.instructions.append(
            "Abre http://127.0.0.1:8765 después de iniciar. Cierra la ventana para detenerla."
        )
    elif kind == "python_library":
        guide.instructions.append(
            "Se abrirá una consola interactiva. Escribe tus funciones y pulsa Entrar; "
            "usa exit() para salir."
        )
    elif kind == "unknown":
        guide.summary_es = "Tus archivos están guardados; abre la carpeta para revisarlos."
        guide.instructions.append(
            "No se detectó un programa HTML o Python ejecutable. "
            "Pide un punto de entrada para probar este formato."
        )
    if kind in {"fastapi", "python_cli", "python_library"}:
        from ai_swe.tools.dependency_detector import (
            detect_python_dependencies,
            installed_modules,
            package_for,
            repository_files,
        )

        files = [f for f in repository_files(root) if not Path(f.path).name.startswith("test_")
                 and "tests" not in Path(f.path).parts]
        manifest = detect_python_dependencies(files)
        modules = set(manifest.third_party_modules)
        if kind == "fastapi":
            modules.update({"fastapi", "uvicorn"})
        if len(modules) > 64 or sum(map(len, modules)) > 3000:
            raise ValueError("Demasiados módulos para preparar un iniciador revisable.")
        guide.dependency_modules = sorted(modules)
        available = installed_modules(modules)
        guide.missing_modules = sorted(modules - set(available))
        guide.suggested_requirements = "".join(p + "\n" for p in sorted({
            package_for(m) for m in modules}))
        guide.installation_command = f'"{runtime}" -m pip install -r requirements.txt'
        unsafe_requirements = any(e.startswith("requirements.txt") for e in manifest.errors)
        if unsafe_requirements:
            guide.installation_command = ""
        if guide.missing_modules:
            guide.summary_es = "Tu aplicación necesita preparar dependencias antes de iniciar."
            guide.instructions.append("Faltan módulos en el Python del iniciador: "
                                      + ", ".join(guide.missing_modules) + ".")
            if not manifest.has_manifest:
                names = guide.suggested_requirements.strip().replace("\n", ", ")
                guide.instructions.append("Primero crea y revisa requirements.txt con: " + names)
            if guide.installation_command:
                guide.instructions.append(
                    "Revisa el archivo y, si autorizas su instalación, ejecuta: "
                    + guide.installation_command)
            guide.instructions.append("No se instalará nada automáticamente. Si ese Python no "
                                      "incluye pip, prepara un entorno Python con pip y configura "
                                      "el iniciador para usarlo; no se usa otra .venv en silencio.")
        if manifest.errors:
            guide.instructions.append("Revisa los archivos Python y requirements.txt antes de "
                                      "instalar: el análisis estático está incompleto.")
        if unsafe_requirements:
            guide.instructions.append("El manifiesto contiene fuentes no admitidas. "
                                      "No se ofrece un comando de instalación hasta corregirlo.")
    guide.prepared = (
        launcher.is_file()
        and not launcher.is_symlink()
        and launcher.read_bytes() == launcher_bytes(guide)
    )
    return guide


def launcher_bytes(guide: LaunchGuide) -> bytes:
    preflight = ""
    if guide.dependency_modules:
        runtime = str(Path(sys.executable).resolve())
        probe = ("import importlib.util,sys;sys.exit(any(importlib.util.find_spec(m) is None "
                 f"for m in {tuple(guide.dependency_modules)!r}))")
        preflight = (
            f'"{runtime}" -I -c "{probe}"\r\n'
            "if errorlevel 1 (\r\n"
            "echo Faltan dependencias en el Python de este iniciador.\r\n"
            "echo Revisa o crea requirements.txt antes de iniciar.\r\n"
            f"echo Instala solo si autorizas el archivo: {guide.installation_command}\r\n"
            "echo Si este Python no incluye pip, prepara un entorno con pip.\r\n"
            "pause\r\nexit /b 1\r\n)\r\n"
        )
    return (
        "@echo off\r\nsetlocal DisableDelayedExpansion\r\nchcp 65001 >nul\r\n"
        "rem AI SWE - iniciador revisable; no contiene credenciales\r\n"
        'cd /d "%~dp0"\r\n' + preflight + guide.command + "\r\n" + "pause\r\n"
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
    if guide.missing_modules:
        raise ValueError("Faltan dependencias: " + ", ".join(guide.missing_modules)
                         + ". Revisa requirements.txt y la guía antes de iniciar.")
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
