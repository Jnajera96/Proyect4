import hashlib
import sys
import zipfile

import pytest

from ai_swe.config import Settings
from ai_swe.resources import frontend_dist
from ai_swe.tools.runner import comando_de
from tools import signed_runtime
from tools.package_command import package_command


def test_signed_bundle_is_installed_without_forging_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "_ai_swe_bundle", tmp_path, raising=False)
    assert Settings(_env_file=None).runtime_mode == "installed"
    assert frontend_dist() == tmp_path / "frontend/dist"
    assert not sys.frozen


def test_signed_worker_is_closed_and_uses_bundled_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "_ai_swe_bundle", tmp_path, raising=False)
    assert comando_de("pytest.unit") == (
        sys.executable,
        str(tmp_path / "start.py"),
        "--run-test-target",
        "pytest.unit",
    )
    assert comando_de("arbitrary.module") is None


def test_runtime_archive_must_match_official_digest(tmp_path):
    archive = tmp_path / "runtime.zip"
    archive.write_bytes(b"untrusted archive")
    with pytest.raises(ValueError, match="SHA256"):
        signed_runtime.assemble(tmp_path, tmp_path, tmp_path / "bundle", archive, tmp_path)


def test_archive_cannot_escape_runtime_directory(tmp_path, monkeypatch):
    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../outside.txt", "not allowed")
    monkeypatch.setattr(
        signed_runtime, "EMBED_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError, match="Unsafe"):
        signed_runtime.assemble(tmp_path, tmp_path, tmp_path / "bundle", archive, tmp_path)
    assert not (tmp_path / "bundle/outside.txt").exists()


def test_package_entry_is_absolute_and_does_not_use_shell(tmp_path):
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime/python.exe").write_bytes(b"fixture")
    (tmp_path / "start.py").write_text("fixture")
    assert package_command(tmp_path) == [
        str(tmp_path / "runtime/python.exe"),
        "-B",
        str(tmp_path / "start.py"),
    ]


def test_incomplete_signed_package_is_not_executable(tmp_path):
    with pytest.raises(ValueError, match="Incomplete"):
        package_command(tmp_path)
