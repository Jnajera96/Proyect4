import json

import httpx
import pytest
from fastapi.testclient import TestClient

from ai_swe.api import crear_app
from ai_swe.models.providers.connection import ConnectionRequest, check_connection
from ai_swe.api.profiles import VaultConfig
from ai_swe.config import Settings
from ai_swe.models.providers.openai_compatible import OpenAICompatibleAdapter


def config(**values):
    return VaultConfig(**{
        "model_base_url": "http://localhost:20128/v1",
        "model_name": "gemini/example", "remote_model_roles": ["coder", "reviewer"],
        "budget_limit": 2, "max_cost_per_run": 0.1, **values,
    })


def test_local_clears_residual_secret_and_replaces_stale_pricing():
    result = config(model_pricing="invalid stale JSON").vault_data({"hf_token": "remote-secret"})
    assert result["hf_token"] == ""
    assert json.loads(result["model_pricing"]) == [{
        "model": "gemini/example", "input_per_1k": 0, "output_per_1k": 0, "currency": "USD",
    }]
    adapter = OpenAICompatibleAdapter(
        name="local", model="example", base_url=result["model_base_url"], api_key="remote-secret"
    )
    assert "Authorization" not in adapter._cabeceras()


def test_remote_provider_change_cannot_reuse_previous_key():
    with pytest.raises(ValueError, match="token"):
        config(model_base_url="https://api.openai.com/v1").vault_data({
            "hf_token": "hf-secret", "model_base_url": "https://router.huggingface.co/v1",
        })


def test_local_without_key_passes_presence_and_gateway_configuration():
    from ai_swe.config import provider_configuration, require_model_credentials
    from ai_swe.models.gateway import gateway_from_settings

    settings = Settings(_env_file=None, model_provider="openai_compatible",
                        model_base_url="http://localhost:11434/v1", model_name="example",
                        model_api_key="", hf_token="", remote_model_roles=["coder"])
    assert not provider_configuration(settings)["missing_fields"]
    require_model_credentials(settings)
    # Construction must succeed without sending any request.
    gateway = gateway_from_settings(settings)
    assert gateway is not None


@pytest.mark.parametrize("token", ["local", "NONE", "null"])
def test_remote_legacy_sentinel_is_not_a_credential(token):
    from ai_swe.config import provider_configuration
    from ai_swe.models.contracts import ProviderConfig

    settings = Settings(_env_file=None, model_provider="openai_compatible",
                        model_base_url="https://api.openai.com/v1", model_name="example",
                        model_api_key=token, hf_token="")
    assert provider_configuration(settings)["missing_fields"]
    assert not ProviderConfig(name="openai_compatible", model="example", api_key=token).has_credentials


@pytest.mark.parametrize("url", [
    "http://localhost.evil.test/v1", "https://user:secret@api.openai.com",
    "https://api.openai.com/v1?key=secret",
])
def test_endpoint_rejects_unsafe_url(url):
    with pytest.raises(ValueError):
        config(model_base_url=url).vault_data({})


def catalog_mock(monkeypatch, status=200, body=None):
    requests = []
    original_client = httpx.Client

    def handle(request):
        requests.append(request)
        return httpx.Response(status, json=body or {"data": [{"id": "gemini/example"}]})

    monkeypatch.setattr("ai_swe.models.providers.connection.httpx.Client",
                        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    return requests


def test_catalog_local_is_bounded_and_never_sends_residual_token(monkeypatch):
    requests = catalog_mock(monkeypatch)
    result = check_connection(ConnectionRequest(
        model_base_url="http://127.0.0.1:20128/v1", model_name="gemini/example",
        hf_token="remote-secret",
    ), {})
    assert result["ok"]
    assert len(requests) == 1
    assert requests[0].method == "GET" and requests[0].url.path == "/v1/models"
    assert "authorization" not in requests[0].headers


@pytest.mark.parametrize("status", [401, 403, 404])
def test_catalog_errors_are_redacted(monkeypatch, status):
    catalog_mock(monkeypatch, status, {"error": "secret"})
    result = check_connection(ConnectionRequest(
        model_base_url="https://api.openai.com/v1", hf_token="secret",
    ), {})
    assert not result["ok"]
    assert "secret" not in json.dumps(result)


def test_catalog_unreachable_redacts_transport_exception(monkeypatch):
    original_client = httpx.Client

    def handle(request):
        raise httpx.ConnectError("private-token", request=request)

    monkeypatch.setattr("ai_swe.models.providers.connection.httpx.Client",
                        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    result = check_connection(ConnectionRequest(
        model_base_url="http://localhost:20128/v1", hf_token="private-token",
    ), {})
    assert not result["ok"]
    assert "private-token" not in json.dumps(result)


def test_catalog_rejects_redirect_without_forwarding_key(monkeypatch):
    requests = catalog_mock(monkeypatch, 302)
    result = check_connection(ConnectionRequest(
        model_base_url="https://api.openai.com/v1", hf_token="private-token",
    ), {})
    assert not result["ok"]
    assert len(requests) == 1


def test_catalog_limits_response_size(monkeypatch):
    catalog_mock(monkeypatch, body={"data": [], "padding": "x" * 1_000_001})
    result = check_connection(ConnectionRequest(model_base_url="http://localhost:20128/v1"), {})
    assert not result["ok"]


def test_missing_model_returns_catalog_without_silent_substitution(monkeypatch):
    catalog_mock(monkeypatch)
    result = check_connection(ConnectionRequest(
        model_base_url="http://localhost:20128/v1", model_name="nonexistent",
    ), {})
    assert not result["ok"]
    assert result["models"] == ["gemini/example"]


def test_adapter_never_substitutes_an_unrelated_or_ambiguous_model():
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
        200, json={"data": [{"id": "provider-a/example"}, {"id": "provider-b/example"}]}
    ))) as client:
        adapter = OpenAICompatibleAdapter(
            name="local", model="nonexistent", api_key="",
            base_url="http://localhost:20128/v1", client=client,
        )
        assert adapter._resolver_modelo_loopback("nonexistent") is None
        assert adapter._resolver_modelo_loopback("example") is None


def test_connection_endpoint_requires_session_and_csrf(tmp_path, monkeypatch):
    app = crear_app(settings=Settings(_env_file=None, profile_mode=True, profiles_root=tmp_path, stt_provider="fake"))
    with TestClient(app) as client:
        payload = {"model_base_url": "http://localhost:20128/v1"}
        assert client.post("/auth/vault/test-connection", json=payload).status_code == 401
        response = client.post("/auth/register", json={
            "name": "owner", "password": "long offline test password",
        })
        assert response.status_code == 201
        assert client.post("/auth/vault/test-connection", json=payload).status_code == 403
        monkeypatch.setattr("ai_swe.api.profiles.check_connection",
                            lambda *_: {"ok": True, "message": "OK", "models": []})
        response = client.post("/auth/vault/test-connection", json=payload,
                               headers={"X-CSRF-Token": response.json()["csrf_token"]})
        assert response.json()["ok"]
