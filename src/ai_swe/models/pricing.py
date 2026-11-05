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

**Como se rellena (F3).** El dato de despliegue entra por dos vias, ambas
explicitas y ambas **verificables por quien las configura**:

  1. `AI_SWE_MODEL_PRICING`, una lista JSON en el entorno, con la forma

         [{"model": "gpt-4o-mini", "input_per_1k": 0.00015,
           "output_per_1k": 0.0006, "currency": "USD"}]

     Los valores son los de la tarifa publicada por el proveedor, **en la moneda
     del proveedor**. Quien la escribe es quien responde de ella.

  2. `PricingTable.add("modelo", ModelPricing(...))` para un despliegue programatico.

Ninguna de las dos esta rellena en el repositorio. Eso es deliberado: el proyecto
no afirma conocer una tarifa que solo el proveedor puede publicar, y una tarifa que
cambia sin avisar es exactamente el dato que no debe quedar congelado en el codigo.

**Verificacion contra el proveedor.** La prueba real
(`tests/test_model_gateway_real.py`) **no** comprueba el precio: comprueba que la
cadena completa funciona. El precio se comprueba en `tests/test_pricing.py`, que
exige que un modelo con precio conocido devuelva una cifra y que uno sin precio
devuelva `None`, sin afirmar que ningun precio concreto sea el vigente.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
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

    @classmethod
    def from_mapping(cls, datos: Mapping[str, object]) -> ModelPricing:
        """Construye el precio desde un diccionario ya deserializado.

        Se valida el **tipo** de cada campo antes de convertirlo. Convertir a
        `float` a ciegas aceptaria `"mucho"` como precio si fallara la conversion
        en otro punto; aqui se comprueba que sea un numero de verdad, y el error
        dice cual falta.
        """
        faltan = [c for c in ("input_per_1k", "output_per_1k") if c not in datos]
        if faltan:
            raise ValueError(
                f"la entrada de precio no declara {', '.join(faltan)}: "
                "un precio a medias es un precio inventado"
            )
        entrada, salida = datos["input_per_1k"], datos["output_per_1k"]
        for nombre, valor in (("input_per_1k", entrada), ("output_per_1k", salida)):
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise ValueError(f"{nombre} debe ser un numero, no {type(valor).__name__}")
        moneda = datos.get("currency", "USD")
        if not isinstance(moneda, str) or not moneda.strip():
            raise ValueError("currency debe ser una cadena no vacia")
        return cls(
            input_per_1k=float(entrada),  # type: ignore[arg-type]
            output_per_1k=float(salida),  # type: ignore[arg-type]
            currency=moneda.strip().upper(),
        )


class PricingTable:
    """Precios por nombre de modelo. Sin entradas, todo cuesta `None`."""

    def __init__(self, entries: Mapping[str, ModelPricing] | None = None) -> None:
        self._entries: dict[str, ModelPricing] = dict(entries or {})

    def add(self, model: str, pricing: ModelPricing) -> None:
        self._entries[model.strip().lower()] = pricing

    def known_models(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def __len__(self) -> int:
        return len(self._entries)

    def cost(self, model: str, usage: ModelUsage) -> float | None:
        """Coste de la llamada, o `None` si falta informacion para calcularlo.

        Devuelve `None` -no cero- si el modelo no tiene precio o si el proveedor no
        reporto tokens. Calcular con un dato ausente daria una cifra con apariencia
        de exacta y sin fundamento.
        """
        precio = self._entries.get(model.strip().lower())
        if precio is None and "/" in model:
            base_model = model.split("/", 1)[-1].strip().lower()
            precio = self._entries.get(base_model)
        if precio is None:
            return None
        if usage.input_tokens is None or usage.output_tokens is None:
            return None
        entrada = usage.input_tokens / 1000 * precio.input_per_1k
        salida = usage.output_tokens / 1000 * precio.output_per_1k
        return entrada + salida


def pricing_from_entries(entradas: Iterable[Mapping[str, object]]) -> PricingTable:
    """Construye una tabla desde una lista de diccionarios con la forma esperada.

    Se separa de `PricingTable` para que la **entrada** (texto de configuracion,
    fichero, variable de entorno) quede fuera del tipo que usa el gateway: el
    gateway no debe saber de donde vinieron los precios.
    """
    tabla = PricingTable()
    for indice, entrada in enumerate(entradas):
        if "model" not in entrada or not str(entrada["model"]).strip():
            raise ValueError(f"la entrada de precio #{indice} no declara 'model'")
        tabla.add(str(entrada["model"]), ModelPricing.from_mapping(entrada))
    return tabla


def pricing_from_json(texto: str) -> PricingTable:
    """Interpreta el JSON de precios. Un texto vacio da una tabla vacia, no error.

    Que la variable no exista debe ser el caso normal (no hay precios declarados),
    no un fallo de arranque. Un JSON **presente pero invalido** si es un error: si
    alguien escribio precios, unos precios mal escritos no deben pasar en silencio.
    """
    if not texto or not texto.strip():
        return PricingTable()
    datos = json.loads(texto)
    if not isinstance(datos, list) or any(not isinstance(e, dict) for e in datos):
        raise ValueError(
            "AI_SWE_MODEL_PRICING debe ser una lista JSON de objetos "
            '[{"model": ..., "input_per_1k": ..., "output_per_1k": ...}]'
        )
    return pricing_from_entries(datos)


# Tabla por defecto: **vacia a proposito**. Ver la nota de arriba.
TABLA_POR_DEFECTO = PricingTable()
