"""Offline checks of the installed profile boundary, without a TLS/network pilot."""

import logging

import pytest
from fastapi.testclient import TestClient

from ai_swe.api import crear_app
from ai_swe.config import Settings


@pytest.mark.parametrize("configured", [False, True])
def test_profile_boundary_hsts_header(tmp_path, configured):
    options = {}
    if configured:
        # These files test the header branch, not certificate validity or a TLS handshake.
        cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
        cert.write_text("synthetic certificate fixture", encoding="utf-8")
        key.write_text("synthetic key fixture", encoding="utf-8")
        options = {"ssl_certfile": cert, "ssl_keyfile": key}
    app = crear_app(settings=Settings(
        _env_file=None, profile_mode=True, profiles_root=tmp_path / "users",
        stt_provider="fake", **options,
    ))
    with TestClient(app) as client:
        for path in ("/health", "/auth/status"):
            response = client.get(path)
            assert response.status_code == 200
            if configured:
                assert response.headers["strict-transport-security"] == (
                    "max-age=31536000; includeSubDomains"
                )
            else:
                assert "strict-transport-security" not in response.headers
            assert response.headers["cache-control"] == "no-store"


def test_profile_auth_throttle_retry_after_and_redacted_audit(tmp_path, caplog):
    password = "Synthetic RC24 private password"
    app = crear_app(settings=Settings(
        _env_file=None, profile_mode=True, profiles_root=tmp_path / "users",
        stt_provider="fake",
    ))
    with (
        caplog.at_level(logging.WARNING, logger="ai_swe.security.audit"),
        TestClient(app) as client,
    ):
        for _ in range(10):
            response = client.post("/auth/login", json={"name": "missing", "password": password})
            assert response.status_code == 401
        blocked = client.post("/auth/login", json={"name": "missing", "password": password})
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == "60"
        assert blocked.headers["cache-control"] == "no-store"
    audit = [r.getMessage() for r in caplog.records if r.name == "ai_swe.security.audit"]
    assert any('"event_type": "RATE_LIMIT_EXCEEDED"' in r for r in audit)
    assert password not in caplog.text and password not in blocked.text
