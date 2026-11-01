import ctypes
import os
import time
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes as w

import pytest
from test_f8_test_runner import repo as repo
from test_f8_test_runner import sandbox as sandbox
from test_runner_output_limits import scripted_target

from ai_swe.tools import runner

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows Job Objects")


def process_api():
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    api.OpenProcess.restype = w.HANDLE
    api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    api.WaitForSingleObject.restype = w.DWORD
    api.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
    api.TerminateProcess.restype = w.BOOL
    api.CloseHandle.argtypes = [w.HANDLE]
    api.CloseHandle.restype = w.BOOL
    api.IsProcessInJob.argtypes = [w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)]
    api.IsProcessInJob.restype = w.BOOL
    return api


def wait_pid(path):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        try:
            return int(path.read_text())
        except (FileNotFoundError, ValueError):
            pass
        time.sleep(.01)
    pytest.fail("Synthetic descendant did not publish its PID")


@pytest.mark.parametrize("parent_waits", [True, False])
def test_runner_terminates_real_descendant(sandbox, monkeypatch, tmp_path, parent_waits):
    pidfile = tmp_path / "descendant.pid"
    assert not pidfile.exists()
    child = (
        "import os,time;from pathlib import Path;"
        f"Path({str(pidfile)!r}).write_text(str(os.getpid()));time.sleep(8)"
    )
    code = (
        "import subprocess,sys,time;"
        f"p=subprocess.Popen([sys.executable,'-c',{child!r}],"
        "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
        f"time.sleep({8 if parent_waits else 1})"
    )
    scripted_target(monkeypatch, code)
    api = process_api()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            runner.ejecutar, sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=2
        )
        pid = wait_pid(pidfile)
        handle = api.OpenProcess(0x100000 | 0x1000 | 1, False, pid)
        assert handle, "Could not observe our synthetic descendant"
        try:
            result = future.result(timeout=10)
            expected = runner.EXIT_TIMEOUT if parent_waits else runner.EXIT_ORPHANS
            assert result.exit_code == expected
            assert not result.passed
            assert api.WaitForSingleObject(handle, 0) == 0, "Descendant survived runner completion"
        finally:
            # Only a handle to the child created by this fixture, never a name/global PID scan.
            if api.WaitForSingleObject(handle, 0) == 258:
                api.TerminateProcess(handle, 1)
                api.WaitForSingleObject(handle, 5000)
            api.CloseHandle(handle)


def test_assignment_failure_never_runs_user_code(sandbox, monkeypatch, tmp_path):
    marker = tmp_path / "executed"
    scripted_target(monkeypatch, f"from pathlib import Path;Path({str(marker)!r}).touch()")
    def refuse(self, process, deadline=None):
        raise runner.JobError("Synthetic assignment failure")
    monkeypatch.setattr(runner.WindowsJob, "assign_and_resume", refuse)
    with pytest.raises(runner.RunnerError, match="Synthetic assignment failure"):
        runner.ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=2)
    assert not marker.exists()


def test_alias_interpreter_rejected_before_launch(monkeypatch):
    import ai_swe.tools.windows_job as jobs
    class Alias:
        st_reparse_tag = 0x8000001B
    monkeypatch.setattr(jobs.os, "lstat", lambda path: Alias())
    with pytest.raises(jobs.JobError, match="alias de Microsoft Store"):
        jobs.WindowsJob()


def test_unverified_shutdown_never_reports_success(sandbox, monkeypatch):
    scripted_target(monkeypatch, "pass")
    original = runner.WindowsJob.terminate_and_wait
    def refuse(self):
        original(self)
        raise runner.JobError("Synthetic verification failure")
    monkeypatch.setattr(runner.WindowsJob, "terminate_and_wait", refuse)
    with pytest.raises(runner.RunnerError, match="no se confirmó el cierre"):
        runner.ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=2)
