"""Real controller death plus a controlled no-watchdog negative fixture."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_swe.tools import docker_runner
from ai_swe.tools.runner import _entorno

IMAGE = os.environ.get("AI_SWE_TEST_DOCKER_IMAGE", "")
pytestmark = pytest.mark.skipif(
    os.name != "nt" or not IMAGE, reason="Opt-in local Docker image required",
)

CHILD = r'''
import json, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from ai_swe.tools import docker_runner
state = json.loads(Path(sys.argv[2]).read_text())
state['root'], state['temp_parent'] = Path(state['root']), Path(state['temp_parent'])
state['_lease'] = None  # This fixture's parent retains the OS lease until external cleanup.
session = docker_runner.DockerSession.__new__(docker_runner.DockerSession)
session.__dict__.update(state)
if sys.argv[5] == 'recover':
    from ai_swe.state.operation_lock import operation_lock
    session._lease = operation_lock(session.root.with_suffix('.lock'))
    session._lease.__enter__()
original = session.run
def observe(arguments, **kwargs):
    if arguments[:2] == ['container', 'create'] and sys.argv[5] == 'disabled':
        arguments = list(arguments)
        index = arguments.index('/opt/aiswe/run_target.py')
        # Trusted negative fixture only: no repository code runs as root.
        arguments[index:index + 2] = ['-c', 'import time; time.sleep(90)']
    result = original(arguments, **kwargs)
    if arguments[:2] == ['container', 'create']:
        output = Path(sys.argv[4])
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps({'cid': result, 'owner': session.owner}))
        temporary.replace(output)
    return result
session.run = observe
docker_runner.DockerSession = lambda: session
docker_runner.execute(SimpleNamespace(raiz=Path(sys.argv[3])), 'pytest.unit',
                      docker_runner.DockerSettings(image=sys.argv[6]), 20)
'''


@pytest.mark.parametrize("watchdog", ["enabled", "disabled", "recover"])
def test_container_watchdog_survives_controller_death(tmp_path, monkeypatch, watchdog):
    monkeypatch.setattr(docker_runner, "session_directory", lambda: tmp_path / "sessions")
    docker_runner.check_ready(docker_runner.DockerSettings(image=IMAGE))
    source = tmp_path / "repository"
    source.mkdir()
    (source / "test_wait.py").write_text(
        "import time\nfrom pathlib import Path\ndef test_wait():\n"
        "    Path('/workspace/started').write_text('running')\n    time.sleep(90)\n",
    )
    session = docker_runner.DockerSession()
    session_file = tmp_path / "session.json"
    session_file.write_text(json.dumps(session.__dict__, default=str))
    if watchdog == "recover":
        session.release()
    receipt = tmp_path / "created.json"
    controller = None
    try:
        with (tmp_path / "controller.log").open("wb") as log:
            controller = subprocess.Popen(
                [sys.executable, "-B", "-c", CHILD,
                 str(Path(docker_runner.__file__).resolve().parents[2]), str(session_file),
                 str(source), str(receipt), watchdog, IMAGE],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
                env=_entorno(SimpleNamespace(raiz=tmp_path)),
            )
            deadline = time.monotonic() + 20
            while not receipt.exists() and time.monotonic() < deadline:
                assert controller.poll() is None, (tmp_path / "controller.log").read_text()
                time.sleep(.05)
            assert receipt.exists(), "Controller did not create its container"
            created = json.loads(receipt.read_text())
            assert created["owner"] == session.owner
            session.cid = created["cid"]
            session.create_started = True
            while time.monotonic() < deadline:
                state = json.loads(session.run(["container", "inspect", session.cid]))[0]["State"]
                if state["Running"]:
                    if watchdog == "disabled":
                        break
                    started = session.run([
                        "container", "exec", session.cid, "/usr/local/bin/python", "-I", "-c",
                        "from pathlib import Path; print(Path('/workspace/started').exists())",
                    ])
                    if started == "True":
                        break
                time.sleep(.05)
            else:
                pytest.fail("Target did not start before controller death")
            if watchdog == "recover":
                assert docker_runner.recover_stopped_sessions()["active"] == 1
            controller.kill()  # Owned process handle, never a PID discovered from another task.
            controller.wait(timeout=10)
            assert controller.returncode != 0
            deadline = time.monotonic() + 23
            while time.monotonic() < deadline:
                state = json.loads(session.run(["container", "inspect", session.cid]))[0]["State"]
                if not state["Running"]:
                    break
                time.sleep(.2)
            if watchdog != "disabled":
                assert not state["Running"] and state["ExitCode"] == 124, state
            else:
                assert state["Running"], "Negative control must outlive the missing watchdog"
            assert session.root.exists(), "Controller death cannot claim snapshot cleanup"
            if watchdog == "recover":
                result = docker_runner.recover_stopped_sessions()
                assert result["removed"] == 1, result
                assert not session.root.exists()
    finally:
        if controller is not None and controller.poll() is None:
            controller.kill()
            controller.wait(timeout=10)
        # Discover only this session's label, including a creation before receipt publication.
        if session.root.exists():
            session.create_started = controller is not None
            session.create_uncertain = controller is not None and not receipt.exists()
            session.close()
    assert not session.root.exists()
