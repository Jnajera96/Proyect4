"""Offline installed-profile smoke for a signed-Python portable candidate."""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import os
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    bundle, output = args.bundle.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    checks: list[str] = []
    report = {"success": False, "checks": checks, "paid_calls": 0}
    children = []
    logs = []
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.upper().startswith("AI_SWE_")
        and k.upper() not in {"HF_TOKEN", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
    }
    env.update(
        LOCALAPPDATA=str(output / "userdata"),
        PATH=str(Path(os.environ["SYSTEMROOT"]) / "System32"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    command = [str(bundle / "runtime/python.exe"), "-B", str(bundle / "start.py")]
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar)
    )
    csrf = ""

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)
        print("OK", label, flush=True)

    def request(path, body=None):
        req = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
        )
        try:
            with opener.open(req, timeout=15) as response:
                raw = response.read()
                return response.status, (
                    json.loads(raw) if "json" in response.headers.get("Content-Type", "") else raw
                )
        except urllib.error.HTTPError as exc:
            return exc.code, None

    def start():
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        log = (output / f"server-{len(children)}.log").open("w", encoding="utf-8")
        logs.append(log)
        child = subprocess.Popen(
            [*command, "--no-browser", "--exit-after", "90"],
            cwd=output,
            env={**env, "AI_SWE_PORT": str(port)},
            stdout=log,
            stderr=log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        children.append(child)
        for _ in range(300):
            try:
                with opener.open(base_url + "/health", timeout=1) as response:
                    if response.status == 200:
                        return child, base_url
            except (OSError, urllib.error.URLError):
                pass
            if child.poll() is not None:
                raise RuntimeError("Portable exited before readiness; inspect server log")
            time.sleep(0.1)
        raise RuntimeError("Readiness timeout")

    try:
        manifest = json.loads((bundle / "BUNDLE-MANIFEST.json").read_text())
        check(
            all(
                hashlib.sha256((bundle / p).read_bytes()).hexdigest() == digest
                for p, digest in manifest.items()
            ),
            "all manifest hashes match",
        )
        check(
            not any(
                p.name.startswith(".env") or p.suffix in {".sqlite3", ".gguf", ".log"}
                for p in bundle.rglob("*")
                if p.is_file()
            ),
            "no developer state or secrets files",
        )
        child, base = start()
        check(
            request("/auth/status")[1] == {"profile_mode": True, "authenticated": False},
            "installed defaults to profiles",
        )
        check(request("/runs")[0] == 401, "private API gated before login")
        check(request("/app/")[0] == 200, "integrated frontend served")
        status, auth = request(
            "/auth/register", {"name": "portable-test", "password": "portable-test-password"}
        )
        check(status == 201, "profile registration with packaged cryptography")
        csrf = auth["csrf_token"]
        uid = auth["user"]["id"]
        check(request("/auth/vault")[1]["has_token"] is False, "empty profile has no global token")
        status, run = request(
            "/runs",
            {
                "instruction": "Explica qué hace el proyecto sin modificar archivos",
                "options": {"execution_mode": "INSPECT_ONLY"},
            },
        )
        check(status == 202, "packaged graph accepts deterministic run")
        run_id = run["run_id"]
        for _ in range(100):
            status, state = request("/runs/" + run_id)
            if state["status"] == "awaiting_human_requirements_confirmation":
                break
            time.sleep(0.1)
        check(
            state["status"] == "awaiting_human_requirements_confirmation",
            "human confirmation required",
        )
        check(child.wait(timeout=105) == 0, "graceful packaged shutdown")
        jar.clear()
        csrf = ""
        child, base = start()
        status, auth = request(
            "/auth/login", {"name": "portable-test", "password": "portable-test-password"}
        )
        check(status == 200, "encrypted profile login survives restart")
        csrf = auth["csrf_token"]
        check(request("/runs/" + run_id)[0] == 200, "SQLite and graph checkpoint survive restart")
        database = output / "userdata/AISWESystem/data/users" / uid / "state.sqlite3"
        if not database.exists():
            matches = list((output / "userdata").rglob("state.sqlite3"))
            check(
                len(matches) == 1 and uid in str(matches[0]), "SQLite isolated under user profile"
            )
            database = matches[0]
        with sqlite3.connect(database) as connection:
            check(
                connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                "persisted SQLite integrity",
            )
        check(child.wait(timeout=105) == 0, "restart shutdown graceful")
        report["success"] = True
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        print(report["error"], flush=True)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
        for log in logs:
            log.close()
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
