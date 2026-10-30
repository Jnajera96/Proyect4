"""Cooperative run/node/attempt cancellation; never claims remote billing stopped."""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from threading import Event


class RunCancelled(Exception):
    pass


class CancellationToken:
    def __init__(self, parent=None):
        self.parent = parent
        self.event = Event()
        self.requested_at = None

    def request(self):
        if not self.event.is_set():
            self.requested_at = datetime.now(UTC)
            self.event.set()

    @property
    def requested(self):
        return self.event.is_set() or (self.parent is not None and self.parent.requested)

    def check(self):
        if self.requested:
            raise RunCancelled("Cancelación solicitada")

    def child(self):
        return CancellationToken(self)


_CURRENT = ContextVar("ai_swe_cancellation", default=None)


def current_cancellation():
    return _CURRENT.get()


@contextmanager
def cancellation_scope(control):
    token = _CURRENT.set(control)
    try:
        yield
    finally:
        _CURRENT.reset(token)
