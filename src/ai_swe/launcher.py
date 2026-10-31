"""Local desktop entry point; bind first, wait for health, then open the real URL."""

from __future__ import annotations

import argparse
import asyncio
import errno
import json
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from pydantic import ValidationError

from ai_swe.config import load_settings
from ai_swe.resources import frontend_dist

HOST = "127.0.0.1"


def reserve_listener(preferred_port: int) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind((HOST, preferred_port))
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE and getattr(exc, "winerror", None) != 10048:
                raise
            listener.bind((HOST, 0))
        listener.listen(128)
        return listener
    except BaseException:
        listener.close()
        raise


def wait_for_health(url: str, thread: threading.Thread, timeout: float) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not thread.is_alive():
            raise RuntimeError("El servidor termino antes de iniciar")
        try:
            request = urllib.request.Request(url + "/health", headers={"Connection": "close"})
            with opener.open(request, timeout=0.5) as response:
                if response.status == 200 and json.load(response).get("status") == "ok":
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise TimeoutError("El servidor no estuvo listo dentro del plazo")


def serve(*, open_browser: bool = True, startup_timeout: float = 30, exit_after=None) -> int:
    import logging
    from contextlib import nullcontext

    from ai_swe.runtime_paths import user_paths
    from ai_swe.state.operation_lock import operation_lock
    from ai_swe.state.upgrade_recovery import recover_upgrade

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = load_settings(prepare=False)
    root = user_paths().root
    lease = (operation_lock(root.parent / f".{root.name}.server.lock")
             if getattr(settings, "runtime_mode", "development") == "installed" else nullcontext())
    with lease:
        if getattr(settings, "runtime_mode", "development") == "installed":
            recover_upgrade(root)
            settings = load_settings()
        return _serve(settings, open_browser=open_browser,
                      startup_timeout=startup_timeout, exit_after=exit_after)


def _serve(settings, *, open_browser=True, startup_timeout=30, exit_after=None) -> int:
    import uvicorn

    from ai_swe.api import crear_app

    if not (frontend_dist() / "index.html").is_file():
        raise FileNotFoundError("Falta la interfaz construida del paquete")
    # App and STT read exactly the same installed settings sources. No credential probe.
    app = crear_app()
    listener = reserve_listener(settings.port)
    url = f"http://{HOST}:{listener.getsockname()[1]}"
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=HOST,
            port=listener.getsockname()[1],
            loop="asyncio",
            http="h11",
            ws="none",
            lifespan="on",
            access_log=False,
            log_level="warning",
            timeout_keep_alive=3,
            timeout_graceful_shutdown=5,
        )
    )
    server_loop = None

    def run_server():
        async def serve_on_loop():
            nonlocal server_loop
            server_loop = asyncio.get_running_loop()
            await server.serve(sockets=[listener])

        asyncio.run(serve_on_loop())

    thread = threading.Thread(target=run_server, daemon=True)
    try:
        thread.start()
        wait_for_health(url, thread, startup_timeout)
        print(f"AI Software Engineering System: {url}/app/", flush=True)
        print("Para cerrar el servidor, pulsa Ctrl+C en esta ventana.", flush=True)
        if open_browser:
            try:
                opened = webbrowser.open(url + "/app/", new=2)
            except (OSError, webbrowser.Error):
                opened = False
            if not opened:
                print("No se pudo abrir el navegador. Abre la direccion anterior.", flush=True)
        deadline = time.monotonic() + exit_after if exit_after is not None else None
        while thread.is_alive():
            if deadline is not None and time.monotonic() >= deadline:
                break
            thread.join(0.1)
        if not server.started:
            raise RuntimeError("El servidor no pudo iniciar")
        return 0
    finally:
        server.should_exit = True
        try:
            if server_loop is not None and not server_loop.is_closed():
                try:
                    server_loop.call_soon_threadsafe(lambda: None)
                except RuntimeError:
                    if not server_loop.is_closed():
                        raise
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError(
                    "El servidor no terminó el cierre ordenado dentro de 10 segundos"
                )
        finally:
            listener.close()


def positive_seconds(value: str) -> float:
    result = float(value)
    if not 0 < result <= 3600:
        raise argparse.ArgumentTypeError("El plazo debe estar entre 0 y 3600 segundos")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="AI Software Engineering System local")
    parser.add_argument(
        "--profiles", action=argparse.BooleanOptionalAction, default=True,
        help="Registro y acceso por usuario (predeterminado); --no-profiles usa el acceso heredado",
    )
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--runtime-info", action="store_true")
    parser.add_argument("--startup-timeout", type=positive_seconds, default=30)
    parser.add_argument("--exit-after", type=positive_seconds, help=argparse.SUPPRESS)
    parser.add_argument(
        "--run-test-target",
        choices=["pytest.unit", "pytest.integration", "ruff.check"],
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    os.environ["AI_SWE_PROFILE_MODE"] = "true" if args.profiles else "false"
    if args.run_test_target:
        return embedded_test_target(args.run_test_target)
    try:
        if args.runtime_info:
            settings = load_settings(prepare=False)
            print(
                json.dumps(
                    {
                        "frozen": bool(getattr(sys, "frozen", False)),
                        "runtime_mode": settings.runtime_mode,
                        "profile_mode": settings.profile_mode,
                        "frontend_present": (frontend_dist() / "index.html").is_file(),
                    }
                )
            )
            return 0
        return serve(
            open_browser=not args.no_browser,
            startup_timeout=args.startup_timeout,
            exit_after=args.exit_after,
        )
    except KeyboardInterrupt:
        return 0
    except ValidationError as exc:
        fields = sorted({str(error["loc"][0]) for error in exc.errors() if error["loc"]})
        print("Configuracion invalida. Revisa: " + ", ".join(fields), file=sys.stderr)
    except FileNotFoundError:
        print(
            "Faltan archivos de la aplicacion. Reconstruye o reinstala el paquete.",
            file=sys.stderr,
        )
    except Exception as exc:
        print(f"No se pudo iniciar la aplicacion ({type(exc).__name__}).", file=sys.stderr)
    return 1


def embedded_test_target(target: str) -> int:
    """Closed worker entry, never an arbitrary Python module or shell command."""
    from ai_swe.tools.runner import TARGET_COMMANDS

    arguments = list(TARGET_COMMANDS[target][3:])
    if target.startswith("pytest."):
        import pytest

        os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        sys.path[:0] = [str(Path.cwd() / "src"), str(Path.cwd())]
        return int(pytest.main(arguments))
    import subprocess

    bundle = getattr(sys, "_ai_swe_bundle", None) or sys._MEIPASS
    ruff = Path(bundle) / "tools" / "ruff.exe"
    return subprocess.run([str(ruff), *arguments], shell=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
