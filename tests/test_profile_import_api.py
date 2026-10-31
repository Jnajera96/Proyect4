import pytest
from fastapi.testclient import TestClient
from test_continuity_m import repo_at

from ai_swe.api import crear_app
from ai_swe.config import Settings
from ai_swe.contracts import RunOptions


@pytest.mark.parametrize("count", [1, 2])
def test_new_device_import_without_registration_preserves_pending_run(tmp_path, count):
    password = "synthetic-archive-password"
    old_repos = [repo_at(tmp_path / "origin" / f"repo-{i}") for i in range(count)]
    source = crear_app(settings=Settings(
        _env_file=None, profile_mode=True, profiles_root=tmp_path / "origin" / "users",
        stt_provider="fake",
    ))
    with TestClient(source) as client:
        registration = client.post("/auth/register", json={"name": "origin", "password": password})
        assert registration.status_code == 201
        auth = registration.json()
        engine = source.state.profiles.contexts[auth["user"]["id"]].app.state.engine
        pending_runs = []
        for old_repo in old_repos:
            state = engine.crear_estado(
                "Modifica app.py para mostrar un saludo",
                options=RunOptions(repo_path=str(old_repo), mode="FULL_PROPOSAL"),
            )
            pending = engine.start(state)
            assert pending.status == "awaiting_human_requirements_confirmation"
            pending_runs.append(pending)
        exported = client.post("/continuity/export", json={"password": password},
                               headers={"X-CSRF-Token": auth["csrf_token"]})
        assert exported.status_code == 200, exported.text
        archive = exported.json()["archive_b64"]

    settings = Settings(_env_file=None, profile_mode=True,
                        profiles_root=tmp_path / "destination" / "users", stt_provider="fake")
    new_repos = [tmp_path / "destination" / f"repo-{i}" for i in range(count)]
    mapping = {str(old): str(new) for old, new in zip(old_repos, new_repos, strict=True)}
    request = {"archive_b64": archive, "password": password, "name": "restored",
               "new_password": "new-device-password", "repo_mapping": mapping}
    with TestClient(crear_app(settings=settings)) as client:
        assert client.get("/runs").status_code == 401
        inspection = {"archive_b64": archive, "password": password}
        malformed = client.post("/auth/inspect-vault", json={
            "archive_b64": archive, "password": {"secret": "must-not-echo"},
        })
        assert malformed.status_code == 422 and "must-not-echo" not in malformed.text
        blocked = client.post("/auth/inspect-vault", json=inspection,
                              headers={"Origin": "https://untrusted.test"})
        assert blocked.status_code == 403
        wrong = client.post("/auth/inspect-vault", json={**inspection, "password": "incorrect"})
        assert wrong.status_code == 400
        preview = client.post("/auth/inspect-vault", json=inspection)
        assert preview.status_code == 200
        assert set(preview.json()) == {"profile_name", "repositories"}
        assert set(preview.json()["repositories"]) == set(mapping)
        assert not list(settings.profiles_root.glob("*/vault.json"))
        assert not any(p.exists() for p in new_repos)
        if count == 2:
            incomplete = client.post("/auth/import-vault", json={
                **request, "repo_mapping": {str(old_repos[0]): str(new_repos[0])},
            })
            assert incomplete.status_code == 400
            duplicate = client.post("/auth/import-vault", json={
                **request, "repo_mapping": {str(old): str(new_repos[0]) for old in old_repos},
            })
            assert duplicate.status_code == 400
            nested = client.post("/auth/import-vault", json={
                **request, "repo_mapping": {
                    str(old_repos[0]): str(new_repos[0]),
                    str(old_repos[1]): str(new_repos[0] / "nested"),
                },
            })
            assert nested.status_code == 400
            assert not any(p.exists() for p in new_repos)
        denied = client.post("/auth/import-vault", json={**request, "password": "incorrect"})
        assert denied.status_code == 400
        assert not any(p.exists() for p in new_repos)
        restored = client.post("/auth/import-vault", json=request)
        assert restored.status_code == 201, restored.text
        assert restored.json()["authenticated"] is True
        for pending, old_repo, new_repo in zip(pending_runs, old_repos, new_repos, strict=True):
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
        for pending in pending_runs:
            assert client.get(f"/runs/{pending.run_id}").json()["status"] == pending.status
