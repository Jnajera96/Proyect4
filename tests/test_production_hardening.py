"""Pruebas de endurecimiento para producción pública (Task D).

Valida:
1. Cabeceras de seguridad HTTP completas (CSP, nosniff, DENY, Referrer-Policy, Permissions-Policy, HSTS).
2. Configuración y validación estricta de TLS/SSL nativo en Settings.
3. Throttling anti fuerza bruta en autenticación (429 con Retry-After).
4. Auditoría de seguridad estructurada (ai_swe.security.audit) libre de secretos.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ai_swe.api import crear_app
from ai_swe.config import Settings
from ai_swe.security import Rol, clear_registered_secrets, log_security_event
from ai_swe.security.audit import SecurityAuditEvent
from ai_swe.state import RunStore

CLAVE_ADMIN = "admin-secret-key-prod-001"
CLAVE_OPERATOR = "operator-secret-prod-002"
CLAVE_READER = "reader-secret-prod-003"

MAPA_CLAVES = {
    CLAVE_ADMIN: "admin",
    CLAVE_OPERATOR: "operator",
    CLAVE_READER: "reader",
}


def test_permissions_policy_header_present(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    store = RunStore(db)
    app = crear_app(store=store, settings=Settings(state_db_path=db))
    client = TestClient(app)

    res = client.get("/health")
    assert res.status_code == 200
    assert "permissions-policy" in res.headers
    perm = res.headers["permissions-policy"]
    assert "camera=()" in perm
    assert "microphone=(self)" in perm
    assert "geolocation=()" in perm
    store.close()


def test_hsts_header_present_when_tls_configured(tmp_path: Path) -> None:
    cert_file = tmp_path / "server.crt"
    key_file = tmp_path / "server.key"
    cert_file.write_text("CERT DATA", encoding="utf-8")
    key_file.write_text("KEY DATA", encoding="utf-8")

    db = tmp_path / "state.db"
    store = RunStore(db)
    settings = Settings(
        state_db_path=db,
        ssl_certfile=cert_file,
        ssl_keyfile=key_file,
    )
    app = crear_app(store=store, settings=settings)
    client = TestClient(app)

    res = client.get("/health")
    assert res.status_code == 200
    assert "strict-transport-security" in res.headers
    assert "max-age=31536000" in res.headers["strict-transport-security"]
    store.close()


def test_ssl_settings_validation(tmp_path: Path) -> None:
    cert_file = tmp_path / "server.crt"
    key_file = tmp_path / "server.key"

    # 1. Configurar sólo certfile sin keyfile debe fallar
    with pytest.raises(ValidationError, match="ssl_certfile y ssl_keyfile deben configurarse conjuntamente"):
        Settings(ssl_certfile=cert_file)

    # 2. Configurar sólo keyfile sin certfile debe fallar
    with pytest.raises(ValidationError, match="ssl_certfile y ssl_keyfile deben configurarse conjuntamente"):
        Settings(ssl_keyfile=key_file)

    # 3. Ficheros que no existen en disco deben fallar
    with pytest.raises(ValidationError, match="no existe o no es un archivo"):
        Settings(ssl_certfile=cert_file, ssl_keyfile=key_file)

    # 4. Creando los ficheros, la validación pasa
    cert_file.write_text("CERT", encoding="utf-8")
    key_file.write_text("KEY", encoding="utf-8")
    s = Settings(ssl_certfile=cert_file, ssl_keyfile=key_file)
    assert s.ssl_certfile == cert_file
    assert s.ssl_keyfile == key_file


def test_auth_throttling_anti_bruteforce(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    store = RunStore(db)
    settings = Settings(
        state_db_path=db,
        api_keys=MAPA_CLAVES,
        auth_rate_limit_enabled=True,
        auth_rate_limit_per_minute=3,
    )
    app = crear_app(store=store, settings=settings)
    client = TestClient(app)

    # Primeros 3 intentos fallidos deben retornar 401
    for i in range(3):
        res = client.get("/runs", headers={"X-API-Key": f"clave-invalida-{i}"})
        assert res.status_code == 401, f"Intento {i+1} debió ser 401"

    # El 4to intento desde la misma IP debe ser bloqueado con 429
    res4 = client.get("/runs", headers={"X-API-Key": "clave-invalida-4"})
    assert res4.status_code == 429
    assert res4.headers.get("retry-after") == "60"
    assert "demasiados intentos de autenticación fallidos" in res4.json()["detail"]

    # Incluso enviando una clave válida mientras está bloqueado, se mantiene 429
    res_bloqueado = client.get("/runs", headers={"X-API-Key": CLAVE_READER})
    assert res_bloqueado.status_code == 429

    store.close()


def test_structured_security_audit_logging(caplog: pytest.LogCaptureFixture) -> None:
    clear_registered_secrets()
    with caplog.at_level(logging.INFO, logger="ai_swe.security.audit"):
        ev = log_security_event(
            event_type="AUTH_FAILURE",
            client_ip="192.168.1.50",
            status="FAILURE",
            detail="Intento no autorizado",
            role="reader",
            key_id="clav...len26",
            resource="/runs",
            extra={"param": "test"},
        )
    assert isinstance(ev, SecurityAuditEvent)
    payload = ev.to_dict()
    assert payload["event_type"] == "AUTH_FAILURE"
    assert payload["client_ip"] == "192.168.1.50"
    assert payload["role"] == "reader"
    assert "timestamp" in payload

    # Verificar que el mensaje fue emitido en el logger de auditoría de seguridad
    records = [r for r in caplog.records if r.name == "ai_swe.security.audit"]
    assert len(records) >= 1
    assert "SECURITY_AUDIT:" in records[-1].getMessage()
