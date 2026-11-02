"""Pruebas de integración para dependencias de Node.js en el motor y en la guía de inicio."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from ai_swe.contracts import (
    Artifacts,
    FileChange,
    Instruction,
    InstructionSource,
    Intent,
    RunOptions,
    RunState,
    Scope,
    TaskInterpretation,
)
from ai_swe.graph import nodes
from ai_swe.launch_guide import describe
from ai_swe.models import FakeModelAdapter, ModelGateway
from ai_swe.tools.dependency_detector import (
    NodeDependencyManifest,
    detect_node_dependencies,
    repository_node_files,
)


def test_repository_node_files_discovers_scripts_and_package_json(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "index.js").write_text("console.log('hello');", encoding="utf-8")
    (repo / "utils.ts").write_text("export const add = (a: number, b: number) => a + b;", encoding="utf-8")
    (repo / "package.json").write_text(json.dumps({"name": "test-pkg"}), encoding="utf-8")
    (repo / "ignored.py").write_text("print('python')", encoding="utf-8")

    node_modules = repo / "node_modules"
    node_modules.mkdir()
    (node_modules / "bad.js").write_text("module.exports = {};", encoding="utf-8")

    files = repository_node_files(repo)
    paths = {f.path for f in files}
    assert "index.js" in paths
    assert "utils.ts" in paths
    assert "package.json" in paths
    assert "ignored.py" not in paths
    assert "node_modules/bad.js" not in paths


def test_coder_dependency_check_stops_on_unpermitted_npm_package(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.js").write_text("import fs from 'node:fs';", encoding="utf-8")

    # Mock Coder proposing unpermitted external package 'axios'
    fake = FakeModelAdapter(
        structured={
            "summary": "Agrega cliente HTTP con axios",
            "rationale": "Usa axios para peticiones http",
            "files": [
                {
                    "path": "client.js",
                    "operation": "create",
                    "new_content": "import axios from 'axios';\nexport const get = (url) => axios.get(url);",
                    "rationale": "archivo cliente",
                }
            ],
        }
    )
    previo = nodes._GATEWAY
    nodes.usar_gateway(ModelGateway([fake]))
    try:
        now = datetime.now(UTC)
        st = RunState(
            run_id="run-node-dep-test",
            trace_id="trace-node-dep-test",
            created_at=now,
            updated_at=now,
            instruction=Instruction(text="agrega cliente http", source=InstructionSource.TEXT, confirmed_by_user=True),
            interpretation=TaskInterpretation(
                intent=Intent.MODIFY,
                scope=Scope(repo_path=str(repo)),
                confidence=0.95,
                rationale="test proposal",
            ),
            options=RunOptions(repo_path=str(repo)),
        )
        res = nodes.coder(st)
        # Debe escalar a DEPENDENCY_UNAVAILABLE porque axios no está en allowed_packages ni en package.json
        assert any(e.error_class == "DEPENDENCY_UNAVAILABLE" for e in res.get("errors", []))
    finally:
        nodes.usar_gateway(previo)


def test_launch_guide_node_app_instructions_without_host_execution(tmp_path: Path) -> None:
    repo = tmp_path / "node_project"
    repo.mkdir()
    server_content = "import http from 'node:http';\nconsole.log('ready');"
    pkg_content = json.dumps({"name": "my-node-app", "dependencies": {}})
    (repo / "server.js").write_text(server_content, encoding="utf-8")
    (repo / "package.json").write_text(pkg_content, encoding="utf-8")

    import hashlib
    server_sha = hashlib.sha256(server_content.encode()).hexdigest()
    pkg_sha = hashlib.sha256(pkg_content.encode()).hexdigest()

    now = datetime.now(UTC)
    from ai_swe.contracts import RunStatus
    st = RunState(
        run_id="run-guide-node",
        trace_id="trace-guide-node",
        created_at=now,
        updated_at=now,
        status=RunStatus.NEEDS_HUMAN,
        instruction=Instruction(text="crea un servidor", source=InstructionSource.TEXT, confirmed_by_user=True),
        options=RunOptions(repo_path=str(repo)),
        artifacts=Artifacts(
            worktree_path=str(repo),
            changed_files=[
                FileChange(path="server.js", operation="create", old_content=None, new_content=server_content, added=1, removed=0, sha256=server_sha),
                FileChange(path="package.json", operation="create", old_content=None, new_content=pkg_content, added=1, removed=0, sha256=pkg_sha),
            ]
        ),
    )

    guide = describe(st)
    assert guide.kind == "node_app"
    assert any("Aplicación Node.js detectada" in ins for ins in guide.instructions)
    assert any("No se ejecuta npm install ni scripts automáticamente" in ins for ins in guide.instructions)
