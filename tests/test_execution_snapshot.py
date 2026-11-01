import hashlib
import json
import os
import subprocess

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Secure Windows snapshot handles")


def test_snapshot_copies_code_and_excludes_credentials_and_git(tmp_path):
    from ai_swe.tools.execution_snapshot import create_snapshot

    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_bytes(b"answer = 42\n")
    (source / ".env").write_text("synthetic-secret")
    (source / "user.aiswe-vault").write_bytes(b"encrypted synthetic fixture")
    (source / ".git").write_text("gitdir: outside")
    dest = tmp_path / "snapshot"
    digest = create_snapshot(source, dest)
    assert (dest / "app.py").read_bytes() == b"answer = 42\n"
    assert sorted(p.name for p in dest.iterdir()) == [".aiswe-snapshot.json", "app.py"]
    manifest = json.loads((dest / ".aiswe-snapshot.json").read_text())
    assert manifest == {"app.py": hashlib.sha256(b"answer = 42\n").hexdigest()}
    assert len(digest) == 64 and "synthetic-secret" not in json.dumps(manifest)


def test_snapshot_rejects_hardlinks_before_copying_their_bytes(tmp_path):
    from ai_swe.tools.execution_snapshot import SnapshotError, create_snapshot

    outside = tmp_path / "outside"
    outside.write_text("synthetic outside secret")
    source = tmp_path / "source"
    source.mkdir()
    os.link(outside, source / "app.py")
    with pytest.raises(SnapshotError):
        create_snapshot(source, tmp_path / "snapshot")
    assert outside.read_text() == "synthetic outside secret"


def test_snapshot_rejects_directory_junction(tmp_path):
    from ai_swe.tools.execution_snapshot import SnapshotError, create_snapshot

    outside, source = tmp_path / "outside", tmp_path / "source"
    outside.mkdir()
    source.mkdir()
    (outside / "secret.txt").write_text("synthetic outside secret")
    subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(source / "external"), str(outside)],
        check=True, capture_output=True,
    )
    with pytest.raises(SnapshotError):
        create_snapshot(source, tmp_path / "snapshot")
    assert (outside / "secret.txt").read_text() == "synthetic outside secret"


def test_snapshot_rejects_occupied_destination_and_self_copy(tmp_path):
    from ai_swe.tools.execution_snapshot import SnapshotError, create_snapshot

    (tmp_path / "app.py").write_text("data = 1")
    with pytest.raises(SnapshotError):
        create_snapshot(tmp_path, tmp_path / "nested")
    assert not (tmp_path / "nested").exists()
    with pytest.raises(SnapshotError):
        create_snapshot(tmp_path, tmp_path)


def test_snapshot_rejects_reserved_manifest_and_oversized_input(tmp_path):
    from ai_swe.tools.execution_snapshot import SnapshotError, create_snapshot

    source = tmp_path / "source"
    source.mkdir()
    (source / ".aiswe-snapshot.json").write_text("untrusted")
    with pytest.raises(SnapshotError):
        create_snapshot(source, tmp_path / "snapshot")
    (source / ".aiswe-snapshot.json").unlink()
    (source / "large.bin").write_bytes(b"x" * 1025)
    with pytest.raises(SnapshotError):
        create_snapshot(source, tmp_path / "bounded", max_bytes=1024)
