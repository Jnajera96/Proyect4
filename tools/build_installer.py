"""Compile the complete verified onedir bundle using an explicitly located ISCC."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_iscc(explicit: Path | None = None) -> Path | None:
    candidates = [explicit, shutil.which("ISCC.exe")]
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            candidates += [Path(base) / f"Inno Setup {version}" / "ISCC.exe" for version in (6, 7)]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates += [Path(local) / "Programs" / "Inno Setup 6" / "ISCC.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    return None


def validate_bundle(bundle: Path) -> None:
    for relative in (
        "AISWESystem.exe",
        "_internal/python313.dll",
        "_internal/frontend/dist/index.html",
    ):
        if not (bundle / relative).is_file():
            raise ValueError("Incomplete verified onedir bundle: " + relative)
    for path in bundle.rglob("*"):
        if path.is_file() and (
            path.name.startswith(".env") or path.suffix in {".sqlite3", ".gguf"}
        ):
            raise ValueError("Mutable/private files must not be installed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iscc", type=Path)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    compiler = find_iscc(args.iscc)
    if compiler is None:
        parser.error("ISCC.exe not found; supply --iscc or install Inno Setup per user")
    bundle, output = args.bundle.resolve(), args.output.resolve()
    validate_bundle(bundle)
    if output.exists():
        parser.error("Use a new installer output directory")
    output.mkdir(parents=True)
    subprocess.run(
        [
            str(compiler),
            f"/DBundleDir={bundle}",
            f"/DInstallerOutput={output}",
            str(ROOT / "packaging/installer.iss"),
        ],
        check=True,
    )
    installer = output / "AISWESystem-v0.1.0-setup.exe"
    report = {
        "installer": str(installer),
        "compiler": str(compiler),
        "sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
        "bytes": installer.stat().st_size,
        "scope": "per-user, no elevation requested",
        "app_sha256": hashlib.sha256((bundle / "AISWESystem.exe").read_bytes()).hexdigest(),
    }
    (output / "installer-build.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
