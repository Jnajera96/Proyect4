"""Capa de seguridad transversal.

Por ahora contiene la redaccion centralizada de secretos (`RNF-S3`). El objetivo
de este paquete es que las garantias transversales -aplicables a logs, errores,
eventos, trazas y configuracion- vivan en un unico sitio, y no se reimplementen
modulo a modulo, que es la forma segura de que alguna se olvide.

La API publica es deliberadamente pequena:

    from ai_swe.security import redact, redact_deep, sanitize, register_secret
    from ai_swe.security import install_redacting_filter
"""

from __future__ import annotations

from ai_swe.security.logging import RedactingFilter, install_redacting_filter
from ai_swe.security.redaction import (
    CLAVES_QUE_REDACTAN_VALOR,
    REDACTADO,
    clear_registered_secrets,
    redact,
    redact_deep,
    register_secret,
    sanitize,
    secrets_registrados,
)

__all__ = [
    "CLAVES_QUE_REDACTAN_VALOR",
    "REDACTADO",
    "RedactingFilter",
    "clear_registered_secrets",
    "install_redacting_filter",
    "redact",
    "redact_deep",
    "register_secret",
    "sanitize",
    "secrets_registrados",
]
