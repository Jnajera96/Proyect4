"""Per-node opt-in routing without process-global credentials or gateway mutation."""

from __future__ import annotations

import os
import subprocess
from contextvars import ContextVar
from functools import wraps
from pathlib import Path

from ai_swe.contracts import RunState

_FACTORY: ContextVar = ContextVar("ai_swe_node_gateway_factory", default=None)
_SETTINGS: ContextVar = ContextVar("ai_swe_node_settings", default=None)


def gateway_from_settings(settings):
    # Construction remains in the graph's existing lazy model boundary.
    from ai_swe.graph.nodes import _gateway_por_defecto

    return _gateway_por_defecto(settings)


def settings_for_node():
    return _SETTINGS.get()


def gateway_for_node(default):
    factory = _FACTORY.get()
    return factory() if factory is not None else default


def bind_settings_node(node, settings):
    """Keep configuration local to this node, including deterministic/tool nodes."""

    @wraps(node)
    def invoke(state: RunState):
        token = _SETTINGS.set(settings)
        try:
            return node(state)
        finally:
            _SETTINGS.reset(token)

    return invoke


def _authorized_git_root(repo: str | None, scope_repo: str) -> bool:
    """Verify the bound root with Git itself before any remote generation."""
    if not repo:
        return False
    try:
        root = Path(repo).resolve()
        if not root.is_dir() or Path(scope_repo).resolve() != root:
            return False
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"}
        }
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel", "--is-inside-work-tree"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            shell=False,
            timeout=10,
            env=environment,
        )
        lines = result.stdout.splitlines()
        valid_root = (
            result.returncode == 0
            and len(lines) == 2
            and lines[1] == "true"
            and Path(lines[0]).resolve() == root
        )
        if not valid_root:
            return False
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD^{commit}"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            shell=False,
            timeout=10,
            env=environment,
        )
        return head.returncode == 0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def bind_model_node(node, role: str, settings, disabled):
    """Bind immutable installation settings; create/close a gateway only if called.

    The override is local to the node invocation. LangGraph workers, concurrent
    runs and separate application instances do not share this mutable resource.
    Non-enabled roles explicitly use the deterministic path, even if a legacy
    test/development gateway was injected globally.
    """

    @wraps(node)
    def invoke(state: RunState):
        gateway = None

        def resolve():
            nonlocal gateway
            if role not in settings.remote_model_roles:
                return disabled
            if gateway is None:
                gateway = gateway_from_settings(settings)
            return gateway

        if isinstance(state, RunState) and role == "coder" and role in settings.remote_model_roles:
            from ai_swe.graph.nodes import _alcance, _error, _escalar

            repo = state.options.repo_path
            scope_repo = _alcance(state).repo_path
            if not _authorized_git_root(repo, scope_repo):
                return _escalar(
                    state,
                    _error(
                        state,
                        "SANDBOX_NO_REPO",
                        "coder",
                        "Selecciona un proyecto Git autorizado antes de generar codigo; "
                        "no hay repositorio valido para el sandbox.",
                        recuperable=False,
                    ),
                )

        token = _FACTORY.set(resolve)
        settings_token = _SETTINGS.set(settings)
        try:
            return node(state)
        finally:
            _FACTORY.reset(token)
            _SETTINGS.reset(settings_token)
            if gateway is not None:
                gateway.close()

    return invoke
