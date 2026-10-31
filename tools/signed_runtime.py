"""Assemble official CPython and lock-selected installed wheels without creating PE files."""

from __future__ import annotations

import base64
import hashlib
import importlib.metadata as metadata
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from packaging.requirements import Requirement

PYTHON_VERSION = "3.13.14"
EMBED_SHA256 = "90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907"


def assemble(root: Path, frontend: Path, bundle: Path, archive: Path, uv: Path) -> dict:
    if hashlib.sha256(archive.read_bytes()).hexdigest() != EMBED_SHA256:
        raise ValueError("Official CPython archive SHA256 mismatch")
    bundle.mkdir(parents=True)
    runtime = bundle / "runtime"
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            target = (runtime / entry.filename).resolve()
            if not target.is_relative_to(runtime.resolve()):
                raise ValueError("Unsafe runtime archive member")
        source.extractall(runtime)
    signature_env = dict(os.environ)
    signature_env.pop("PSModulePath", None)
    signatures = subprocess.check_output(
        [
            shutil.which("pwsh.exe") or "powershell.exe",
            "-NoProfile",
            "-Command",
            "$files=Get-ChildItem -LiteralPath '"
            + str(runtime).replace("'", "''")
            + "' -Filter *.exe; @($files | ForEach-Object { "
            "$s=Get-AuthenticodeSignature -LiteralPath $_.FullName; "
            "[pscustomobject]@{name=$_.Name;status=[string]$s.Status;"
            "signer=$s.SignerCertificate.Subject} }) | ConvertTo-Json",
        ],
        text=True,
        env=signature_env,
    )
    signed = json.loads(signatures)
    if not signed or any(s["status"] != "Valid" for s in signed):
        raise ValueError("CPython executable Authenticode verification failed")
    requirements = subprocess.check_output(
        [
            str(uv),
            "export",
            "--frozen",
            "--extra",
            "voice",
            "--extra",
            "dev",
            "--no-emit-project",
            "--no-hashes",
            "--format",
            "requirements-txt",
        ],
        cwd=root,
        text=True,
    )
    (bundle / "DEPENDENCIES.txt").write_text(requirements, encoding="utf-8")
    packages = bundle / "packages"
    packages.mkdir()
    site = Path(sys.prefix) / "Lib/site-packages"
    selected = []
    for line in requirements.splitlines():
        if not re.match(r"^[\w.-]+==", line):
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        name = requirement.name
        version = next(iter(requirement.specifier)).version
        dist = metadata.distribution(name)
        if dist.version != version:
            raise ValueError("Environment differs from lock: " + name)
        selected.append({"name": name, "version": version})
        for relative in dist.files or []:
            original = Path(dist.locate_file(relative)).resolve()
            if not original.is_relative_to(site.resolve()) or not original.is_file():
                continue
            if original.suffix in {".pyc", ".pth"}:
                continue
            if relative.hash:
                actual = (
                    base64.urlsafe_b64encode(
                        hashlib.new(relative.hash.mode, original.read_bytes()).digest()
                    )
                    .decode()
                    .rstrip("=")
                )
                if actual != relative.hash.value:
                    raise ValueError("Installed wheel RECORD mismatch: " + str(relative))
            target = packages / original.relative_to(site.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
    shutil.copytree(
        root / "src/ai_swe", bundle / "app/ai_swe", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copytree(frontend, bundle / "frontend/dist")
    shutil.copytree(root / "contracts", bundle / "contracts") if (
        root / "contracts"
    ).exists() else None
    (bundle / "tools").mkdir()
    shutil.copy2(Path(sys.executable).parent / "ruff.exe", bundle / "tools/ruff.exe")
    shutil.copy2(root / "packaging/signed_start.py", bundle / "start.py")
    shutil.copy2(root / "tools/upgrade_portable.py", bundle / "tools/upgrade_portable.py")
    (runtime / "python313._pth").write_text(
        "python313.zip\n.\n../packages\n../app\nimport site\n", encoding="utf-8"
    )
    (bundle / "AISWESystem.cmd").write_text(
        '@echo off\r\n"%~dp0runtime\\python.exe" -B "%~dp0start.py" %*\r\n', encoding="ascii"
    )
    private = [
        p
        for p in bundle.rglob("*")
        if p.is_file() and (p.name.startswith(".env") or p.suffix in {".sqlite3", ".gguf"})
    ]
    if private:
        raise ValueError("Mutable/private files must not enter the bundle")
    manifest = {
        p.relative_to(bundle).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in bundle.rglob("*")
        if p.is_file()
    }
    (bundle / "BUNDLE-MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "format": "signed-python-onedir",
        "python": PYTHON_VERSION,
        "archive_sha256": EMBED_SHA256,
        "runtime_signatures": signed,
        "dependencies": selected,
        "launcher": "AISWESystem.cmd",
        "sys_frozen": False,
        "note": (
            "CPython executables are signed. Official wheel binaries are unmodified, "
            "not all Authenticode-signed."
        ),
    }
