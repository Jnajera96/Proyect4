"""Install/uninstall the real candidate, with reduced PATH and deterministic local model HTTP.

This is an isolated destination on the development host, NOT an independent VM.
Only new owned shortcut paths and the installer's own HKCU registration are touched.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
import winreg
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REGISTRY_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion"
    r"\Uninstall\{7202DDE2-BCB0-4CFE-8C15-33D97B136DD8}_is1"
)


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def folder(csidl):
    buffer = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buffer) != 0:
        raise RuntimeError("Cannot locate user shortcut folder")
    return Path(buffer.value)


def registered():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY):
            return True
    except FileNotFoundError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("installer", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    installer, output = args.installer.resolve(), args.output.resolve()
    if output.exists():
        parser.error("Use a new isolated output directory")
    output.mkdir(parents=True)
    install = output / "installed-app"
    profile = output / "profile"
    group_name = "AI-SWE-Installer-Test-" + uuid.uuid4().hex[:8]
    menu = folder(0x02) / group_name
    default_menu = folder(0x02) / "AI Software Engineering System"
    desktop = folder(0x10) / "AI Software Engineering System.lnk"
    if desktop.exists() or menu.exists() or default_menu.exists() or registered():
        parser.error("Existing shortcut/product registration found; will not overwrite user state")
    report = {
        "environment": "isolated destination/profile and reduced PATH on development host",
        "independent_vm": False,
        "paid_inference_calls": 0,
        "checks": [],
        "success": False,
        "host_elevated": bool(ctypes.windll.shell32.IsUserAnAdmin()),
    }

    def check(name, value):
        if not value:
            raise AssertionError(name)
        report["checks"].append(name)
        print("OK", name, flush=True)

    env = {
        k: v
        for k, v in os.environ.items()
        if not k.upper().startswith("AI_SWE_")
        and k.upper() not in {"HF_TOKEN", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
    }
    git_exe = shutil.which("git")
    if not git_exe:
        parser.error("Git is an explicit external prerequisite")
    env["PATH"] = (
        str(Path(os.environ["SYSTEMROOT"]) / "System32") + os.pathsep + str(Path(git_exe).parent)
    )
    env["LOCALAPPDATA"] = str(profile)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    calls = []

    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                self.send_error(404)
                return
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            text = "\n".join(m["content"] for m in data["messages"])
            is_review = '"ReviewVerdict"' in text
            calls.append("reviewer" if is_review else "coder")
            payload = (
                {
                    "decision": "accept",
                    "summary": "Deterministic fixture; real tests and gates remain authoritative.",
                }
                if is_review
                else {
                    "files": [
                        {
                            "path": "src/app.py",
                            "operation": "modify",
                            "new_content": "def f():\n    return 42\n",
                            "rationale": "fixture correction",
                        }
                    ],
                    "rationale": "Deterministic test proposal only",
                }
            )
            body = json.dumps(
                {
                    "id": "local-fixture",
                    "model": "deterministic-install-fixture",
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": json.dumps(payload)},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    fixture = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threading.Thread(target=fixture.serve_forever, daemon=True).start()
    children, log_handles = [], []
    installed = False
    key = "synthetic-installer-admin"

    def request(base, path, body=None):
        req = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json", "X-API-Key": key},
        )
        with opener.open(req, timeout=10) as response:
            raw = response.read()
            return json.loads(raw) if "json" in response.headers.get("Content-Type", "") else raw

    def start():
        log = (output / f"app-{len(children)}.log").open("w", encoding="utf-8")
        log_handles.append(log)
        child = subprocess.Popen(
            [str(install / "AISWESystem.exe"), "--no-browser", "--exit-after", "20"],
            cwd=output,
            env={**env, "AI_SWE_PORT": "8000"},
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            creationflags=flags,
        )
        children.append(child)
        lines = queue.Queue()

        def read():
            for line in child.stdout:
                lines.put(line)

        threading.Thread(target=read, daemon=True).start()
        end = time.monotonic() + 45
        while time.monotonic() < end:
            try:
                match = re.search(r"http://127\.0\.0\.1:\d+", lines.get(timeout=0.1))
                if match:
                    return child, match.group()
            except queue.Empty:
                if child.poll() is not None:
                    break
        raise RuntimeError("Installed launcher did not become ready")

    def wait_state(base, run_id, expected):
        end = time.monotonic() + 15
        while time.monotonic() < end:
            state = request(base, "/runs/" + run_id)
            if state["status"] == expected:
                return state
            if state["status"] in {"failed", "needs_human", "cancelled", "completed"}:
                raise AssertionError("Unexpected terminal state: " + json.dumps(state["errors"]))
            time.sleep(0.1)
        raise TimeoutError("Waiting for " + expected)

    def uninstall():
        uninstaller = (install / "unins000.exe").resolve()
        if not uninstaller.is_relative_to(output) or not uninstaller.is_file():
            raise RuntimeError("Refusing uninstall outside the owned isolated destination")
        return subprocess.run(
            [
                str(uninstaller),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                f"/LOG={output / 'uninstall.log'}",
            ],
            env=env,
            cwd=output,
            timeout=90,
            creationflags=flags,
        ).returncode

    try:
        result = subprocess.run(
            [
                str(installer),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/SP-",
                f"/DIR={install}",
                f"/GROUP={group_name}",
                "/TASKS=desktopicon",
                f"/LOG={output / 'install.log'}",
            ],
            env=env,
            cwd=output,
            timeout=120,
            creationflags=flags,
        )
        installed = result.returncode == 0
        check("silent per-user installation succeeds", installed)
        check("complete onedir runtime installed", (install / "_internal/python313.dll").is_file())
        report["app_sha256"] = hash_file(install / "AISWESystem.exe")
        check(
            "Start Menu and Desktop shortcuts created",
            (menu / "AI Software Engineering System.lnk").is_file() and desktop.is_file(),
        )
        check("user uninstall registration created", registered())
        config = profile / "AISWESystem/config/.env"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(
            "AI_SWE_MODEL_PROVIDER=openai_compatible\n"
            f"AI_SWE_MODEL_BASE_URL=http://127.0.0.1:{fixture.server_port}/v1\n"
            "AI_SWE_MODEL_NAME=deterministic-install-fixture\n"
            "AI_SWE_MODEL_API_KEY=synthetic-local-fixture-key\n"
            'AI_SWE_REMOTE_MODEL_ROLES=["coder","reviewer"]\n'
            'AI_SWE_ALLOWED_TEST_TARGETS=["pytest.unit"]\n'
            "AI_SWE_API_KEYS=" + json.dumps({key: "admin"}) + "\n",
            encoding="utf-8",
        )
        repo = output / "disposable-repository"
        (repo / "src").mkdir(parents=True)
        (repo / "tests").mkdir()
        source = repo / "src/app.py"
        test = repo / "tests/test_app.py"
        source.write_text("def f():\n    return 1\n", encoding="utf-8")
        test.write_text(
            "from app import f\n\n\ndef test_f():\n    assert f() == 42\n", encoding="utf-8"
        )

        def git(*arguments):
            return subprocess.check_output(
                [git_exe, *arguments], cwd=repo, text=True, creationflags=flags
            ).strip()

        git("init", "-q")
        git("add", ".")
        git(
            "-c",
            "user.name=Installer Test",
            "-c",
            "user.email=installer@example.invalid",
            "commit",
            "-qm",
            "fixture",
        )
        head, before, protected = git("rev-parse", "HEAD"), hash_file(source), hash_file(test)
        baseline = subprocess.run(
            [str(install / "AISWESystem.exe"), "--run-test-target", "pytest.unit"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
            creationflags=flags,
        )
        (output / "baseline-test.log").write_text(
            baseline.stdout + baseline.stderr, encoding="utf-8"
        )
        check("functional test fails before proposal", baseline.returncode == 1)
        child, base = start()
        check(
            "installed API and frontend start",
            request(base, "/health")["status"] == "ok"
            and b"AI Software Engineering System" in request(base, "/app/"),
        )
        check(
            "installed API reports release version 0.1.0",
            request(base, "/openapi.json")["info"]["version"] == "0.1.0",
        )
        project = request(
            base, "/projects", {"name": "Installer promotion fixture", "repo_path": str(repo)}
        )
        run = request(
            base,
            "/runs",
            {
                "instruction": (
                    "Modifica src/app.py para que f devuelva 42. "
                    "No cambies las pruebas existentes."
                ),
                "project_id": project["project_id"],
                "options": {"allowed_paths": ["src/app.py"], "protected_paths": ["tests"]},
            },
        )
        run_id = run["run_id"]
        wait_state(base, run_id, "awaiting_human_requirements_confirmation")
        check(
            "requirements gate leaves original clean",
            hash_file(source) == before and git("status", "--porcelain") == "",
        )
        request(base, f"/runs/{run_id}/confirm-requirements", {"decision": "approved"})
        reviewed = wait_state(base, run_id, "awaiting_approval")
        check(
            "real packaged tests pass in worktree",
            bool(reviewed["evidence"]["test_runs"])
            and all(t["exit_code"] == 0 for t in reviewed["evidence"]["test_runs"]),
        )
        check(
            "review gate leaves original clean",
            hash_file(source) == before and git("status", "--porcelain") == "",
        )
        reviewed_bytes = (Path(reviewed["artifacts"]["worktree_path"]) / "src/app.py").read_bytes()
        check("graceful stop at persisted approval gate", child.wait(timeout=35) == 0)
        child, base = start()
        check(
            "SQLite and checkpoint survive application restart",
            request(base, "/runs/" + run_id)["status"] == "awaiting_approval"
            and len(request(base, "/projects")) == 1,
        )
        request(base, f"/runs/{run_id}/approve", {"decision": "approved"})
        completed = wait_state(base, run_id, "completed")
        check(
            "exact reviewed bytes promoted after explicit approval",
            source.read_bytes() == reviewed_bytes and b"return 42" in reviewed_bytes,
        )
        check(
            "protected tests and original commit unchanged",
            hash_file(test) == protected and git("rev-parse", "HEAD") == head,
        )
        check("only approved source path changed", git("diff", "--name-only") == "src/app.py")
        check(
            "final report has no promotion failure",
            completed["final_report"] is not None
            and not any(e["error_class"] == "PROMOTION_FAILED" for e in completed["errors"]),
        )
        check("deterministic fixture used only Coder and Reviewer", calls == ["coder", "reviewer"])
        check("shutdown completes before uninstall", child.wait(timeout=35) == 0)
        data_root = profile / "AISWESystem"
        preserved = {
            p.relative_to(data_root).as_posix(): hash_file(p)
            for p in data_root.rglob("*")
            if p.is_file()
        }
        check("SQLite exists outside installation", "data/state.sqlite3" in preserved)
        check("uninstaller succeeds", uninstall() == 0)
        installed = False
        check(
            "program and internal runtime removed",
            not (install / "AISWESystem.exe").exists() and not (install / "_internal").exists(),
        )
        check(
            "owned shortcuts and registration removed",
            not desktop.exists() and not menu.exists() and not registered(),
        )
        after = {
            p.relative_to(data_root).as_posix(): hash_file(p)
            for p in data_root.rglob("*")
            if p.is_file()
        }
        check("all user data including configuration preserved byte-for-byte", after == preserved)
        report.update(
            {
                "success": True,
                "fixture_calls": calls,
                "run_id": run_id,
                "final_status": completed["status"],
                "preserved_user_files": sorted(preserved),
            }
        )
    except Exception as exc:
        report["error"] = str(exc)
        print(type(exc).__name__, str(exc), flush=True)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
        if installed and (install / "unins000.exe").is_file():
            report["failure_cleanup_uninstall_exit"] = uninstall()
        for log in log_handles:
            log.close()
        fixture.shutdown()
        fixture.server_close()
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
