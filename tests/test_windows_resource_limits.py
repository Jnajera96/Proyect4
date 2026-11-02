import ctypes
import os
import sys

import pytest
from pydantic import ValidationError
from test_f8_test_runner import repo as repo
from test_f8_test_runner import sandbox as sandbox
from test_runner_output_limits import scripted_target

from ai_swe.config import Settings
from ai_swe.tools import runner
from ai_swe.tools.windows_job import WindowsJob, _ExtendedLimits

STORE_ALIAS = getattr(os.lstat(sys._base_executable), "st_reparse_tag", 0) == 0x8000001B
WINDOWS = pytest.mark.skipif(os.name != "nt" or STORE_ALIAS, reason="Windows Job Objects require non-Store Python")


@pytest.mark.parametrize("values", [
    {"max_processes": 0}, {"max_processes": 129}, {"memory_mb": 63},
    {"memory_mb": True}, {"cpu_seconds": 0}, {"cpu_seconds": float("inf")},
    {"unknown": 1},
])
def test_invalid_limits_are_rejected(values):
    from ai_swe.tools.windows_job import JobLimits

    with pytest.raises(ValidationError):
        JobLimits(**values)


def test_settings_loads_validated_limits_from_configuration(monkeypatch):
    monkeypatch.setenv(
        "AI_SWE_RUNNER_LIMITS", '{"max_processes":3,"memory_mb":256,"cpu_seconds":9}',
    )
    assert Settings(_env_file=None).runner_limits.model_dump() == {
        "max_processes": 3, "memory_mb": 256, "cpu_seconds": 9,
    }


@WINDOWS
def test_default_job_applies_resource_limits_before_any_process_starts():
    job = WindowsJob()
    try:
        info = _ExtendedLimits()
        assert job._query(job.handle, 9, ctypes.byref(info), ctypes.sizeof(info), None)
        assert info.basic.max_processes == 16
        assert info.job_memory == 1024 * 1024 * 1024
        assert info.basic.job_time == 600 * 10_000_000
        assert info.basic.flags & 0x220C == 0x220C
        assert not info.basic.flags & 0x1800
    finally:
        job.close()


@WINDOWS
@pytest.mark.parametrize("memory_mb,allowed", [(64, False), (256, True)])
def test_committed_memory_is_bounded_with_a_successful_control(
    sandbox, monkeypatch, memory_mb, allowed,
):
    from ai_swe.tools.windows_job import JobLimits

    scripted_target(monkeypatch,
        "print('before',flush=True);a=bytearray(128*1024*1024);print('allocated')")
    result = runner.ejecutar(
        sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=10,
        limits=JobLimits(memory_mb=memory_mb),
    )
    assert "before" in result.stdout
    assert result.passed == allowed
    if allowed:
        assert "allocated" in result.stdout
    else:
        assert "MemoryError" in result.stderr
        assert "allocated" not in result.stdout


@WINDOWS
@pytest.mark.parametrize("max_processes,allowed", [(1, False), (2, True)])
def test_process_limit_denies_creation_but_allows_an_in_limit_child(
    sandbox, monkeypatch, max_processes, allowed,
):
    from ai_swe.tools.windows_job import JobLimits

    scripted_target(monkeypatch,
        "import subprocess,sys;print('before',flush=True);"
        "p=subprocess.Popen([sys.executable,'-c','pass']);"
        "assert p.wait()==0;print('child finished')")
    result = runner.ejecutar(
        sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=10,
        limits=JobLimits(max_processes=max_processes),
    )
    assert "before" in result.stdout
    assert result.passed == allowed
    if allowed:
        assert "child finished" in result.stdout
    else:
        assert "WinError" in result.stderr
        assert "child finished" not in result.stdout


@WINDOWS
def test_total_user_cpu_limit_terminates_busy_job_before_wall_timeout(sandbox, monkeypatch):
    from ai_swe.tools.windows_job import JobLimits

    scripted_target(monkeypatch, "while True: pass")
    result = runner.ejecutar(
        sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=10,
        limits=JobLimits(cpu_seconds=1),
    )
    assert result.exit_code == 0xC0000044
    assert not result.passed
    assert "cuota" in result.stderr.lower()


@WINDOWS
def test_cleanup_preserves_memory_and_cpu_limits():
    from ai_swe.tools.windows_job import JobLimits

    job = WindowsJob(JobLimits(memory_mb=256, cpu_seconds=9))
    try:
        job.terminate_and_wait()
        info = _ExtendedLimits()
        assert job._query(job.handle, 9, ctypes.byref(info), ctypes.sizeof(info), None)
        assert info.job_memory == 256 * 1024 * 1024
        assert info.basic.job_time == 90_000_000
        assert info.basic.max_processes == 1
        assert info.basic.flags & 0x2200 == 0x2200
    finally:
        job.close()
