"""Registro estructurado de auditoría de seguridad para eventos sensibles.

Registra en formato trazable y libre de secretos:
  - AUTH_FAILURE: intentos de autenticación fallidos o bloqueados por límite de reintentos
  - AUTH_SUCCESS: autenticación exitosa
  - ACCESS_DENIED: intento de acceder a un recurso con rol insuficiente (403)
  - RATE_LIMIT_EXCEEDED: peticiones excediendo umbral de tasa (429)
  - SENSITIVE_OPERATION: aprobación de parches, rollback o exportación/importación de estado

Todos los datos sensibles son redactados automáticamente antes de su emisión.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from ai_swe.security.redaction import redact_deep

log = logging.getLogger("ai_swe.security.audit")


@dataclass(frozen=True)
class SecurityAuditEvent:
    timestamp: str
    event_type: str
    client_ip: str
    status: str
    detail: str
    role: str | None = None
    key_id: str | None = None
    resource: str | None = None
    extra: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        raw = {k: v for k, v in asdict(self).items() if v is not None}
        return redact_deep(raw)


def log_security_event(
    event_type: str,
    client_ip: str,
    status: str,
    detail: str,
    *,
    role: str | None = None,
    key_id: str | None = None,
    resource: str | None = None,
    extra: dict[str, Any] | None = None,
) -> SecurityAuditEvent:
    """Emite un evento de auditoría de seguridad estructurado."""
    event = SecurityAuditEvent(
        timestamp=datetime.now(UTC).isoformat(),
        event_type=event_type,
        client_ip=client_ip,
        status=status,
        detail=detail,
        role=role,
        key_id=key_id,
        resource=resource,
        extra=extra,
    )
    payload = event.to_dict()
    level = logging.WARNING if status in ("FAILURE", "DENIED", "BLOCKED") else logging.INFO
    log.log(level, "SECURITY_AUDIT: %s", json.dumps(payload, ensure_ascii=False))
    return event
