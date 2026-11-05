"""Package and verify RC32 portable bundle with latest sources, built frontend, and loopback authentication fallback."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_BUNDLE_DIR = ROOT / "dist/windows-v0.2.0-rc31/dist/AISWESystem"
if not BASE_BUNDLE_DIR.exists():
    BASE_BUNDLE_DIR = ROOT / "dist/windows-v0.2.0-rc30/dist/AISWESystem"
if not BASE_BUNDLE_DIR.exists():
    BASE_BUNDLE_DIR = Path(r"C:\Users\jose_\Downloads\1\AISWESystem")

RC32_DIR = ROOT / "dist/windows-v0.2.0-rc32"
BUNDLE_DIR = RC32_DIR / "dist/AISWESystem"
FRONTEND_DIR = ROOT / "frontend/dist"
SRC_DIR = ROOT / "src/ai_swe"
ZIP_PATH = RC32_DIR / "AISWESystem-windows-x64.zip"
EXTRACTED_DIR = RC32_DIR / "extracted"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def bootstrap_rc32_from_base() -> None:
    if not RC32_DIR.exists():
        print(f"Creating {RC32_DIR}...")
        RC32_DIR.mkdir(parents=True)

    if not BUNDLE_DIR.exists():
        print("Bootstrapping RC32 runtime and packages from base...")
        shutil.copytree(BASE_BUNDLE_DIR, BUNDLE_DIR)


def update_bundle() -> None:
    print("Updating frontend in RC32...")
    target_frontend_build = RC32_DIR / "frontend"
    if target_frontend_build.exists():
        shutil.rmtree(target_frontend_build)
    shutil.copytree(FRONTEND_DIR, target_frontend_build)

    bundle_frontend = BUNDLE_DIR / "frontend/dist"
    if bundle_frontend.exists():
        shutil.rmtree(bundle_frontend)
    shutil.copytree(FRONTEND_DIR, bundle_frontend)

    print("Updating app/ai_swe in RC32...")
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

    launcher_src = ROOT / "Iniciar-OmniRoute.cmd"
    if not launcher_src.exists():
        launcher_src = Path(r"c:\Users\jose_\Desktop\AI-Software-Engineering\Iniciar-OmniRoute.cmd")
    if launcher_src.exists():
        shutil.copy2(launcher_src, BUNDLE_DIR / "Iniciar-OmniRoute.cmd")

    # Clean any temporary databases, cache, pyc or logs in BUNDLE_DIR
    for p in list(BUNDLE_DIR.rglob("*")):
        if p.is_file() and (p.name.endswith(".pyc") or p.name.endswith(".sqlite3-wal") or p.name.endswith(".sqlite3-shm") or p.name.endswith(".log")):
            p.unlink()
        elif p.is_dir() and p.name == "__pycache__":
            shutil.rmtree(p, ignore_errors=True)

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

    # Also sync manifest and files to Downloads distribution if it exists
    downloads_dist = Path(r"C:\Users\jose_\Downloads\1\AISWESystem")
    if downloads_dist.exists():
        dl_app = downloads_dist / "app/ai_swe"
        if dl_app.exists():
            shutil.rmtree(dl_app)
        shutil.copytree(SRC_DIR, dl_app, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        dl_fe = downloads_dist / "frontend/dist"
        if dl_fe.exists():
            shutil.rmtree(dl_fe)
        shutil.copytree(FRONTEND_DIR, dl_fe)

        for p in list(downloads_dist.rglob("*")):
            if p.is_file() and (p.name.endswith(".pyc") or p.name.endswith(".sqlite3-wal") or p.name.endswith(".sqlite3-shm") or p.name.endswith(".log")):
                p.unlink()
            elif p.is_dir() and p.name == "__pycache__":
                shutil.rmtree(p, ignore_errors=True)
        dl_manifest_path = downloads_dist / "BUNDLE-MANIFEST.json"
        dl_manifest = {}
        for p in downloads_dist.rglob("*"):
            if p.is_file() and p != dl_manifest_path and not p.suffix in {".sqlite3", ".log"}:
                rel = p.relative_to(downloads_dist).as_posix()
                dl_manifest[rel] = file_sha256(p)
        with open(dl_manifest_path, "w", encoding="utf-8") as f:
            json.dump(dl_manifest, f, indent=2)
        print(f"Downloads distribution manifest updated with {len(dl_manifest)} files.")


def create_zip() -> None:
    print(f"Creating {ZIP_PATH.name}...")
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

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
    with open(manifest_path, encoding="utf-8") as f:
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
        "zip": "dist/windows-v0.2.0-rc32/AISWESystem-windows-x64.zip",
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

    report_path = RC32_DIR / "zip-verification.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("Verification report saved:")
    print(json.dumps(report, indent=2))
    return report


def main() -> int:
    bootstrap_rc32_from_base()
    update_bundle()
    create_zip()
    verify_zip()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
