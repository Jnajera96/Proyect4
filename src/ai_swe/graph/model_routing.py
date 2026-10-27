"""Per-node opt-in routing without process-global credentials or gateway mutation."""

from __future__ import annotations

from contextvars import ContextVar
from functools import wraps

from ai_swe.contracts import RunState

_FACTORY: ContextVar = ContextVar("ai_swe_node_gateway_factory", default=None)
_SETTINGS: ContextVar = ContextVar("ai_swe_node_model_settings", default=None)


def gateway_from_settings(settings):
    # Construction remains in the graph's existing lazy model boundary.
    from ai_swe.graph.nodes import _gateway_por_defecto

    return _gateway_por_defecto(settings)


def settings_for_node():
    return _SETTINGS.get()


def gateway_for_node(default):
    factory = _FACTORY.get()
    return factory() if factory is not None else default


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
