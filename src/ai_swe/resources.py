"""Read-only assets have a bundle location distinct from mutable user state."""

import sys
from pathlib import Path


def frontend_dist() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "frontend" / "dist"
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"
