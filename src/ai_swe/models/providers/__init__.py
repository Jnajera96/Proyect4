"""Adapters de proveedor.

Este es el **unico** paquete autorizado a conocer la forma concreta de un
proveedor. Fuera de aqui no hay ningun import de proveedor, y hay una prueba que lo
comprueba: es lo que garantiza que cambiar de proveedor no obligue a tocar a los
agentes.
"""

from __future__ import annotations

from ai_swe.models.providers.base import ProviderAdapter, ProviderResponse
from ai_swe.models.providers.fake import FakeModelAdapter
from ai_swe.models.providers.openai_compatible import (
    BASE_URL_POR_DEFECTO,
    OpenAICompatibleAdapter,
)

__all__ = [
    "BASE_URL_POR_DEFECTO",
    "FakeModelAdapter",
    "OpenAICompatibleAdapter",
    "ProviderAdapter",
    "ProviderResponse",
]
