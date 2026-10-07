"""Pruebas de configuracion y presupuesto preparado para M2.

Cubre dos cosas que la fase F1 debia dejar listas **antes** de conectar un modelo:

  1. Que M1 arranca sin ninguna credencial, y que la exigencia de clave solo se
     evalua cuando de verdad se va a usar el modelo, con un error tipado y seguro.
  2. Que el `Budget` ya tiene los contadores que M2 necesitara (llamadas al modelo
     y coste), que son validos, serializables y sobreviven a un ciclo de ida y
     vuelta por el checkpoint.

No hay ninguna credencial real en este fichero.
"""

from __future__ import annotations

import pytest

from ai_swe.config import (
    ConfiguracionInsuficiente,
    Settings,
    load_settings,
    require_model_credentials,
)
from ai_swe.contracts import Budget


# ------------------------------------------------------------- arranque sin clave


def test_m1_arranca_sin_clave_de_api() -> None:
    """El sistema debe poder arrancar sin proveedor configurado.

    Es un requisito explicito: M1 no usa modelos, y exigir una clave para arrancar
    impediria ejecutar el grafo y la API sin credenciales.
    """
    ajustes = load_settings()
    assert ajustes.model_api_key.get_secret_value() == ""
    assert ajustes.model_provider  # hay un proveedor por defecto, aunque sin clave


def test_proveedor_local_no_exige_clave() -> None:
    """Un proveedor local expone un endpoint y no usa clave."""
    ajustes = Settings(model_provider="ollama", model_api_key="")
    require_model_credentials(ajustes)  # no debe lanzar


def test_proveedor_con_clave_sin_clave_lanza_error_tipado() -> None:
    ajustes = Settings(model_provider="openai", model_api_key="", model_name="modelo-x")
    with pytest.raises(ConfiguracionInsuficiente) as info:
        require_model_credentials(ajustes)
    assert info.value.campo == "model_api_key"


def test_el_error_de_configuracion_no_filtra_el_valor_del_secreto() -> None:
    """El mensaje nombra el campo que falta, nunca su valor."""
    clave = "esto-nunca-debe-aparecer-12345"
    ajustes = Settings(model_provider="openai", model_api_key=clave, model_name="")
    with pytest.raises(ConfiguracionInsuficiente) as info:
        require_model_credentials(ajustes)
    assert clave not in str(info.value)


def test_proveedor_con_clave_y_modelo_pasa() -> None:
    ajustes = Settings(
        model_provider="openai", model_api_key="clave-falsa", model_name="modelo-x"
    )
    require_model_credentials(ajustes)  # no debe lanzar


# -------------------------------------------------------------- presupuesto M2


def test_budget_tiene_contadores_para_llamadas_al_modelo() -> None:
    presupuesto = Budget()
    assert presupuesto.used_model_calls == 0
    assert presupuesto.max_model_calls >= 1
    assert presupuesto.remaining_model_calls == presupuesto.max_model_calls


def test_budget_de_coste_sin_limite_es_none_no_cero() -> None:
    """Sin limite declarado no hay tope; cero significaria 'no gastar nada'."""
    presupuesto = Budget()
    assert presupuesto.max_cost is None
    assert presupuesto.remaining_cost is None
    assert "cost" not in presupuesto.exhausted_reasons()


def test_budget_coste_agotado() -> None:
    presupuesto = Budget(max_cost=1.0, used_cost=1.0)
    assert presupuesto.remaining_cost == 0
    assert "cost" in presupuesto.exhausted_reasons()


@pytest.mark.parametrize(
    ("kwargs", "motivo"),
    [
        ({"max_tokens": 10, "used_tokens": 10}, "tokens"),
        ({"max_tool_calls": 3, "used_tool_calls": 3}, "tool_calls"),
        ({"max_model_calls": 4, "used_model_calls": 4}, "model_calls"),
        ({"max_seconds": 5.0, "elapsed_seconds": 5.0}, "seconds"),
        ({"max_cost": 0.5, "used_cost": 0.5}, "cost"),
        ({"max_review_cycles": 1, "review_cycles_used": 2}, "review_cycles"),
    ],
)
def test_budget_informa_del_motivo_del_agotamiento(kwargs: dict, motivo: str) -> None:
    """El motivo importa: parar sin decir por que obliga a adivinar cual de los seis limites salto."""
    presupuesto = Budget(**kwargs)
    assert presupuesto.exhausted is True
    assert motivo in presupuesto.exhausted_reasons()


def test_budget_puede_agotarse_por_varios_motivos_a_la_vez() -> None:
    presupuesto = Budget(max_tokens=1, used_tokens=1, max_cost=0.0)
    motivos = presupuesto.exhausted_reasons()
    assert "tokens" in motivos and "cost" in motivos


def test_budget_con_margen_no_esta_agotado() -> None:
    presupuesto = Budget(used_tokens=10, used_tool_calls=1, used_model_calls=1)
    assert presupuesto.exhausted is False
    assert presupuesto.exhausted_reasons() == ()


def test_budget_rechaza_contadores_negativos() -> None:
    """Un contador negativo es un dato imposible: debe fallar al construirlo."""
    with pytest.raises(ValueError):
        Budget(used_tokens=-1)
    with pytest.raises(ValueError):
        Budget(used_model_calls=-1)
    with pytest.raises(ValueError):
        Budget(used_cost=-0.01)


def test_budget_es_serializable_y_sobrevive_a_ida_y_vuelta() -> None:
    """El presupuesto vive en el estado persistido: debe poder viajar entero.

    `model_dump` -> `model_validate` es el camino que sigue el checkpoint. Si un
    campo se perdiera por el camino, la reanudacion arrancaria con un dato falso.
    """
    original = Budget(
        max_cost=2.5, used_cost=1.25, max_model_calls=10, used_model_calls=3
    )
    recuperado = Budget.model_validate(original.model_dump())
    assert recuperado == original
    assert recuperado.used_cost == 1.25
    assert recuperado.used_model_calls == 3
