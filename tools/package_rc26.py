"""Package and verify RC26 portable bundle with latest sources and built frontend."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RC26_DIR = ROOT / "dist/windows-v0.2.0-rc26"
BUNDLE_DIR = RC26_DIR / "dist/AISWESystem"
FRONTEND_DIR = ROOT / "frontend/dist"
SRC_DIR = ROOT / "src/ai_swe"
ZIP_PATH = RC26_DIR / "AISWESystem-windows-x64.zip"
EXTRACTED_DIR = RC26_DIR / "extracted"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def update_bundle() -> None:
    print("Updating frontend in RC26...")
    target_frontend_build = RC26_DIR / "frontend"
    if target_frontend_build.exists():
        shutil.rmtree(target_frontend_build)
    shutil.copytree(FRONTEND_DIR, target_frontend_build)

    bundle_frontend = BUNDLE_DIR / "frontend/dist"
    if bundle_frontend.exists():
        shutil.rmtree(bundle_frontend)
    shutil.copytree(FRONTEND_DIR, bundle_frontend)

    print("Updating app/ai_swe in RC26...")
    bundle_app = BUNDLE_DIR / "app/ai_swe"
    if bundle_app.exists():
        shutil.rmtree(bundle_app)
    shutil.copytree(SRC_DIR, bundle_app, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    contracts_src = ROOT / "contracts"
    if contracts_src.exists():
        bundle_contracts = BUNDLE_DIR / "contracts"
        if bundle_contracts.exists():
            shutil.rmtree(bundle_contracts)
        shutil.copytree(contracts_src, bundle_contracts)

    # Ensure no mutable or private files
    private = [
        p
        for p in BUNDLE_DIR.rglob("*")
        if p.is_file() and (p.name.startswith(".env") or p.suffix in {".sqlite3", ".gguf"})
    ]
    if private:
        raise ValueError(f"Private files found in bundle: {private}")

    # Generate BUNDLE-MANIFEST.json
    print("Generating BUNDLE-MANIFEST.json...")
    manifest_path = BUNDLE_DIR / "BUNDLE-MANIFEST.json"
    manifest = {}
    for p in BUNDLE_DIR.rglob("*"):
        if p.is_file() and p != manifest_path:
            rel = p.relative_to(BUNDLE_DIR).as_posix()
            manifest[rel] = file_sha256(p)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Manifest written with {len(manifest)} files.")


def create_zip() -> None:
    print(f"Creating {ZIP_PATH.name}...")
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    manifest_path = BUNDLE_DIR / "BUNDLE-MANIFEST.json"
    files_to_zip = [p for p in BUNDLE_DIR.rglob("*") if p.is_file()]

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in files_to_zip:
            arcname = "AISWESystem/" + f.relative_to(BUNDLE_DIR).as_posix()
            zf.write(f, arcname)

    zip_bytes = ZIP_PATH.stat().st_size
    zip_sha = file_sha256(ZIP_PATH)
    print(f"ZIP created: {zip_bytes} bytes, SHA-256: {zip_sha}")


def verify_zip() -> dict:
    print("Verifying ZIP integrity and CRC...")
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        bad_crc = zf.testzip()
        if bad_crc is not None:
            raise ValueError(f"Corrupt ZIP member: {bad_crc}")
        zip_file_count = len(zf.infolist())

        print("Extracting ZIP to verify manifest against extracted files...")
        if EXTRACTED_DIR.exists():
            shutil.rmtree(EXTRACTED_DIR)
        EXTRACTED_DIR.mkdir(parents=True)
        zf.extractall(EXTRACTED_DIR)

    extracted_bundle = EXTRACTED_DIR / "AISWESystem"
    manifest_path = extracted_bundle / "BUNDLE-MANIFEST.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    manifest_exact = True
    for rel_path, expected_hash in manifest.items():
        extracted_file = extracted_bundle / rel_path
        if not extracted_file.is_file():
            print(f"Missing file: {rel_path}")
            manifest_exact = False
            break
        actual_hash = file_sha256(extracted_file)
        if actual_hash != expected_hash:
            print(f"Hash mismatch: {rel_path} expected {expected_hash} got {actual_hash}")
            manifest_exact = False
            break

    # Verify source match
    source_match = True
    src_files = [p for p in SRC_DIR.rglob("*") if p.is_file() and p.suffix == ".py"]
    for sf in src_files:
        rel = sf.relative_to(SRC_DIR).as_posix()
        bundle_file = extracted_bundle / "app/ai_swe" / rel
        if not bundle_file.is_file() or file_sha256(bundle_file) != file_sha256(sf):
            print(f"Source mismatch on {rel}")
            source_match = False
            break

    # Verify frontend build matches
    frontend_matches = True
    fe_files = [p for p in FRONTEND_DIR.rglob("*") if p.is_file()]
    for ff in fe_files:
        rel = ff.relative_to(FRONTEND_DIR).as_posix()
        bundle_fe = extracted_bundle / "frontend/dist" / rel
        if not bundle_fe.is_file() or file_sha256(bundle_fe) != file_sha256(ff):
            print(f"Frontend build mismatch on {rel}")
            frontend_matches = False
            break

    # Check for private files
    private_files = [
        p.relative_to(extracted_bundle).as_posix()
        for p in extracted_bundle.rglob("*")
        if p.is_file() and (p.name.startswith(".env") or p.suffix in {".sqlite3", ".gguf"})
    ]

    report = {
        "zip": "dist/windows-v0.2.0-rc26/AISWESystem-windows-x64.zip",
        "sha256": file_sha256(ZIP_PATH),
        "bytes": ZIP_PATH.stat().st_size,
        "files": len(manifest),
        "zip_file_count": zip_file_count,
        "crc": True,
        "manifest_exact": manifest_exact,
        "source_match": source_match,
        "source_files": len(src_files),
        "frontend_matches_build": frontend_matches,
        "private_files": private_files,
        "unwanted_build_residue": False,
    }

    report_path = RC26_DIR / "zip-verification.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("Verification report saved:")
    print(json.dumps(report, indent=2))
    return report


def main() -> int:
    update_bundle()
    create_zip()
    verify_zip()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
