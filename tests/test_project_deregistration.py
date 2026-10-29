from fastapi.testclient import TestClient

from ai_swe.api import crear_app
from ai_swe.config import Settings


def test_project_removal_requires_admin_in_legacy_key_mode(tmp_path):
    settings = Settings(
        _env_file=None, profile_mode=False, state_db_path=tmp_path / "state.sqlite3",
        stt_provider="fake", api_keys={
            "offline-reader-key": "reader", "offline-operator-key": "operator",
            "offline-admin-key": "admin",
        },
    )
    with TestClient(crear_app(settings=settings)) as client:
        assert client.delete("/projects/not-found").status_code == 401
        for key in ("offline-reader-key", "offline-operator-key"):
            response = client.delete("/projects/not-found", headers={"X-API-Key": key})
            assert response.status_code == 403
        assert client.delete("/projects/not-found", headers={
            "X-API-Key": "offline-admin-key",
        }).status_code == 404


def test_project_removal_is_profile_scoped_and_keeps_history_and_bytes(tmp_path):
    settings = Settings(
        _env_file=None, profile_mode=True, profiles_root=tmp_path / "users",
        stt_provider="fake", authorized_repos=[tmp_path / "repos"],
    )
    (tmp_path / "repos").mkdir()
    with TestClient(crear_app(settings=settings)) as client:
        password = "offline profile password"
        alice = client.post("/auth/register", json={"name": "alice", "password": password})
        headers_a = {"X-CSRF-Token": alice.json()["csrf_token"]}
        path = tmp_path / "repos" / "new"
        created = client.post("/projects", headers=headers_a, json={
            "name": "new", "repo_path": str(path), "create_if_missing": True,
        })
        assert created.status_code == 201, created.text
        project_id = created.json()["project_id"]
        before = {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}
        assert client.delete("/projects/" + project_id).status_code == 403
        assert client.delete("/projects/" + project_id, headers={
            **headers_a, "Origin": "https://evil.test",
        }).status_code == 403
        run = client.post("/runs", headers=headers_a, json={
            "instruction": "Inspecciona el repositorio sin modificar archivos",
            "project_id": project_id,
        })
        assert run.status_code == 202, run.text
        run_id = run.json()["run_id"]
        assert client.post("/auth/logout", headers=headers_a).status_code == 200
        bob = client.post("/auth/register", json={"name": "bob", "password": password})
        headers_b = {"X-CSRF-Token": bob.json()["csrf_token"]}
        assert client.delete("/projects/" + project_id, headers=headers_b).status_code == 404
        assert client.post("/auth/logout", headers=headers_b).status_code == 200
        alice = client.post("/auth/login", json={"name": "alice", "password": password})
        headers_a = {"X-CSRF-Token": alice.json()["csrf_token"]}
        assert client.get("/projects/" + project_id).status_code == 200
        assert client.delete("/projects/" + project_id, headers=headers_a).status_code == 204
        assert client.get("/projects/" + project_id).status_code == 404
        assert client.get("/runs/" + run_id).status_code == 200
        assert client.delete("/projects/" + project_id, headers=headers_a).status_code == 404
        after = {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}
        assert after == before
