"""Tabla de precios, separada de la logica del gateway y de los agentes.

**Regla: no se inventan precios.** La tabla esta **vacia por defecto**, asi que el
gateway registra `cost = None` salvo que alguien rellene una entrada a proposito.
Un precio inventado es peor que un precio ausente: el ausente obliga a mirar, el
inventado se cree.

`None` significa «no se sabe» y es distinto de `0.0`, que significa «gratis». El
presupuesto de coste solo actua cuando el usuario declaro `max_cost` **y** hay
precio; sin precio no se puede decidir, y fingir que si seria peor.

Rellenar la tabla es un dato de despliegue, no codigo de agente: por eso vive aqui
y no repartida por los nodos.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ai_swe.models.contracts import ModelUsage


@dataclass(frozen=True)
class ModelPricing:
    """Precio por mil tokens, en la moneda del proveedor."""

    input_per_1k: float
    output_per_1k: float
    currency: str = "USD"

    def __post_init__(self) -> None:
        if self.input_per_1k < 0 or self.output_per_1k < 0:
            raise ValueError("un precio no puede ser negativo")


class PricingTable:
    """Precios por nombre de modelo. Sin entradas, todo cuesta `None`."""

    def __init__(self, entries: Mapping[str, ModelPricing] | None = None) -> None:
        self._entries: dict[str, ModelPricing] = dict(entries or {})

    def add(self, model: str, pricing: ModelPricing) -> None:
        self._entries[model.strip().lower()] = pricing

    def known_models(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def cost(self, model: str, usage: ModelUsage) -> float | None:
        """Coste de la llamada, o `None` si falta informacion para calcularlo.

        Devuelve `None` -no cero- si el modelo no tiene precio o si el proveedor no
        reporto tokens. Calcular con un dato ausente daria una cifra con apariencia
        de exacta y sin fundamento.
        """
        precio = self._entries.get(model.strip().lower())
        if precio is None:
            return None
        if usage.input_tokens is None or usage.output_tokens is None:
            return None
        entrada = usage.input_tokens / 1000 * precio.input_per_1k
        salida = usage.output_tokens / 1000 * precio.output_per_1k
        return entrada + salida


# Tabla por defecto: **vacia a proposito**. Ver la nota de arriba.
TABLA_POR_DEFECTO = PricingTable()
