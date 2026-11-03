"""Offline generation through human gates, promotion and launch-guide preparation."""

import subprocess

from fastapi.testclient import TestClient
from test_project_builder_pipeline import BuilderAdapter, project_files

from ai_swe.api.app import crear_app
from ai_swe.config import Settings
from ai_swe.contracts import RunOptions
from ai_swe.graph import model_routing
from ai_swe.models import ModelGateway


def test_promoted_offline_project_exposes_guide_without_get_side_effects(tmp_path, monkeypatch):
    repo = tmp_path / "application"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@localhost",
            "commit",
            "--allow-empty",
            "-qm",
            "initial",
        ],
        check=True,
        capture_output=True,
    )
    adapter = BuilderAdapter(project_files("calendar"))
    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: ModelGateway([adapter]))
    settings = Settings(
        _env_file=None, network_egress_enabled=True,
        profile_mode=False,
        profile_id="delivery-fixture",
        state_db_path=tmp_path / "state.sqlite3",
        workspace_root=tmp_path / "worktrees",
        remote_model_roles=["coder", "reviewer"],
        allowed_test_targets=["pytest.unit", "ruff.check"],
        api_keys={"operator-fixture": "operator"},
    )
    app = crear_app(settings=settings)
    with TestClient(app) as client:
        engine = app.state.engine
        state = engine.crear_estado(
            "Construye un calendario", options=RunOptions(repo_path=str(repo))
        )
        assert engine.start(state).status == "awaiting_human_requirements_confirmation"
        assert adapter.calls == []
        assert engine.resume(state.run_id, "approved").status == "awaiting_approval"
        assert not (repo / "index.html").exists()
        assert engine.resume(state.run_id, "approved").status == "completed"
        url = f"/runs/{state.run_id}/launch-guide"
        headers = {"X-API-Key": "operator-fixture"}
        response = client.get(url, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["kind"] == "web_static"
        assert not (repo / "iniciar.bat").exists()
        response = client.post(url + "/prepare", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["prepared"]
        assert b"index.html" in (repo / "iniciar.bat").read_bytes()
        assert [call.agent_role for call in adapter.calls] == ["coder", "reviewer"]
