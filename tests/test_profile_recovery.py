import pytest
from fastapi.testclient import TestClient

from ai_swe.api import crear_app
from ai_swe.config import Settings
from ai_swe.security.vault import VaultError
from ai_swe.state.profiles import ProfileStore

PWD = "original-test-password"
NEW = "replacement-test-password"


def test_rescue_keeps_data_rotates_and_consumes_code(tmp_path):
    store = ProfileStore(tmp_path / "users")
    profile = store.create("alice", PWD)
    profile.save({"hf_token": "synthetic-private-value"})
    (profile.paths.root / "untouched.txt").write_text("keep")
    first = store.generate_recovery("alice", PWD)
    second = store.generate_recovery("alice", PWD)
    assert len(second) >= 40 and first != second
    assert second not in profile.paths.vault.read_text()
    with pytest.raises(VaultError):
        store.recover("alice", first, NEW)
    profile.save({"hf_token": "synthetic-updated"})
    with pytest.raises(VaultError):
        store.recover("alice", "wrong-rescue-code", NEW)
    restored = store.recover("alice", second, NEW)
    assert restored.user_id == profile.user_id
    assert restored.data["hf_token"] == "synthetic-updated"
    assert (profile.paths.root / "untouched.txt").read_text() == "keep"
    assert store.unlock("alice", NEW).data == restored.data
    with pytest.raises(VaultError):
        profile.save({"hf_token": "stale-session-must-not-rewrap-old-password"})
    for password in (PWD,):
        with pytest.raises(VaultError):
            store.unlock("alice", password)
    with pytest.raises(VaultError):
        store.recover("alice", second, "another-long-password")


def test_rescue_wrong_owner_password_and_missing_code(tmp_path):
    store = ProfileStore(tmp_path / "users")
    alice = store.create("alice", PWD)
    bob = store.create("bob", PWD)
    code = store.generate_recovery("alice", PWD)
    with pytest.raises(VaultError):
        store.generate_recovery("alice", NEW)
    with pytest.raises(VaultError):
        store.recover("bob", code, NEW)
    with pytest.raises(VaultError):
        store.recover("unknown", code, NEW)
    assert store.unlock("alice", PWD).user_id == alice.user_id
    assert store.unlock("bob", PWD).user_id == bob.user_id


def test_registration_safe_errors_and_authenticated_recovery(tmp_path):
    app = crear_app(
        settings=Settings(
            _env_file=None, profile_mode=True, profiles_root=tmp_path / "users", stt_provider="fake"
        )
    )
    with TestClient(app) as client:
        result = client.post("/auth/register", json={"name": "alice", "password": PWD})
        assert result.status_code == 201
        csrf = {"X-CSRF-Token": result.json()["csrf_token"]}
        assert client.post("/auth/recovery-key", json={"password": PWD}).status_code == 403
        assert (
            client.post("/auth/recovery-key", json={"password": NEW}, headers=csrf).status_code
            == 400
        )
        generated = client.post("/auth/recovery-key", json={"password": PWD}, headers=csrf)
        assert generated.status_code == 200 and generated.headers["cache-control"] == "no-store"
        code = generated.json()["recovery_code"]
        duplicate = client.post("/auth/register", json={"name": "alice", "password": NEW})
        assert duplicate.status_code == 400 and "nombre ya existe" in duplicate.json()["detail"]
        invalid = client.post("/auth/register", json={"name": "name@example.com", "password": NEW})
        assert invalid.status_code == 400 and "Nombre inválido" in invalid.json()["detail"]
        secret = "tiny"
        invalid = client.post(
            "/auth/recover", json={"name": "alice", "password": secret, "recovery_code": code}
        )
        assert secret not in invalid.text and code not in invalid.text
        recovered = client.post(
            "/auth/recover", json={"name": "alice", "password": NEW, "recovery_code": code}
        )
        assert recovered.status_code == 200
        assert not client.get("/auth/status").json()["authenticated"]
        assert client.get("/runs").status_code == 401
        assert (
            client.post("/auth/login", json={"name": "alice", "password": PWD}).status_code == 401
        )
        assert (
            client.post("/auth/login", json={"name": "alice", "password": NEW}).status_code == 200
        )


def test_rescue_rejects_stale_verified_login(tmp_path):
    import asyncio

    from ai_swe.api.profiles import ProfileManager

    manager = ProfileManager(Settings(_env_file=None, profiles_root=tmp_path / "users"))
    stale = manager.store.create("alice", PWD)
    code = manager.store.generate_recovery("alice", PWD)
    manager.store.recover("alice", code, NEW)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as rejected:
        asyncio.run(manager.login(stale))
    assert rejected.value.status_code == 401


def test_recovery_origin_and_active_requests_fail_closed(tmp_path):
    app = crear_app(
        settings=Settings(
            _env_file=None, profile_mode=True, profiles_root=tmp_path / "users", stt_provider="fake"
        )
    )
    with TestClient(app) as client:
        auth = client.post("/auth/register", json={"name": "alice", "password": PWD}).json()
        code = client.post(
            "/auth/recovery-key",
            json={"password": PWD},
            headers={"X-CSRF-Token": auth["csrf_token"]},
        ).json()["recovery_code"]
        payload = {"name": "alice", "password": NEW, "recovery_code": code}
        assert (
            client.post(
                "/auth/recover", json=payload, headers={"Origin": "https://foreign.invalid"}
            ).status_code
            == 403
        )
        context = app.state.profiles.contexts[auth["user"]["id"]]
        context.requests = 1
        assert client.post("/auth/recover", json=payload).status_code == 409
        context.requests = 0
        assert app.state.profiles.store.unlock("alice", PWD).user_id == auth["user"]["id"]
        assert client.post("/auth/recover", json=payload).status_code == 200
