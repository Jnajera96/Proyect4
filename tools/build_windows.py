"""Build a fresh, isolated onedir artifact. No global installs or credential copying."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True, help="New artifact directory")
    args = parser.parse_args()
    output = args.output.resolve()
    if os.name != "nt" or output.exists():
        parser.error("Build on Windows and use a new output directory")
    output.mkdir(parents=True)
    frontend = output / "frontend"
    npm = shutil.which("npm.cmd")
    if not npm:
        parser.error("Node/npm are required only on the build machine")
    subprocess.run(
        [npm, "exec", "--", "tsc", "--noEmit"], cwd=ROOT / "frontend", check=True,
    )
    subprocess.run(
        [npm, "exec", "--", "vite", "build", "--outDir", str(frontend)],
        cwd=ROOT / "frontend", check=True,
    )
    env = {**os.environ, "AI_SWE_PACKAGE_FRONTEND": str(frontend)}
    subprocess.run([
        sys.executable, "-m", "PyInstaller", str(ROOT / "packaging/ai-swe.spec"),
        "--distpath", str(output / "dist"), "--workpath", str(output / "build"),
    ], cwd=ROOT, env=env, check=True)
    bundle = output / "dist/AISWESystem"
    forbidden = [p for p in bundle.rglob("*") if p.is_file() and (
        p.name == ".env" or p.suffix in {".sqlite3", ".gguf"}
    )]
    if forbidden:
        raise RuntimeError("Unexpected mutable or private file in bundle")
    exe = bundle / "AISWESystem.exe"
    report = {
        "format": "onedir", "python": sys.version.split()[0],
        "executable": str(exe), "sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
        "bundle_bytes": sum(p.stat().st_size for p in bundle.rglob("*") if p.is_file()),
        "secret_files_included": False,
    }
    (output / "build-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
