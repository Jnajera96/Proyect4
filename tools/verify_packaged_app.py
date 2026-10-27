"""Real EXE smoke in an isolated profile and reduced PATH, without Python/Node children."""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--voice-model", type=Path)
    parser.add_argument("--voice-audio", type=Path)
    args = parser.parse_args()
    exe, output = args.executable.resolve(), args.output.resolve()
    if output.exists():
        parser.error("Use a new evidence directory")
    output.mkdir(parents=True)
    cwd = output / "unrelated-working-directory"
    cwd.mkdir()
    report = {"checks": [], "paid_inference_calls": 0, "success": False}

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        report["checks"].append(name)
        print("OK", name, flush=True)

    env = {
        k: v
        for k, v in os.environ.items()
        if not k.upper().startswith("AI_SWE_")
        and k.upper() not in {"HF_TOKEN", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
    }
    git = shutil.which("git")
    env["PATH"] = str(Path(os.environ["SYSTEMROOT"]) / "System32")
    if git:
        env["PATH"] += os.pathsep + str(Path(git).parent)
    env["LOCALAPPDATA"] = str(output / "user-profile")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if args.voice_model:
        env["AI_SWE_STT_MODEL"] = str(args.voice_model.resolve())
        env["AI_SWE_STT_DEVICE"] = "cpu"
        env["AI_SWE_STT_COMPUTE_TYPE"] = "int8"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(base, path, body=None, key=None):
        headers = {"Content-Type": "application/json"}
        if key:
            headers["X-API-Key"] = key
        req = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
        )
        try:
            with opener.open(req, timeout=10) as response:
                raw = response.read()
                return response.status, json.loads(raw) if "json" in response.headers.get(
                    "Content-Type", ""
                ) else raw
        except urllib.error.HTTPError as exc:
            return exc.code, None

    children = []
    logs = []

    def start(port):
        child_env = {**env, "AI_SWE_PORT": str(port)}
        log = (output / f"stderr-{len(children)}.log").open("w", encoding="utf-8")
        logs.append(log)
        child = subprocess.Popen(
            [str(exe), "--no-browser", "--exit-after", "18"],
            cwd=cwd,
            env=child_env,
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
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=0.1)
                match = re.search(r"http://127\.0\.0\.1:\d+", line)
                if match:
                    return child, match.group()
            except queue.Empty:
                if child.poll() is not None:
                    break
        raise RuntimeError("Packaged launcher did not become ready; inspect stderr log")

    try:
        info = subprocess.run(
            [str(exe), "--runtime-info"],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
            creationflags=flags,
        )
        check("native frozen runtime diagnostics work", info.returncode == 0)
        report["runtime"] = json.loads(info.stdout)
        check(
            "sys.frozen activates installed mode",
            report["runtime"]
            == {
                "frozen": True,
                "runtime_mode": "installed",
                "frontend_present": True,
            },
        )
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            preferred = occupied.getsockname()[1]
            child, base = start(preferred)
            check("occupied preferred port is avoided", not base.endswith(":" + str(preferred)))
            check("health responds without provider credential", request(base, "/health")[0] == 200)
            status, html = request(base, "/app/")
            check(
                "bundled React frontend is served",
                status == 200 and b"AI Software Engineering System" in html,
            )
            asset = re.search(rb'src="([^"]+\.js)"', html).group(1).decode()
            check("bundled JavaScript is served", request(base, asset)[0] == 200)
            check("projects accessible in local mode", request(base, "/projects")[0] == 200)
            if args.voice_model and args.voice_audio:
                boundary = "packaged-voice-test-boundary"
                body = (
                    (
                        f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; '
                        'filename="spanish.wav"\r\nContent-Type: audio/wav\r\n\r\n'
                    ).encode()
                    + args.voice_audio.read_bytes()
                    + f"\r\n--{boundary}--\r\n".encode()
                )
                req = urllib.request.Request(
                    base + "/transcriptions",
                    data=body,
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                )
                with opener.open(req, timeout=90) as response:
                    transcript = json.load(response)
                check(
                    "packaged CPU/int8 transcribes local Spanish audio",
                    transcript["language"] == "es"
                    and "analiza el proyecto" in transcript["text"].lower(),
                )
                report["voice_text"] = transcript["text"]
            repo = output / "synthetic-repository"
            repo.mkdir()
            (repo / "src").mkdir()
            (repo / "tests").mkdir()
            (repo / "src/app.py").write_text("def f():\n    return 42\n", encoding="utf-8")
            (repo / "tests/test_app.py").write_text(
                "from app import f\n\n\ndef test_f():\n    assert f() == 42\n", encoding="utf-8"
            )
            for command in (
                ["init"],
                ["add", "."],
                [
                    "-c",
                    "user.name=Package Test",
                    "-c",
                    "user.email=package@example.invalid",
                    "commit",
                    "-m",
                    "fixture",
                ],
            ):
                subprocess.run(
                    [git, *command], cwd=repo, check=True, capture_output=True, creationflags=flags
                )
            status, project = request(
                base, "/projects", {"name": "package-fixture", "repo_path": str(repo)}
            )
            check("packaged API registers a synthetic Git project", status == 201)
            status, run = request(
                base,
                "/runs",
                {"instruction": "analiza el proyecto", "project_id": project["project_id"]},
            )
            check("packaged engine creates a run", status == 202)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                _, state = request(base, "/runs/" + run["run_id"])
                if state["status"] == "awaiting_human_requirements_confirmation":
                    break
                time.sleep(0.1)
            check(
                "packaged LangGraph waits for human confirmation",
                state["status"] == "awaiting_human_requirements_confirmation",
            )
            check("automatic test shutdown is graceful", child.wait(timeout=25) == 0)
            key = "synthetic-package-admin"
            config = output / "user-profile/AISWESystem/config/.env"
            config.write_text(
                "AI_SWE_API_KEYS=" + json.dumps({key: "admin"}) + "\n", encoding="utf-8"
            )
            child, base = start(preferred)
            check("authentication works after restart", request(base, "/projects")[0] == 401)
            status, projects = request(base, "/projects", key=key)
            check("SQLite persists across packaged restarts", status == 200 and len(projects) == 1)
            check("restart shutdown releases server", child.wait(timeout=25) == 0)
        for target in ("pytest.unit", "ruff.check"):
            result = subprocess.run(
                [str(exe), "--run-test-target", target],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
                timeout=45,
                creationflags=flags,
            )
            (output / (target + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
            check(
                "embedded " + target + " needs no development interpreter", result.returncode == 0
            )
        check(
            "SQLite outside installation",
            (output / "user-profile/AISWESystem/data/state.sqlite3").exists(),
        )
        check("unrelated current directory remains empty", not list(cwd.iterdir()))
        report["success"] = True
    except Exception as exc:
        report["error"] = str(exc)
        print(type(exc).__name__, str(exc), flush=True)
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
