"""Offline regression for conservative pre-call spending protection."""

import json
import uuid

import pytest

from ai_swe.config import Settings
from ai_swe.models import ModelMessage, ModelRequest, ModelUsage, gateway_from_settings
from ai_swe.models.errors import ModelConfigurationError
from ai_swe.models.providers.fake import FakeModelAdapter
from ai_swe.state.budget_ledger import BudgetLedger


def test_request_without_conservative_reservation_never_reaches_adapter(tmp_path):
    settings = Settings(
        _env_file=None,
        profile_id=str(uuid.uuid4()),
        state_db_path=tmp_path / "state.sqlite3",
        max_cost_per_run=0.8,
        model_provider="openai_compatible",
        model_name="test",
        model_pricing=json.dumps(
            [{"model": "test", "input_per_1k": 1, "output_per_1k": 0, "currency": "USD"}]
        ),
    )
    ledger = BudgetLedger(settings.state_db_path)
    ledger.set_limit(0.8)
    adapter = FakeModelAdapter(model="test", usage=ModelUsage(input_tokens=1, output_tokens=1))
    request = ModelRequest(
        messages=[ModelMessage(role="user", content="!?" * 500)],
        model="test",
        run_id="budget-test",
        max_output_tokens=10,
    )
    gateway = gateway_from_settings(settings, adapters=[adapter])
    try:
        with pytest.raises(ModelConfigurationError):
            gateway.generate(request)
        assert not adapter.calls
        assert ledger.summary()["reserved"] == 0
    finally:
        gateway.close()
