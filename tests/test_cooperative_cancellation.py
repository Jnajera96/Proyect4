import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from test_project_builder_pipeline import BuilderAdapter, project_files

from ai_swe.config import Settings
from ai_swe.contracts import RunOptions
from ai_swe.graph import NothingToResume, RunEngine, model_routing
from ai_swe.models import ModelGateway, ModelUsage
from ai_swe.models.gateway import gateway_from_settings
from ai_swe.state import RunStore
from ai_swe.state.budget_ledger import BudgetLedger


def settings_for(tmp_path):
    return Settings(
        _env_file=None,
        network_egress_enabled=True,  # Trusted synthetic native-execution fixtures.
        profile_id="cancel-fixture",
        model_provider="fake",
        model_name="fixture",
        remote_model_roles=["coder", "reviewer"],
        state_db_path=tmp_path / "state.sqlite3",
        workspace_root=tmp_path / "worktrees",
        max_cost_per_run=0.1,
        model_pricing='[{"model":"fixture","input_per_1k":0.001,"output_per_1k":0.001}]',
    )


def test_unverified_execution_cleanup_preserves_worktree_and_reservations(tmp_path):
    settings = settings_for(tmp_path)
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado("crea un juego")
        engine.create(state)
        worktree = settings.workspace_root / state.run_id
        worktree.mkdir(parents=True)
        state = state.model_copy(update={"artifacts": state.artifacts.model_copy(
            update={"worktree_path": str(worktree)})})
        engine._app.update_state(engine._config(state.run_id), state.model_dump())
        ledger = BudgetLedger(settings.state_db_path)
        ledger.set_limit(5)
        ledger.reserve_call(state.run_id, run_limit=0.1, estimate=0.01)
        engine._cancel_control(state.run_id).block_cleanup("Contenedor sin cierre verificado")
        result = engine.request_cancel(state.run_id)
        assert result.status == "needs_human" and worktree.exists()
        assert result.cancellation.status == "requested"
        assert result.cancellation.finished_at is None
        assert result.cancellation.released_reservations == 0
        assert ledger.summary()["reserved"] == 0.1
        assert result.errors[-1].error_class == "CANCEL_CLEANUP_UNVERIFIED"


def repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@localhost",
            "commit",
            "--allow-empty",
            "-qm",
            "base",
        ],
        check=True,
        capture_output=True,
    )
    return root


def test_queued_cancel_does_not_execute_and_releases_only_unsent(tmp_path):
    settings = settings_for(tmp_path)
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado("crea un juego")
        engine.create(state)
        ledger = BudgetLedger(settings.state_db_path)
        ledger.set_limit(5)
        ledger.reserve_call(state.run_id, run_limit=0.1, estimate=0.01)
        sent = ledger.reserve_call("other", run_limit=0.2, estimate=0.01)
        ledger.mark_dispatched(sent)
        result = engine.request_cancel(state.run_id)
        assert result.status == "cancelled"
        assert result.cancellation.status == "confirmed"
        assert result.cancellation.released_reservations == 1
        assert ledger.summary()["reserved"] == 0.2
        assert engine.execute(state.run_id).status == "cancelled"
        assert engine.request_cancel(state.run_id).status == "cancelled"
        with pytest.raises(NothingToResume):
            engine.resume(state.run_id, "approved")


def test_cancel_at_approval_removes_only_owned_worktree(tmp_path, monkeypatch):
    settings = settings_for(tmp_path)
    repo = repository(tmp_path)
    adapter = BuilderAdapter(project_files("calendar"))
    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: ModelGateway([adapter]))
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado("crea un calendario", options=RunOptions(repo_path=str(repo)))
        engine.start(state)
        waiting = engine.resume(state.run_id, "approved")
        assert waiting.status == "awaiting_approval", waiting.errors
        from pathlib import Path

        worktree = Path(waiting.artifacts.worktree_path)
        assert worktree.exists()
        result = engine.request_cancel(state.run_id)
        assert result.status == "cancelled"
        assert result.cancellation.worktree_cleanup == "removed"
        assert not worktree.exists() and repo.exists()
        assert not (repo / "index.html").exists()
        with pytest.raises(NothingToResume):
            engine.resume(state.run_id, "approved")
        assert len(adapter.calls) == 2


@pytest.mark.parametrize("known_usage", [True, False])
def test_active_model_finishes_before_confirmation_no_next_agent_and_no_false_refund(
    tmp_path,
    monkeypatch,
    known_usage,
):
    settings = settings_for(tmp_path)
    repo = repository(tmp_path)
    entered, release = Event(), Event()

    class BlockingAdapter(BuilderAdapter):
        def generate(self, request):
            entered.set()
            assert release.wait(15), "test must release the fake adapter"
            return super().generate(request)

    adapter = BlockingAdapter(project_files("calendar"))
    adapter._model = "fixture"
    if not known_usage:
        adapter._usage = ModelUsage()
    monkeypatch.setattr(
        model_routing,
        "gateway_from_settings",
        lambda configured: gateway_from_settings(configured, adapters=[adapter]),
    )
    with RunStore(settings.state_db_path) as store:
        ledger = BudgetLedger(settings.state_db_path)
        ledger.set_limit(5)
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado("crea un calendario", options=RunOptions(repo_path=str(repo)))
        engine.start(state)
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(engine.resume, state.run_id, "approved")
            try:
                assert entered.wait(10)
                pending = engine.request_cancel(state.run_id)
                assert pending.cancellation.status == "requested"
                assert pending.status != "cancelled"
                assert ledger.summary()["reserved"] == 0.1
            finally:
                release.set()
            result = future.result(timeout=30)
        assert result.status == "cancelled"
        assert result.cancellation.status == "confirmed"
        assert len(adapter.calls) == 1
        assert not (repo / "index.html").exists()
        assert not result.promotion_receipt
        if known_usage:
            assert ledger.summary()["consumed"] > 0 and ledger.summary()["reserved"] == 0
            assert result.cancellation.unresolved_reservations == 0
        else:
            assert ledger.summary()["reserved"] == 0.1
            assert result.cancellation.unresolved_reservations == 1


def test_legacy_unknown_reservation_is_not_refunded(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.sqlite3")
    ledger.set_limit(1)
    ledger.reserve("legacy", 0.5, run_limit=1)
    assert ledger.reconcile_cancelled("legacy") == {"released": 0, "unresolved": 1}
    assert ledger.summary()["reserved"] == 0.5


def test_unknown_settlement_is_not_proof_of_no_dispatch(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.sqlite3")
    ledger.set_limit(1)
    reservation = ledger.reserve_call("unknown", run_limit=0.5, estimate=0.01)
    ledger.settle(reservation, None)
    assert ledger.reconcile_cancelled("unknown") == {"released": 0, "unresolved": 1}


def test_cancel_never_deletes_repository_as_worktree(tmp_path):
    settings = settings_for(tmp_path)
    repo = repository(tmp_path)
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado("analiza el proyecto", options=RunOptions(repo_path=str(repo)))
        waiting = engine.start(state)
        artifacts = waiting.artifacts.model_copy(update={"worktree_path": str(repo)})
        engine._app.update_state(
            engine._config(state.run_id),
            waiting.model_copy(update={"artifacts": artifacts}).model_dump(),
        )
        result = engine.request_cancel(state.run_id)
        assert result.status == "cancelled"
        assert result.cancellation.worktree_cleanup == "failed"
        assert (repo / ".git").exists()


def test_cancellation_during_atomic_promotion_reports_too_late(tmp_path, monkeypatch):
    from functools import wraps

    from ai_swe.graph import nodes

    settings = settings_for(tmp_path)
    repo = repository(tmp_path)
    entered, release = Event(), Event()
    original = nodes.promote_changes

    @wraps(original)
    def promotion(state):
        entered.set()
        assert release.wait(15)
        return original(state)

    monkeypatch.setattr(nodes, "promote_changes", promotion)
    adapter = BuilderAdapter(project_files("calendar"))
    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: ModelGateway([adapter]))
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado("crea un calendario", options=RunOptions(repo_path=str(repo)))
        engine.start(state)
        assert engine.resume(state.run_id, "approved").status == "awaiting_approval"
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(engine.resume, state.run_id, "approved")
            try:
                assert entered.wait(10)
                assert engine.request_cancel(state.run_id).cancellation.status == "requested"
            finally:
                release.set()
            result = future.result(timeout=30)
        assert result.status == "completed", result.errors
        assert result.cancellation.status == "too_late"
        assert result.promotion_receipt.status == "promoted"
        assert (repo / "index.html").exists()
        assert result.final_report
