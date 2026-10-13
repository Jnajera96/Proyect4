"""Capa de seguridad transversal.

Contiene las garantias que valen para todo el sistema y que, si se reimplementaran
modulo a modulo, alguna se olvidaria:

  - la **redaccion centralizada de secretos** (`RNF-S3`), aplicable a logs, errores,
    eventos y trazas;
  - el **tratamiento del contenido no confiable** que llega al contexto del modelo
    (extractos del repositorio, salida de sus pruebas).

La API publica es deliberadamente pequena:

    from ai_swe.security import redact, redact_deep, sanitize, register_secret
    from ai_swe.security import install_redacting_filter
    from ai_swe.security import AVISO_NO_CONFIABLE, bloque_no_confiable
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
from ai_swe.security.untrusted import (
    AVISO_NO_CONFIABLE,
    MARCA_FIN,
    MARCA_INICIO,
    bloque_no_confiable,
)

__all__ = [
    "AVISO_NO_CONFIABLE",
    "CLAVES_QUE_REDACTAN_VALOR",
    "MARCA_FIN",
    "MARCA_INICIO",
    "REDACTADO",
    "RedactingFilter",
    "bloque_no_confiable",
    "clear_registered_secrets",
    "install_redacting_filter",
    "redact",
    "redact_deep",
    "register_secret",
    "sanitize",
    "secrets_registrados",
]
