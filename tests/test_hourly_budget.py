from concurrent.futures import ThreadPoolExecutor

import pytest

from ai_swe.models.errors import BudgetExceededError
from ai_swe.state.budget_ledger import BudgetLedger


def test_rolling_hour_and_unknown_reservations_survive_restart(tmp_path, monkeypatch):
    import ai_swe.state.budget_ledger as module

    now = [10000.0]
    monkeypatch.setattr(module.time, "time", lambda: now[0])
    path = tmp_path / "budget.sqlite3"
    ledger = BudgetLedger(path)
    ledger.set_limit(5)
    first = ledger.reserve_call("one", run_limit=0.4, estimate=0.1, hourly_limit=0.5)
    ledger.settle(first, 0.4)
    with pytest.raises(BudgetExceededError, match="horario"):
        ledger.reserve_call("two", run_limit=0.2, estimate=0.1, hourly_limit=0.5)
    now[0] += 3601
    ledger = BudgetLedger(path)
    pending = ledger.reserve_call("three", run_limit=0.4, estimate=0.1, hourly_limit=0.5)
    ledger.settle(pending, None)
    now[0] += 7200
    with pytest.raises(BudgetExceededError):
        ledger.reserve_call("four", run_limit=0.2, estimate=0.1, hourly_limit=0.5)
    assert ledger.summary()["consumed"] == 0.4
    assert ledger.summary()["reserved"] == 0.4


def test_hourly_check_and_reservation_are_atomic(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite3")
    ledger.set_limit(5)

    def reserve(index):
        try:
            ledger.reserve_call(str(index), run_limit=0.4, estimate=0.1, hourly_limit=0.5)
            return True
        except BudgetExceededError:
            return False

    with ThreadPoolExecutor(2) as pool:
        assert sum(pool.map(reserve, range(2))) == 1


def test_hourly_limit_stops_gateway_before_fake_adapter(tmp_path):
    from ai_swe.config import Settings
    from ai_swe.models import FakeModelAdapter, ModelMessage, ModelRequest
    from ai_swe.models.gateway import gateway_from_settings

    settings = Settings(_env_file=None, profile_id="hourly-fixture",
                        state_db_path=tmp_path / "gateway.sqlite3", model_name="fixture",
                        max_cost_per_run=.4, max_cost_per_hour=.3,
                        model_pricing='[{"model":"fixture","input_per_1k":0.001,"output_per_1k":0.001}]')
    ledger = BudgetLedger(settings.state_db_path)
    ledger.set_limit(5)
    adapter = FakeModelAdapter(model="fixture")
    gateway = gateway_from_settings(settings, adapters=[adapter])
    try:
        with pytest.raises(BudgetExceededError, match="horario"):
            gateway.generate(ModelRequest(messages=[ModelMessage(role="user", content="Hello")],
                                          model="fixture", max_output_tokens=10, run_id="hourly"))
        assert adapter.calls == []
        assert ledger.summary()["reserved"] == 0
    finally:
        gateway.close()
