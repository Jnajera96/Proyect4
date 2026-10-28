"""Offline guard tests; no model requests or public catalog access."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decimal import Decimal

import pytest

from tools.model_lab import Candidate, GateRequired
from tools.verify_calculator_e2e import main, reserve_batch, verify_activity


def fixture_paths(tmp_path):
    ledger = tmp_path / "spend.json"
    ledger.write_text(json.dumps({"authorized_usd": "3", "reserved_usd": "1.17", "batches": []}))
    observations = tmp_path / "observations.json"
    observations.write_text(
        json.dumps(
            [
                {
                    "reservations": [
                        {
                            "id": "ui-id",
                            "run_id": "ui-run",
                            "reserved": 1,
                            "consumed": 0.0001,
                        }
                    ]
                }
            ]
        )
    )
    candidate = Candidate(
        model_id="Qwen/Coder",
        provider="nscale",
        status="live",
        context_length=32768,
        input_usd_per_million=0.02,
        output_usd_per_million=0.06,
    )
    return ledger, observations, candidate


def test_default_is_offline(monkeypatch):
    monkeypatch.setattr("tools.model_lab.discover", lambda: pytest.fail("network forbidden"))
    assert main([]) == 0


def test_reserve_all_attempts_deduplicates_ui_and_retains_full_reservation(tmp_path):
    ledger, observations, candidate = fixture_paths(tmp_path)
    first = reserve_batch(ledger, observations, candidate, tmp_path / "a.json")
    second = reserve_batch(ledger, observations, candidate, tmp_path / "b.json")
    state = json.loads(ledger.read_text())
    assert Decimal(state["reserved_usd"]) == Decimal("2.17") + first + second
    assert len([b for b in state["batches"] if b.get("observation_id") == "ui-id"]) == 1
    assert state["batches"][-1]["maximum_attempts"] == 18
    assert not ledger.with_suffix(".calculator.lock").exists()


def test_insufficient_budget_retains_observation_but_no_inference_batch(tmp_path):
    ledger, observations, candidate = fixture_paths(tmp_path)
    candidate.input_usd_per_million = 1000
    with pytest.raises(GateRequired):
        reserve_batch(ledger, observations, candidate, tmp_path / "a.json")
    state = json.loads(ledger.read_text())
    assert Decimal(state["reserved_usd"]) == Decimal("2.17")
    assert len(state["batches"]) == 1


def test_unknown_tariff_refuses_and_existing_lock_is_preserved(tmp_path):
    ledger, observations, candidate = fixture_paths(tmp_path)
    candidate.input_usd_per_million = None
    with pytest.raises(GateRequired):
        reserve_batch(ledger, observations, candidate, tmp_path / "a.json")
    lock = ledger.with_suffix(".calculator.lock")
    lock.write_text("other process")
    with pytest.raises(FileExistsError):
        reserve_batch(ledger, observations, candidate, tmp_path / "a.json")
    assert lock.read_text() == "other process"


def test_activity_requires_remote_review_after_tests():
    events = [
        {"seq": 1, "kind": "model_response_received", "data": {}},
        {"seq": 2, "kind": "test_target_started", "data": {"target": "pytest.unit"}},
        {"seq": 3, "kind": "test_target_completed", "data": {"target": "pytest.unit"}},
        {"seq": 4, "kind": "test_target_completed", "data": {"target": "ruff.check"}},
        {"seq": 5, "kind": "model_response_received", "data": {}},
    ]
    verify_activity(events)
    with pytest.raises(AssertionError):
        verify_activity(events[:-1])


@pytest.mark.parametrize(
    "bounds",
    [
        {"maximum_attempts": 2, "logical_calls": 2},
        {"max_output_tokens": 992},
        {"max_input_tokens": 11200},
    ],
)
def test_unenforced_smaller_bounds_cannot_shrink_reservation(tmp_path, bounds):
    ledger, observations, candidate = fixture_paths(tmp_path)
    before = ledger.read_bytes()
    with pytest.raises(ValueError):
        reserve_batch(ledger, observations, candidate, tmp_path / "report.json", **bounds)
    assert ledger.read_bytes() == before
