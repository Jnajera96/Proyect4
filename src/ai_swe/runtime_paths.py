"""Installed mutable state lives in the user profile, never beside bundled code."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def default_runtime_mode() -> str:
    return "installed" if getattr(sys, "frozen", False) else "development"


@dataclass(frozen=True)
class UserPaths:
    root: Path

    @property
    def config_file(self) -> Path:
        return self.root / "config" / ".env"

    @property
    def database(self) -> Path:
        return self.root / "data" / "state.sqlite3"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def worktrees(self) -> Path:
        return self.root / "worktrees"

    @property
    def cache(self) -> Path:
        return self.root / "cache"


def user_paths() -> UserPaths:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return UserPaths(base.expanduser().resolve() / "AISWESystem")


def prepare_user_directories() -> None:
    paths = user_paths()
    for directory in (
        paths.config_file.parent, paths.database.parent, paths.logs, paths.worktrees, paths.cache,
    ):
        directory.mkdir(parents=True, exist_ok=True)
