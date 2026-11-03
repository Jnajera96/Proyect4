"""Verify a fixed offline REST product through real worktree tests and promotion."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ai_swe.config import Settings
from ai_swe.contracts import AgentRole, RunOptions, RunStatus
from ai_swe.graph import RunEngine, model_routing
from ai_swe.models import FakeModelAdapter, ModelGateway
from ai_swe.state import RunStore
from ai_swe.tools.runner import ejecutar

ROOT = Path(__file__).resolve().parents[1]

APP_CODE = '''"""Local task service. Run with uvicorn task_api:app when available."""
import sqlite3
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=80)
    completed: bool = False

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        if not value.strip():
            raise ValueError("Title must contain visible characters")
        return value.strip()


class Task(TaskInput):
    id: int


def create_app(database="tasks.sqlite3"):
    lock = threading.RLock()

    @asynccontextmanager
    async def lifespan(app):
        db = sqlite3.connect(str(database), check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("CREATE TABLE IF NOT EXISTS tasks "
                   "(id INTEGER PRIMARY KEY, title TEXT NOT NULL, completed INTEGER NOT NULL)")
        db.commit()
        app.state.db = db
        try:
            yield
        finally:
            db.close()

    app = FastAPI(lifespan=lifespan)

    def find(task_id):
        row = app.state.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Task not found")
        return Task(**dict(row))

    @app.post("/tasks", response_model=Task, status_code=201)
    def create(task: TaskInput):
        with lock, app.state.db as db:
            cursor = db.execute("INSERT INTO tasks(title, completed) VALUES(?,?)",
                                (task.title, int(task.completed)))
            return find(cursor.lastrowid)

    @app.get("/tasks", response_model=list[Task])
    def list_tasks():
        with lock:
            return [Task(**dict(row)) for row in app.state.db.execute(
                "SELECT * FROM tasks ORDER BY id")]

    @app.get("/tasks/{task_id}", response_model=Task)
    def get(task_id: int):
        with lock:
            return find(task_id)

    @app.put("/tasks/{task_id}", response_model=Task)
    def update(task_id: int, task: TaskInput):
        with lock, app.state.db as db:
            find(task_id)
            db.execute("UPDATE tasks SET title=?, completed=? WHERE id=?",
                       (task.title, int(task.completed), task_id))
            return find(task_id)

    @app.delete("/tasks/{task_id}")
    def delete(task_id: int):
        with lock, app.state.db as db:
            find(task_id)
            db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            return {"deleted": True}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
'''

TEST_CODE = """import socket

import pytest
from fastapi.testclient import TestClient

from task_api import create_app


def test_crud_and_status_codes():
    with TestClient(create_app(":memory:")) as client:
        assert client.get("/tasks").json() == []
        created = client.post("/tasks", json={"title": "Read a book"})
        assert created.status_code == 201
        task = created.json()
        assert task == {"id": 1, "title": "Read a book", "completed": False}
        assert client.get("/tasks/1").status_code == 200
        assert client.get("/tasks/1").json() == task
        assert client.get("/tasks").json() == [task]
        updated = client.put("/tasks/1", json={"title": "Finished", "completed": True})
        assert updated.status_code == 200
        assert updated.json()["completed"] is True
        assert client.delete("/tasks/1").status_code == 200
        assert client.get("/tasks/1").status_code == 404
        assert client.put("/tasks/1", json={"title": "Missing"}).status_code == 404
        assert client.delete("/tasks/1").status_code == 404


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "},
                                 {"title": "a" * 81}, {"title": "Task", "extra": 1}])
def test_validation(body):
    with TestClient(create_app(":memory:")) as client:
        assert client.post("/tasks", json=body).status_code == 422
        assert client.get("/tasks/not-an-integer").status_code == 422
        assert client.get("/tasks").json() == []


def test_file_database_survives_restart_and_parameterizes_sql(tmp_path):
    path = tmp_path / "tasks.sqlite3"
    title = "Read'); DROP TABLE tasks; --"
    with TestClient(create_app(path)) as client:
        assert client.post("/tasks", json={"title": title}).status_code == 201
    with TestClient(create_app(path)) as client:
        assert client.get("/tasks/1").json()["title"] == title
        assert client.post("/tasks", json={"title": "Still usable"}).status_code == 201
        assert len(client.get("/tasks").json()) == 2


def test_memory_databases_are_independent():
    with TestClient(create_app(":memory:")) as first:
        assert first.post("/tasks", json={"title": "Private to this instance"}).status_code == 201
    with TestClient(create_app(":memory:")) as second:
        assert second.get("/tasks").json() == []


def test_internet_attempt_is_blocked_before_connect():
    with pytest.raises(RuntimeError, match="External network denied"):
        socket.create_connection(("198.51.100.1", 443), timeout=0.01)
"""

GUARD_CODE = '''"""Python-level internet guard for this fixed trusted fixture, not an OS sandbox."""
import ipaddress
import sys


def network_guard(event, args):
    if event not in {"socket.connect", "socket.getaddrinfo"}:
        return
    address = args[1] if event == "socket.connect" else args[0]
    host = address[0] if isinstance(address, tuple) else address
    if host in {None, "localhost"}:
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise RuntimeError("External network denied by fixed-product test guard")


sys.addaudithook(network_guard)
'''

PACKAGES = ("fastapi", "pydantic", "httpx", "starlette", "anyio", "uvicorn")


class ProductAdapter(FakeModelAdapter):
    def generate(self, request):
        if request.agent_role is AgentRole.REVIEWER:
            self._structured = {
                "decision": "accept",
                "findings": [],
                "required_fixes": [],
                "summary": "Accept fixed fixture after real pytest and Ruff evidence",
            }
        else:
            assert request.agent_role is AgentRole.CODER
        return super().generate(request)


def run_product2_verification(output_dir: Path | None = None) -> dict:
    if not __debug__:
        raise RuntimeError("Verification requires enabled assertions")
    start = time.perf_counter()
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    root = Path(tempfile.mkdtemp(prefix="aiswe-rest-e2e-"))
    repo = root / "user-repo"
    repo.mkdir()

    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(repo), *args], text=True, timeout=15
        ).strip()

    git("init", "-q")
    git(
        "-c",
        "user.name=Verifier",
        "-c",
        "user.email=verifier@local",
        "commit",
        "--allow-empty",
        "-qm",
        "Synthetic baseline",
    )
    baseline = git("rev-parse", "HEAD")
    versions = {name: importlib.metadata.version(name) for name in PACKAGES}
    files = {
        "task_api.py": APP_CODE,
        "test_task_api.py": TEST_CODE,
        "conftest.py": GUARD_CODE,
        "requirements.txt": "".join(f"{name}=={version}\n" for name, version in versions.items()),
    }
    proposal = {
        "files": [
            {
                "path": path,
                "operation": "create",
                "new_content": content,
                "rationale": "Fixed offline REST product fixture",
            }
            for path, content in files.items()
        ],
        "rationale": "Task CRUD with Pydantic, local SQLite and real offline HTTP tests",
    }
    adapter = ProductAdapter(structured=proposal)
    settings = Settings(
        _env_file=None,
        network_egress_enabled=True,
        profile_mode=False,
        profile_id="product2-fixed-fixture",
        workspace_root=root / "worktrees",
        remote_model_roles=["coder", "reviewer"],
        allowed_packages=list(PACKAGES),
        allowed_test_targets=["pytest.unit", "ruff.check"],
    )
    stages = []
    with (
        ModelGateway([adapter]) as gateway,
        patch.object(model_routing, "gateway_from_settings", lambda _: gateway),
        RunStore(root / "state.sqlite3") as store,
    ):
        engine = RunEngine(store, settings=settings)
        text = (
            "Crea un microservicio REST de tareas con FastAPI y Pydantic, SQLite local, "
            "CRUD y validaciÃƒÆ’Ã‚Â³n; incluye task_api.py y pruebas HTTP offline."
        )
        state = engine.crear_estado(text, options=RunOptions(repo_path=str(repo)))
        first = engine.start(state)
        assert first.instruction.text == text
        assert first.status is RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION
        assert first.interpretation.intent.value == "modify"
        stages.append(first.status.value)
        ready = engine.resume(state.run_id, "approved")
        assert ready.status is RunStatus.AWAITING_APPROVAL, ready.model_dump_json()
        assert ready.plan is not None and ready.interpretation.confirmed_by_user
        assert ready.outputs.reviewer_output.decision.value == "accept"
        assert not ready.errors
        assert {t.target for t in ready.evidence.test_runs} == {"pytest.unit", "ruff.check"}
        assert all(t.exit_code == 0 for t in ready.evidence.test_runs)
        worktree = Path(ready.artifacts.worktree_path)
        assert worktree.resolve() != repo.resolve()
        for path, content in files.items():
            assert (worktree / path).read_bytes() == content.encode()
            assert not (repo / path).exists()
        assert git("rev-parse", "HEAD") == baseline
        stages.append(ready.status.value)
        result = engine.resume(state.run_id, "approved")
        assert result.status is RunStatus.COMPLETED and not result.errors
        assert result.promotion_receipt is not None
        stages.append(result.status.value)
        test_runs = [t.model_dump(mode="json") for t in ready.evidence.test_runs]
    assert [c.agent_role for c in adapter.calls] == [AgentRole.CODER, AgentRole.REVIEWER]
    artifacts = {}
    changed = {f.path: f.sha256 for f in ready.outputs.coder_output.files_changed}
    for path, content in files.items():
        actual = (repo / path).read_bytes()
        digest = hashlib.sha256(actual).hexdigest()
        assert actual == content.encode() and digest == changed[path]
        artifacts[path] = {"sha256": digest, "bytes": len(actual)}
    post = [
        ejecutar(
            SimpleNamespace(raiz=repo),
            target,
            permitidos=("pytest.unit", "ruff.check"),
            network_egress_enabled=True,
        )
        for target in ("pytest.unit", "ruff.check")
    ]
    assert all(t.exit_code == 0 for t in post), [t.model_dump() for t in post]
    assert "9 passed" in post[0].stdout
    for path, record in artifacts.items():
        assert hashlib.sha256((repo / path).read_bytes()).hexdigest() == record["sha256"]
    assert (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=15
        ).strip()
        == source_commit
    ), "Base changed during E2E; rerun required"
    evidence = {
        "verified_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "product": "Product 2: Offline task REST service",
        "status": "APPROVED_LOCAL_SCOPE",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "python": platform.python_version(),
        "seconds": time.perf_counter() - start,
        "repository": str(repo),
        "baseline_commit": baseline,
        "stages": stages,
        "human_gates": 2,
        "artifacts": artifacts,
        "sandbox_tests": test_runs,
        "promoted_tests": [t.model_dump(mode="json") for t in post],
        "dependencies": versions,
        "installed_packages": False,
        "model": {
            "adapter": "FakeModelAdapter",
            "calls": len(adapter.calls),
            "roles": [c.agent_role.value for c in adapter.calls],
            "paid_spend_usd": 0,
        },
        "http_statuses_asserted": [200, 201, 404, 422],
        "launch_command": ["python", "task_api.py"],
        "launch_server_tested": False,
        "network": {
            "real_http_server": False,
            "http_transport": "ASGI TestClient in memory",
            "python_external_connect_and_dns_guard": True,
            "guard_scope": "pytest subprocesses only; not an OS firewall",
            "guard_negative_probe_passed": True,
            "os_network_isolation": False,
            "native_fixture_opt_in": True,
            "observed_external_provider_calls": 0,
        },
        "limitations": [
            "Fixed simulated proposals/review, not LLM quality evidence",
            "Worktree plus Python guards is not Docker/VM isolation",
            "Loopback event-loop control sockets permitted",
        ],
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "E2E-PRODUCT2-REST-API-EVIDENCE.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    result = run_product2_verification(args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "seconds": result["seconds"],
                "http_statuses": result["http_statuses_asserted"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
