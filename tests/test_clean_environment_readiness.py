"""Readiness boundaries: stripped environment, no host discovery and verified bundle bytes."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.verify_second_pc_pilot import PROBE, clean_environment, run_pilot, verify_manifest


def manifest_at(root, entries):
    (root / "BUNDLE-MANIFEST.json").write_text(json.dumps(entries), encoding="utf-8")


@pytest.mark.skipif(os.name != "nt", reason="Windows clean-environment contract")
def test_clean_environment_strips_credentials_configuration_and_proxy(tmp_path, monkeypatch):
    for name in ("HF_TOKEN", "OPENAI_API_KEY", "AI_SWE_PROFILE_MODE", "HTTP_PROXY", "PYTHONPATH"):
        monkeypatch.setenv(name, "synthetic-do-not-inherit")
    env = clean_environment(tmp_path / "user")
    assert env["PATH"] == str(Path(os.environ["SYSTEMROOT"]) / "System32")
    assert env["HF_HUB_OFFLINE"] == "1"
    assert env["LOCALAPPDATA"] == str((tmp_path / "user").resolve())
    assert "synthetic-do-not-inherit" not in env.values()


@pytest.mark.skipif(os.name != "nt", reason="Windows clean-environment contract")
def test_clean_child_cannot_discover_fake_host_tools(tmp_path, monkeypatch):
    tools = tmp_path / "developer-tools"
    tools.mkdir()
    for name in ("python", "node", "git"):
        (tools / (name + ".exe")).write_bytes(b"never execute this synthetic marker")
        assert shutil.which(name, path=str(tools)) is not None
    monkeypatch.setenv("PATH", str(tools))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json,shutil; print(json.dumps({n:shutil.which(n) "
            "for n in ('python','node','git')}))",
        ],
        cwd=tmp_path,
        env=clean_environment(tmp_path / "user"),
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert json.loads(result.stdout) == {"python": None, "node": None, "git": None}


@pytest.mark.parametrize(
    "path", ["../escape", "/escape", "C:/escape", "a\\escape", "a//b", "a:stream"]
)
def test_manifest_rejects_unsafe_names_before_execution(tmp_path, path):
    manifest_at(tmp_path, {path: "0" * 64})
    with pytest.raises(ValueError, match="Unsafe"):
        verify_manifest(tmp_path)


def test_manifest_detects_tampering_and_unlisted_files(tmp_path):
    content = tmp_path / "fixture.txt"
    content.write_bytes(b"trusted")
    manifest_at(tmp_path, {"fixture.txt": hashlib.sha256(b"trusted").hexdigest()})
    assert verify_manifest(tmp_path)["files"] == 1
    content.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_manifest(tmp_path)
    content.write_bytes(b"trusted")
    (tmp_path / "unlisted.txt").write_bytes(b"residue")
    with pytest.raises(ValueError, match="inventory"):
        verify_manifest(tmp_path)


def test_manifest_rejects_case_collisions(tmp_path):
    (tmp_path / "file.txt").write_bytes(b"trusted")
    digest = hashlib.sha256(b"trusted").hexdigest()
    manifest_at(tmp_path, {"file.txt": digest, "FILE.txt": digest})
    with pytest.raises(ValueError, match="Case-colliding"):
        verify_manifest(tmp_path)


def test_embedded_runtime_probe_compiles():
    compile(PROBE, "second-pc-runtime-probe", "exec")


@pytest.mark.skipif(os.name != "nt", reason="Windows pilot boundary")
def test_evidence_directory_cannot_modify_historical_bundle(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    with pytest.raises(ValueError, match="outside"):
        run_pilot(bundle, bundle / "evidence")
    assert not (bundle / "evidence").exists()
