import json
import tomllib
from pathlib import Path

from ai_swe import __version__
from ai_swe.api import crear_app
from ai_swe.state import RunStore


def test_release_versions_match_across_python_api_and_frontend(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("AI_SWE_STATE_DB_PATH", str(tmp_path / "state.sqlite3"))
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    frontend = json.loads((root / "frontend/package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "frontend/package-lock.json").read_text(encoding="utf-8"))
    assert __version__ == project["project"]["version"] == "0.2.0"
    with RunStore(tmp_path / "isolated.sqlite3") as store:
        assert crear_app(store=store).version == __version__
    assert frontend["version"] == lock["version"] == lock["packages"][""]["version"] == __version__
