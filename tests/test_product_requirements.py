"""Short product requests remain proposals until a person confirms them."""

import pytest
from test_f3_interpret_analyst import estado, json_valido

from ai_swe.graph import nodes
from ai_swe.models import FakeModelAdapter, ModelGateway


@pytest.mark.parametrize(
    "text,feature",
    [
        ("hazme una calculadora científica", "seno"),
        ("calculadora", "Operaciones"),
        ("un calendario interactivo", "eventos"),
        ("un contador de calorías", "alimentos"),
    ],
)
def test_local_analyst_proposes_reviewable_baseline(text, feature, monkeypatch):
    monkeypatch.setattr(nodes, "_GATEWAY", nodes.SIN_GATEWAY)
    interpretation = nodes.interpret(estado(text, repo="/fixture"))["interpretation"]
    assert interpretation.intent == "modify"
    assert interpretation.confidence >= 0.85
    assert not interpretation.confirmed_by_user
    for fragment in (feature, "Validaciones", "Interfaz", "Pruebas", "Propuesta"):
        assert fragment in interpretation.rationale


@pytest.mark.parametrize(
    "text,intent",
    [
        ("¿Qué es una calculadora científica?", "question"),
        ("analiza el calendario", "inspect"),
        ("no crees una calculadora", "inspect"),
        ("publica un calendario en GitHub", "out_of_scope"),
        ("corrige el error del calendario", "modify"),
        ("crea una calculadora solo para sumar", "modify"),
    ],
)
def test_baseline_does_not_expand_questions_repairs_or_explicit_limits(text, intent, monkeypatch):
    monkeypatch.setattr(nodes, "_GATEWAY", nodes.SIN_GATEWAY)
    interpretation = nodes.interpret(estado(text))["interpretation"]
    assert interpretation.intent == intent
    assert "Propuesta base" not in interpretation.rationale


def test_model_receives_product_role_and_clear_intent_floor(monkeypatch):
    fake = FakeModelAdapter(
        structured=json_valido(confidence=0.5, rationale="Propuesta del modelo")
    )
    monkeypatch.setattr(nodes, "_GATEWAY", ModelGateway([fake]))
    interpretation = nodes.interpret(estado("crea una calculadora"))["interpretation"]
    assert interpretation.confidence >= 0.85
    assert not interpretation.confirmed_by_user
    prompt = fake.calls[0].messages[0].content
    for fragment in ("Product Manager", "ARQUETIPO", "Validaciones", "Pruebas", "0.85"):
        assert fragment in prompt
    for fragment in ("SÍNTESIS UNIVERSAL", "CUALQUIER", "3 a 5", "pytest"):
        assert fragment in prompt


def test_short_request_waits_for_human_and_coder_receives_adjustments(tmp_path, monkeypatch):
    import subprocess

    from test_project_builder_pipeline import BuilderAdapter, project_files

    from ai_swe.config import Settings
    from ai_swe.contracts import RunOptions
    from ai_swe.graph import RunEngine, model_routing
    from ai_swe.state import RunStore

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@localhost",
            "commit",
            "--allow-empty",
            "-qm",
            "initial",
        ],
        check=True,
        capture_output=True,
    )
    fake = BuilderAdapter(project_files("calendar"))
    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: ModelGateway([fake]))
    settings = Settings(
        _env_file=None, network_egress_enabled=True,
        profile_id="product-fixture",
        remote_model_roles=["coder", "reviewer"],
        state_db_path=tmp_path / "state.sqlite3",
        workspace_root=tmp_path / "worktrees",
        allowed_test_targets=["pytest.unit", "ruff.check"],
    )
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado("un calendario", options=RunOptions(repo_path=str(repo)))
        waiting = engine.start(state)
        assert waiting.status == "awaiting_human_requirements_confirmation"
        assert "Propuesta base" in waiting.interpretation.rationale
        assert fake.calls == []
        adjusted = "Construir un calendario mensual con eventos personales y pruebas de fechas."
        result = engine.resume(state.run_id, {"decision": "modified", "rationale": adjusted})
        assert result.status == "awaiting_approval", result.errors
        assert result.interpretation.confirmed_by_user
        assert result.interpretation.rationale == adjusted
        assert adjusted in "\n".join(message.content for message in fake.calls[0].messages)
        assert not (repo / "index.html").exists()


@pytest.mark.parametrize(
    "text",
    [
        "un conversor de monedas",
        "un temporizador pomodoro",
        "un tablero de notas",
        "un juego de tres en raya",
        "un generador de contraseñas",
        "un reloj pomodoro",
        "una herramienta de clasificación de libros",
        "crea un simulador de órbitas",
        "un gestor de listas",
    ],
)
def test_new_products_have_four_dimensions_and_wait_for_confirmation(tmp_path, monkeypatch, text):
    from ai_swe.config import Settings
    from ai_swe.contracts import RunOptions
    from ai_swe.graph import RunEngine, model_routing
    from ai_swe.state import RunStore

    fake = FakeModelAdapter()
    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: ModelGateway([fake]))
    settings = Settings(
        _env_file=None, network_egress_enabled=True,
        profile_id="universal-fixture",
        remote_model_roles=["coder", "reviewer"],
        state_db_path=tmp_path / "state.sqlite3",
        workspace_root=tmp_path / "worktrees",
    )
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        waiting = engine.start(
            engine.crear_estado(text, options=RunOptions(repo_path=str(tmp_path)))
        )
        assert waiting.status == "awaiting_human_requirements_confirmation"
        interpretation = waiting.interpretation
        assert interpretation.intent == "modify" and interpretation.confidence >= 0.85
        assert not interpretation.confirmed_by_user
        bullets = [line for line in interpretation.rationale.splitlines() if line.startswith("- ")]
        assert len(bullets) == 4
        for heading, bullet in zip(
            ("Funcionalidades", "Validaciones", "Interfaz", "Pruebas"), bullets, strict=True
        ):
            assert bullet.startswith("- " + heading)
        assert fake.calls == []


@pytest.mark.parametrize(
    "text,intent",
    [
        ("¿Qué es un conversor de monedas?", "question"),
        ("cómo crear un juego de tres en raya", "question"),
        ("analiza un tablero de notas", "inspect"),
        ("analiza cómo crear un juego", "inspect"),
        ("analiza el tablero y corrige el error", "modify"),
        ("no hagas un generador de contraseñas", "inspect"),
        ("crea un conversor de divisas sin conexión a Internet", "modify"),
    ],
)
def test_universal_synthesis_preserves_questions_and_exclusions(text, intent, monkeypatch):
    monkeypatch.setattr(nodes, "_GATEWAY", nodes.SIN_GATEWAY)
    interpretation = nodes.interpret(estado(text))["interpretation"]
    assert interpretation.intent == intent
    assert "Propuesta base" not in interpretation.rationale


@pytest.mark.parametrize(
    "text,expected",
    [
        ("un conversor de monedas", "unidades"),
        ("un temporizador pomodoro", "pausa"),
        ("un tablero de notas", "búsqueda"),
        ("un juego de tres en raya", "victoria"),
        ("un generador de contraseñas", "criptográfica"),
        ("crea un simulador de órbitas", "simulador de órbitas"),
    ],
)
def test_family_capabilities_and_unknown_nominal_core(text, expected, monkeypatch):
    monkeypatch.setattr(nodes, "_GATEWAY", nodes.SIN_GATEWAY)
    rationale = nodes.interpret(estado(text))["interpretation"].rationale
    assert expected in rationale
