"""Controlled Docker Desktop prerequisite proof; not an application runner backend."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ai_swe.tools.runner import _capturar  # noqa: E402

PROBE = r'''
import errno,json,os,socket,subprocess,sys
from pathlib import Path
checks=[]
def check(condition,name):
    assert condition,name
    checks.append(name)
check(os.getuid()==65532,'non_root_user')
status=Path('/proc/self/status').read_text()
fields=dict(line.split(':',1) for line in status.splitlines() if ':' in line)
check(int(fields['CapEff'].strip(),16)==0,'no_capabilities')
check(fields['NoNewPrivs'].strip()=='1','no_new_privileges')
check(fields['Seccomp'].strip()=='2','seccomp_enabled')
check(not any(k in os.environ for k in ('HF_TOKEN','OPENAI_API_KEY','AISWE_PROBE_HOST_ONLY')),
      'host_credentials_absent')
check(Path('/input/inside.txt').read_text()=='synthetic input','input_canary_readable')
check(not Path('/input/outside.txt').exists(),'outside_canary_not_mounted')
for filename in ('/input/inside.txt','/etc/aiswe-write-probe'):
    try:
        Path(filename).write_text('unexpected write')
    except OSError as exc:
        check(exc.errno in (errno.EROFS,errno.EACCES),'write_denied:'+filename)
    else:
        raise AssertionError('Protected write succeeded')
Path('/tmp/writable').write_text('ok')
check(Path('/tmp/writable').read_text()=='ok','temporary_writes_allowed')
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0))
with socket.socket() as sock:
    sock.settimeout(2)
    try:
        sock.connect(('1.1.1.1',443))
    except OSError as exc:
        check(exc.errno==errno.ENETUNREACH,'network_egress_unreachable')
    else:
        raise AssertionError('External connection succeeded')
cgroup=Path('/sys/fs/cgroup')
check((cgroup/'memory.max').read_text().strip()=='536870912','memory_cgroup_limit')
check((cgroup/'pids.max').read_text().strip()=='32','pids_cgroup_limit')
quota,period=(cgroup/'cpu.max').read_text().split()
check(quota!='max' and int(quota)<=int(period),'cpu_cgroup_limit')
tests=Path('/tmp/tests')
tests.mkdir()
testfile=tests/'test_smoke.py'
testfile.write_bytes(Path('/input/test_smoke.py').read_bytes())
testfile.chmod(0o644)
check(testfile.read_bytes()==Path('/input/test_smoke.py').read_bytes()
      and not testfile.stat().st_mode & 0o111,'normalized_linux_snapshot_permissions')
subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider',str(testfile)],check=True)
checks.append('real_pytest_passed')
subprocess.run(['ruff','check','--no-cache',str(testfile)],check=True)
checks.append('real_ruff_passed')
print('AISWE_PROOF:'+json.dumps(checks),flush=True)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="Local immutable image ID: sha256:<64 hex>")
    parser.add_argument("output", type=Path, help="New directory for controlled fixtures/report")
    args = parser.parse_args()
    if not __debug__:
        parser.error("Run this assertion-based proof without Python optimization")
    if os.name != "nt" or not re.fullmatch(r"sha256:[0-9a-f]{64}", args.image):
        parser.error("Requires Windows Docker Desktop and an immutable local image ID")
    docker = Path.home() / "AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
    if not docker.is_file():
        docker = Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe")
    output = args.output.resolve()
    if not docker.is_file() or output.exists() or "," in str(output):
        parser.error("Docker CLI missing or output directory is occupied/unsupported")
    output.mkdir(parents=True)
    config = output / "docker-config"
    config.mkdir()
    (config / "config.json").write_text(json.dumps({"auths": {}}))
    prefix = [str(docker), "--host", "npipe:////./pipe/dockerDesktopLinuxEngine",
              "--config", str(config)]
    nonce = uuid.uuid4().hex
    label = "io.aiswe.isolation-proof=" + nonce
    report = {"success": False, "image_id": args.image, "owner_label": label,
              "paid_calls": 0, "application_backend_integrated": False, "checks": []}

    def run(*arguments):
        result = _capturar([*prefix, *arguments], SimpleNamespace(raiz=output), 60)
        if result.returncode:
            raise RuntimeError(
                "Docker operation failed:\n" + result.stdout[-1000:] + "\n" + result.stderr[-1000:]
            )
        return result.stdout.strip()

    try:
        image_platform = run(
            "image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", args.image,
        )
        assert image_platform == "linux/amd64"
        report["checks"].append("local_linux_amd64_image")
        inputs = output / "input"
        inputs.mkdir()
        (inputs / "inside.txt").write_text("synthetic input")
        (inputs / "test_smoke.py").write_text("def test_sum():\n    assert 1 + 1 == 2\n")
        (output / "outside.txt").write_text("synthetic outside canary")
        os.environ["AISWE_PROBE_HOST_ONLY"] = nonce
        cid = run("container", "create", "--pull=never", "--label", label,
                  "--network=none", "--read-only", "--user", "65532:65532", "--cap-drop=ALL",
                  "--security-opt=no-new-privileges=true", "--memory=512m", "--memory-swap=512m",
                  "--cpus=1", "--pids-limit=32", "--log-driver=none", "--workdir=/tmp",
                  "--cgroupns=private",
                  "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m,mode=1777", "--mount",
                  f"type=bind,source={inputs},target=/input,readonly", "--entrypoint",
                  "/usr/local/bin/python", args.image, "-I", "-c", PROBE)
        if not re.fullmatch(r"[0-9a-f]{64}", cid):
            raise RuntimeError("Invalid owned container ID")
        inspected = json.loads(run("container", "inspect", cid))[0]
        host = inspected["HostConfig"]
        assert host["ReadonlyRootfs"] and host["NetworkMode"] == "none" and not host["Privileged"]
        assert host["Memory"] == host["MemorySwap"] == 536870912
        assert host["PidsLimit"] == 32 and host["NanoCpus"] == 1_000_000_000
        mounts = [m for m in inspected["Mounts"] if m["Type"] == "bind"]
        assert len(mounts) == 1 and mounts[0]["Destination"] == "/input" and not mounts[0]["RW"]
        report["checks"].append("restricted_container_configuration")
        text = run("container", "start", "--attach", cid)
        state = json.loads(run("container", "inspect", cid))[0]["State"]
        assert not state["Running"] and state["ExitCode"] == 0, "Container execution failed"
        proof = [line.removeprefix("AISWE_PROOF:") for line in text.splitlines()
                 if line.startswith("AISWE_PROOF:")]
        assert len(proof) == 1, "Missing completed in-container assertions"
        report["checks"].extend(json.loads(proof[0]))
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            ids = run(
                "container", "ls", "-aq", "--no-trunc", "--filter", "label=" + label,
            ).splitlines()
            for cid in ids:
                if not re.fullmatch(r"[0-9a-f]{64}", cid):
                    raise RuntimeError("Invalid cleanup ID")
                owner = json.loads(run("container", "inspect", cid))[0]["Config"]["Labels"]
                if owner.get("io.aiswe.isolation-proof") != nonce:
                    raise RuntimeError("Cleanup ownership mismatch")
                run("container", "rm", "--force", "--volumes", cid)
            assert not run("container", "ls", "-aq", "--filter", "label=" + label)
            report["checks"].append("owned_containers_removed")
        except Exception as exc:
            report["cleanup_error"] = f"{type(exc).__name__}: {exc}"
        report["success"] = "error" not in report and "cleanup_error" not in report
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
