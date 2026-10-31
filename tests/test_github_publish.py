import subprocess
import traceback
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from test_launch_guide import promoted

from ai_swe.api import crear_app
from ai_swe.config import Settings
from ai_swe.github_publish import (
    GitHubPublishRequest,
    create_repository,
    git_environment,
    publish,
    push,
)


def request():
    return GitHubPublishRequest(repo_name="my-app", pat_token="synthetic-pat-for-tests")


def init(root):
    def git(*args):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    git("init", "-q")
    (root / "README.md").write_text("My app")
    git("add", "README.md")
    git("-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-qm", "initial")
    return git


def test_github_api_is_mocked_private_and_token_not_in_url(monkeypatch):
    import ai_swe.models.providers.github_repository as module

    actual = httpx.Client

    def handle(req):
        assert str(req.url) == "https://api.github.com/user/repos"
        assert req.headers["Authorization"] == "Bearer synthetic-pat-for-tests"
        assert b'"private":true' in req.content
        return httpx.Response(201, json={"owner": {"login": "fixture-owner"}})

    monkeypatch.setattr(
        module.httpx, "Client", lambda **kw: actual(transport=httpx.MockTransport(handle), **kw)
    )
    assert create_repository(request()) == "https://github.com/fixture-owner/my-app.git"
    assert "synthetic" not in repr(request())


def test_commit_contains_only_approved_files_and_no_token(tmp_path, monkeypatch):
    import ai_swe.github_publish as module

    state = promoted(tmp_path)
    root = tmp_path / "application"
    init(root)
    monkeypatch.setattr(
        "ai_swe.models.providers.github_repository.validate_token", lambda _: "fixture-owner"
    )
    (root / ".env").write_text("SECRET=do-not-publish")
    monkeypatch.setattr(
        module, "create_repository", lambda _: "https://github.com/fixture-owner/my-app.git"
    )
    monkeypatch.setattr(module, "push", lambda *args: None)
    result = publish(state, request())
    assert result["published"]
    names = module.git(root, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    assert sorted(names) == ["README.md", "index.html"]
    config = (root / ".git/config").read_text()
    assert "synthetic-pat" not in config and "https://github.com/fixture-owner/my-app.git" in config


def test_existing_remote_prevents_network_and_mutations(tmp_path, monkeypatch):
    import ai_swe.github_publish as module

    state = promoted(tmp_path)
    git = init(tmp_path / "application")
    git("remote", "add", "origin", "https://github.com/existing/project.git")
    monkeypatch.setattr(module, "create_repository", lambda _: pytest.fail("network must not run"))
    with pytest.raises(ValueError, match="remota"):
        publish(state, request())


def test_push_credentials_only_in_ephemeral_environment(tmp_path, monkeypatch):
    import ai_swe.github_publish as module

    def fake_git(root, *args, **kwargs):
        assert "synthetic-pat" not in repr(args)
        assert "--force" not in args
        if args[0] == "symbolic-ref":
            return "main"
        assert args[:4] == ("push", "--no-verify", "-u", "origin")
        env = kwargs["env"]
        assert any("Authorization: Basic " in v for v in env.values())
        assert env["GIT_TERMINAL_PROMPT"] == "0"
        return ""

    monkeypatch.setattr(module, "git", fake_git)
    push(tmp_path, "https://github.com/fixture-owner/my-app.git", "synthetic-pat-for-tests")
    assert not any("Authorization: Basic " in v for v in git_environment().values())


@pytest.fixture
def github_http(monkeypatch):
    import ai_swe.models.providers.github_repository as module

    actual = httpx.Client

    def install(handler):
        monkeypatch.setattr(
            module.httpx,
            "Client",
            lambda **kw: actual(transport=httpx.MockTransport(handler), **kw),
        )

    return install


@pytest.mark.parametrize(
    "scopes,accepted", [("repo, user", True), ("public_repo", False), ("", False)]
)
def test_validate_identity_requires_explicit_repo_scope(github_http, scopes, accepted):
    from ai_swe.models.providers.github_repository import validate_token

    def handle(req):
        assert req.method == "GET" and str(req.url) == "https://api.github.com/user"
        assert req.headers["Authorization"] == "Bearer synthetic-pat-for-tests"
        return httpx.Response(
            200, headers={"X-OAuth-Scopes": scopes}, json={"login": "fixture-owner"}
        )

    github_http(handle)
    if accepted:
        assert validate_token(request().pat_token.get_secret_value()) == "fixture-owner"
    else:
        with pytest.raises(ValueError, match="PAT clásico"):
            validate_token(request().pat_token.get_secret_value())


@pytest.mark.parametrize("status", [401, 403, 422, 500])
def test_creation_errors_never_echo_remote_body_or_pat(github_http, status, caplog):
    token = request().pat_token.get_secret_value()
    github_http(lambda req: httpx.Response(status, json={"message": token}))
    with pytest.raises(ValueError) as exc:
        create_repository(request())
    assert token not in "".join(traceback.format_exception(exc.value)) + caplog.text


@pytest.mark.parametrize("operation", ["validate", "create"])
def test_network_errors_and_invalid_identity_are_sanitized(github_http, operation):
    from ai_swe.models.providers.github_repository import validate_token

    token = request().pat_token.get_secret_value()

    def fail(req):
        raise httpx.ConnectError(token, request=req)

    github_http(fail)
    with pytest.raises(ValueError) as exc:
        validate_token(token) if operation == "validate" else create_repository(request())
    assert token not in "".join(traceback.format_exception(exc.value))


def test_organization_repository_creation(github_http):
    def handle(req):
        assert str(req.url) == "https://api.github.com/orgs/fixture-org/repos"
        assert b'"private":false' in req.content
        return httpx.Response(201, json={"owner": {"login": "fixture-org"}})

    github_http(handle)
    req = request().model_copy(update={"organization": "fixture-org", "private": False})
    assert create_repository(req) == "https://github.com/fixture-org/my-app.git"


def test_draft_cannot_create_remote_or_commit(tmp_path, monkeypatch):
    import ai_swe.github_publish as module

    state = promoted(tmp_path)
    state.status = "needs_human"
    state.artifacts.worktree_path = state.options.repo_path
    monkeypatch.setattr(module, "create_repository", lambda _: pytest.fail("No network"))
    with pytest.raises(ValueError, match="aprueba"):
        publish(state, request())


def test_real_git_push_failure_is_sanitized(tmp_path, monkeypatch):
    import ai_swe.github_publish as module

    token = request().pat_token.get_secret_value()

    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired(token, 60, stderr=token)

    monkeypatch.setattr(module.subprocess, "run", fail)
    with pytest.raises(ValueError) as exc:
        module.git(tmp_path, "push")
    assert token not in "".join(traceback.format_exception(exc.value))


@pytest.mark.parametrize("stream", [False, True])
def test_endpoint_publishes_with_real_commit_and_mock_http(
    tmp_path, monkeypatch, github_http, stream, caplog
):
    import json

    import ai_swe.github_publish as module

    state = promoted(tmp_path)
    root = tmp_path / "application"
    init(root)
    seen = []

    def handle(req):
        seen.append(req.method)
        if req.method == "GET":
            return httpx.Response(
                200, headers={"X-OAuth-Scopes": "repo"}, json={"login": "fixture-owner"}
            )
        return httpx.Response(201, json={"owner": {"login": "fixture-owner"}})

    github_http(handle)
    pushed = []
    monkeypatch.setattr(module, "push", lambda *args: pushed.append(args))
    app = crear_app(
        settings=Settings(
            _env_file=None,
            profile_mode=False,
            state_db_path=tmp_path / "api.sqlite3",
            api_keys={"admin-fixture": "admin", "reader-fixture": "reader"},
        )
    )
    monkeypatch.setattr(app.state.engine, "get", lambda _: state)
    monkeypatch.setattr(app.state.store, "proyecto", lambda _: SimpleNamespace(repo_path=str(root)))
    monkeypatch.setattr(
        app.state.store, "list_summaries", lambda **_: [SimpleNamespace(run_id=state.run_id)]
    )
    body = {"repo_name": "my-app", "pat_token": "synthetic-pat-for-tests", "private": True}
    with TestClient(app) as client:
        path = "/projects/fixture/publish-github" + ("?stream=true" if stream else "")
        assert client.post(path, json=body).status_code == 401
        assert (
            client.post(path, json=body, headers={"X-API-Key": "reader-fixture"}).status_code == 403
        )
        response = client.post(path, json=body, headers={"X-API-Key": "admin-fixture"})
        assert response.status_code == 200
        if stream:
            events = [json.loads(line) for line in response.text.splitlines()]
            assert [e["stage"] for e in events[:-1]] == ["validating", "creating", "uploading"]
            result = events[-1]
        else:
            result = response.json()
        assert result["published"] and result["url"] == "https://github.com/fixture-owner/my-app"
        assert body["pat_token"] not in response.text
        # A rejected request must not echo a secret in FastAPI's validation errors.
        invalid = client.post(
            path,
            json={**body, "repo_name": "bad name", "pat_token": "badsecret"},
            headers={"X-API-Key": "admin-fixture"},
        )
        assert invalid.status_code == 422 and "badsecret" not in invalid.text
    assert seen == ["GET", "POST"] and len(pushed) == 1
    assert body["pat_token"] not in caplog.text
    assert body["pat_token"].encode() not in (tmp_path / "api.sqlite3").read_bytes()
    assert body["pat_token"] not in (root / ".git/config").read_text()


def test_invalid_pat_does_not_create_remote_or_mutate_git(tmp_path, monkeypatch, github_http):
    import ai_swe.github_publish as module

    state = promoted(tmp_path)
    root = tmp_path / "application"
    init(root)
    before = module.git(root, "rev-parse", "HEAD")
    seen = []

    def handle(req):
        seen.append(req.method)
        return httpx.Response(401, json={"message": "synthetic-pat-for-tests"})

    github_http(handle)
    with pytest.raises(ValueError, match="rechazó"):
        publish(state, request())
    assert seen == ["GET"]
    assert module.git(root, "rev-parse", "HEAD") == before
    assert module.git(root, "remote") == ""


def test_secret_in_initial_history_blocks_network(tmp_path, monkeypatch):
    import ai_swe.github_publish as module

    state = promoted(tmp_path)
    root = tmp_path / "application"
    init(root)
    (root / "README.md").write_text("ghp_syntheticsecret")
    module.git(root, "add", "README.md")
    module.git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@localhost",
        "commit",
        "--amend",
        "--no-edit",
    )
    (root / "README.md").write_text("clean today")
    monkeypatch.setattr(module, "create_repository", lambda _: pytest.fail("No network"))
    with pytest.raises(ValueError, match="historial"):
        publish(state, request())
