import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ai_swe.cancellation import CancellationToken, RunCancelled, cancellation_scope
from ai_swe.tools import docker_runner
from ai_swe.tools.docker_runner import DockerError, DockerSettings
from ai_swe.tools.runner import RunnerError, ejecutar


@pytest.mark.parametrize("values", [
    {"image": "python:latest"}, {"memory_mb": 0}, {"cpus": float("nan")},
    {"cpu_seconds": 0}, {"pids_limit": 2}, {"network": "host"},
])
def test_docker_policy_rejects_mutable_images_and_invalid_limits(values):
    with pytest.raises(ValidationError):
        DockerSettings(**values)


def test_explicit_docker_failure_never_falls_back_to_native(tmp_path, monkeypatch):
    def fail(*args):
        raise DockerError("Imagen ausente")

    monkeypatch.setattr(docker_runner, "execute", fail)
    monkeypatch.setattr("ai_swe.tools.runner._capturar", lambda *a: pytest.fail("native fallback"))
    with pytest.raises(RunnerError, match="Imagen ausente"):
        ejecutar(SimpleNamespace(raiz=tmp_path), "pytest.unit", permitidos=("pytest.unit",),
                 docker=DockerSettings())


def test_docker_timeout_records_docker_command_not_native_python(tmp_path, monkeypatch):
    command = ["docker.exe", "container", "start", "--attach", "synthetic-cid"]

    def timeout(*args):
        raise subprocess.TimeoutExpired(command, 1, output="last output")

    monkeypatch.setattr(docker_runner, "execute", timeout)
    result = ejecutar(SimpleNamespace(raiz=tmp_path), "pytest.unit",
                      permitidos=("pytest.unit",), docker=DockerSettings())
    assert result.exit_code == 124 and result.argv == command
    assert result.stdout == "last output"


def test_failed_cleanup_blocks_parent_cancellation_and_preserves_journal(tmp_path, monkeypatch):
    root = tmp_path / "aiswe-docker-test"
    root.mkdir()
    control = CancellationToken()
    with cancellation_scope(control.child()):
        monkeypatch.setattr(docker_runner, "docker_executable", lambda: "docker.exe")
        monkeypatch.setattr(docker_runner.tempfile, "mkdtemp", lambda **kw: str(root))
        session = docker_runner.DockerSession()
    session.create_started = True
    monkeypatch.setattr(session, "run", lambda *a, **kw: (
        _ for _ in ()).throw(DockerError("offline")))
    with pytest.raises(DockerError, match="sin verificar"):
        session.close()
    assert control.cleanup_error and root.exists()
    assert json.loads((root / "recovery.json").read_text())["owner_label"] == session.label


def test_missing_docker_image_blocks_coder_before_model_call(tmp_path, monkeypatch):
    from test_cooperative_cancellation import repository, settings_for
    from test_project_builder_pipeline import BuilderAdapter, project_files

    from ai_swe.contracts import RunOptions
    from ai_swe.graph import RunEngine, model_routing
    from ai_swe.models import ModelGateway
    from ai_swe.readiness import check_readiness
    from ai_swe.state import RunStore

    settings = settings_for(tmp_path).model_copy(update={"runner_docker": DockerSettings()})
    repo = repository(tmp_path)
    adapter = BuilderAdapter(project_files("calendar"))
    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: ModelGateway([adapter]))
    monkeypatch.setattr(docker_runner, "check_ready", lambda _: (_ for _ in ()).throw(
        DockerError("Falta imagen local")))
    report = check_readiness(settings, str(repo))
    assert not report.ready
    check = next(c for c in report.checks if c.code == "DOCKER")
    assert not check.ready and check.action == "configure_runner"
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado("crea un calendario", options=RunOptions(repo_path=str(repo)))
        assert engine.start(state).status == "awaiting_human_requirements_confirmation"
        result = engine.resume(state.run_id, "approved")
        assert result.status == "needs_human"
        assert any(e.error_class == "RUNNER_NOT_READY" for e in result.errors)
        assert not adapter.calls


IMAGE = os.environ.get("AI_SWE_TEST_DOCKER_IMAGE", "")
real = pytest.mark.skipif(not IMAGE or os.name != "nt", reason="Opt-in local Docker image required")


def run_source(tmp_path, code, *, target="pytest.unit", timeout=20, **limits):
    (tmp_path / "test_generated.py").write_text(code, encoding="utf-8")
    return ejecutar(SimpleNamespace(raiz=tmp_path), target, permitidos=(target,), timeout=timeout,
                    docker=DockerSettings(image=IMAGE, **limits))


@real
def test_real_docker_runs_isolated_code_without_host_secrets_or_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "synthetic-host-secret")
    (tmp_path / ".env").write_text("synthetic-host-secret")
    code = '''import os, signal, socket
from pathlib import Path

def test_isolation():
    assert os.getuid() == 65532
    fields = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines()
                  if ':' in line)
    assert int(fields['CapEff'].strip(), 16) == 0
    assert fields['NoNewPrivs'].strip() == '1' and fields['Seccomp'].strip() == '2'
    assert int(Path('/sys/fs/cgroup/memory.max').read_text()) == 512 * 1024 * 1024
    assert int(Path('/sys/fs/cgroup/pids.max').read_text()) == 32
    assert 'HF_TOKEN' not in os.environ and not Path('.env').exists()
    assert not Path('/input/.env').exists()
    for path in ('/input/test_generated.py', '/etc/host-write'):
        try:
            Path(path).write_text('escape')
        except OSError:
            pass
        else:
            raise AssertionError('write escaped')
    try:
        os.kill(1, signal.SIGSTOP)
    except PermissionError:
        pass
    else:
        raise AssertionError('watchdog exposed')
    connection = socket.socket()
    connection.settimeout(.2)
    try:
        connection.connect(('1.1.1.1', 443))
    except OSError:
        pass
    else:
        raise AssertionError('network exposed')
    finally:
        connection.close()
    Path('generated.txt').write_text('container only')
'''
    result = run_source(tmp_path, code)
    assert result.exit_code == 0, result.stderr + result.stdout
    assert "1 passed" in result.stdout
    assert not (tmp_path / "generated.txt").exists()
    assert (tmp_path / "test_generated.py").read_text(encoding="utf-8") == code
    assert any(arg.startswith("io.aiswe.snapshot=") for arg in result.argv)


@real
@pytest.mark.parametrize("target,code,expected", [
    ("pytest.unit", "def test_failure():\n    assert False\n", 1),
    ("ruff.check", "def test_valid():\n    assert True\n", 0),
    ("pytest.unit", "def test_busy():\n    while True:\n        pass\n", 126),
    ("pytest.unit", "import subprocess\ndef test_orphan():\n"
     "    subprocess.Popen(['python', '-c', 'import time; time.sleep(60)'])\n", 125),
])
def test_real_docker_reports_actual_exit_and_cleans_container(tmp_path, target, code, expected):
    result = run_source(tmp_path, code, target=target, cpu_seconds=1 if expected == 126 else 10)
    assert result.exit_code == expected, result.stderr + result.stdout


@real
def test_real_docker_cancellation_waits_for_container_removal(tmp_path, monkeypatch):
    started = Event()
    control = CancellationToken()
    original = docker_runner.DockerSession.run
    sessions = []

    def observe(session, arguments, **kwargs):
        result = original(session, arguments, **kwargs)
        if arguments[:2] == ["container", "create"]:
            session.cid = result
            sessions.append(session)
            started.set()
        return result

    monkeypatch.setattr(docker_runner.DockerSession, "run", observe)

    def worker():
        with cancellation_scope(control):
            return run_source(tmp_path, "import time\ndef test_wait():\n    time.sleep(60)\n")

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        assert started.wait(20)
        session = sessions[0]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            state = json.loads(original(session, ["container", "inspect", session.cid]))[0]["State"]
            if state["Running"]:
                break
            time.sleep(.05)
        else:
            pytest.fail("Container did not start before cancellation")
        control.request()
        with pytest.raises(RunCancelled):
            future.result(timeout=30)
    assert not control.cleanup_error
    assert not sessions[0].root.exists()
    cli = docker_runner.docker_executable()
    result = subprocess.run([cli, "--host", "npipe:////./pipe/dockerDesktopLinuxEngine",
                             "container", "ls", "-aq", "--filter", "label=" + sessions[0].label],
                            check=True, capture_output=True, timeout=10)
    assert not result.stdout.strip()


@real
def test_real_docker_wall_timeout_is_bounded_and_output_is_capped(tmp_path):
    result = run_source(tmp_path, "import time\ndef test_wait(capfd):\n"
                        "    with capfd.disabled():\n"
                        "        print('x' * 300000, flush=True)\n"
                        "        time.sleep(60)\n", timeout=20)
    assert result.exit_code == 124
    assert len(result.stdout) <= 200000 and len(result.stderr) <= 200000
    assert "[recortado]" in result.stdout


@real
def test_real_graph_promotes_only_after_docker_tests_and_human_approval(tmp_path, monkeypatch):
    from test_cooperative_cancellation import repository, settings_for
    from test_project_builder_pipeline import BuilderAdapter, project_files

    from ai_swe.contracts import RunOptions
    from ai_swe.graph import RunEngine, model_routing
    from ai_swe.models import ModelGateway
    from ai_swe.state import RunStore

    settings = settings_for(tmp_path).model_copy(update={
        "runner_docker": DockerSettings(image=IMAGE),
    })
    repo = repository(tmp_path)
    adapter = BuilderAdapter(project_files("calendar"))
    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: ModelGateway([adapter]))
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado("crea un calendario", options=RunOptions(repo_path=str(repo)))
        assert engine.start(state).status == "awaiting_human_requirements_confirmation"
        waiting = engine.resume(state.run_id, "approved")
        assert waiting.status == "awaiting_approval", waiting.errors
        assert waiting.evidence.test_runs
        assert all(t.exit_code == 0 for t in waiting.evidence.test_runs)
        assert all("--network=none" in t.argv for t in waiting.evidence.test_runs)
        assert not (repo / "index.html").exists()
        completed = engine.resume(state.run_id, "approved")
        assert completed.status == "completed", completed.errors
        assert completed.promotion_receipt.status == "promoted"
        assert (repo / "index.html").is_file()
        assert len(adapter.calls) == 2
