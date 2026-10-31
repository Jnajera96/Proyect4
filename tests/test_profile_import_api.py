from fastapi.testclient import TestClient
from test_continuity_m import repo_at

from ai_swe.api import crear_app
from ai_swe.config import Settings
from ai_swe.contracts import RunOptions


def test_new_device_import_without_registration_preserves_pending_run(tmp_path):
    password = "synthetic-archive-password"
    old_repo = repo_at(tmp_path / "origin" / "repo")
    source = crear_app(settings=Settings(
        _env_file=None, profile_mode=True, profiles_root=tmp_path / "origin" / "users",
        stt_provider="fake",
    ))
    with TestClient(source) as client:
        registration = client.post("/auth/register", json={"name": "origin", "password": password})
        assert registration.status_code == 201
        auth = registration.json()
        engine = source.state.profiles.contexts[auth["user"]["id"]].app.state.engine
        state = engine.crear_estado(
            "Modifica app.py para mostrar un saludo",
            options=RunOptions(repo_path=str(old_repo), mode="FULL_PROPOSAL"),
        )
        pending = engine.start(state)
        assert pending.status == "awaiting_human_requirements_confirmation"
        exported = client.post("/continuity/export", json={"password": password},
                               headers={"X-CSRF-Token": auth["csrf_token"]})
        assert exported.status_code == 200, exported.text
        archive = exported.json()["archive_b64"]

    settings = Settings(_env_file=None, profile_mode=True,
                        profiles_root=tmp_path / "destination" / "users", stt_provider="fake")
    new_repo = tmp_path / "destination" / "repo"
    request = {"archive_b64": archive, "password": password, "name": "restored",
               "new_password": "new-device-password", "repo_mapping": {"*": str(new_repo)}}
    with TestClient(crear_app(settings=settings)) as client:
        assert client.get("/runs").status_code == 401
        denied = client.post("/auth/import-vault", json={**request, "password": "incorrect"})
        assert denied.status_code == 400
        assert not new_repo.exists()
        restored = client.post("/auth/import-vault", json=request)
        assert restored.status_code == 201, restored.text
        assert restored.json()["authenticated"] is True
        run = client.get(f"/runs/{pending.run_id}").json()
        assert run["status"] == pending.status
        assert run["options"]["repo_path"] == str(new_repo.resolve())
        assert run["budget"]["used_model_calls"] == 0
        assert (new_repo / "app.py").read_bytes() == (old_repo / "app.py").read_bytes()
        assert client.post("/auth/import-vault", json=request).status_code == 400

    with TestClient(crear_app(settings=settings)) as client:
        login = client.post(
            "/auth/login", json={"name": "restored", "password": "new-device-password"}
        )
        assert login.status_code == 200
        assert client.get(f"/runs/{pending.run_id}").json()["status"] == pending.status
