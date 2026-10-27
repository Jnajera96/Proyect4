from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from pydantic import ValidationError

from ai_swe.config import Settings
from ai_swe.graph import model_routing
from ai_swe.graph.workflow import construir_grafo


def test_remote_roles_are_opt_in_and_restricted():
    assert Settings(_env_file=None).remote_model_roles == []
    with pytest.raises(ValidationError):
        Settings(_env_file=None, remote_model_roles=["supervisor"])


def test_disabled_role_never_builds_gateway(monkeypatch):
    def unexpected(_):
        pytest.fail("deterministic role must not construct a provider")

    monkeypatch.setattr(model_routing, "gateway_from_settings", unexpected)
    disabled, legacy = object(), object()
    settings = Settings(_env_file=None, remote_model_roles=["coder", "reviewer"])
    for role in ["requirements_analyst", "supervisor"]:
        node = model_routing.bind_model_node(
            lambda _: model_routing.gateway_for_node(legacy), role, settings, disabled,
        )
        assert node(None) is disabled
    assert model_routing.gateway_for_node(legacy) is legacy


def test_gateway_is_closed_and_override_reset_after_node_failure(monkeypatch):
    closed = []

    class Gateway:
        def close(self):
            closed.append(True)

    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: Gateway())

    def broken(_):
        model_routing.gateway_for_node(None)
        raise RuntimeError("synthetic failure")

    node = model_routing.bind_model_node(
        broken, "coder", Settings(_env_file=None, remote_model_roles=["coder"]), object(),
    )
    with pytest.raises(RuntimeError):
        node(None)
    assert closed == [True]
    assert model_routing.gateway_for_node("legacy") == "legacy"


def test_concurrent_nodes_do_not_share_model_configuration(monkeypatch):
    barrier = Barrier(2)
    closed = []

    class Gateway:
        def __init__(self, name):
            self.name = name

        def close(self):
            closed.append(self.name)

    monkeypatch.setattr(
        model_routing, "gateway_from_settings", lambda settings: Gateway(settings.model_name),
    )

    def run(name):
        def node(_):
            barrier.wait(timeout=5)
            return model_routing.gateway_for_node(None).name

        settings = Settings(_env_file=None, remote_model_roles=["coder"], model_name=name)
        return model_routing.bind_model_node(node, "coder", settings, object())(None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run, ["first", "second"])) == ["first", "second"]
    assert sorted(closed) == ["first", "second"]


def test_configured_graph_compiles_with_real_node_annotations():
    settings = Settings(_env_file=None, remote_model_roles=["coder", "reviewer"])
    construir_grafo(settings=settings).compile()


def test_reviewer_model_comes_from_bound_settings_not_environment(monkeypatch):
    from ai_swe.graph import nodes

    monkeypatch.setattr(nodes, "_MODELO_REVIEWER", None)
    monkeypatch.setenv("AI_SWE_REVIEWER_MODEL", "unrelated-installation")
    settings = Settings(
        _env_file=None, remote_model_roles=["reviewer"], reviewer_model="configured-model",
    )
    node = model_routing.bind_model_node(
        lambda _: nodes._modelo_del_reviewer(), "reviewer", settings, object(),
    )
    assert node(None) == "configured-model"


def test_reviewer_sees_applied_git_diff_instead_of_replacement_encoding():
    import hashlib
    from datetime import UTC, datetime

    from ai_swe.contracts import Artifacts, CodeChange, Instruction, Outputs, RunState
    from ai_swe.graph import nodes

    synthetic = "--- /dev/null\n+++ b/src/app.py\n@@ -0,0 +1 @@\n+return 42\n"
    actual = "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-return 1\n+return 42\n"
    state = RunState(
        run_id="synthetic-review", trace_id="synthetic-trace",
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        instruction=Instruction(text="Modifica src/app.py", source="text", confirmed_by_user=True),
        artifacts=Artifacts(worktree_path="synthetic-worktree", diff=actual),
        outputs=Outputs(coder_output=CodeChange(
            files_changed=[], diff=synthetic, rationale="replacement encoding",
            diff_sha256=hashlib.sha256(synthetic.encode()).hexdigest(),
        )),
    )
    context = nodes._contexto_de_revision(state)
    assert actual in context
    assert "--- /dev/null" not in context
