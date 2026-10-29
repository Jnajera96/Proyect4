import pytest

from ai_swe.graph.nodes import _clasificar


@pytest.mark.parametrize("text, expected", [
    ("Crea una calculadora sin dependencias de producción.", "modify"),
    ("Crea una calculadora; no publiques en GitHub.", "modify"),
    ("Crea una función push_button para una interfaz local.", "modify"),
    ("Crea una calculadora y publica en GitHub.", "out_of_scope"),
    ("Crea una calculadora sin dependencias y despliega a producción.", "out_of_scope"),
    ("Crea una calculadora; no toques producción, pero haz push.", "out_of_scope"),
    ("No tengas miedo, publica en GitHub.", "out_of_scope"),
    ("No modifiques ni crea archivos; analiza el código.", "inspect"),
])
def test_negated_scope_mentions_do_not_hide_affirmative_remote_actions(text, expected):
    assert _clasificar(text) == expected
