import subprocess

import httpx
import pytest
from test_launch_guide import promoted

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
        env = kwargs["env"]
        assert any("Authorization: Basic " in v for v in env.values())
        assert env["GIT_TERMINAL_PROMPT"] == "0"
        return ""

    monkeypatch.setattr(module, "git", fake_git)
    push(tmp_path, "https://github.com/fixture-owner/my-app.git", "synthetic-pat-for-tests")
    assert not any("Authorization: Basic " in v for v in git_environment().values())
