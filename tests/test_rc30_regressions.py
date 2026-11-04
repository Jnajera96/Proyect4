import os
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ai_swe.api.app import crear_app
from ai_swe.config import Settings
from ai_swe.contracts.state import BudgetExceededError
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

    # Caso 1: 429 rate limit libera su reserva en 0.0 y permite reintento exitoso
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

    # Caso 2: HTTP 408 timeout conserva la reserva previa como pasivo incierto.
    # Al reservar todo el remanente de la corrida, el reintento se detiene conservadoramente con BudgetExceededError.
    mock_408 = MagicMock()
    mock_408.name = "adapter_408"
    mock_408._model = "m"
    mock_408.generate.side_effect = [ModelTimeoutError("timeout HTTP 408", status_code=408), mock_resp]

    gw_408 = ModelGateway(
        adapters=[mock_408],
        pricing=pricing,
        profile_settings=MagicMock(model_name="m", max_cost_per_run=5.0, max_cost_per_hour=None, state_db_path=db_path),
        max_retries=1,
        sleep=lambda _: None,
    )
    req2 = ModelRequest(messages=[ModelMessage(role=MessageRole.USER, content="hi")], run_id="run-408", max_output_tokens=10)
    with pytest.raises(BudgetExceededError):
        gw_408._intentar(mock_408, req2)

    with sqlite3.connect(db_path) as conn:
        rows_408 = conn.execute("SELECT reserved, consumed, dispatched FROM budget_reservations WHERE run_id='run-408'").fetchall()
    assert len(rows_408) == 1
    assert rows_408[0][1] is None  # El intento 408 NO fue liberado en 0.0; conserva la incertidumbre
    assert rows_408[0][2] == 1     # Marcado como despachado al proveedor

    # Verificar que el ledger conserva la reserva de 408 en summary()
    summary = ledger.summary()
    assert summary["reserved"] == 5.0
    assert abs(summary["available"] - 15.0) < 0.01

    # Verificar que reconcile conserva la reserva no resuelta de 408
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, status TEXT)")
        conn.execute("INSERT OR REPLACE INTO runs VALUES ('run-408', 'failed')")
    rec = ledger.reconcile_unsettled_run("run-408")
    assert rec["released"] == 0
    assert rec["unresolved"] == 1


def test_transport_timeout_and_fallback_preserve_uncertainty(tmp_path):
    """P1: Timeout de transporte y retries agotados o con respaldo conservan reservas inciertas."""
    db_path = tmp_path / "state.sqlite3"
    ledger = BudgetLedger(db_path)
    ledger.set_limit(20.0)

    pricing = pricing_from_json('[{"model": "m", "input_per_1k": 0.001, "output_per_1k": 0.002, "currency": "USD"}]')
    mock_resp = ProviderResponse(content='{"ok": true}', usage=ModelUsage(input_tokens=10, output_tokens=10), model="m")

    # 1. Timeout de transporte con retries agotados: conserva reserva intacta
    mock_timeout = MagicMock()
    mock_timeout.name = "adapter_timeout"
    mock_timeout._model = "m"
    mock_timeout.generate.side_effect = ModelTimeoutError("Transport timed out")

    gw_timeout = ModelGateway(
        adapters=[mock_timeout],
        pricing=pricing,
        profile_settings=MagicMock(model_name="m", max_cost_per_run=5.0, max_cost_per_hour=None, state_db_path=db_path),
        max_retries=0,
        sleep=lambda _: None,
    )
    req = ModelRequest(messages=[ModelMessage(role=MessageRole.USER, content="hi")], run_id="run-transport-to", max_output_tokens=10)
    with pytest.raises(ModelTimeoutError):
        gw_timeout.generate(req)

    with sqlite3.connect(db_path) as conn:
        rows_to = conn.execute("SELECT reserved, consumed, dispatched FROM budget_reservations WHERE run_id='run-transport-to'").fetchall()
    assert len(rows_to) == 1
    assert rows_to[0][1] is None
    assert rows_to[0][2] == 1

    # 2. Respaldo: Primary da timeout 408, pero la corrida no puede exceder el límite para llamar al respaldo.
    # Se detiene de forma conservadora preservando la reserva incierta del primary.
    mock_primary = MagicMock()
    mock_primary.name = "primary"
    mock_primary._model = "m"
    mock_primary.generate.side_effect = ModelTimeoutError("upstream timeout (HTTP 408)", status_code=408)

    mock_fallback = MagicMock()
    mock_fallback.name = "fallback"
    mock_fallback._model = "m"
    mock_fallback.generate.return_value = mock_resp

    gw_fallback = ModelGateway(
        adapters=[mock_primary, mock_fallback],
        pricing=pricing,
        profile_settings=MagicMock(model_name="m", max_cost_per_run=5.0, max_cost_per_hour=None, state_db_path=db_path),
        max_retries=0,
        sleep=lambda _: None,
    )
    req_fb = ModelRequest(messages=[ModelMessage(role=MessageRole.USER, content="hi")], run_id="run-fallback", max_output_tokens=10)
    with pytest.raises(BudgetExceededError):
        gw_fallback.generate(req_fb)

    with sqlite3.connect(db_path) as conn:
        rows_fb = conn.execute("SELECT reserved, consumed, dispatched FROM budget_reservations WHERE run_id='run-fallback'").fetchall()
    assert len(rows_fb) == 1
    assert rows_fb[0][1] is None  # Reserva del primary con timeout 408 conservada
    assert rows_fb[0][2] == 1     # Despachada


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

    # Con clave de admin: status en respuesta
    client.headers["Authorization"] = "Bearer admin-secret-key"
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp
        res = client.post("/system/launch-omniroute")
        assert res.status_code == 200
        assert res.json()["status"] == "already_running"
    store.close()


def test_launcher_rejects_untrusted_cwd_and_sanitizes_environment(tmp_path, monkeypatch):
    """P1/P2: El launcher no ejecuta scripts ajenos en CWD y no filtra DATABASE_URL ni credenciales."""
    # 1. Directorio de trabajo actual con un iniciar.cmd falso SIN package.json de omniroute
    fake_cwd = tmp_path / "untrusted_workdir"
    fake_cwd.mkdir()
    fake_script = fake_cwd / "iniciar.cmd"
    fake_script.write_text("@echo malicious", encoding="utf-8")
    monkeypatch.chdir(fake_cwd)
    monkeypatch.delenv("OMNIROUTE_DIR", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///super_secret_db.sqlite")
    monkeypatch.setenv("PRIVATE_SECRET_KEY", "super_secret_key_123")

    db_path = tmp_path / "state.sqlite3"
    store = RunStore(db_path)
    settings = Settings(
        api_keys={"admin-key": "admin"},
        state_db_path=db_path,
        profile_mode=False,
    )
    app = crear_app(store=store, settings=settings)
    client = TestClient(app)
    client.headers["Authorization"] = "Bearer admin-key"

    captured_exec = []

    def fake_popen(args, cwd, env, **kwargs):
        captured_exec.append((args, cwd, env))
        return MagicMock()

    # Cuando OMNIROUTE_DIR apunta a una carpeta que no tiene package.json omniroute válido
    non_omni = tmp_path / "non_omni"
    non_omni.mkdir()
    (non_omni / "iniciar.cmd").write_text("@echo not omniroute", encoding="utf-8")
    monkeypatch.setenv("OMNIROUTE_DIR", str(non_omni))

    with patch("subprocess.Popen", side_effect=fake_popen), \
         patch("urllib.request.urlopen", side_effect=Exception("offline")):
        res = client.post("/system/launch-omniroute")
        assert res.status_code == 200
        # No debe haber ejecutado fake_script de CWD
        assert not any(str(fake_script) in str(c[0]) or c[1] == str(fake_cwd) for c in captured_exec)

    # 2. Ahora creamos una carpeta válida con package.json identificando omniroute
    valid_omni = tmp_path / "valid_omni"
    valid_omni.mkdir()
    (valid_omni / "package.json").write_text('{"name": "omniroute", "version": "3.6.1"}', encoding="utf-8")
    valid_cmd = valid_omni / "iniciar.cmd"
    valid_cmd.write_text("@echo starting", encoding="utf-8")
    monkeypatch.setenv("OMNIROUTE_DIR", str(valid_omni))

    captured_env = {}

    def fake_popen_valid(args, cwd, env, **kwargs):
        captured_env.update(env)
        return MagicMock()

    with patch("subprocess.Popen", side_effect=fake_popen_valid), patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_url.side_effect = [Exception("offline"), mock_resp]

        res = client.post("/system/launch-omniroute")
        assert res.status_code == 200
        assert res.json()["status"] in ("running", "launching")

        # Verificar que DATABASE_URL y PRIVATE_SECRET_KEY NO se filtraron
        assert "DATABASE_URL" not in captured_env
        assert "PRIVATE_SECRET_KEY" not in captured_env
        assert captured_env.get("OMNIROUTE_USE_TURBOPACK") == "1"
    store.close()
