"""Immutable PID-1 supervisor. Untrusted targets never run with supervisor credentials."""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

TARGETS = {
    "pytest.unit": [sys.executable, "-m", "pytest", "-q", "--no-header", "-p",
                    "no:cacheprovider", "-m", "not real_provider", "."],
    "pytest.integration": [sys.executable, "-m", "pytest", "-q", "--no-header", "-p",
                           "no:cacheprovider", "-m", "integration", "."],
    "ruff.check": ["ruff", "check", "--no-cache", "."],
}


def worker(target, digest):
    if os.getuid() != 65532 or target not in TARGETS:
        raise ValueError("Invalid worker credentials or target")
    source, destination = Path("/input"), Path("/workspace")
    metadata = source / ".aiswe-snapshot.json"
    raw = metadata.read_bytes()
    if len(raw) > 1_000_000 or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Snapshot manifest mismatch")
    files = json.loads(raw)
    if not isinstance(files, dict) or len(files) > 2000:
        raise ValueError("Invalid snapshot file inventory")
    actual = set()
    for entry in source.rglob("*"):
        if entry.is_symlink():
            raise ValueError("Snapshot contains links")
        if entry.is_file() and entry != metadata:
            actual.add(entry.relative_to(source).as_posix())
    if actual != set(files):
        raise ValueError("Snapshot inventory mismatch")
    total = 0
    for name, expected in files.items():
        path = PurePosixPath(name)
        if (path.is_absolute() or ".." in path.parts or not path.parts
                or any(c in name for c in "\\:\x00")):
            raise ValueError("Invalid snapshot path")
        data = (source / name).read_bytes()
        total += len(data)
        if total > 64 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Snapshot content mismatch")
        output = destination / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        output.chmod(0o644)
    os.chdir(destination)
    os.execvpe(TARGETS[target][0], TARGETS[target], {
        "PATH": os.environ["PATH"], "HOME": "/tmp", "TMPDIR": "/tmp", "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": "/workspace/src:/workspace",
        "PYTHONIOENCODING": "utf-8", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "OPENBLAS_NUM_THREADS": "1",
    })


def main():
    target, digest, wall, cpu = sys.argv[1:]
    wall, cpu = float(wall), int(cpu)
    if (target not in TARGETS or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not 0 < wall <= 3600 or not 0 < cpu <= 3600
            or os.getpid() != 1 or os.getuid() != 0):
        raise ValueError("Invalid trusted runner invocation")
    fields = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines()
                  if ":" in line)
    if (int(fields["CapEff"].strip(), 16) != 0xC0 or fields["NoNewPrivs"].strip() != "1"
            or fields["Seccomp"].strip() != "2"):
        raise ValueError("Required supervisor restrictions are missing")
    started = time.monotonic()
    stats = Path("/sys/fs/cgroup/cpu.stat")

    def cpu_used():
        values = dict(line.split() for line in stats.read_text().splitlines())
        return int(values["user_usec"])

    initial_cpu = cpu_used()
    process = subprocess.Popen(
        [sys.executable, "-I", __file__, "--worker", target, digest],
        stdin=subprocess.DEVNULL, user=65532, group=65532, extra_groups=[],
    )
    # Different non-root UIDs prevent the target from stopping or modifying its watchdog.
    os.setgroups([])
    os.setgid(65533)
    os.setuid(65533)
    while process.poll() is None:
        if time.monotonic() - started >= wall:
            print("Se alcanzó el límite de tiempo del contenedor", file=sys.stderr, flush=True)
            os._exit(124)
        if cpu_used() - initial_cpu >= cpu * 1_000_000:
            print("Se alcanzó la cuota de CPU del contenedor", file=sys.stderr, flush=True)
            os._exit(126)
        time.sleep(.05)
    # PID 1 exits last: the kernel kills all remaining namespace members on its exit.
    deadline = time.monotonic() + .2
    while time.monotonic() < deadline:
        try:
            while os.waitpid(-1, os.WNOHANG)[0]:
                pass
        except ChildProcessError:
            pass
        if int(Path("/sys/fs/cgroup/pids.current").read_text()) <= 1:
            os._exit(process.returncode if process.returncode >= 0 else 128 - process.returncode)
        time.sleep(.01)
    print("Quedaron descendientes; el contenedor los terminará", file=sys.stderr, flush=True)
    os._exit(125)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--worker"]:
        worker(*sys.argv[2:])
    else:
        main()
