"""Interfaz de adapter de proveedor.

**Reparto de responsabilidades, que es la razon de que exista esta capa.**

| Capa | Sabe de | NO sabe de |
|---|---|---|
| Adapter | HTTP, cabeceras, forma cruda de la respuesta | presupuesto, reintentos, fallback |
| Gateway | presupuesto, reintentos, fallback, validacion | HTTP, SDK, forma cruda |

Un adapter que conociera el presupuesto tendria que decidir si reintentar, y esa
decision estaria repetida en cada proveedor. Un gateway que conociera la forma
cruda de cada proveedor dejaria de ser sustituible.

**El adapter es sincrono.** Ver `docs/MODEL-GATEWAY-DESIGN.md` §1: la llamada al
modelo ocurre en un hilo de trabajo, no en el camino `async` de la peticion. Un
adapter `async` obligaria a cada nodo sincrono a abrir un bucle de eventos por
llamada y a convertir LangGraph, que esta fuera del alcance de esta fase.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from ai_swe.models.contracts import ModelRequest, ModelUsage


class ProviderResponse(BaseModel):
    """Respuesta **cruda** de un proveedor, antes de normalizar.

    El gateway la convierte en `ModelResponse`. Se mantiene aparte para que el
    gateway no tenga que conocer ninguna forma especifica de proveedor.
    """

    content: str = ""
    model: str = ""
    # Se deja como cadena cruda: el gateway la mapea a `FinishReason`, y un valor
    # que el proveedor invente no debe romper la normalizacion.
    finish_reason: str = ""
    usage: ModelUsage = Field(default_factory=ModelUsage)
    provider_request_id: str | None = None


@runtime_checkable
class ProviderAdapter(Protocol):
    """Contrato que cumple todo proveedor.

    Es un `Protocol`, no una clase base: un adapter no necesita heredar de nada
    para ser valido, solo cumplir la forma. Eso mantiene el acoplamiento en el
    minimo y permite que un doble de prueba sea valido sin ceremonia.
    """

    @property
    def name(self) -> str:
        """Identificador del proveedor, tal como se registra."""
        ...

    def generate(self, request: ModelRequest) -> ProviderResponse:
        """Realiza la llamada y devuelve la respuesta cruda.

        Debe lanzar errores de `ai_swe.models.errors`, nunca excepciones del SDK
        del proveedor: filtrarlas acoplaria el gateway a un proveedor concreto.
        """
        ...
