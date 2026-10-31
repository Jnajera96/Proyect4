import hashlib
import json
import sqlite3
import sys
import zipfile
from contextlib import closing
from types import SimpleNamespace

import pytest
from test_migrations import legacy, version

from ai_swe.state.migrations import MigrationError, SchemaMigrator
from ai_swe.state.operation_lock import operation_lock
from tools import upgrade_portable as tool


def files(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


@pytest.fixture
def installations(tmp_path, monkeypatch):
    source, target, data = [tmp_path / p for p in ("old", "new", "installed")]
    for directory in (source, target):
        (directory / "runtime").mkdir(parents=True)
        (directory / "runtime/python.exe").write_bytes(b"synthetic signed runtime placeholder")
        (directory / "start.py").write_text("# test bootstrap")
    monkeypatch.setattr(tool, "assert_server_stopped", lambda *_: None)
    monkeypatch.setattr(tool, "user_paths", lambda: SimpleNamespace(root=data))
    return source, target, data


def test_upgrade_tool_end_to_end(installations, monkeypatch, capsys):
    source, target, data = installations
    legacy(source / "data/users/alice/state.sqlite3")
    (source / ".env").write_text("HF_TOKEN=synthetic-only")
    (source / "recovery.aiswe-vault").write_bytes(b"encrypted-fixture")
    original, runtime = files(source), files(target)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "upgrade_portable.py",
            "--source",
            str(source),
            "--target",
            str(target),
            "--data-dir",
            str(data),
        ],
    )
    assert tool.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["databases"] == 1 and report["runtime_unchanged"]
    assert version(target / "data/users/alice/state.sqlite3") == 3
    assert (target / ".env").read_bytes() == (source / ".env").read_bytes()
    assert (target / "recovery.aiswe-vault").read_bytes() == b"encrypted-fixture"
    assert files(source) == original
    assert all(files(target)[p] == digest for p, digest in runtime.items())
    with zipfile.ZipFile(report["backup"]) as archive:
        assert archive.testzip() is None
        assert "upgrade-backup-manifest.json" in archive.namelist()
        assert any(name.endswith("state.sqlite3") for name in archive.namelist())


def test_external_installed_data_and_budget_preserved(installations):
    source, target, data = installations
    legacy(data / "data/users/alice/state.sqlite3")
    (data / "config").mkdir()
    (data / "config/.env").write_text("HF_TOKEN=fake")
    original = files(data)
    report = tool.upgrade(source, target, data_dir=data)
    assert version(data / "data/users/alice/state.sqlite3") == 3
    assert files(tool.Path(report["previous_data"])) == original
    with closing(sqlite3.connect(data / "data/users/alice/state.sqlite3")) as db:
        assert db.execute("SELECT reserved,consumed FROM budget_reservations").fetchall() == [
            (0.5, None)
        ]
        assert db.execute("SELECT repo_path FROM projects").fetchone()[0] == "C:/repos/demo"


def test_failure_on_second_database_changes_neither_installation(installations, monkeypatch):
    source, target, data = installations
    for name in ("alice", "bob"):
        legacy(source / f"users/{name}/state.sqlite3")
    original, destination = files(source), files(target)
    migrate = SchemaMigrator.migrate_database
    calls = []

    def fail(self, path):
        calls.append(path)
        if len(calls) == 2:
            raise MigrationError("Fallo simulado")
        return migrate(self, path)

    monkeypatch.setattr(SchemaMigrator, "migrate_database", fail)
    with pytest.raises(MigrationError):
        tool.upgrade(source, target, data_dir=data)
    assert len(calls) == 2 and files(source) == original and files(target) == destination
    assert list((target.parent / "upgrade-backups").glob("*.zip"))


def test_failed_publish_restores_external_data(installations, monkeypatch):
    source, target, data = installations
    legacy(data / "data/users/alice/state.sqlite3")
    original, destination = files(data), files(target)
    replace = tool.os.replace

    def fail(origin, dest):
        if tool.Path(origin).name == "installed" and tool.Path(dest) == data:
            raise OSError("Simulated publish failure")
        replace(origin, dest)

    monkeypatch.setattr(tool.os, "replace", fail)
    with pytest.raises(OSError):
        tool.upgrade(source, target, data_dir=data)
    assert files(data) == original and files(target) == destination


def test_dry_run_and_destination_conflict(installations):
    source, target, data = installations
    legacy(source / "users/alice/state.sqlite3")
    original, destination = files(source), files(target)
    report = tool.upgrade(source, target, data_dir=data, dry_run=True)
    assert report["backup"] is None and report["databases"] == 1
    assert files(source) == original and files(target) == destination
    (target / "users").mkdir()
    with pytest.raises(tool.UpgradeError, match="ya contiene"):
        tool.upgrade(source, target, data_dir=data)


def test_server_lease_blocks_upgrade(installations):
    source, target, data = installations
    original = files(target)
    with operation_lock(data.parent / f".{data.name}.server.lock"), pytest.raises(OSError):
        tool.upgrade(source, target, data_dir=data)
    assert files(target) == original


def test_generated_app_databases_are_not_migrated(installations):
    source, target, data = installations
    path = source / "worktrees/app/state.sqlite3"
    legacy(path)
    report = tool.upgrade(source, target, data_dir=data)
    assert report["databases"] == 0
    assert (target / "worktrees/app/state.sqlite3").read_bytes() == path.read_bytes()


def test_process_preflight_refuses_legacy_server(monkeypatch):
    if tool.os.name != "nt":
        pytest.skip("Windows process preflight")
    monkeypatch.setattr(
        tool.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            stdout=json.dumps(
                [
                    {"Name": "python.exe", "CommandLine": "python C:/old/start.py --no-browser"},
                ]
            )
        ),
    )
    with pytest.raises(tool.UpgradeError, match="ejecucion"):
        tool.assert_server_stopped(tool.Path("C:/old"), tool.Path("C:/new"))


def test_installed_launcher_obeys_upgrade_lease(installations, monkeypatch):
    import ai_swe.runtime_paths as paths
    from ai_swe import launcher

    _, _, data = installations
    monkeypatch.setattr(paths, "user_paths", lambda: SimpleNamespace(root=data))
    monkeypatch.setattr(
        launcher, "load_settings", lambda **kwargs: SimpleNamespace(runtime_mode="installed")
    )
    monkeypatch.setattr(
        launcher, "_serve", lambda *a, **k: pytest.fail("Must not start during upgrade")
    )
    with operation_lock(data.parent / f".{data.name}.server.lock"), pytest.raises(OSError):
        launcher.serve(open_browser=False)


@pytest.mark.parametrize("published", [False, True])
def test_hard_interruption_restores_installed_data_without_deleting_new_data(
    installations,
    published,
):
    import subprocess

    from ai_swe.state.upgrade_recovery import journal_path, recover_upgrade

    _, _, data = installations
    legacy(data / "data/users/alice/state.sqlite3")
    original = files(data)
    script = """
import os, sys
from pathlib import Path
from ai_swe.state.upgrade_recovery import write_journal
root = Path(sys.argv[1])
previous = root.with_name(root.name + '.pre-upgrade-abc123')
write_journal(root, previous, 'prepared')
os.replace(root, previous)
if sys.argv[2] == 'True':
    root.mkdir()
    (root / 'new-data.txt').write_text('preserve this too')
os._exit(74)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(data), str(published)], check=False, timeout=30
    )
    assert result.returncode == 74 and journal_path(data).is_file()
    assert recover_upgrade(data) and files(data) == original
    assert not journal_path(data).exists()
    if published:
        assert len(list(data.parent.glob(data.name + ".interrupted-*/new-data.txt"))) == 1


def test_launcher_recovers_before_preparing_directories(installations, monkeypatch):
    import ai_swe.runtime_paths as paths
    from ai_swe import launcher
    from ai_swe.state.upgrade_recovery import write_journal

    _, _, data = installations
    data.mkdir()
    (data / "original").write_text("preserved")
    previous = data.with_name(data.name + ".pre-upgrade-abc123")
    write_journal(data, previous, "prepared")
    tool.os.replace(data, previous)
    calls = []

    def settings(*, prepare=True):
        calls.append(prepare)
        assert data.exists() == prepare
        return SimpleNamespace(runtime_mode="installed")

    monkeypatch.setattr(paths, "user_paths", lambda: SimpleNamespace(root=data))
    monkeypatch.setattr(launcher, "load_settings", settings)
    monkeypatch.setattr(launcher, "_serve", lambda *a, **k: 0)
    assert launcher.serve(open_browser=False) == 0
    assert calls == [False, True] and (data / "original").read_text() == "preserved"


def test_recovery_rejects_foreign_paths_and_keeps_committed_update(installations):
    from ai_swe.state.upgrade_recovery import journal_path, recover_upgrade, write_journal

    _, _, data = installations
    data.mkdir()
    journal_path(data).write_text(json.dumps({"state": "prepared", "previous": "../other"}))
    with pytest.raises(RuntimeError, match="invalido"):
        recover_upgrade(data)
    assert data.exists()
    previous = data.with_name(data.name + ".pre-upgrade-abc123")
    previous.mkdir()
    (previous / "old").write_text("old")
    (data / "new").write_text("new")
    write_journal(data, previous, "committed")
    assert not recover_upgrade(data)
    assert (data / "new").read_text() == "new" and (previous / "old").read_text() == "old"


def test_cli_explains_preflight_rejection(installations, monkeypatch, capsys):
    source, target, _ = installations

    def running(*args, **kwargs):
        raise tool.UpgradeError("El servidor esta en ejecucion")

    monkeypatch.setattr(tool, "upgrade", running)
    monkeypatch.setattr(
        sys, "argv", ["upgrade_portable.py", "--source", str(source), "--target", str(target)]
    )
    assert tool.main() == 1
    assert "servidor esta en ejecucion" in capsys.readouterr().out
