"""Offline contracts: strict network isolation and static-only Node support."""

import subprocess
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ai_swe.config import Settings
from ai_swe.tools import runner
from ai_swe.tools.dependency_detector import SourceFile, detect_node_dependencies
from ai_swe.tools.docker_runner import DockerSettings
from ai_swe.tools.policy import node_dependency_issues


def test_network_default_is_strict(monkeypatch):
    monkeypatch.delenv("AI_SWE_NETWORK_EGRESS_ENABLED", raising=False)
    assert Settings(_env_file=None).network_egress_enabled is False
    with pytest.raises(ValidationError):
        Settings(_env_file=None, network_egress_enabled="perhaps")


def test_native_strict_contract_refuses_before_process_or_socket(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Strict mode must not launch a process or open a socket")

    monkeypatch.setattr(runner, "_capturar", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    with pytest.raises(runner.RunnerError, match="no garantiza el bloqueo físico") as error:
        runner.ejecutar(SimpleNamespace(raiz=tmp_path), "pytest.unit", permitidos=("pytest.unit",))
    assert error.value.operacion == "network_egress"


def test_explicit_native_optin_preserves_target_authorization(tmp_path, monkeypatch):
    calls = []

    def capture(*args):
        calls.append(args)
        return subprocess.CompletedProcess(args[0], 0, "fixture", "")

    monkeypatch.setattr(runner, "_capturar", capture)
    sandbox = SimpleNamespace(raiz=tmp_path)
    result = runner.ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",),
                            network_egress_enabled=True)
    assert result.passed and len(calls) == 1
    with pytest.raises(runner.TargetNoPermitido):
        runner.ejecutar(sandbox, "npm.install", permitidos=("pytest.unit",),
                        network_egress_enabled=True)
    assert len(calls) == 1


def test_strict_docker_route_never_uses_host(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_capturar", lambda *a: pytest.fail("Host execution"))
    monkeypatch.setattr("ai_swe.tools.docker_runner.execute", lambda *a:
                        subprocess.CompletedProcess(["docker", "fixture"], 0, "", ""))
    assert runner.ejecutar(SimpleNamespace(raiz=tmp_path), "pytest.unit",
                           permitidos=("pytest.unit",), docker=DockerSettings()).passed
    with pytest.raises(ValidationError):
        DockerSettings(network="host")


def test_node_inventory_empty_is_missing_even_when_authorized_and_declared():
    manifest = detect_node_dependencies([
        SourceFile("server.js", "import express from 'express';"),
        SourceFile("package.json", '{"dependencies":{"express":"4"},'
                   '"engines":{"node":">=24.22.1","npm":">=11"}}'),
    ])
    assert any("offline" in issue for issue in node_dependency_issues(manifest, ["express"]))
    assert any("allowed_packages" in issue for issue in node_dependency_issues(manifest, []))
    report = manifest.preflight()
    assert report["required_versions"] == {"node": ">=24.22.1", "npm": ">=11"}
    assert report["scope"] == "static_only" and not report["runtime_available"]
    assert report["offline_packages"] == [] and report["missing_packages"] == ["express"]


def test_runner_has_no_npm_host_target():
    assert not any("npm" in arg or "npx" in arg
                   for command in runner.TARGET_COMMANDS.values() for arg in command)
    for target in ("npm.install", "npm.update", "npx", "npm.test"):
        assert runner.comando_de(target) is None


def test_graph_consumes_network_setting_and_escalates_once(tmp_path, monkeypatch):
    from test_f8_test_runner import _estado

    from ai_swe.graph import model_routing, nodes

    state = _estado(tmp_path)
    state = state.model_copy(update={"artifacts": state.artifacts.model_copy(
        update={"worktree_path": str(tmp_path)})})
    settings = Settings(_env_file=None, network_egress_enabled=False)
    monkeypatch.setattr(model_routing, "settings_for_node", lambda: settings)
    monkeypatch.setattr(nodes, "_entorno_dependencias", lambda *a: (settings, {}))
    monkeypatch.setattr(nodes, "_targets_permitidos", lambda: ("pytest.unit", "ruff.check"))
    monkeypatch.setattr(runner, "_capturar", lambda *a: pytest.fail("No host execution"))
    result = nodes.run_tests(state)
    assert result["status"] == "needs_human" and result["next_step"] is None
    assert result["errors"][-1].error_class == "NETWORK_EGRESS_UNAVAILABLE"
    assert not result["errors"][-1].recoverable
    assert state.budget.used_tool_calls == 0
