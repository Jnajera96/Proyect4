"""Pruebas para el agente y la interpretación de pedidos dictados por voz."""

from __future__ import annotations

from datetime import UTC, datetime
import pytest

from ai_swe.contracts import Instruction, InstructionSource, Intent, RunState, TranscriptMeta
from ai_swe.graph import nodes
from ai_swe.models import FakeModelAdapter, ModelGateway


@pytest.fixture(autouse=True)
def _restaurar_gateway():
    previo = nodes._GATEWAY
    yield
    nodes.usar_gateway(previo)


def estado_voz(texto: str, *, repo: str | None = None) -> RunState:
    ahora = datetime.now(UTC)
    meta = TranscriptMeta(
        provider="faster-whisper:large-v3",
        language="es",
        confidence=0.92,
        duration_s=4.5,
    )
    return RunState(
        run_id="run-voice-test",
        trace_id="trace-voice-test",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text=texto,
            source=InstructionSource.VOICE,
            transcript_meta=meta,
            confirmed_by_user=True,
        ),
    )


@pytest.mark.parametrize(
    "texto,nucleo_esperado",
    [
        ("Oye por favor crea una calculadora con operaciones básicas", "calculadora"),
        ("mira quiero una app para contar calorias", "app"),
        ("a ver hazme un convertidor de monedas", "convertidor de monedas"),
        ("buenas necesito un cronometro", "cronometro"),
        ("hola podrías crear un gestor de tareas", "gestor de tareas"),
        ("oye haz una calculadora", "calculadora"),
    ],
)
def test_voice_conversational_intros_extract_nominal_core(texto: str, nucleo_esperado: str) -> None:
    assert nodes._clasificar(texto) == Intent.MODIFY
    nucleo = nodes._nucleo_producto(texto)
    assert nucleo_esperado in nucleo.lower()


def test_voice_modification_verbs_without_archetype() -> None:
    # "agrega", "ponle", "elimina" modifican código existente sin ser arquetipos nuevos
    assert nodes._clasificar("porfa agrega una función para validar contraseñas") == Intent.MODIFY
    assert nodes._clasificar("mira ponle un botón para cerrar sesión") == Intent.MODIFY
    assert nodes._clasificar("a ver quita el console.log de la línea 5") == Intent.MODIFY


def test_voice_instruction_tagged_for_model() -> None:
    fake = FakeModelAdapter(
        structured={
            "intent": "modify",
            "scope": {"repo_path": "/repo", "allowed_paths": [], "protected_paths": []},
            "constraints": [],
            "confidence": 0.95,
            "rationale": "Propuesta base para confirmar:\n- Funcionalidades: calculadora",
        }
    )
    nodes.usar_gateway(ModelGateway([fake]))

    st = estado_voz("Oye mira porfa hazme una calculadora sencilla")
    res = nodes.interpret(st)
    assert res["interpretation"].intent == Intent.MODIFY
    assert len(fake.calls) == 1
    mensajes = fake.calls[0].messages
    assert any("[Instruccion dictada por voz]" in m.content for m in mensajes if m.role.value == "user")


@pytest.mark.parametrize(
    "texto,intent_esperado",
    [
        ("Oye disculpa, ¿cómo funciona este script?", Intent.QUESTION),
        ("hola, explica qué hace la función principal", Intent.QUESTION),
        ("a ver revisa si hay pruebas en tests/", Intent.INSPECT),
        ("porfa haz un git push al repositorio remoto", Intent.OUT_OF_SCOPE),
    ],
)
def test_voice_preserves_questions_inspections_and_out_of_scope(texto: str, intent_esperado: Intent) -> None:
    assert nodes._clasificar(texto) == intent_esperado
