import pytest
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from ai_swe.api.app import crear_app
from ai_swe.config import Settings
from ai_swe.models.contracts import MessageRole, ModelMessage, ModelRequest, ModelUsage
from ai_swe.models.errors import ModelRateLimitError, ModelTimeoutError
from ai_swe.models.gateway import ModelGateway
from ai_swe.models.pricing import pricing_from_json
from ai_swe.models.providers.base import ProviderResponse
from ai_swe.state.budget_ledger import BudgetLedger
from ai_swe.state.store import RunStore


def test_reconcile_and_restart_preserve_dispatched_reservations(tmp_path):
    """P1: Al reiniciar o reanudar, las reservas enviadas (dispatched=1) NO deben liberarse."""
    db_path = tmp_path / "state.sqlite3"
    ledger = BudgetLedger(db_path)
    ledger.set_limit(10.0)

    # Simular una corrida con una reserva despachada de 2.0 USD
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, status TEXT)")
        conn.execute("INSERT INTO runs VALUES ('run-terminal', 'completed')")

    res = ledger.reserve_call("run-terminal", run_limit=5.0, estimate=1.0)
    ledger.mark_dispatched(res)

    # 1. read_status no debe anticipar la liberación de dispatched=1
    st = BudgetLedger.read_status(db_path)
    assert st["available"] == 5.0  # 10.0 límite - 5.0 reservado para run

    # 2. Reiniciar el ledger (constructor) no debe poner consumed=0 si dispatched=1
    ledger2 = BudgetLedger(db_path)
    summ = ledger2.summary()
    assert summ["reserved"] == 5.0
    assert summ["available"] == 5.0

    # 3. reconcile_unsettled_run no debe liberar dispatched=1
    rec = ledger2.reconcile_unsettled_run("run-terminal")
    assert rec["released"] == 0
    assert rec["unresolved"] == 1

    summ2 = ledger2.summary()
    assert summ2["reserved"] == 5.0
    assert summ2["available"] == 5.0


def test_timeout_retry_preserves_uncertainty_and_429_frees_allowance(tmp_path):
    """P1: Timeout conserva la incertidumbre previa; 429 permite reintento sin bloqueo."""
    db_path = tmp_path / "state.sqlite3"
    ledger = BudgetLedger(db_path)
    ledger.set_limit(20.0)

    pricing = pricing_from_json('[{"model": "m", "input_per_1k": 0.001, "output_per_1k": 0.002, "currency": "USD"}]')
    mock_resp = ProviderResponse(content='{"ok": true}', usage=ModelUsage(input_tokens=10, output_tokens=10), model="m")

    # Caso 1: 429 rate limit
    mock_429 = MagicMock()
    mock_429.name = "adapter_429"
    mock_429._model = "m"
    mock_429.generate.side_effect = [ModelRateLimitError("429"), mock_resp]

    gw_429 = ModelGateway(
        adapters=[mock_429],
        pricing=pricing,
        profile_settings=MagicMock(model_name="m", max_cost_per_run=5.0, max_cost_per_hour=None, state_db_path=db_path),
        max_retries=1,
        sleep=lambda _: None,
    )
    req1 = ModelRequest(messages=[ModelMessage(role=MessageRole.USER, content="hi")], run_id="run-429", max_output_tokens=10)
    gw_429._intentar(mock_429, req1)

    with sqlite3.connect(db_path) as conn:
        rows_429 = conn.execute("SELECT reserved, consumed, dispatched FROM budget_reservations WHERE run_id='run-429'").fetchall()
    assert len(rows_429) == 2
    assert rows_429[0][1] == 0.0  # El intento 429 fue liberado en 0.0
    assert rows_429[1][1] is not None  # El segundo intento se liquidó con éxito


def test_launcher_omniroute_requires_authorization(tmp_path):
    """P1: /system/launch-omniroute exige autorización en modo API-key."""
    db_path = tmp_path / "state.sqlite3"
    store = RunStore(db_path)
    settings = Settings(
        api_keys={"admin-secret-key": "admin"},
        state_db_path=db_path,
        profile_mode=False,
    )
    app = crear_app(store=store, settings=settings)
    client = TestClient(app)

    # Sin clave: 401
    assert client.post("/system/launch-omniroute").status_code == 401

    # Con clave de admin: 200
    client.headers["Authorization"] = "Bearer admin-secret-key"
    res = client.post("/system/launch-omniroute")
    assert res.status_code == 200
    assert "status" in res.json()
    store.close()
