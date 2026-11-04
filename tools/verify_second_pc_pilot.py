"""Audit an extracted RC26 under a simulated clean Windows user environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
RC26_MANIFEST_SHA256 = "74ed0c478889084899b2ac084c00eaac80453fcf161b7f72aa5789f134cdf754"

PROBE = r"""
import json, os, platform, shutil, subprocess, sys, time
from pathlib import Path
if not __debug__:
    raise RuntimeError('Verification requires assertions')
bundle, output = map(lambda x: Path(x).resolve(), sys.argv[1:])
sys._ai_swe_bundle = bundle
import ai_swe
assert Path(ai_swe.__file__).resolve().is_relative_to(bundle/'app')
assert Path(sys.executable).resolve()==bundle/'runtime/python.exe'
assert platform.python_version()=='3.13.14'
checks=['bundled CPython 3.13.14 and ai_swe imports verified']
discovery={name:shutil.which(name) for name in ('python','node','git')}
assert all(value is None for value in discovery.values()), discovery
checks.append('PATH System32 discovers no Python Node or Git')
from ai_swe.config import Settings
from ai_swe.runtime_paths import prepare_user_directories, user_paths
settings=Settings(_env_file=None)
assert settings.runtime_mode=='installed' and settings.profile_mode
prepare_user_directories()
assert user_paths().root==Path(os.environ['LOCALAPPDATA'])/'AISWESystem'
assert user_paths().database.parent.is_dir()
checks.append('installed user directories created outside bundle')
import av, ctranslate2, faster_whisper
assert av.__version__=='18.1.0'
assert settings.stt_device=='cpu' and settings.stt_compute_type=='int8'
assert 'int8' in ctranslate2.get_supported_compute_types('cpu')
from ai_swe.stt import crear_adaptador_stt
voice=crear_adaptador_stt(settings)
assert voice._dispositivo=='cpu' and voice._tipo_computo=='int8' and voice._cargado is None
checks.append('voice dependencies import and CPU int8 factory prepared without loading weights')
from ai_swe.tools.windows_job import WindowsJob, JobLimits, CREATE_SUSPENDED
marker=output/'job-child.json'
grand=("import json,os,sys,time\nfrom pathlib import Path\n"
       "ready=Path(sys.argv[1]); temporary=ready.with_suffix('.tmp')\n"
       "temporary.write_text(json.dumps({'grandchild':os.getpid()}))\n"
       "temporary.replace(ready)\ntime.sleep(60)\n")
code=("import subprocess,sys,time\n"
      "subprocess.Popen([sys.executable,'-B','-c',"+repr(grand)+",sys.argv[1]],"
      "creationflags=subprocess.CREATE_NO_WINDOW)\ntime.sleep(60)\n")
job=WindowsJob(JobLimits(max_processes=4,memory_mb=256,cpu_seconds=30))
child=None
try:
    child=subprocess.Popen([sys.executable,'-B','-c',code,str(marker)],cwd=output,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=CREATE_SUSPENDED|subprocess.CREATE_NO_WINDOW)
    assert job.assign_and_resume(child)
    deadline=time.monotonic()+10
    while not marker.exists():
        assert child.poll() is None, 'Owned child exited before spawning descendant'
        assert time.monotonic()<deadline, 'Descendant readiness timeout'
        time.sleep(.02)
    descendants=json.loads(marker.read_text())
    active=job.active()
    assert active>=2, f"Expected at least two owned members, observed {active}"
    import ctypes
    from ctypes import wintypes
    query=ctypes.WinDLL('kernel32',use_last_error=True).QueryFullProcessImageNameW
    query.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    query.restype=wintypes.BOOL
    member_images=[]
    for pid in (child.pid,descendants['grandchild']):
        handle=job._check(job._open_process(0x100000|0x1000,False,pid),'Open owned member')
        try:
            belongs=wintypes.BOOL()
            job._check(job._in_job(handle,job.handle,ctypes.byref(belongs)),'Confirm membership')
            assert belongs.value, f'Owned process {pid} escaped Job'
            name=ctypes.create_unicode_buffer(32768)
            size=wintypes.DWORD(len(name))
            job._check(query(handle,0,name,ctypes.byref(size)),'Read owned executable')
            assert Path(name.value).resolve()==bundle/'runtime/python.exe', name.value
            member_images.append(name.value)
        finally:
            job._close(handle)
    checks.append('Windows Job created assigned before resume and contains child plus descendant')
    kill_on_close=bool(job._limits.basic.flags & 0x2000)
    assert kill_on_close
    job.terminate_and_wait()
    assert job.active()==0 and job.wait_empty(2)
    assert child.wait(timeout=5)!=0
    checks.append('TerminateJobObject cascades and verifies both owned processes terminated')
finally:
    try:
        if child is not None and child.poll() is None:
            try:
                job.terminate_and_wait()
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
    finally:
        job.close()
print(json.dumps(dict(success=True,checks=checks,discovery=discovery,python=sys.version,
    executable=sys.executable,platform=platform.platform(),machine=platform.machine(),
    user_root=str(user_paths().root),module=ai_swe.__file__,job_descendant_pid=descendants['grandchild'],
    job_initial_active_members=active,job_member_images=member_images,
    kill_on_close_configured=kill_on_close,close_only_kill_tested=False,
    voice=dict(av=av.__version__,ctranslate2=ctranslate2.__version__,device='cpu',compute_type='int8',
        model_loaded=False,real_audio=False,real_inference=False),paid_calls=0)))
"""


def clean_environment(user_data: Path) -> dict[str, str]:
    environment = {
        k: v
        for k, v in os.environ.items()
        if k.upper()
        in {
            "SYSTEMROOT",
            "SYSTEMDRIVE",
            "WINDIR",
            "COMSPEC",
            "PATHEXT",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "NUMBER_OF_PROCESSORS",
            "PROCESSOR_ARCHITECTURE",
        }
    }
    environment.update(
        PATH=str(Path(os.environ["SYSTEMROOT"]) / "System32"),
        LOCALAPPDATA=str(user_data.resolve()),
        HF_HOME=str(user_data / "hf-cache"),
        HF_HUB_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        TRANSFORMERS_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONIOENCODING="utf-8",
    )
    return environment


def verify_manifest(bundle: Path) -> dict:
    bundle = bundle.resolve()
    raw = (bundle / "BUNDLE-MANIFEST.json").read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("Empty or invalid manifest")
    names = set()
    size = 0
    for name, digest in manifest.items():
        rel = PurePosixPath(name)
        if (
            rel.is_absolute()
            or str(rel) != name
            or "\\" in name
            or ":" in name
            or any(p in {".", ".."} or p.endswith((".", " ")) for p in rel.parts)
        ):
            raise ValueError("Unsafe manifest path")
        if name.casefold() in names:
            raise ValueError("Case-colliding manifest path")
        names.add(name.casefold())
        path = bundle / name
        if not path.resolve().is_relative_to(bundle) or path.is_symlink():
            raise ValueError("Manifest path escapes bundle")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != digest:
            raise ValueError("Bundle hash mismatch: " + name)
        size += path.stat().st_size
    inventory = {p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file()}
    if inventory != set(manifest) | {"BUNDLE-MANIFEST.json"}:
        raise ValueError("Unexpected bundle file inventory")
    return dict(
        manifest_sha256=hashlib.sha256(raw).hexdigest(),
        files=len(manifest),
        bytes=size,
        bundled_git=any(PurePosixPath(n).name.lower() == "git.exe" for n in manifest),
    )


def runtime_signatures(bundle: Path, environment: dict) -> list[dict]:
    powershell = Path(environment["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    script = (
        "$s=Get-AuthenticodeSignature -LiteralPath $env:AISWE_PILOT_EXE; "
        "[pscustomobject]@{status=$s.Status.ToString();subject=$s.SignerCertificate.Subject} "
        "| ConvertTo-Json -Compress"
    )
    reports = []
    for name in ("python.exe", "pythonw.exe"):
        result = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
            env={**environment, "AISWE_PILOT_EXE": str(bundle / "runtime" / name)},
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        signature = json.loads(result.stdout)
        if (
            signature["status"] != "Valid"
            or "Python Software Foundation" not in signature["subject"]
        ):
            raise ValueError("Runtime PSF signature not valid: " + name)
        reports.append({"file": name, **signature})
    return reports


def run_pilot(bundle: Path, output: Path) -> dict:
    if os.name != "nt":
        raise RuntimeError("This pilot requires Windows x64")
    bundle = bundle.resolve()
    output = output.resolve()
    if output.is_relative_to(bundle):
        raise ValueError("Evidence must stay outside the immutable bundle")
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        status="failed",
        physical_second_pc=False,
        clean_environment_simulated=True,
        paid_api_calls=0,
        downloads=0,
        pushes=0,
        bundle=str(bundle),
        output=str(output),
    )
    try:
        integrity = verify_manifest(bundle)
        if integrity["manifest_sha256"] != RC26_MANIFEST_SHA256:
            raise ValueError("Extraction does not match the independently pinned RC26 manifest")
        report["integrity"] = integrity
        runtime = bundle / "runtime/python.exe"
        environment = clean_environment(output / "probe-userdata")
        report["runtime_signatures"] = runtime_signatures(bundle, environment)
        result = subprocess.run(
            [str(runtime), "-B", "-c", PROBE, str(bundle), str(output)],
            cwd=output,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        (output / "probe.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError("Clean-runtime probe failed; inspect probe.log")
        report["runtime_probe"] = json.loads(result.stdout.splitlines()[-1])
        smoke = subprocess.run(
            [
                str(runtime),
                "-B",
                str(ROOT / "tools/verify_portable_profiles.py"),
                str(bundle),
                str(output / "profiles"),
            ],
            cwd=output,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            timeout=240,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        (output / "profiles.log").write_text(smoke.stdout, encoding="utf-8")
        report["profiles"] = json.loads((output / "profiles/report.json").read_text())
        if smoke.returncode or not report["profiles"]["success"]:
            raise RuntimeError("Portable profile lifecycle failed; inspect profiles.log")
        report["post_run_integrity"] = verify_manifest(bundle)
        assert report["post_run_integrity"] == integrity
        report["status"] = "passed_simulated_clean_environment"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Extracted AISWESystem directory (not a ZIP)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path(tempfile.gettempdir()) / ("aiswe-clean-" + uuid.uuid4().hex[:10])
    report = run_pilot(args.bundle, output)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs/SECOND-PC-PILOT-EVIDENCE.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed_simulated_clean_environment" else 1


if __name__ == "__main__":
    raise SystemExit(main())
