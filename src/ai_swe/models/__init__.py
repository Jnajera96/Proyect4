"""Model Gateway: la frontera unica entre el sistema y cualquier modelo LLM.

**Regla de la capa.** Ningun agente importa un SDK de proveedor. Todos dependen de
`ModelGateway`, y el proveedor se elige por configuracion, no por codigo.

    Agente -> ModelGateway -> ProviderAdapter -> proveedor externo

Uso minimo:

    from ai_swe.models import ModelGateway, ModelRequest, ModelMessage, FakeModelAdapter

    gateway = ModelGateway([FakeModelAdapter()])
    respuesta = gateway.generate(
        ModelRequest(messages=[ModelMessage(role="user", content="Hola")])
    )

Uso con presupuesto y salida estructurada:

    respuesta = gateway.generate_structured(
        request, response_model=MiContrato, budget=presupuesto
    )
    presupuesto = gateway.consume(presupuesto, respuesta)   # devuelve uno nuevo

Diseno completo y decisiones: `docs/MODEL-GATEWAY-DESIGN.md`.
"""

from __future__ import annotations

from ai_swe.models.budget import (
    assert_budget_available,
    consume,
    effective_timeout_s,
)
from ai_swe.models.contracts import (
    FinishReason,
    MessageRole,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    ProviderConfig,
)
from ai_swe.models.errors import (
    BudgetExceededError,
    InvalidResponseError,
    ModelAuthenticationError,
    ModelConfigurationError,
    ModelGatewayError,
    ModelRateLimitError,
    ModelTimeoutError,
    ProviderUnavailableError,
    StructuredOutputError,
    UnknownProviderError,
)
from ai_swe.models.gateway import ModelGateway, gateway_from_settings
from ai_swe.models.pricing import (
    ModelPricing,
    PricingTable,
    pricing_from_entries,
    pricing_from_json,
)
from ai_swe.models.providers import (
    FakeModelAdapter,
    OpenAICompatibleAdapter,
    ProviderAdapter,
    ProviderResponse,
)
from ai_swe.models.registry import (
    build_adapter,
    provider_config_from_settings,
    register_provider,
    registered_providers,
    requires_credentials,
)

__all__ = [
    "BudgetExceededError",
    "FakeModelAdapter",
    "FinishReason",
    "InvalidResponseError",
    "MessageRole",
    "ModelAuthenticationError",
    "ModelConfigurationError",
    "ModelGateway",
    "ModelGatewayError",
    "ModelMessage",
    "ModelPricing",
    "ModelRateLimitError",
    "ModelRequest",
    "ModelResponse",
    "ModelTimeoutError",
    "ModelUsage",
    "OpenAICompatibleAdapter",
    "PricingTable",
    "ProviderAdapter",
    "ProviderConfig",
    "ProviderResponse",
    "ProviderUnavailableError",
    "StructuredOutputError",
    "UnknownProviderError",
    "assert_budget_available",
    "build_adapter",
    "consume",
    "effective_timeout_s",
    "gateway_from_settings",
    "pricing_from_entries",
    "pricing_from_json",
    "provider_config_from_settings",
    "register_provider",
    "registered_providers",
    "requires_credentials",
]
