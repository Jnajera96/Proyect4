import json

import httpx
import pytest

from ai_swe.config import Settings
from ai_swe.preflight import HF_IDENTITY, HF_ROUTER, diagnose, user_config_path


def hybrid(**changes):
    values = {
        "remote_model_roles": ["coder", "reviewer"],
        "model_provider": "openai_compatible",
        "model_name": "example/model:provider",
        "model_base_url": HF_ROUTER,
        "model_api_key": "synthetic-preflight-secret",
    }
    return Settings(_env_file=None, **{**values, **changes})


def test_offline_profile_needs_no_gguf_or_network(tmp_path):
    def server(_):
        pytest.fail("offline preflight must not contact providers")

    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        report = diagnose(Settings(_env_file=None), config_path=tmp_path / "missing", client=client)
    assert report.profile == "offline"
    assert not any(check.status == "error" for check in report.checks)
    assert report.inference_calls == 0
    assert report.checks[1].code == "deterministic_roles"


def test_user_config_uses_localappdata_and_is_not_created(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert user_config_path() == tmp_path / "AISWESystem" / "config" / ".env"
    diagnose(Settings(_env_file=None))
    assert not list(tmp_path.iterdir())


def test_presence_is_not_credential_or_billing_validation(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("no opt-in"))) as client:
        report = diagnose(hybrid(), config_path=tmp_path / "missing", client=client)
    assert report.remote_configuration_ready
    assert report.credential_validated is None
    assert not report.billing_verified
    assert not report.inference_verified
    assert "synthetic-preflight-secret" not in report.model_dump_json()


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"model_name": ""}, "missing_model"),
        ({"model_api_key": ""}, "missing_runtime_key"),
        ({"model_base_url": "https://untrusted.example/v1"}, "unsupported_diagnostic_endpoint"),
        ({"model_provider": "unsupported"}, "unsupported_provider"),
    ],
)
def test_invalid_configuration_never_sends_credentials(changes, code, tmp_path):
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("invalid config"))
    ) as client:
        report = diagnose(
            hybrid(**changes),
            config_path=tmp_path / "missing",
            check_remote=True,
            client=client,
        )
    assert report.checks[-1].code == code
    assert not report.remote_configuration_ready


def test_remote_probe_only_checks_identity_and_does_not_export_it(tmp_path):
    calls = []

    def server(request):
        calls.append(request)
        assert str(request.url) == HF_IDENTITY
        assert request.method == "GET"
        assert request.headers["Authorization"] == "Bearer synthetic-preflight-secret"
        return httpx.Response(
            200,
            json={
                "name": "private-account",
                "auth": {"type": "access_token"},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        report = diagnose(
            hybrid(), config_path=tmp_path / "missing", check_remote=True, client=client
        )
    assert len(calls) == 1
    assert report.credential_validated is True
    assert report.billing_verified is False
    assert "private-account" not in report.model_dump_json()


@pytest.mark.parametrize("status,validated", [(401, False), (403, False), (429, None), (503, None)])
def test_rejection_does_not_echo_secrets_or_invent_zero_credit(status, validated, tmp_path):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(status, text="synthetic-preflight-secret"),
        )
    ) as client:
        report = diagnose(
            hybrid(), config_path=tmp_path / "missing", check_remote=True, client=client
        )
    assert report.credential_validated is validated
    assert not report.billing_verified
    assert "synthetic-preflight-secret" not in report.model_dump_json()


@pytest.mark.parametrize(
    "url",
    [
        "https://remote.example/v1",
        "http://127.0.0.1@remote.example/v1",
        "http://[malformed/v1",
        "http://127.0.0.1:invalid/v1",
        "http://127.0.0.1:0/v1",
    ],
)
def test_local_probe_rejects_non_loopback_or_malformed_urls(url, tmp_path):
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("unsafe URL"))) as client:
        report = diagnose(
            Settings(_env_file=None),
            config_path=tmp_path / "missing",
            local_base_url=url,
            client=client,
        )
    assert report.checks[1].code == "invalid_loopback_url"


def test_local_probe_carries_no_remote_secret_and_rejects_redirects(tmp_path):
    calls = []

    def server(request):
        calls.append(request)
        assert str(request.url) == "http://127.0.0.1:8089/health"
        assert "Authorization" not in request.headers
        return httpx.Response(302, headers={"location": "https://untrusted.example/"})

    with httpx.Client(transport=httpx.MockTransport(server), follow_redirects=True) as client:
        report = diagnose(
            Settings(_env_file=None),
            config_path=tmp_path / "missing",
            local_base_url="http://127.0.0.1:8089/v1",
            client=client,
        )
    assert len(calls) == 1
    assert report.checks[1].code == "unavailable"
    assert json.loads(report.model_dump_json())["inference_calls"] == 0


def test_identity_redirect_does_not_forward_the_token(tmp_path):
    calls = []

    def server(request):
        calls.append(request)
        assert str(request.url) == HF_IDENTITY
        return httpx.Response(302, headers={"location": "https://untrusted.example/"})

    with httpx.Client(transport=httpx.MockTransport(server), follow_redirects=True) as client:
        report = diagnose(
            hybrid(),
            config_path=tmp_path / "missing",
            check_remote=True,
            client=client,
        )
    assert len(calls) == 1
    assert report.credential_validated is None


def test_invalid_cli_configuration_never_echoes_input(monkeypatch, capsys):
    from ai_swe.preflight import main

    monkeypatch.setattr("sys.argv", ["preflight"])
    monkeypatch.setenv("AI_SWE_REMOTE_MODEL_ROLES", '["synthetic-secret-in-invalid-setting"]')
    assert main() == 1
    output = capsys.readouterr().out
    assert "invalid_configuration" in output
    assert "synthetic-secret-in-invalid-setting" not in output
