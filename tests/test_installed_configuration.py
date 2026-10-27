"""Installed first run: external state, safe diagnostics and zero credentialless calls."""

import json
import logging
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ai_swe.api import crear_app
from ai_swe.config import Settings, load_settings, provider_configuration
from ai_swe.runtime_logging import close_installed_log_handler, installed_log_handler
from ai_swe.runtime_paths import user_paths
from ai_swe.stt import crear_adaptador_stt


@pytest.fixture
def installed(tmp_path, monkeypatch):
    code = tmp_path / "installation"
    code.mkdir()
    monkeypatch.chdir(code)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    monkeypatch.setenv("AI_SWE_RUNTIME_MODE", "installed")
    for key in (
        "HF_TOKEN", "AI_SWE_HF_TOKEN", "AI_SWE_MODEL_API_KEY", "AI_SWE_MODEL_NAME",
        "AI_SWE_MODEL_BASE_URL", "AI_SWE_REMOTE_MODEL_ROLES", "AI_SWE_STATE_DB_PATH",
        "AI_SWE_WORKSPACE_ROOT", "AI_SWE_LOG_DIR", "AI_SWE_CACHE_DIR", "AI_SWE_API_KEYS",
    ):
        monkeypatch.delenv(key, raising=False)
    return code


def test_installed_paths_are_external_and_settings_are_read_only(installed):
    settings = Settings()
    paths = user_paths()
    assert settings.state_db_path == paths.database
    assert settings.workspace_root == paths.worktrees
    assert settings.log_dir == paths.logs
    assert settings.cache_dir == paths.cache
    assert settings.stt_download_root == paths.cache / "speech"
    assert not paths.root.exists()
    load_settings()
    assert paths.config_file.parent.is_dir()
    assert paths.worktrees.is_dir() and paths.cache.is_dir()
    assert not paths.config_file.exists(), "never create a credential file implicitly"
    assert list(installed.iterdir()) == []


def test_installed_ignores_code_dotenv_and_reads_external_config(installed, monkeypatch):
    (installed / ".env").write_text("AI_SWE_MODEL_NAME=wrong-from-code\n", encoding="utf-8")
    config = user_paths().config_file
    config.parent.mkdir(parents=True)
    config.write_text(
        'AI_SWE_MODEL_NAME=external-model\n'
        'AI_SWE_MODEL_BASE_URL=https://router.huggingface.co/v1\n'
        'HF_TOKEN=synthetic-external-hf-secret\n'
        'AI_SWE_REMOTE_MODEL_ROLES=["coder","reviewer"]\n', encoding="utf-8",
    )
    settings = Settings()
    assert settings.model_name == "external-model"
    assert settings.model_api_key.get_secret_value() == "synthetic-external-hf-secret"
    assert provider_configuration(settings)["status"] == "configured"
    monkeypatch.setenv("AI_SWE_MODEL_NAME", "environment-wins")
    assert Settings().model_name == "environment-wins"
    assert Settings(model_name="explicit-wins").model_name == "explicit-wins"
    assert "synthetic-external-hf-secret" not in repr(settings)


def test_development_preserves_relative_paths_and_local_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_SWE_RUNTIME_MODE", "development")
    (tmp_path / ".env").write_text("AI_SWE_MODEL_NAME=development-model\n", encoding="utf-8")
    settings = Settings()
    assert settings.model_name == "development-model"
    assert str(settings.state_db_path).replace('\\', '/') == "var/state.sqlite3"
    assert settings.log_dir is None and settings.cache_dir is None


def test_frozen_defaults_to_installed_without_cwd_config(installed, monkeypatch):
    monkeypatch.delenv("AI_SWE_RUNTIME_MODE")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert Settings().runtime_mode == "installed"


def test_absolute_custom_locations_preserved(installed, tmp_path):
    settings = Settings(state_db_path=tmp_path / "custom" / "state.db")
    assert settings.state_db_path == tmp_path / "custom" / "state.db"


@pytest.mark.parametrize("field", [
    "state_db_path", "workspace_root", "log_dir", "cache_dir", "stt_download_root",
])
def test_installed_rejects_relative_overrides(installed, field):
    with pytest.raises(ValidationError):
        Settings(**{field: "relative/location"})


def test_hf_token_never_authenticates_other_providers(installed):
    settings = Settings(HF_TOKEN="synthetic-hf-only", model_base_url="https://example.invalid/v1")
    assert not settings.model_api_key.get_secret_value()


def test_missing_provider_health_and_local_api_still_work(installed, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("configuration diagnosis must not construct a gateway")

    monkeypatch.setattr("ai_swe.graph.model_routing.gateway_from_settings", forbidden)
    with TestClient(crear_app()) as client:
        health = client.get("/health")
        assert health.status_code == 200 and health.json()["status"] == "ok"
        status = health.json()["provider_configuration"]
        assert status["status"] == "not_configured"
        assert not status["remote_enabled"]
        assert client.get("/projects").status_code == 200
        assert client.get("/runs").json() == []
        assert client.post("/runs", json={"instruction": "analiza el proyecto"}).status_code == 202
    assert user_paths().database.exists()
    assert list(installed.iterdir()) == []


def test_missing_hybrid_credential_blocks_before_run_creation(installed, monkeypatch):
    monkeypatch.setenv("AI_SWE_MODEL_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_SWE_REMOTE_MODEL_ROLES", '["coder","reviewer"]')
    monkeypatch.setenv("AI_SWE_MODEL_BASE_URL", "https://router.huggingface.co/v1")
    monkeypatch.setenv("AI_SWE_MODEL_NAME", "Qwen/Qwen2.5-Coder-32B-Instruct:nscale")
    monkeypatch.setattr(
        "ai_swe.graph.model_routing.gateway_from_settings",
        lambda *args: pytest.fail("must not construct a provider without credentials"),
    )
    with TestClient(crear_app()) as client:
        response = client.post("/runs", json={"instruction": "analiza el proyecto"})
        assert response.status_code == 503
        assert "HF_TOKEN" in response.json()["detail"]
        assert client.get("/runs").json() == []


def test_logs_rotate_externally_and_redact_secret(installed):
    settings = load_settings()
    from ai_swe.security import register_secret

    register_secret("synthetic-file-secret")
    logger = logging.getLogger("ai_swe.installed-test")
    handler = installed_log_handler(settings.log_dir)
    try:
        logger.warning("credential synthetic-file-secret")
        handler.flush()
        text = (settings.log_dir / "application.log").read_text(encoding="utf-8")
        assert "synthetic-file-secret" not in text
        assert "[REDACTED]" in text
        assert handler.maxBytes > 0 and handler.backupCount == 3
    finally:
        close_installed_log_handler(handler)


def test_stt_factory_uses_installed_cache_lazily(installed, monkeypatch):
    calls = []

    def model(name, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("probe only")

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=model))
    adapter = crear_adaptador_stt(Settings())
    assert calls == []
    from ai_swe.stt import STTError

    with pytest.raises(STTError):
        adapter.transcribe(b"fixture")
    assert calls[0]["download_root"] == str(user_paths().cache / "speech")


def test_provider_diagnostic_never_contains_credential(installed):
    settings = Settings(model_name="model", model_api_key="synthetic-private-key")
    report = provider_configuration(settings)
    assert "synthetic-private-key" not in json.dumps(report)
    assert report["credential_validated"] is False
    assert report["inference_verified"] is False


def test_hf_gateway_rejects_missing_key_before_building_adapter(installed, monkeypatch):
    from ai_swe.models import ModelConfigurationError, gateway_from_settings

    monkeypatch.setattr(
        "ai_swe.models.gateway.build_adapter",
        lambda *args: pytest.fail("adapter must not be constructed without HF credential"),
    )
    settings = Settings(
        model_provider="openai_compatible", model_name="example/model",
        model_base_url="https://router.huggingface.co/v1",
    )
    with pytest.raises(ModelConfigurationError):
        gateway_from_settings(settings)


def test_local_openai_compatible_still_needs_no_key(installed):
    from ai_swe.models import gateway_from_settings

    settings = Settings(
        model_provider="ollama", model_name="local-model",
        model_base_url="http://127.0.0.1:8089/v1", remote_model_roles=["coder"],
    )
    assert provider_configuration(settings)["status"] == "configured"
    gateway = gateway_from_settings(settings)
    gateway.close()
