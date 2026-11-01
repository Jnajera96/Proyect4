from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import subprocess

import pytest

from ai_swe.config import Settings
from ai_swe.contracts import Instruction, RunOptions, RunState, RunStatus
from ai_swe.contracts.outputs import CodeProposal, FileOperation, FileProposal, TestRun
from ai_swe.graph import nodes
from ai_swe.graph.engine import RunEngine
from ai_swe.sandbox import crear as crear_sandbox
from ai_swe.state import RunStore
from ai_swe.state.budget_ledger import BudgetLedger
from ai_swe.state.continuity import ContinuityError, ContinuityStore, import_vault_to_profile
from ai_swe.state.memory import MemoryStore
from ai_swe.state.profiles import ProfileStore


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True)
    return result.stdout.decode("utf-8").strip()


def repo_at(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q")
    (path / "app.py").write_bytes(b"value = 1\n")
    (path / "deleted.bin").write_bytes(b"\x00old\xff")
    git(path, "add", ".")
    git(path, "-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-qm", "base")
    return path


def make_state(repo: Path, run_id: str = "run-m1", mode: str = "FULL_PROPOSAL") -> RunState:
    now = datetime.now(UTC)
    return RunState(
        run_id=run_id,
        trace_id=f"trace-{run_id}",
        created_at=now,
        updated_at=now,
        instruction=Instruction(
            text="modifica app.py sapphire",
            source="text",
            confirmed_by_user=True,
        ),
        options=RunOptions(repo_path=str(repo), mode=mode),
    )


def test_worktree_snapshot_captures_modified_binary_untracked_and_deleted(tmp_path):
    repo = repo_at(tmp_path / "repo")
    db = tmp_path / "state.sqlite3"
    wt_root = tmp_path / "worktrees"
    sandbox = crear_sandbox(repo, "run-snap", workspace_root=wt_root)
    (sandbox.raiz / "app.py").write_bytes(b"value = 77\n")
    (sandbox.raiz / "added.bin").write_bytes(b"\x00new\xfe\x01")
    (sandbox.raiz / "nested" / "note.txt").parent.mkdir(parents=True, exist_ok=True)
    (sandbox.raiz / "nested" / "note.txt").write_bytes(b"untracked note\n")
    (sandbox.raiz / "deleted.bin").unlink()

    continuity = ContinuityStore(db, "alice", worktrees_root=wt_root)
    snap = continuity.capture_worktree(
        "run-snap", repo, sandbox.raiz, base_commit=sandbox.base_commit
    )
    by_path = {item["path"]: item for item in snap["inventory"]}
    assert by_path["app.py"]["status"] == "present"
    assert by_path["added.bin"]["status"] == "present"
    assert by_path["nested/note.txt"]["status"] == "present"
    assert by_path["deleted.bin"]["status"] == "deleted"

    restored_wt_root = tmp_path / "restored-worktrees"
    reconstructed = continuity.reconstruct_worktree("run-snap", repo, restored_wt_root)
    assert (reconstructed / "app.py").read_bytes() == b"value = 77\n"
    assert (reconstructed / "added.bin").read_bytes() == b"\x00new\xfe\x01"
    assert (reconstructed / "nested" / "note.txt").read_bytes() == b"untracked note\n"
    assert not (reconstructed / "deleted.bin").exists()

    # Reject malicious path traversal in inventory
    bad_snap = {
        **snap,
        "inventory": [
            {
                "path": "../escape.txt",
                "status": "present",
                "sha256": "0" * 64,
                "size": 1,
                "mode": 0o644,
                "content_b64": "YQ==",
            }
        ],
    }
    with pytest.raises(ContinuityError):
        continuity.reconstruct_worktree("run-snap", repo, restored_wt_root, snapshot=bad_snap)


def test_manual_cooperative_pause_at_node_boundary_and_resume(tmp_path):
    repo = repo_at(tmp_path / "repo")
    settings = Settings(
        _env_file=None,
        profile_id="alice",
        state_db_path=tmp_path / "alice.sqlite3",
        workspace_root=tmp_path / "worktrees",
        remote_model_roles=[],
    )
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        st = engine.create(make_state(repo, "run-pause", "PLAN_ONLY"))

        # Export while a run is 'planned' (in-flight) is rejected
        with pytest.raises(ContinuityError):
            engine.continuity.export_archive("correct-horse-battery")

        # Cooperative manual pause transitions run to 'paused'
        paused = engine.request_pause(st.run_id)
        assert paused.status is RunStatus.PAUSED

        # Now export succeeds because run is paused at a consistent checkpoint
        archive = engine.continuity.export_archive("correct-horse-battery")
        assert archive

        # Resume paused run to completion
        resumed = engine.resume_paused(st.run_id)
        if resumed.status.is_awaiting_human:
            resumed = engine.resume(st.run_id, "approved")
        assert resumed.status is RunStatus.COMPLETED
        assert resumed.plan is not None


def test_export_archive_encryption_tamper_wrong_password_and_no_plaintext(tmp_path):
    repo = repo_at(tmp_path / "repo")
    db = tmp_path / "alice.sqlite3"
    settings = Settings(
        _env_file=None,
        profile_id="alice",
        state_db_path=db,
        workspace_root=tmp_path / "worktrees",
        remote_model_roles=[],
    )
    with RunStore(db) as store:
        engine = RunEngine(store, settings=settings)
        run = engine.start(make_state(repo, "run-sec", "INSPECT_ONLY"))
        assert run.status is RunStatus.COMPLETED
        archive = engine.continuity.export_archive("super-secret-pass-123")

    assert b"SQLite format 3" not in archive
    assert b"modifica app.py sapphire" not in archive

    target_cont = ContinuityStore(tmp_path / "dest.sqlite3", "bob", worktrees_root=tmp_path / "dest-wt")
    with pytest.raises(ContinuityError):
        target_cont.import_archive(
            archive,
            "wrong-password-123",
            repo_mapping={str(repo): tmp_path / "new-repo"},
        )
    with pytest.raises(ContinuityError):
        target_cont.import_archive(
            archive[:-10] + b"tampered",
            "super-secret-pass-123",
            repo_mapping={str(repo): tmp_path / "new-repo"},
        )


def test_auto_backup_defers_when_running_and_writes_atomically_when_stabilized(tmp_path):
    repo = repo_at(tmp_path / "repo")
    db = tmp_path / "alice.sqlite3"
    backup_folder = tmp_path / "sync-folder"
    settings = Settings(
        _env_file=None,
        profile_id="alice",
        state_db_path=db,
        workspace_root=tmp_path / "worktrees",
        remote_model_roles=[],
    )
    with RunStore(db) as store:
        engine = RunEngine(store, settings=settings)
        engine.continuity.configure_backup(backup_folder, enabled=True)

        # When active_runs > 0, auto_backup defers and writes nothing
        assert engine.continuity.auto_backup("backup-password-123", active_runs=1) is None
        status = engine.continuity.backup_status()
        assert status["deferred"] is True
        assert status["status"] == "deferred"

        # When stabilized, writes unique encrypted .aiswe-vault file
        engine.start(make_state(repo, "run-bkp", "INSPECT_ONLY"))
        written1 = engine.continuity.auto_backup("backup-password-123", active_runs=0)
        written2 = engine.continuity.auto_backup("backup-password-123", active_runs=0)
        assert written1 is not None and written1.exists()
        assert written2 is not None and written2.exists()
        assert written1 != written2
        assert b"SQLite format 3" not in written1.read_bytes()
        status = engine.continuity.backup_status()
        assert status["deferred"] is False
        assert status["status"] == "completed"


def test_lost_device_e2e_recovery_at_review_gate_without_rerunning_coder_or_reviewer(
    tmp_path, monkeypatch
):
    old_repo = repo_at(tmp_path / "old-machine" / "repo")
    old_users = tmp_path / "old-machine" / "users"
    old_profiles = ProfileStore(old_users)
    alice = old_profiles.create("alice", "alice-password-123")

    ledger = BudgetLedger(alice.paths.database)
    ledger.set_limit(10.0)
    res_id = ledger.reserve("run-recover", 1.5, run_limit=2.0)
    ledger.settle(res_id, 0.75)

    proposal = CodeProposal(
        files=[
            FileProposal(
                path="app.py",
                operation=FileOperation.MODIFY,
                new_content="value = 99\n",
                rationale="set value to 99",
            )
        ],
        rationale="update app.py for recovery test",
    )
    change = nodes._cambio_desde_propuesta(proposal)
    monkeypatch.setattr(
        nodes,
        "_coder_del_modelo",
        lambda s: (change, s.budget, [], proposal),
    )
    monkeypatch.setattr(
        nodes,
        "ejecutar_target",
        lambda sandbox, target, permitidos=(), limits=None: TestRun(
            target=target,
            command=["pytest", "-q"],
            exit_code=0,
            passed=True,
            duration_s=0.1,
            output_excerpt="1 passed",
        ),
    )

    alice_settings = alice.settings(Settings(_env_file=None, remote_model_roles=[]))
    with RunStore(alice.paths.database) as old_store:
        old_engine = RunEngine(old_store, settings=alice_settings)
        run = old_engine.start(make_state(old_repo, "run-recover", "FULL_PROPOSAL"))
        assert run.status is RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION
        run = old_engine.resume("run-recover", "approved")
        assert run.status is RunStatus.AWAITING_APPROVAL
        assert (old_repo / "app.py").read_bytes() == b"value = 1\n"

        continuity = ContinuityStore(
            alice.paths.database,
            alice.user_id,
            profile_name=alice.name,
            worktrees_root=alice.paths.worktrees,
        )
        archive_bytes = continuity.export_archive("alice-password-123")

    # Simulate lost device: import into a brand-new ProfileStore and brand-new empty repo path
    new_users = tmp_path / "new-machine" / "users"
    new_profiles = ProfileStore(new_users)
    new_repo = tmp_path / "new-machine" / "authorized-repo"

    restored_profile = import_vault_to_profile(
        new_profiles,
        archive_bytes,
        "alice-password-123",
        new_name="alice-restored",
        new_password="new-device-password-123",
        repo_mapping={str(old_repo): new_repo},
    )

    # Importing into an existing profile name is rejected (no overwrite)
    with pytest.raises(ContinuityError):
        import_vault_to_profile(
            new_profiles,
            archive_bytes,
            "alice-password-123",
            new_name="alice-restored",
            repo_mapping={str(old_repo): tmp_path / "other-repo"},
        )

    # Verify ledger spend, FTS5 memory, and pending gate are preserved without auto-execution
    restored_ledger = BudgetLedger(restored_profile.paths.database)
    assert restored_ledger.summary()["consumed"] == pytest.approx(0.75)
    assert restored_ledger.summary()["limit"] == pytest.approx(10.0)

    restored_mem = MemoryStore(restored_profile.paths.database, restored_profile.user_id)
    assert restored_mem.search(new_repo, "sapphire", exclude_run="another-run")

    # Forbid Coder and Reviewer from running again after import!
    def must_not_rerun(*args, **kwargs):
        pytest.fail("Coder/Reviewer/Tests must not re-run when resuming from approval_gate")

    monkeypatch.setattr(nodes, "_coder_del_modelo", must_not_rerun)
    monkeypatch.setattr(nodes, "ejecutar_target", must_not_rerun)
    monkeypatch.setattr(nodes, "_veredicto_determinista", must_not_rerun)

    restored_settings = restored_profile.settings(Settings(_env_file=None, remote_model_roles=[]))
    with RunStore(restored_profile.paths.database) as new_store:
        new_engine = RunEngine(new_store, settings=restored_settings)
        recovered = new_engine.get("run-recover")
        assert recovered.run_id == "run-recover"
        assert recovered.status is RunStatus.AWAITING_APPROVAL
        assert recovered.next_step == "approval_gate"
        assert Path(recovered.options.repo_path) == new_repo.resolve()
        assert (new_repo / "app.py").read_bytes() == b"value = 1\n"

        # Now approve at approval_gate on the new machine -> promotes directly to new_repo!
        completed = new_engine.resume("run-recover", "approved")
        assert completed.status is RunStatus.COMPLETED
        assert completed.promotion_receipt is not None
        assert completed.promotion_receipt.status == "promoted"
        assert (new_repo / "app.py").read_text(encoding="utf-8") == "value = 99\n"
        assert (old_repo / "app.py").read_bytes() == b"value = 1\n"


def test_import_rejects_occupied_non_git_dir_dirty_repo_and_ledger_rollback(tmp_path):
    repo = repo_at(tmp_path / "repo")
    db = tmp_path / "alice.sqlite3"
    settings = Settings(
        _env_file=None,
        profile_id="alice",
        state_db_path=db,
        workspace_root=tmp_path / "worktrees",
        remote_model_roles=[],
    )
    ledger = BudgetLedger(db)
    ledger.set_limit(10.0)
    r1 = ledger.reserve("r1", 1.0, run_limit=2.0)
    ledger.settle(r1, 1.0)

    with RunStore(db) as store:
        engine = RunEngine(store, settings=settings)
        engine.start(make_state(repo, "run-1", "INSPECT_ONLY"))
        archive = engine.continuity.export_archive("valid-password-123")

    # 1. Occupied non-git destination directory is rejected
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "file.txt").write_text("do not overwrite", encoding="utf-8")
    dest1 = ContinuityStore(tmp_path / "dest1.sqlite3", "u1", worktrees_root=tmp_path / "wt1")
    with pytest.raises(ContinuityError):
        dest1.import_archive(archive, "valid-password-123", repo_mapping={str(repo): occupied})
    assert (occupied / "file.txt").read_text(encoding="utf-8") == "do not overwrite"

    # 2. Existing dirty git repository is rejected
    dirty_repo = repo_at(tmp_path / "dirty-repo")
    (dirty_repo / "app.py").write_bytes(b"dirty local edit\n")
    dest2 = ContinuityStore(tmp_path / "dest2.sqlite3", "u2", worktrees_root=tmp_path / "wt2")
    with pytest.raises(ContinuityError):
        dest2.import_archive(archive, "valid-password-123", repo_mapping={str(repo): dirty_repo})
    assert (dirty_repo / "app.py").read_bytes() == b"dirty local edit\n"

    # 3. Destination database with higher ledger spend is rejected (no ledger rollback)
    dest3_db = tmp_path / "dest3.sqlite3"
    dest3_ledger = BudgetLedger(dest3_db)
    dest3_ledger.set_limit(20.0)
    r_high = dest3_ledger.reserve("r-high", 5.0, run_limit=5.0)
    dest3_ledger.settle(r_high, 5.0)
    dest3 = ContinuityStore(dest3_db, "u3", worktrees_root=tmp_path / "wt3")
    with pytest.raises(ContinuityError):
        dest3.import_archive(
            archive,
            "valid-password-123",
            repo_mapping={str(repo): tmp_path / "clean-target"},
        )
