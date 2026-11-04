import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from ai_swe.api import crear_app
from ai_swe.config import Settings
from ai_swe.security.vault import VaultError, create_vault, open_sealed, seal, unlock_vault
from ai_swe.state.budget_ledger import BudgetLedger, LedgerError
from ai_swe.state.profiles import ProfileStore, UserPaths

PASSWORD = "a long test password"


def test_vault_authenticated_owner_and_password():
    envelope, key = create_vault("owner", PASSWORD, {"hf_token": "private-token"})
    assert "private-token" not in json.dumps(envelope)
    assert unlock_vault("owner", PASSWORD, envelope)[1]["hf_token"] == "private-token"
    for owner, password in [("other", PASSWORD), ("owner", "wrong password")]:
        with pytest.raises(VaultError):
            unlock_vault(owner, password, envelope)
    blob = seal(key, b"backup", b"owner:backup")
    with pytest.raises(VaultError):
        open_sealed(key, blob[:-1] + bytes([blob[-1] ^ 1]), b"owner:backup")
    assert seal(key, b"backup", b"owner:backup") != blob


def test_profile_identity_and_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "GLOBAL-SECRET")
    store = ProfileStore(tmp_path)
    p = store.create(" Alice ", PASSWORD)
    with pytest.raises(ValueError):
        store.create("ALICE", PASSWORD)
    with pytest.raises(ValueError):
        UserPaths.for_user(tmp_path, "../outside")
    unlocked = store.unlock("alice", PASSWORD)
    settings = unlocked.settings(Settings(_env_file=None))
    assert settings.hf_token.get_secret_value() == ""
    assert settings.model_api_key.get_secret_value() == ""
    assert settings.state_db_path == p.paths.database


def test_failed_creation_rollback_releases_name_without_touching_other_profile(tmp_path):
    store = ProfileStore(tmp_path / "users")
    existing = store.create("existing", PASSWORD)
    transient = store.create("temporary", PASSWORD)
    other_store = ProfileStore(tmp_path / "other-users")
    with pytest.raises(ValueError):
        other_store.rollback_creation(transient)
    assert transient.paths.vault.exists()
    store.rollback_creation(transient)
    replacement = store.create("temporary", PASSWORD)
    assert replacement.user_id != transient.user_id
    assert not transient.paths.root.exists()
    assert store.unlock("existing", PASSWORD).user_id == existing.user_id


def test_ledger_atomic_and_unknown_usage(tmp_path):
    ledger = BudgetLedger(tmp_path / "state.sqlite3")
    ledger.set_limit(1)

    def reserve(_):
        try:
            return ledger.reserve("run", 0.6, run_limit=1)
        except LedgerError:
            return None

    with ThreadPoolExecutor(2) as pool:
        ids = list(pool.map(reserve, range(2)))
    assert sum(x is not None for x in ids) == 1
    ledger.settle(next(x for x in ids if x), None)
    assert ledger.summary()["reserved"] == 0.6
    with pytest.raises(LedgerError):
        ledger.reserve("another", 0.5, run_limit=1)


def register(client, name):
    r = client.post("/auth/register", json={"name": name, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()["csrf_token"]


def test_profile_dispatch_cookie_csrf_and_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "GLOBAL-SECRET")
    app = crear_app(
        settings=Settings(
            _env_file=None, profile_mode=True, profiles_root=tmp_path / "users", stt_provider="fake"
        )
    )
    with TestClient(app) as client:
        assert client.get("/auth/status").json()["profile_mode"] is True
        assert client.get("/runs", headers={"X-API-Key": "global"}).status_code == 401
        assert (
            client.post(
                "/auth/register",
                headers={"Origin": "https://evil.test"},
                json={"name": "evil", "password": PASSWORD},
            ).status_code
            == 403
        )
        csrf_a = register(client, "alice")
        cookie_a = client.cookies.get("aiswe_session")
        assert client.post("/runs", json={"instruction": "inspect"}).status_code == 403
        r = client.post(
            "/runs", json={"instruction": "inspect this project"}, headers={"X-CSRF-Token": csrf_a}
        )
        assert r.status_code == 202, r.text
        run = r.json()["run_id"]
        assert client.get("/auth/vault").json()["has_token"] is False
        assert client.post("/auth/logout", headers={"X-CSRF-Token": csrf_a}).status_code == 200
        register(client, "bob")
        assert client.get("/runs").json() == []
        assert client.get("/runs/" + run).status_code == 404
        assert (
            client.post(
                "/runs", json={"instruction": "inspect"}, headers={"X-CSRF-Token": csrf_a}
            ).status_code
            == 403
        )
        client.cookies.set("aiswe_session", cookie_a)
        assert client.get("/runs").status_code == 401


def test_profile_vault_configuration_cookie_flags_and_expiry(tmp_path):
    app = crear_app(
        settings=Settings(
            _env_file=None, profile_mode=True, profiles_root=tmp_path / "users", stt_provider="fake"
        )
    )
    with TestClient(app) as client:
        r = client.post("/auth/register", json={"name": "alice", "password": PASSWORD})
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie and "max-age=" in cookie
        csrf = r.json()["csrf_token"]
        config = dict(
            hf_token="hf_local-test-secret",
            model_name="test-model",
            remote_model_roles=[],
            model_pricing="",
            budget_limit=3,
            max_cost_per_run=1,
        )
        headers = {"X-CSRF-Token": csrf}
        assert (
            client.put(
                "/auth/vault", json=config, headers={**headers, "Origin": "https://evil.test"}
            ).status_code
            == 403
        )
        assert client.put("/auth/vault", json=config, headers=headers).status_code == 200
        body = client.get("/auth/vault").json()
        assert body["has_token"] and body["ledger"]["limit"] == 3
        assert "hf_local-test-secret" not in json.dumps(body)
        context = next(iter(app.state.profiles.contexts.values()))
        assert "hf_local-test-secret" not in context.profile.paths.vault.read_text()
        assert context.app.state.settings.model_api_key.get_secret_value() == "hf_local-test-secret"
        assert client.get("/health").json()["ejecuciones"] == 0
        # Enabling remote without its tariff must fail before any gateway can call.
        assert (
            client.put(
                "/auth/vault", json={**config, "remote_model_roles": ["coder"]}, headers=headers
            ).status_code
            == 422
        )
        session = next(iter(app.state.profiles.sessions.values()))
        session.expires = 0
        assert client.get("/runs").status_code == 401
        assert client.get("/auth/status").json()["authenticated"] is False


def test_login_throttle_and_validation_do_not_echo_secrets(tmp_path):
    app = crear_app(
        settings=Settings(
            _env_file=None, profile_mode=True, profiles_root=tmp_path / "users", stt_provider="fake"
        )
    )
    with TestClient(app) as client:
        register(client, "alice")
        for _ in range(9):
            r = client.post(
                "/auth/login", json={"name": "alice", "password": "wrong-secret-password"}
            )
            assert r.status_code == 401
            assert "wrong-secret-password" not in r.text
        assert (
            client.post("/auth/login", json={"name": "alice", "password": PASSWORD}).status_code
            == 429
        )
        r = client.post("/auth/login", json={"name": "alice", "password": "secret"})
        assert r.status_code == 422 and "secret" not in r.text


def test_gateway_profile_reserves_before_call_and_preserves_unknown(tmp_path):
    from ai_swe.models import ModelMessage, ModelRequest, ModelUsage, gateway_from_settings
    from ai_swe.models.errors import BudgetExceededError, ModelConfigurationError
    from ai_swe.models.providers.fake import FakeModelAdapter

    p = ProfileStore(tmp_path / "users").create("alice", PASSWORD)
    p.save(
        dict(
            model_name="test",
            hf_token="profile-secret",
            max_cost_per_run=1,
            model_pricing=json.dumps([dict(model="test", input_per_1k=0.001, output_per_1k=0.002)]),
        )
    )
    settings = p.settings(Settings(_env_file=None))
    ledger = BudgetLedger(p.paths.database)
    adapter = FakeModelAdapter(model="test")
    gateway = gateway_from_settings(settings, adapters=[adapter])
    request = ModelRequest(
        messages=[ModelMessage(role="user", content="hello")],
        model="test",
        run_id="one",
        max_output_tokens=10,
    )
    with pytest.raises(BudgetExceededError):
        gateway.generate(request)
    assert adapter.calls == []
    ledger.set_limit(2)
    gateway.generate(request)
    assert len(adapter.calls) == 1
    assert ledger.summary()["consumed"] > 0
    unknown = FakeModelAdapter(model="test", usage=ModelUsage())
    unknown_gateway = gateway_from_settings(settings, adapters=[unknown])
    request = request.model_copy(update={"run_id": "two"})
    with pytest.raises(ModelConfigurationError):
        unknown_gateway.generate(request)
    assert ledger.summary()["reserved"] == 1
    with pytest.raises(BudgetExceededError):
        unknown_gateway.generate(request)
    assert len(unknown.calls) == 1
    other = ProfileStore(tmp_path / "other").create("bob", PASSWORD)
    assert BudgetLedger(other.paths.database).summary()["consumed"] == 0


def test_profile_logs_filter_worker_context_and_logout_drains(tmp_path):
    import logging
    import threading

    from ai_swe.graph.worker import RunWorker
    from ai_swe.runtime_logging import (
        close_installed_log_handler,
        installed_log_handler,
        profile_log_context,
    )

    logger = logging.getLogger("ai_swe.profile_test")
    logger.setLevel(logging.INFO)
    started, finish = threading.Event(), threading.Event()

    class Engine:
        def execute(self, run_id):
            started.set()
            finish.wait(5)
            logger.info("only-alice-event")

    handlers = [installed_log_handler(tmp_path / uid, profile_id=uid) for uid in ("a", "b")]
    worker = RunWorker(Engine())
    token = profile_log_context.set("a")
    try:
        worker.submit("run")
    finally:
        profile_log_context.reset(token)
    assert started.wait(5)
    assert worker.active == 1
    finish.set()
    worker.shutdown(wait=True)
    assert worker.active == 0
    for handler in handlers:
        close_installed_log_handler(handler)
    assert "only-alice-event" in (tmp_path / "a/application.log").read_text()
    assert not (tmp_path / "b/application.log").exists()


def test_profile_projects_transcriptions_and_sse_are_private(tmp_path):
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    app = crear_app(
        settings=Settings(
            _env_file=None, profile_mode=True, profiles_root=tmp_path / "users", stt_provider="fake"
        )
    )
    with TestClient(app) as client:
        csrf = register(client, "alice")
        r = client.post(
            "/projects",
            json={"name": "private-project", "repo_path": str(repo)},
            headers={"X-CSRF-Token": csrf},
        )
        assert r.status_code == 201, r.text
        project_id = r.json()["project_id"]
        r = client.post(
            "/runs", json={"instruction": "inspect this project"}, headers={"X-CSRF-Token": csrf}
        )
        run_id = r.json()["run_id"]
        with client.stream("GET", f"/runs/{run_id}/events?timeout_s=2") as response:
            assert response.status_code == 200
            assert any("event:" in line for line in response.iter_lines())
        assert (
            client.post(
                "/transcriptions", files={"audio": ("x.wav", b"123", "audio/wav")}
            ).status_code
            == 403
        )
        register(client, "bob")
        assert client.get("/projects").json() == []
        assert client.get("/projects/" + project_id).status_code == 404
        assert client.get(f"/runs/{run_id}/events?user_id=alice&api_key=global").status_code == 404
        assert client.get("/runs?user_id=alice").json() == []


def test_profile_rejects_repository_inside_private_storage(tmp_path):
    from ai_swe.config import repositorio_autorizado

    store = ProfileStore(tmp_path / "users")
    alice = store.create("alice", PASSWORD)
    bob = store.create("bob", PASSWORD)
    settings = alice.settings(Settings(_env_file=None))
    assert not repositorio_autorizado(settings, bob.paths.worktrees)
    assert not repositorio_autorizado(settings, alice.paths.root)
    assert not repositorio_autorizado(settings, tmp_path)
    assert repositorio_autorizado(settings, tmp_path / "external-repo")
    app = crear_app(
        settings=Settings(
            _env_file=None, profile_mode=True, profiles_root=tmp_path / "users", stt_provider="fake"
        )
    )
    with TestClient(app) as client:
        result = client.post("/auth/login", json={"name": "alice", "password": PASSWORD})
        response = client.post(
            "/runs",
            json={"instruction": "read files", "options": {"repo_path": str(bob.paths.root)}},
            headers={"X-CSRF-Token": result.json()["csrf_token"]},
        )
        assert response.status_code == 403


def test_vault_ciphertext_tamper_and_sensitive_validation(tmp_path):
    import copy

    envelope, _ = create_vault("alice", PASSWORD, {"hf_token": "SECRET"})
    damaged = copy.deepcopy(envelope)
    damaged["data"] = ("A" if damaged["data"][0] != "A" else "B") + damaged["data"][1:]
    with pytest.raises(VaultError):
        unlock_vault("alice", PASSWORD, damaged)
    app = crear_app(
        settings=Settings(
            _env_file=None, profile_mode=True, profiles_root=tmp_path / "users", stt_provider="fake"
        )
    )
    with TestClient(app) as client:
        csrf = register(client, "alice")
        response = client.put(
            "/auth/vault",
            json={"hf_token": {"secret": "do-not-echo"}},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 422
        assert "do-not-echo" not in response.text and "input" not in response.text


def test_normalized_identity_unique_across_store_instances(tmp_path):
    stores = [ProfileStore(tmp_path), ProfileStore(tmp_path)]

    def create(index):
        try:
            return stores[index].create(" Alice " if index else "ALICE", PASSWORD)
        except ValueError:
            return None

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(create, range(2)))
    assert sum(result is not None for result in results) == 1
    assert stores[0].unlock("alice", PASSWORD).name == "alice"


def test_ledger_connections_close_on_success_and_rollback(tmp_path, monkeypatch):
    import sqlite3

    connections = []
    connect = sqlite3.connect

    def tracked(*args, **kwargs):
        connection = connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", tracked)
    ledger = BudgetLedger(tmp_path / "ledger.sqlite3")
    ledger.set_limit(1)
    reservation = ledger.reserve("run", 0.5, run_limit=1)
    ledger.settle(reservation, 0.2)
    assert ledger.summary()["consumed"] == 0.2
    with pytest.raises(LedgerError):
        ledger.set_limit(0.1)
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_four_remote_roles_vault_and_settings(tmp_path):
    app = crear_app(
        settings=Settings(
            _env_file=None, profile_mode=True, profiles_root=tmp_path / "users", stt_provider="fake"
        )
    )
    with TestClient(app) as client:
        r = client.post("/auth/register", json={"name": "carol", "password": PASSWORD})
        csrf = r.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf}
        pricing = json.dumps([{"model": "custom-model", "input_per_1k": 0.001, "output_per_1k": 0.002, "currency": "USD"}])
        config_4roles = dict(
            hf_token="hf_test_secret_token",
            model_name="custom-model",
            remote_model_roles=["coder", "reviewer", "supervisor", "requirements_analyst"],
            model_pricing=pricing,
            budget_limit=10,
            max_cost_per_run=2,
        )
        res = client.put("/auth/vault", json=config_4roles, headers=headers)
        assert res.status_code == 200, res.text
        vault_state = client.get("/auth/vault").json()
        assert vault_state["remote_model_roles"] == ["coder", "reviewer", "supervisor", "requirements_analyst"]
        context = next(iter(app.state.profiles.contexts.values()))
        assert context.app.state.settings.remote_model_roles == ["coder", "reviewer", "supervisor", "requirements_analyst"]


def test_budget_exceeded_error_redacts_secrets():
    from ai_swe.contracts.state import BudgetExceededError
    from ai_swe.security import register_secret

    secret = "secret-token-to-hide-12345"
    register_secret(secret)
    err = BudgetExceededError(f"Presupuesto agotado con {secret}", motivos=(f"motivo: {secret}",))
    assert secret not in str(err)
    assert "[REDACTED]" in str(err)
    assert secret not in err.message
    assert "[REDACTED]" in err.message
    assert secret not in err.motivos[0]
    assert "[REDACTED]" in err.motivos[0]

