"""Offline project creation, path safety, and profile boundaries."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ai_swe.api import crear_app
from ai_swe.config import Settings
from ai_swe.projects import crear_proyecto_git
from ai_swe.sandbox import SandboxError


def settings(tmp_path):
    return Settings(
        _env_file=None,
        profile_mode=False,
        state_db_path=tmp_path / "private" / "state.sqlite3",
        workspace_root=tmp_path / "internal",
        profiles_root=tmp_path / "users",
        log_dir=tmp_path / "logs",
        cache_dir=tmp_path / "cache",
        stt_download_root=tmp_path / "speech",
        authorized_repos=[tmp_path],
    )


@pytest.mark.parametrize("empty", [False, True])
def test_initial_commit_and_existing_registration(tmp_path, empty):
    path = tmp_path / "new"
    if empty:
        path.mkdir()
    with TestClient(crear_app(settings=settings(tmp_path))) as client:
        body = {"name": "Calendar", "repo_path": str(path), "create_if_missing": True}
        response = client.post("/projects", json=body)
        assert response.status_code == 201, response.text
        assert (path / "README.md").read_text().startswith("# Calendar")
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0 and len(result.stdout.strip()) == 40
        assert client.post("/projects", json=body).status_code == 422
        body["create_if_missing"] = False
        assert client.post("/projects", json=body).status_code == 201


def test_invalid_paths_never_invoke_git_or_create(tmp_path, monkeypatch):
    config = settings(tmp_path)
    monkeypatch.setattr(
        "ai_swe.projects.subprocess.run", lambda *a, **k: pytest.fail("Git must not run")
    )
    for raw in [
        "relative",
        "https://example.org/new",
        str(tmp_path / "users" / "new"),
        str(tmp_path / "internal" / "new"),
        str(tmp_path.parent / "outside-new"),
        str(tmp_path / "missing-parent" / "new"),
    ]:
        with pytest.raises(SandboxError):
            crear_proyecto_git(raw, "new", config)
    assert not (tmp_path / "users").exists()
    assert not (tmp_path / "missing-parent").exists()


def test_nonempty_directory_untouched(tmp_path, monkeypatch):
    target = tmp_path / "existing"
    target.mkdir()
    (target / "valuable.txt").write_text("keep")
    monkeypatch.setattr(
        "ai_swe.projects.subprocess.run", lambda *a, **k: pytest.fail("Git must not run")
    )
    with pytest.raises(SandboxError):
        crear_proyecto_git(str(target), "new", settings(tmp_path))
    assert list(target.iterdir()) == [target / "valuable.txt"]
    assert (target / "valuable.txt").read_text() == "keep"


def test_linked_private_path_denied(tmp_path, monkeypatch):
    private = tmp_path / "users"
    private.mkdir()
    link = tmp_path / "shortcut"
    try:
        link.symlink_to(private, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink privilege unavailable")
    monkeypatch.setattr(
        "ai_swe.projects.subprocess.run", lambda *a, **k: pytest.fail("Git must not run")
    )
    with pytest.raises(SandboxError):
        crear_proyecto_git(str(link / "new"), "new", settings(tmp_path))
    assert not (private / "new").exists()


def test_profile_cookie_csrf_and_project_isolation(tmp_path):
    config = settings(tmp_path).model_copy(update={"profile_mode": True})
    target = tmp_path / "calendar"
    body = {"name": "Calendar", "repo_path": str(target), "create_if_missing": True}
    with TestClient(crear_app(settings=config)) as client:
        assert client.post("/projects", json=body).status_code == 401
        csrf = client.post(
            "/auth/register", json={"name": "alice", "password": "a long test password"}
        ).json()["csrf_token"]
        assert client.post("/projects", json=body).status_code == 403
        assert not target.exists()
        response = client.post("/projects", json=body, headers={"X-CSRF-Token": csrf})
        assert response.status_code == 201, response.text
        project_id = response.json()["project_id"]
        client.post("/auth/logout", headers={"X-CSRF-Token": csrf})
        client.post("/auth/register", json={"name": "bob", "password": "a long test password"})
        assert client.get("/projects").json() == []
        assert client.get("/projects/" + project_id).status_code == 404


def test_reparse_ancestor_rejected_before_mutation(tmp_path, monkeypatch):
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == tmp_path:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(SandboxError):
        crear_proyecto_git(str(tmp_path / "new"), "new", settings(tmp_path))
    assert not (tmp_path / "new").exists()


def test_failed_git_preserves_partial_and_cleans_only_claim(tmp_path, monkeypatch):
    target = tmp_path / "partial"
    calls = []
    monkeypatch.setenv("GIT_DIR", "must-not-inherit")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")

    def fail(command, **kwargs):
        calls.append(command)
        assert "GIT_DIR" not in kwargs["env"]
        assert "GIT_CONFIG_COUNT" not in kwargs["env"]
        assert kwargs["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["shell"] is False and kwargs["timeout"] == 30
        assert "--template=" in command
        (target / "partial-owned.txt").write_text("review me")
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr("ai_swe.projects.subprocess.run", fail)
    with pytest.raises(SandboxError):
        crear_proyecto_git(str(target), "new", settings(tmp_path))
    assert len(calls) == 1
    assert (target / "partial-owned.txt").read_text() == "review me"
    assert not (target / ".aiswe-bootstrap-lock").exists()


def test_concurrent_claim_untouched(tmp_path, monkeypatch):
    target = tmp_path / "claimed"
    claim = target / ".aiswe-bootstrap-lock"
    claim.mkdir(parents=True)
    monkeypatch.setattr(
        "ai_swe.projects.subprocess.run", lambda *a, **k: pytest.fail("Git must not run")
    )
    with pytest.raises(SandboxError):
        crear_proyecto_git(str(target), "new", settings(tmp_path))
    assert claim.is_dir()


@pytest.mark.parametrize("folder", ["private", "logs", "cache", "speech"])
def test_internal_paths_rejected_before_mutation(tmp_path, monkeypatch, folder):
    monkeypatch.setattr(
        "ai_swe.projects.subprocess.run", lambda *a, **k: pytest.fail("Git must not run")
    )
    with pytest.raises(SandboxError):
        crear_proyecto_git(str(tmp_path / folder / "new"), "new", settings(tmp_path))
    assert not (tmp_path / folder).exists()


def test_missing_git_does_not_create_folder(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_swe.projects.shutil.which", lambda name: None)
    with pytest.raises(SandboxError, match="Git"):
        crear_proyecto_git(str(tmp_path / "new"), "new", settings(tmp_path))
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("value", ["true", 1, "false"])
def test_creation_requires_literal_boolean(tmp_path, value):
    with TestClient(crear_app(settings=settings(tmp_path))) as client:
        assert (
            client.post(
                "/projects",
                json={
                    "name": "new",
                    "repo_path": str(tmp_path / "new"),
                    "create_if_missing": value,
                },
            ).status_code
            == 422
        )
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("metadata_name", [".git", ".GiT", ".git.", ".git "])
def test_git_metadata_target_rejected_without_mutation(tmp_path, monkeypatch, metadata_name):
    metadata = tmp_path / "existing" / ".git"
    refs = metadata / "refs"
    refs.mkdir(parents=True)
    head = metadata / "HEAD"
    head.write_text("ref: refs/heads/main\n")
    target = tmp_path / "existing" / metadata_name / "refs" / "new-project"
    monkeypatch.setattr(
        "ai_swe.projects.subprocess.run", lambda *a, **k: pytest.fail("Git must not run")
    )
    with pytest.raises(SandboxError, match="metadatos"):
        crear_proyecto_git(str(target), "new", settings(tmp_path))
    assert not target.exists()
    assert list(refs.iterdir()) == []
    assert head.read_text() == "ref: refs/heads/main\n"


@pytest.mark.parametrize("component", ["private.", "users ", "file:stream"])
def test_ambiguous_components_rejected_without_mutation(tmp_path, monkeypatch, component):
    monkeypatch.setattr(
        "ai_swe.projects.subprocess.run", lambda *a, **k: pytest.fail("Git must not run")
    )
    with pytest.raises(SandboxError, match="ambiguos"):
        crear_proyecto_git(str(tmp_path / component / "new"), "new", settings(tmp_path))
    assert not (tmp_path / component).exists()
