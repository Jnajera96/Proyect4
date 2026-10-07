"""Pruebas del generador del diagrama arquitectonico.

Dos cosas distintas:

  1. Que el layout actual es geometricamente valido y tiene el numero esperado
     de elementos.
  2. Que el validador **detecta de verdad** los defectos que dice detectar.

La segunda parte es la importante. Una validacion que nunca ha fallado no ha
demostrado nada: puede estar comprobando una lista vacia y aun asi informar
"sin errores".
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
BUILD = RAIZ / "tools" / "build_diagram.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_diagram", BUILD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bd = _load()


@pytest.fixture
def layout_restaurado():
    """Restaura el layout despues de cada prueba: el modulo es estado global."""
    original = (copy.deepcopy(bd.LABELS), copy.deepcopy(bd.NODES), copy.deepcopy(bd.EDGES),
                copy.deepcopy(bd.LEGEND))
    try:
        yield
    finally:
        labels, nodes, edges, legend = original
        bd.LABELS[:] = labels
        bd.NODES.clear()
        bd.NODES.update(nodes)
        bd.EDGES.clear()
        bd.EDGES.update(edges)
        bd.LEGEND[:] = legend


# ------------------------------------------------------ 1. el layout actual
def test_el_layout_es_geometricamente_valido() -> None:
    assert bd.validate() == []


def test_el_numero_de_elementos_es_el_esperado() -> None:
    """Control positivo: sin esto, un layout vacio pasaria la validacion."""
    assert len(bd.NODES) == 16
    assert len(bd.EDGES) == 20
    assert len(bd.LABELS) == 5
    assert len(bd.LEGEND) == 3
    assert len(bd.ZONES) == 2


def test_el_svg_declara_su_espacio_de_nombres_y_su_tamano() -> None:
    svg = bd.emit_svg()
    assert svg.startswith("<?xml")
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert f'viewBox="0 0 {bd.CANVAS_W} {bd.CANVAS_H}"' in svg
    assert svg.count("<title") == 1 and svg.count("<desc") == 1


def test_todas_las_aristas_estan_dibujadas() -> None:
    svg = bd.emit_svg()
    for key, (_, _, pts) in bd.EDGES.items():
        inicio = "M" + " L".join(f"{x} {y}" for x, y in pts)
        assert inicio in svg, f"la arista {key} no aparece en el SVG"


# ---------------------------------------------- 2. el validador funciona
def _mutar_y_validar(mutacion) -> list[str]:
    mutacion()
    return bd.validate()


def test_detecta_una_etiqueta_sobre_un_nodo(layout_restaurado) -> None:
    def mutacion():
        bd.LABELS[0] = ("stt_api", "texto confirmado", 560, 380, "start")

    errores = _mutar_y_validar(mutacion)
    assert any("pisa el nodo" in e for e in errores), errores


def test_detecta_un_nodo_fuera_del_lienzo(layout_restaurado) -> None:
    def mutacion():
        bd.NODES["result"] = (400, 910, 720, bd.CANVAS_H + 120, "green", "Resultado", "x")

    errores = _mutar_y_validar(mutacion)
    assert any("fuera del lienzo" in e for e in errores), errores


def test_detecta_nodos_solapados(layout_restaurado) -> None:
    def mutacion():
        bd.NODES["coder"] = bd.NODES["researcher"]

    errores = _mutar_y_validar(mutacion)
    assert any("solape de nodos" in e for e in errores), errores


def test_detecta_una_arista_a_un_nodo_inexistente(layout_restaurado) -> None:
    def mutacion():
        bd.EDGES["sup_llm"] = ("supervisor", "fantasma", [(950, 472), (1080, 472)])

    errores = _mutar_y_validar(mutacion)
    assert any("destino inexistente" in e for e in errores), errores


def test_detecta_una_etiqueta_que_cruza_una_arista(layout_restaurado) -> None:
    def mutacion():
        # Centrada en la vertical x=560 de la arista stt -> api.
        bd.LABELS[0] = ("stt_api", "cruce", 560, 322, "middle")

    errores = _mutar_y_validar(mutacion)
    assert any("cruza el trazo" in e for e in errores), errores


def test_detecta_un_nodo_que_cruza_el_borde_de_una_zona(layout_restaurado) -> None:
    def mutacion():
        bd.NODES["llm"] = (1000, 438, 1360, 613, "teal", "Foundation Model", "x")

    errores = _mutar_y_validar(mutacion)
    assert any("cruza el borde de la zona" in e for e in errores), errores


def test_detecta_una_leyenda_sobre_un_nodo(layout_restaurado) -> None:
    """Regresion del defecto real: la leyenda pisaba `result` y `tts`.

    El texto es el que tenia la leyenda antes de incorporarla al modelo
    validado. Es invisible en el render porque es gris claro sobre relleno
    claro, y por eso la comprobacion tiene que ser geometrica.
    """
    texto_original = (
        "Linea continua: flujo principal. Linea discontinua: flujo opcional o transversal. "
        "El repositorio del usuario no se modifica hasta que se aprueba la promocion desde el worktree."
    )

    def mutacion():
        bd.LEGEND[0] = (texto_original, 70, 966)

    errores = _mutar_y_validar(mutacion)
    assert any("leyenda" in e and "pisa el nodo result" in e for e in errores), errores
    assert any("leyenda" in e and "pisa el nodo tts" in e for e in errores), errores


def test_detecta_un_recuento_inesperado(layout_restaurado) -> None:
    def mutacion():
        bd.NODES.pop("tts")

    errores = _mutar_y_validar(mutacion)
    assert any("se esperaban 16 nodos" in e for e in errores), errores


def test_el_layout_sigue_siendo_valido_tras_restaurar(layout_restaurado) -> None:
    """El fixture restaura bien: si no, las mutaciones contaminarian otras pruebas."""
    assert bd.validate() == []
