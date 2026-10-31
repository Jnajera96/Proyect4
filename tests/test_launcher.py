import socket
import sys
from types import SimpleNamespace

import pytest

from ai_swe import launcher
from ai_swe.config import Settings
from ai_swe.resources import frontend_dist


@pytest.fixture(autouse=True)
def isolated_profile_mode(monkeypatch):
    monkeypatch.setenv("AI_SWE_PROFILE_MODE", "false")


def test_listener_is_loopback_and_reserved():
    with launcher.reserve_listener(0) as listener:
        address = listener.getsockname()
        assert address[0] == "127.0.0.1" and address[1] > 0
        with socket.socket() as other, pytest.raises(OSError):
            other.bind(address)


def test_occupied_port_uses_different_available_port():
    with (
        launcher.reserve_listener(0) as first,
        launcher.reserve_listener(first.getsockname()[1]) as second,
    ):
        assert first.getsockname()[1] != second.getsockname()[1]


def test_frozen_assets_are_inside_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert frontend_dist() == tmp_path / "frontend" / "dist"
    assert Settings(_env_file=None).runtime_mode == "installed"


def test_invalid_config_error_does_not_echo_input(monkeypatch, capsys):
    monkeypatch.setenv("AI_SWE_PORT", "synthetic-private-value")
    assert launcher.main(["--no-browser"]) == 1
    error = capsys.readouterr().err
    assert "port" in error and "synthetic-private-value" not in error


def test_missing_assets_returns_readable_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "frontend_dist", lambda: tmp_path)
    assert launcher.main(["--no-browser"]) == 1
    assert "Faltan archivos" in capsys.readouterr().err


def test_dead_server_does_not_open_browser():
    with pytest.raises(RuntimeError):
        launcher.wait_for_health("http://127.0.0.1:1", SimpleNamespace(is_alive=lambda: False), 1)


def test_timeout_does_not_open_browser():
    with pytest.raises(TimeoutError):
        launcher.wait_for_health("http://127.0.0.1:1", SimpleNamespace(is_alive=lambda: True), 0.01)


def test_startup_exception_is_reported_without_details(monkeypatch, capsys):
    def fail(**kwargs):
        raise RuntimeError("synthetic-private-value")
    monkeypatch.setattr(launcher, "serve", fail)
    assert launcher.main(["--no-browser"]) == 1
    assert "synthetic-private-value" not in capsys.readouterr().err


def test_frozen_runner_uses_only_closed_worker_targets(monkeypatch):
    from ai_swe.tools.runner import comando_de

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert comando_de("pytest.unit") == (sys.executable, "--run-test-target", "pytest.unit")
    assert comando_de("arbitrary.module") is None


def test_worker_rejects_arbitrary_python_modules():
    with pytest.raises(SystemExit):
        launcher.main(["--run-test-target", "arbitrary.module"])


@pytest.mark.parametrize(
    "arguments,expected", [([], True), (["--profiles"], True), (["--no-profiles"], False)]
)
def test_launcher_defaults_to_user_registration_even_with_legacy_environment(
    monkeypatch, arguments, expected
):
    monkeypatch.setenv("AI_SWE_PROFILE_MODE", "false")
    observed = []

    def serve(**kwargs):
        observed.append(Settings(_env_file=None).profile_mode)
        return 0

    monkeypatch.setattr(launcher, "serve", serve)
    assert launcher.main([*arguments, "--no-browser"]) == 0
    assert observed == [expected]


def test_browser_opens_actual_url_only_after_health(tmp_path, monkeypatch):
    import uvicorn

    import ai_swe.api

    (tmp_path / "index.html").write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(launcher, "frontend_dist", lambda: tmp_path)
    monkeypatch.setattr(launcher, "load_settings", lambda **kwargs: SimpleNamespace(port=0))
    monkeypatch.setattr(ai_swe.api, "crear_app", lambda: object())
    events = []

    class Server:
        def __init__(self, config):
            assert config.timeout_keep_alive == 3
            assert config.timeout_graceful_shutdown == 5
            self.started = False
            self.should_exit = False

        async def serve(self, **kwargs):
            import asyncio

            self.started = True
            while not self.should_exit:
                await asyncio.sleep(0.001)
            events.append("shutdown")

    monkeypatch.setattr(uvicorn, "Server", Server)
    monkeypatch.setattr(launcher, "wait_for_health", lambda *args: events.append("healthy"))
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url, **kw: events.append(url) or True)
    assert launcher.serve(exit_after=0.01) == 0
    assert events[0] == "healthy"
    assert events[1].startswith("http://127.0.0.1:") and events[1].endswith("/app/")
    assert events[2] == "shutdown"


def test_shutdown_timeout_is_bounded_and_never_reported_as_success(tmp_path, monkeypatch):
    import uvicorn

    import ai_swe.api

    (tmp_path / "index.html").write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(launcher, "frontend_dist", lambda: tmp_path)
    monkeypatch.setattr(launcher, "load_settings", lambda **kwargs: SimpleNamespace(port=0))
    monkeypatch.setattr(ai_swe.api, "crear_app", lambda: object())
    listener = launcher.reserve_listener(0)
    monkeypatch.setattr(launcher, "reserve_listener", lambda port: listener)
    monkeypatch.setattr(launcher, "wait_for_health", lambda *args: None)
    joins = []

    class StuckThread:
        def __init__(self, **kwargs):
            pass

        def start(self):
            pass

        def is_alive(self):
            return True

        def join(self, timeout=None):
            joins.append(timeout)

    monkeypatch.setattr(uvicorn, "Server", lambda config: SimpleNamespace(started=True))
    monkeypatch.setattr(launcher.threading, "Thread", StuckThread)
    with pytest.raises(RuntimeError, match="10 segundos"):
        launcher.serve(open_browser=False, exit_after=0)
    assert joins == [10]
    assert listener.fileno() == -1
