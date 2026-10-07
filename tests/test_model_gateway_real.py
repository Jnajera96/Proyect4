"""Prueba de integracion **real** con un proveedor. Opt-in y separada.

**Por que esta en su propio fichero y saltada por defecto.** Una API externa nunca
debe ser dependencia del CI ni de la suite normal: haria que un fallo de red, un
corte del proveedor o una cuota agotada aparecieran como un fallo del proyecto. La
suite estandar tiene que pasar **sin Internet, sin credenciales y sin proveedor**.

Se ejecuta solo si se piden las dos cosas a la vez:

    AI_SWE_RUN_REAL_PROVIDER_TESTS=1
    AI_SWE_MODEL_API_KEY=<clave>

Comando:

    AI_SWE_RUN_REAL_PROVIDER_TESTS=1 AI_SWE_MODEL_API_KEY=... \\
        python -m pytest tests/test_model_gateway_real.py -m real_provider

**Que comprueba.** Que la cadena completa funciona de verdad contra un proveedor:
configuracion -> adapter -> gateway -> proveedor -> respuesta -> usage -> validacion
Pydantic. Es una prueba **pequena, barata y sin informacion sensible**: no toca el
repositorio, no lee archivos del usuario y no envia codigo privado.
"""

from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from ai_swe.config import load_settings
from ai_swe.models import MessageRole, ModelMessage, ModelRequest, gateway_from_settings

pytestmark = pytest.mark.real_provider

_ACTIVO = os.environ.get("AI_SWE_RUN_REAL_PROVIDER_TESTS") == "1"
_CLAVE = os.environ.get("AI_SWE_MODEL_API_KEY", "").strip()
_MODELO = os.environ.get("AI_SWE_MODEL_NAME", "").strip()

MOTIVO = (
    "prueba de integracion real: exige AI_SWE_RUN_REAL_PROVIDER_TESTS=1, "
    "AI_SWE_MODEL_API_KEY y AI_SWE_MODEL_NAME"
)


class RespuestaMinima(BaseModel):
    """Contrato minimo. No es un prompt de agente: es una sonda."""

    value: int


@pytest.mark.skipif(not (_ACTIVO and _CLAVE and _MODELO), reason=MOTIVO)
def test_llamada_real_controlada() -> None:
    """Una sola llamada, pidiendo un valor trivial y sin contexto del proyecto."""
    ajustes = load_settings()
    gateway = gateway_from_settings(ajustes)
    try:
        respuesta = gateway.generate_structured(
            ModelRequest(
                messages=[
                    ModelMessage(
                        role=MessageRole.SYSTEM, content="Return the requested structure."
                    ),
                    ModelMessage(role=MessageRole.USER, content="Return value 42."),
                ],
                max_output_tokens=64,
                temperature=0.0,
            ),
            response_model=RespuestaMinima,
        )
    finally:
        gateway.close()

    assert respuesta.provider  # respondio alguien
    assert respuesta.latency_ms > 0
    assert respuesta.structured_data is not None
    # El valor lo decide el modelo: se comprueba la forma, no el contenido exacto.
    assert isinstance(RespuestaMinima.model_validate(respuesta.structured_data).value, int)
    # El usage puede faltar en algunos proveedores; si viene, debe ser coherente.
    if respuesta.usage.total_tokens is not None:
        assert respuesta.usage.total_tokens >= 0
