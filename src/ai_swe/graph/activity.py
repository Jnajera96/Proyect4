"""Run-local activity, propagated to graph workers without global run ownership."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from time import perf_counter

from ai_swe.cancellation import cancellation_scope, current_cancellation

_SINK = ContextVar("ai_swe_activity_sink", default=None)
_NODE = ContextVar("ai_swe_activity_node", default=None)
_ROLE = ContextVar("ai_swe_activity_role", default=None)


@contextmanager
def activity_sink(callback):
    token = _SINK.set(callback)
    try:
        yield
    finally:
        _SINK.reset(token)


def emit(kind, **data):
    callback = _SINK.get()
    if callback is not None:
        callback(kind, {"node": _NODE.get(), "role": _ROLE.get(), **data})


def activity_node(node, role=None, mode="deterministic"):
    @wraps(node)
    def invoke(state):
        token = _NODE.set(node.__name__)
        role_token = _ROLE.set(role or node.__name__)
        start = perf_counter()
        try:
            control = current_cancellation()
            promoted = state.promotion_receipt and state.promotion_receipt.status == "promoted"
            if control and not promoted:
                control.check()
            emit("node_started", mode=mode)
            with cancellation_scope(control.child() if control else None):
                result = node(state)
            emit("node_completed", duration_ms=(perf_counter() - start) * 1000)
            if (
                node.__name__ == "finalize"
                and state.interpretation
                and state.interpretation.intent in {"inspect", "question"}
            ):
                for skipped in (
                    "coder",
                    "apply_sandbox",
                    "run_tests",
                    "reviewer",
                    "promote_changes",
                ):
                    emit("node_skipped", node=skipped, reason="No aplica en modo inspeccion")
            return result
        finally:
            _ROLE.reset(role_token)
            _NODE.reset(token)

    return invoke
