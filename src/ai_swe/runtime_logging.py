"""Owned rotating file handler for installed sessions; secrets are redacted first."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ai_swe.security import RedactingFilter


def installed_log_handler(directory: Path | None):
    if directory is None:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        directory / "application.log", maxBytes=2 * 1024 * 1024, backupCount=3,
        encoding="utf-8", delay=True,
    )
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger("ai_swe").addHandler(handler)
    return handler


def close_installed_log_handler(handler) -> None:
    if handler is not None:
        logging.getLogger("ai_swe").removeHandler(handler)
        handler.close()
