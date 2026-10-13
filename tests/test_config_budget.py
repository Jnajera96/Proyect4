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

from pathlib import Path

import pytest

from ai_swe.config import (
    ConfiguracionInsuficiente,
    Settings,
    load_settings,
    repositorio_autorizado,
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


# -------------------------------------- configuracion efectiva: el Budget real


def test_el_presupuesto_efectivo_sale_de_la_configuracion() -> None:
    """Los ajustes `AI_SWE_MAX_*_PER_RUN` **construyen** el `Budget`, no lo decoran.

    Antes existian y no se leian en ningun sitio: poner
    `AI_SWE_MAX_TOKENS_PER_RUN=1000` no cambiaba nada, porque el `Budget` de cada
    ejecucion se creaba con sus propios valores por defecto. Un control declarado
    que no se aplica se cree aplicado, y eso es peor que no tenerlo.
    """
    ajustes = Settings(
        max_tokens_per_run=1234,
        max_tool_calls_per_run=7,
        max_model_calls_per_run=9,
        max_seconds_per_run=42.5,
        max_review_cycles=3,
        max_cost_per_run=2.5,
    )

    presupuesto = ajustes.presupuesto()

    assert presupuesto.max_tokens == 1234
    assert presupuesto.max_tool_calls == 7
    assert presupuesto.max_model_calls == 9
    assert presupuesto.max_seconds == 42.5
    assert presupuesto.max_review_cycles == 3
    assert presupuesto.max_cost == 2.5


def test_los_valores_por_defecto_de_configuracion_y_de_contrato_coinciden() -> None:
    """Es lo que hace equivalente `RunEngine(store)` y `RunEngine(store, settings=...)`.

    El motor sin configuracion usa los valores por defecto del contrato; con
    configuracion, los de `Settings`. Si divergieran, el mismo codigo se comportaria
    distinto segun como se construya el motor, y las pruebas que lo construyen sin
    configuracion dejarian de decir nada sobre el servidor.
    """
    assert Settings().presupuesto() == Budget()


def test_sin_limite_de_coste_declarado_el_presupuesto_no_lo_inventa() -> None:
    """`None` es "no se sabe", no cero: cero seria "no se permite gastar nada"."""
    assert Settings().presupuesto().max_cost is None
    assert Settings().presupuesto().remaining_cost is None


def test_una_variable_de_entorno_vacia_usa_el_valor_por_defecto(monkeypatch) -> None:
    """Copiar `.env.example` a `.env` no puede romper el arranque.

    Sin `env_ignore_empty`, `AI_SWE_MAX_COST_PER_RUN=` -una linea sin valor en la
    plantilla- no es un `float` y el arranque falla. Dejar una linea vacia tiene que
    equivaler a no declararla.
    """
    monkeypatch.setenv("AI_SWE_MAX_COST_PER_RUN", "")
    monkeypatch.setenv("AI_SWE_MAX_TOKENS_PER_RUN", "")

    ajustes = Settings()

    assert ajustes.max_cost_per_run is None
    assert ajustes.max_tokens_per_run == 200_000


# ----------------------------------------------- alcance de repositorios


def test_sin_lista_de_repositorios_no_hay_restriccion_adicional() -> None:
    """Vacio = modo local mono-usuario: la autorizacion es registrar el proyecto."""
    assert repositorio_autorizado(Settings(authorized_repos=[]), "/cualquier/sitio")


def test_con_lista_solo_se_acepta_lo_que_cuelga_de_ella(tmp_path: Path) -> None:
    permitido = tmp_path / "permitido"
    (permitido / "sub").mkdir(parents=True)
    otro = tmp_path / "otro"
    otro.mkdir()
    # Un hermano cuyo nombre **empieza** igual: comparar texto en vez de rutas es
    # como se cuelan estos fallos.
    hermano = tmp_path / "permitido-otro"
    hermano.mkdir()

    ajustes = Settings(authorized_repos=[permitido])

    assert repositorio_autorizado(ajustes, permitido)
    assert repositorio_autorizado(ajustes, permitido / "sub")
    assert not repositorio_autorizado(ajustes, otro)
    assert not repositorio_autorizado(ajustes, hermano)


def test_una_ruta_con_puntos_no_esquiva_la_lista(tmp_path: Path) -> None:
    """Se comparan rutas **resueltas**: si no, `permitido/../otro` pasaria."""
    permitido = tmp_path / "permitido"
    permitido.mkdir()
    (tmp_path / "otro").mkdir()

    ajustes = Settings(authorized_repos=[permitido])

    assert not repositorio_autorizado(ajustes, permitido / ".." / "otro")


# ------------------------------------- config -> Run -> Budget efectivo (extremo)


def test_el_motor_arranca_la_ejecucion_con_el_presupuesto_configurado(tmp_path: Path) -> None:
    """El camino **entero**: configuracion -> ejecucion -> `RunState.budget`.

    Comprobar `Settings.presupuesto()` en aislamiento no demuestra que el motor lo
    use. Si `RunEngine` recibiera los ajustes y aun asi creara la ejecucion con el
    `Budget` por defecto, la traduccion seria correcta y el resultado el mismo de
    siempre: `AI_SWE_MAX_TOKENS_PER_RUN` seguiria sin hacer nada. Esta prueba ata las
    dos puntas y es la que convierte "el campo se lee" en "el campo se aplica".
    """
    from ai_swe.graph.engine import RunEngine
    from ai_swe.state import RunStore

    store = RunStore(tmp_path / "estado.db")
    try:
        ajustes = Settings(
            max_tokens_per_run=4242,
            max_tool_calls_per_run=11,
            max_seconds_per_run=99.0,
            max_review_cycles=4,
        )
        motor = RunEngine(store, settings=ajustes)

        estado = motor.crear_estado("explica el modulo de autenticacion")

        assert estado.budget.max_tokens == 4242
        assert estado.budget.max_tool_calls == 11
        assert estado.budget.max_seconds == 99.0
        assert estado.budget.max_review_cycles == 4
    finally:
        store.close()


def test_el_motor_sin_configuracion_usa_el_presupuesto_del_contrato(tmp_path: Path) -> None:
    """Sin `settings` el motor no inventa: usa el contrato, que **coincide** con `Settings`.

    Es la otra rama de `RunEngine._presupuesto`. Se comprueba que no diverge, porque
    de eso depende que `RunEngine(store)` -como lo construyen las pruebas- se comporte
    igual que el motor del servidor: si los dos caminos dieran presupuestos distintos,
    media suite dejaria de decir nada sobre el sistema que se despliega.
    """
    from ai_swe.graph.engine import RunEngine
    from ai_swe.state import RunStore

    store = RunStore(tmp_path / "estado.db")
    try:
        motor = RunEngine(store)

        estado = motor.crear_estado("explica el modulo de autenticacion")

        assert estado.budget == Budget()
    finally:
        store.close()
