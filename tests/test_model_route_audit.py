from decimal import Decimal

import pytest

from tools.audit_model_catalog import assess
from tools.model_lab import Candidate, GateRequired
from tools.validate_model_routes import reserve_session


def candidate(**kwargs):
    return Candidate(
        model_id="fixture/model",
        provider="fixture",
        status="live",
        context_length=4096,
        input_usd_per_million=0.1,
        output_usd_per_million=0.2,
        supports_structured_output=True,
        **kwargs,
    )


def test_audit_keeps_historical_reservations_and_does_not_claim_inference():
    ledger = {"authorized_usd": "5", "reserved_usd": "4.99999104"}
    result = assess(
        [{"id": "fixture/model:fixture", "label": "Fixture", "projectValidated": False}],
        [candidate()],
        ledger,
    )
    assert result["available_conservative_usd"] == "0.00000896"
    assert result["inference_calls"] == 0
    assert result["models"][0]["status"] == "candidate_unverified"
    assert not result["models"][0]["budget_allows_batch"]
    assert ledger["reserved_usd"] == "4.99999104"


def test_missing_structured_output_is_not_mislabeled_as_failed_inference():
    c = candidate().model_copy(update={"supports_structured_output": False})
    result = assess(
        [{"id": c.routing_id, "label": "Fixture", "projectValidated": False}],
        [c],
        {"authorized_usd": "5", "reserved_usd": "0"},
    )
    assert result["models"][0]["status"] == "structured_output_not_declared"
    assert not result["models"][0]["new_inference_tested"]
    assert result["models"][0]["batch_reservation_usd"] is None


def session(**kwargs):
    return {
        "total_ceiling_usd": "5",
        "account_usage_usd": "0.04",
        "account_credit_usd": "4.96",
        "authorized_usd": "2",
        "reserved_usd": "0",
        "billing_evidence": "user-provided account screenshot, 2026-10-31",
        **kwargs,
    }


def test_session_has_bounded_reservations_and_does_not_mutate_evidence():
    ledger = session()
    amount = reserve_session(ledger, [candidate()])
    assert Decimal(0) < amount < Decimal("2")
    assert ledger["reserved_usd"] == "0"
    with pytest.raises(GateRequired):
        reserve_session(session(reserved_usd="2"), [candidate()])


@pytest.mark.parametrize(
    "overrides",
    [
        {"authorized_usd": "3"},
        {"account_usage_usd": "4.99"},
        {"billing_evidence": ""},
        {"total_ceiling_usd": "6"},
        {"reserved_usd": "NaN"},
        {"account_credit_usd": "0"},
    ],
)
def test_session_cannot_bypass_ceiling_or_missing_evidence(overrides):
    with pytest.raises(GateRequired):
        reserve_session(session(**overrides), [candidate()])
