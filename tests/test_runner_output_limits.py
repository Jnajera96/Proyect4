import tracemalloc

import pytest
from test_f8_test_runner import repo as repo
from test_f8_test_runner import sandbox as sandbox

from ai_swe.tools import runner


def scripted_target(monkeypatch, code):
    # Exercise the collector with fixed scripts even when the package routes targets to start.py.
    monkeypatch.setattr(runner, "comando_de", lambda target: runner.TARGET_COMMANDS.get(target))
    monkeypatch.setitem(
        runner.TARGET_COMMANDS, "pytest.unit", (runner.sys.executable, "-u", "-c", code)
    )


def test_large_output_retains_tail_without_unbounded_parent_memory(sandbox, monkeypatch):
    code = (
        "import os; chunk=b'x'*65536; "
        "[(os.write(1,chunk),os.write(2,chunk)) for _ in range(256)]; "
        "os.write(1,b'FINAL_STDOUT');os.write(2,b'FINAL_STDERR')"
    )
    scripted_target(monkeypatch, code)
    tracemalloc.start()
    try:
        result = runner.ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=30,
            network_egress_enabled=True)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    print("capture_parent_peak_bytes=", peak)
    assert result.exit_code == 0
    assert result.stdout.endswith("FINAL_STDOUT") and result.stderr.endswith("FINAL_STDERR")
    assert len(result.stdout) <= 200_000 and len(result.stderr) <= 200_000
    assert peak < 8 * 1024 * 1024, f"Parent capture allocated {peak} bytes for 32 MiB output"


def test_binary_and_unicode_output_cannot_break_capture(sandbox, monkeypatch):
    code = "import os;os.write(1,b'\\xff'+ 'Español 😀'.encode('utf-8'));os.write(2,b'error')"
    scripted_target(monkeypatch, code)
    result = runner.ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=10,
        network_egress_enabled=True)
    assert result.exit_code == 0 and "Español 😀" in result.stdout
    assert "\ufffd" in result.stdout and result.stderr == "error"


def test_continuous_output_cannot_starve_deadline(sandbox, monkeypatch):
    code = "import os\nwhile True:\n os.write(1,b'x'*65536);os.write(2,b'y'*65536)"
    scripted_target(monkeypatch, code)
    result = runner.ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=0.4,
        network_egress_enabled=True)
    assert result.exit_code == runner.EXIT_TIMEOUT and not result.passed
    assert len(result.stdout) <= 200_000 and len(result.stderr) <= 200_000
    assert result.duration_s < 8 and "supero" in result.stderr


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_invalid_deadline_never_launches_a_process(sandbox, monkeypatch, timeout):
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: pytest.fail("Must not spawn"))
    with pytest.raises(runner.RunnerError, match="positivo y finito"):
        runner.ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=timeout,
            network_egress_enabled=True)


def test_capture_setup_failure_closes_the_child_without_unbounded_fallback(sandbox, monkeypatch):
    processes = []
    original = runner.subprocess.Popen

    def launch(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    def unavailable(*args):
        raise OSError("Synthetic unsupported pipe")

    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner.os, "set_blocking", unavailable)
    with pytest.raises(runner.RunnerError, match="acotada"):
        runner.ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=10,
            network_egress_enabled=True)
    assert len(processes) == 1 and processes[0].poll() is not None
