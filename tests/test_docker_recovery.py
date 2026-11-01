import json
import os

import pytest

from ai_swe.tools import docker_runner


def test_recovery_does_not_touch_live_session(tmp_path, monkeypatch):
    monkeypatch.setattr(docker_runner, "session_directory", lambda: tmp_path)
    monkeypatch.setattr(docker_runner, "docker_executable", lambda: "docker.exe")
    session = docker_runner.DockerSession()
    try:
        monkeypatch.setattr(session, "run", lambda *a, **kw: pytest.fail("live owner queried"))
        result = docker_runner.recover_stopped_sessions()
        assert result["active"] == 1 and session.root.exists()
    finally:
        session.close()


@pytest.mark.parametrize("phase,expected", [("prepared", "removed"), ("creating", "uncertain")])
def test_recovery_only_removes_confirmed_uncreated_sessions(tmp_path, monkeypatch, phase, expected):
    monkeypatch.setattr(docker_runner, "session_directory", lambda: tmp_path)
    monkeypatch.setattr(docker_runner, "docker_executable", lambda: "docker.exe")
    session = docker_runner.DockerSession()
    session.record(phase)
    session.release()
    monkeypatch.setattr(docker_runner.DockerSession, "run", lambda *a, **kw: "")
    result = docker_runner.recover_stopped_sessions()
    assert result[expected] == 1
    assert session.root.exists() == (phase == "creating")


def test_recovery_rejects_journal_with_arbitrary_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(docker_runner, "session_directory", lambda: tmp_path)
    root = tmp_path / "aiswe-docker-abcdefgh"
    root.mkdir()
    (root / "execution.json").write_text(json.dumps({"version": 1, "owner": "other-app"}))
    (root / "keep.txt").write_text("preserve")
    result = docker_runner.recover_stopped_sessions()
    assert result["unresolved"] == 1 and (root / "keep.txt").read_text() == "preserve"


@pytest.mark.parametrize("running", [True, False])
def test_recovery_leaves_running_container_and_only_removes_owned_stopped_one(
    tmp_path, monkeypatch, running,
):
    monkeypatch.setattr(docker_runner, "session_directory", lambda: tmp_path)
    monkeypatch.setattr(docker_runner, "docker_executable", lambda: "docker.exe")
    session = docker_runner.DockerSession()
    session.cid = "a" * 64
    session.image = "sha256:" + "b" * 64
    session.record("created")
    session.release()
    removed = []

    def run(self, arguments, **kwargs):
        if arguments[:2] == ["container", "inspect"]:
            return json.dumps([{"Config": {"Image": session.image, "Labels": {
                "io.aiswe.execution": session.owner, "io.aiswe.session": session.root.name}},
                "State": {"Running": running}}])
        if arguments[:2] == ["container", "rm"]:
            removed.append(arguments[-1])
            return ""
        return "" if removed else session.cid

    monkeypatch.setattr(docker_runner.DockerSession, "run", run)
    result = docker_runner.recover_stopped_sessions()
    assert result["running" if running else "removed"] == 1
    assert removed == ([] if running else [session.cid])
    assert session.root.exists() == running


def test_recovery_ignores_unknown_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(docker_runner, "session_directory", lambda: tmp_path)
    root = tmp_path / "other-application"
    root.mkdir()
    result = docker_runner.recover_stopped_sessions()
    assert result["removed"] == 0 and root.exists()


def test_recovery_preserves_data_when_daemon_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(docker_runner, "session_directory", lambda: tmp_path)
    monkeypatch.setattr(docker_runner, "docker_executable", lambda: "docker.exe")
    session = docker_runner.DockerSession()
    session.release()

    def unavailable(*a, **kw):
        raise docker_runner.DockerError("Motor detenido")

    monkeypatch.setattr(docker_runner.DockerSession, "run", unavailable)
    result = docker_runner.recover_stopped_sessions()
    assert result["unresolved"] == 1 and session.root.exists()


def test_recovery_rejects_hardlinked_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(docker_runner, "session_directory", lambda: tmp_path)
    monkeypatch.setattr(docker_runner, "docker_executable", lambda: "docker.exe")
    session = docker_runner.DockerSession()
    session.release()
    os.link(session.root / "execution.json", tmp_path / "foreign.json")
    monkeypatch.setattr(docker_runner.DockerSession, "run", lambda *a, **kw: pytest.fail("queried"))
    assert docker_runner.recover_stopped_sessions()["unresolved"] == 1
    assert (tmp_path / "foreign.json").exists() and session.root.exists()


def test_recovery_rejects_hardlinked_lock_without_writing_foreign_file(tmp_path, monkeypatch):
    monkeypatch.setattr(docker_runner, "session_directory", lambda: tmp_path)
    monkeypatch.setattr(docker_runner, "docker_executable", lambda: "docker.exe")
    session = docker_runner.DockerSession()
    session.release()
    foreign = tmp_path / "foreign.sqlite3"
    foreign.write_bytes(b"")
    os.link(foreign, session.root.with_suffix(".lock"))
    assert docker_runner.recover_stopped_sessions()["unresolved"] == 1
    assert foreign.read_bytes() == b"" and session.root.exists()


def test_recovery_rejects_container_from_different_session(tmp_path, monkeypatch):
    monkeypatch.setattr(docker_runner, "session_directory", lambda: tmp_path)
    monkeypatch.setattr(docker_runner, "docker_executable", lambda: "docker.exe")
    session = docker_runner.DockerSession()
    session.cid, session.image = "a" * 64, "sha256:" + "b" * 64
    session.record("created")
    session.release()

    def run(self, arguments, **kwargs):
        assert arguments[:2] != ["container", "rm"]
        if arguments[:2] == ["container", "inspect"]:
            return json.dumps([{"Config": {"Image": session.image, "Labels": {
                "io.aiswe.execution": session.owner, "io.aiswe.session": "another-session"}},
                "State": {"Running": False}}])
        return session.cid

    monkeypatch.setattr(docker_runner.DockerSession, "run", run)
    assert docker_runner.recover_stopped_sessions()["unresolved"] == 1
    assert session.root.exists()


@pytest.mark.parametrize("profiles", [False, True])
def test_api_startup_runs_recovery_only_when_docker_is_requested(tmp_path, monkeypatch, profiles):
    from fastapi.testclient import TestClient

    from ai_swe.api import crear_app
    from ai_swe.config import Settings

    calls = []
    report = {"removed": 0, "unresolved": 1}
    monkeypatch.setattr(docker_runner, "recover_stopped_sessions", lambda: (
        calls.append(1) or report))
    settings = Settings(_env_file=None, profile_mode=profiles, stt_provider="fake",
                        state_db_path=tmp_path / "state.sqlite3", profiles_root=tmp_path / "users",
                        runner_docker=docker_runner.DockerSettings())
    app = crear_app(settings=settings)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert app.state.docker_recovery == report
    assert calls == [1]
    with TestClient(crear_app(settings=settings.model_copy(update={"runner_docker": None}))):
        pass
    assert calls == [1]
