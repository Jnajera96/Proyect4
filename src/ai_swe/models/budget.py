"""Consumo del presupuesto, como funciones puras.

**Por que funciones y no un objeto con estado.** El gateway no posee el
presupuesto: lo recibe y devuelve el delta. Sin estado compartido no hay carrera
que proteger, y dos ejecuciones concurrentes quedan aisladas por construccion en
lugar de por cerrojo. Ademas encaja con el estilo que ya usan los nodos
(`_con_presupuesto` devuelve un `Budget` nuevo en vez de mutar el existente).

`Budget` vive en `ai_swe.contracts.state` y **no se redefine aqui**: se consume.
"""

from __future__ import annotations

from ai_swe.contracts import Budget
from ai_swe.models.contracts import ModelUsage
from ai_swe.models.errors import BudgetExceededError

# Nombres de motivo de `Budget.exhausted_reasons()` que el gateway puede provocar.
# `tool_calls` y `review_cycles` no los toca el modelo y no se comprueban aqui.
MOTIVOS_DE_MODELO = frozenset({"tokens", "model_calls", "seconds", "cost"})


def assert_budget_available(budget: Budget, *, provider: str | None = None) -> None:
    """Comprueba el presupuesto **antes** de gastar una llamada.

    Si esta agotado, lanza `BudgetExceededError` con los motivos. No se gasta la
    llamada: el modelo no puede ignorar el presupuesto, y el error dice **por que**
    se nego, no solo que se nego.
    """
    motivos = tuple(m for m in budget.exhausted_reasons() if m in MOTIVOS_DE_MODELO)
    if motivos:
        raise BudgetExceededError(
            f"presupuesto agotado: {', '.join(motivos)}",
            motivos=motivos,
            provider=provider,
        )


def effective_timeout_s(budget: Budget, timeout_s: float | None) -> float | None:
    """Acota el timeout al tiempo que queda de presupuesto.

    Un agente no puede esperar mas de lo que le queda, aunque el proveedor este
    dispuesto a responder. Devuelve `None` si no hay limite aplicable, para que el
    adapter use el suyo.
    """
    if budget.max_seconds <= 0:
        return timeout_s
    restante = budget.max_seconds - budget.elapsed_seconds
    if restante <= 0:
        return 0.0  # agotado: el llamante deberia haber cortado antes
    if timeout_s is None:
        return restante
    return min(timeout_s, restante)


def consume(
    budget: Budget,
    *,
    usage: ModelUsage | None = None,
    cost: float | None = None,
) -> Budget:
    """Devuelve un `Budget` **nuevo** con la llamada y el consumo aplicados.

    Reglas:

    - una llamada al modelo siempre cuenta, aunque el proveedor no reporte tokens:
      el contador de llamadas es lo que evita un bucle infinito de peticiones;
    - los tokens solo se suman si el proveedor los reporto. `None` no se convierte
      en cero, porque cero afirmaria que no se consumio nada;
    - el coste solo se suma si se conoce (`cost is not None`). `None` significa «no
      se sabe», y sumarlo como cero falsearia el gasto acumulado.
    """
    datos = budget.model_dump()
    datos["used_model_calls"] = budget.used_model_calls + 1

    if usage is not None and usage.known_total is not None:
        datos["used_tokens"] = budget.used_tokens + usage.known_total
        # F14: el desglose entrada/salida. Solo se suma la parte que el proveedor
        # reporto: `None` no se convierte en cero, porque cero afirmaria que no se
        # consumio nada. Una respuesta sin desglose deja los contadores como estaban
        # y el total sigue siendo correcto.
        if usage.input_tokens is not None:
            datos["used_input_tokens"] = budget.used_input_tokens + usage.input_tokens
        if usage.output_tokens is not None:
            datos["used_output_tokens"] = budget.used_output_tokens + usage.output_tokens

    if cost is not None:
        datos["used_cost"] = budget.used_cost + cost

    return Budget.model_validate(datos)
