from pathlib import Path

import pytest

from tools.build_installer import find_iscc, validate_bundle


def test_installation_preserves_user_data_and_does_not_request_elevation():
    source = (Path(__file__).resolve().parents[1] / "packaging/installer.iss").read_text()
    assert "PrivilegesRequired=lowest" in source
    assert "PrivilegesRequiredOverridesAllowed" not in source
    assert "recursesubdirs createallsubdirs" in source
    assert "[UninstallDelete]\n" not in source
    assert "{localappdata}\\Programs\\AISWESystem" in source
    assert "{autodesktop}" in source and "{group}" in source
    assert "DisableProgramGroupPage=no" in source, "Custom /GROUP must be honored"


def test_incomplete_bundle_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Incomplete"):
        validate_bundle(tmp_path)


def test_private_files_are_rejected(tmp_path):
    for relative in (
        "AISWESystem.exe",
        "_internal/python313.dll",
        "_internal/frontend/dist/index.html",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    (tmp_path / ".env").write_text("HF_TOKEN=synthetic")
    with pytest.raises(ValueError, match="private"):
        validate_bundle(tmp_path)


def test_explicit_compiler_path_is_supported(tmp_path):
    compiler = tmp_path / "ISCC.exe"
    compiler.write_bytes(b"fixture")
    assert find_iscc(compiler) == compiler
