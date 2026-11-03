"""K regressions at the real graph/worktree and offline Hub download boundaries."""

import hashlib
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_swe.api import crear_app
from ai_swe.config import Settings
from ai_swe.contracts import (
    CodeChange,
    FileChange,
    Instruction,
    Outputs,
    RunOptions,
    RunState,
    TestRun,
)
from ai_swe.graph import model_routing, nodes
from ai_swe.graph.workflow import construir_grafo
from ai_swe.state.profiles import ProfileStore
from ai_swe.stt import crear_adaptador_stt

PASSWORD = "long synthetic password"


def _state(repo, name):
    diff = "--- /dev/null\n+++ b/private.py\n@@ -0,0 +1 @@\n+secret = 42\n"
    return RunState(
        run_id=name,
        trace_id=name,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        instruction=Instruction(text="create private.py", source="text", confirmed_by_user=True),
        options=RunOptions(repo_path=str(repo)),
        outputs=Outputs(
            coder_output=CodeChange(
                files_changed=[
                    FileChange(
                        path="private.py",
                        added=1,
                        removed=0,
                        sha256=hashlib.sha256(b"secret = 42\n").hexdigest(),
                    )
                ],
                diff=diff,
                diff_sha256=hashlib.sha256(diff.encode()).hexdigest(),
                rationale="test",
            )
        ),
    )


@pytest.mark.parametrize("remote_roles", [[], ["coder", "reviewer"]])
def test_profile_graph_owns_real_worktree_and_test_targets(tmp_path, monkeypatch, remote_roles):
    repo = tmp_path / "source"
    repo.mkdir()
    for args in [
        ("init", "-q"),
        (
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@localhost",
            "commit",
            "--allow-empty",
            "-qm",
            "initial",
        ),
    ]:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    base = Settings(
        _env_file=None,
        profiles_root=tmp_path / "users",
        profile_mode=True,
        workspace_root=tmp_path / "global",
        allowed_test_targets=["global-target"],
        stt_provider="fake",
    )
    monkeypatch.setattr("ai_swe.config.load_settings", lambda: base)
    # Legacy test/development hooks must not override authenticated profile policy.
    monkeypatch.setattr(nodes, "_WORKSPACE_ROOT", base.workspace_root)
    monkeypatch.setattr(nodes, "_TARGETS_PERMITIDOS", ("global-target",))
    store = ProfileStore(base.profiles_root)
    profiles = [store.create(name, PASSWORD) for name in ("alice", "bob")]
    paths = []
    calls = []

    def execute(sandbox, target, *, permitidos, limits=None, network_egress_enabled=False):
        calls.append((sandbox.raiz, target, permitidos, limits))
        return TestRun(target=target, exit_code=0, duration_s=0)

    monkeypatch.setattr(nodes, "ejecutar_target", execute)
    for index, (profile, targets) in enumerate(zip(profiles, [["pytest"], ["ruff"]], strict=True)):
        profile.data["remote_model_roles"] = remote_roles
        from ai_swe.tools.windows_job import JobLimits

        settings = profile.settings(base).model_copy(update={
            "allowed_test_targets": targets, "runner_limits": JobLimits(max_processes=index + 2),
        })
        graph = construir_grafo(settings=settings)
        state = _state(repo, profile.user_id)
        applied = graph.nodes["apply_sandbox"].runnable.invoke(state)
        assert applied["next_step"] == "run_tests", applied
        path = Path(applied["artifacts"].worktree_path)
        paths.append(path)
        assert path.parent == profile.paths.worktrees
        assert (path / "private.py").read_text() == "secret = 42\n"
        assert not (repo / "private.py").exists()
        tested = graph.nodes["run_tests"].runnable.invoke(state.model_copy(update=applied))
        assert [r.target for r in tested["evidence"].test_runs] == targets
        assert calls[-1] == (
            path, targets[0], tuple(targets), settings.runner_limits if os.name == "nt" else None,
        )
        assert model_routing.settings_for_node() is None
    assert paths[0] != paths[1]
    assert not base.workspace_root.exists()
    # Exercise the authenticated API boundary with the actual other user's worktree.
    with TestClient(crear_app(settings=base)) as client:
        login = client.post("/auth/login", json={"name": "bob", "password": PASSWORD})
        headers = {"X-CSRF-Token": login.json()["csrf_token"]}
        assert (
            client.post(
                "/projects", json={"name": "foreign", "repo_path": str(paths[0])}, headers=headers
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/runs",
                json={"instruction": "inspect", "options": {"repo_path": str(paths[0])}},
                headers=headers,
            ).status_code
            == 403
        )


@pytest.mark.parametrize("global_source", ["environment", "cached"])
@pytest.mark.parametrize("owner_credential", ["", "synthetic-owner-token"])
def test_profile_speech_download_is_anonymous_even_with_global_credentials(
    tmp_path,
    monkeypatch,
    global_source,
    owner_credential,
):
    whisper = pytest.importorskip("faster_whisper")
    import huggingface_hub
    from faster_whisper.utils import download_model
    from huggingface_hub import constants
    from huggingface_hub.utils import _headers, build_hf_headers

    monkeypatch.setenv("HF_TOKEN", "synthetic-global-token")
    if global_source == "cached":
        monkeypatch.delenv("HF_TOKEN")
    monkeypatch.setattr(constants, "HF_HUB_DISABLE_IMPLICIT_TOKEN", False)
    resolutions = []

    def synthetic_token_resolver():
        resolutions.append(global_source)
        return os.environ.get("HF_TOKEN") or "synthetic-cached-token"

    monkeypatch.setattr(_headers, "get_token", synthetic_token_resolver)
    captures = []

    def snapshot(repo_id, **kwargs):
        captures.append((kwargs, build_hf_headers(token=kwargs.get("token"))))
        return "no-download-performed"

    monkeypatch.setattr(huggingface_hub, "snapshot_download", snapshot)

    def model(name, **kwargs):
        download_model(
            name, cache_dir=kwargs.get("download_root"), use_auth_token=kwargs.get("use_auth_token")
        )
        return object()

    monkeypatch.setattr(whisper, "WhisperModel", model)
    base = Settings(_env_file=None, stt_provider="faster-whisper", stt_model="tiny")
    profile = ProfileStore(tmp_path / "users").create("alice", PASSWORD)
    profile.data["hf_token"] = owner_credential
    before = dict(os.environ)
    crear_adaptador_stt(profile.settings(base))._modelo_cargado()
    assert captures[0][0].get("token") is False
    assert "authorization" not in captures[0][1]
    assert captures[0][0]["cache_dir"] == str(profile.paths.cache / "speech")
    assert resolutions == []
    assert dict(os.environ) == before
    # Legacy behavior stays implicit, proven with the same installed download/header path.
    crear_adaptador_stt(base)._modelo_cargado()
    expected = (
        "synthetic-global-token" if global_source == "environment" else "synthetic-cached-token"
    )
    assert captures[1][1]["authorization"] == "Bearer " + expected
    assert resolutions == [global_source]


def test_bound_profile_settings_reset_after_failure_and_ignore_legacy_model_hooks(
    tmp_path, monkeypatch
):
    settings = ProfileStore(tmp_path).create("alice", PASSWORD).settings(Settings(_env_file=None))
    monkeypatch.setattr(nodes, "_MODELO_REVIEWER", "global-reviewer")
    monkeypatch.setattr(nodes, "_GATEWAY", object())
    observed = []

    def fail(state):
        observed.append(
            (
                model_routing.settings_for_node(),
                nodes._modelo_del_reviewer(),
                model_routing.gateway_for_node(nodes._GATEWAY),
            )
        )
        raise RuntimeError("synthetic")

    monkeypatch.setattr(nodes, "reviewer", fail)
    node = construir_grafo(settings=settings).nodes["reviewer"].runnable
    with pytest.raises(RuntimeError, match="synthetic"):
        node.invoke(_state(tmp_path, "run"))
    assert observed == [(settings, None, nodes.SIN_GATEWAY)]
    assert model_routing.settings_for_node() is None
    assert model_routing.gateway_for_node(nodes._GATEWAY) is nodes._GATEWAY


@pytest.mark.parametrize("configured", [False, True])
def test_legacy_graph_preserves_injected_model_and_tool_hooks(tmp_path, monkeypatch, configured):
    settings = Settings(_env_file=None, remote_model_roles=[]) if configured else None
    gateway = object()
    monkeypatch.setattr(nodes, "_GATEWAY", gateway)
    monkeypatch.setattr(nodes, "_MODELO_REVIEWER", "legacy-reviewer")
    monkeypatch.setattr(nodes, "_WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(nodes, "_TARGETS_PERMITIDOS", ("legacy-target",))

    def observe(state):
        return (
            model_routing.gateway_for_node(nodes._GATEWAY),
            nodes._modelo_del_reviewer(),
            nodes._workspace_root(),
            nodes._targets_permitidos(),
        )

    monkeypatch.setattr(nodes, "reviewer", observe)
    graph = construir_grafo(settings=settings)
    assert graph.nodes["reviewer"].runnable.invoke(_state(tmp_path, "legacy")) == (
        gateway,
        "legacy-reviewer",
        tmp_path,
        ("legacy-target",),
    )
    assert model_routing.settings_for_node() is None
