"""Owned rotating file handler for installed sessions; secrets are redacted first."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ai_swe.security import RedactingFilter

profile_log_context: ContextVar[str | None] = ContextVar("profile_log_context", default=None)


class ProfileLogFilter(logging.Filter):
    def __init__(self, profile_id):
        super().__init__()
        self.profile_id = profile_id

    def filter(self, record):
        owner = profile_log_context.get()
        record.profile_id = owner or "legacy"
        return owner == self.profile_id


def installed_log_handler(directory: Path | None, *, profile_id: str | None = None):
    if directory is None:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        directory / "application.log", maxBytes=2 * 1024 * 1024, backupCount=3,
        encoding="utf-8", delay=True,
    )
    handler.addFilter(ProfileLogFilter(profile_id))
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(profile_id)s] %(name)s %(message)s"
    ))
    logging.getLogger("ai_swe").addHandler(handler)
    return handler


def close_installed_log_handler(handler) -> None:
    if handler is not None:
        logging.getLogger("ai_swe").removeHandler(handler)
        handler.close()
