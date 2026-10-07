"""Adaptador de Speech-to-Text: contrato e implementaciones.

El STT es un **adaptador de borde** (docs/01-arquitectura.md, seccion 0). Su unica
responsabilidad es producir texto con metadatos. No conoce agentes, ni planes, ni
herramientas, y el sistema funciona sin el.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class Segment(BaseModel):
    start_s: float = Field(ge=0.0)
    end_s: float = Field(ge=0.0)
    text: str


class Transcript(BaseModel):
    """Resultado de una transcripcion. **No** crea ninguna ejecucion (`RF-02`)."""

    text: str = Field(min_length=1)
    language: str = Field(min_length=2, max_length=16)
    confidence: float = Field(ge=0.0, le=1.0)
    duration_s: float = Field(ge=0.0)
    provider: str = Field(min_length=1)
    segments: list[Segment] = Field(default_factory=list, max_length=2000)
    low_confidence: bool = Field(
        default=False,
        description="La confianza esta por debajo del umbral y hay que avisar al usuario.",
    )


@runtime_checkable
class STTAdapter(Protocol):
    """Contrato del adaptador. Implementaciones intercambiables por configuracion."""

    def transcribe(self, audio: bytes, *, vocabulary: list[str] | None = None) -> Transcript: ...

    def health(self) -> bool: ...


class FakeAdapter:
    """Adaptador determinista, sin audio real.

    No es un detalle menor: es lo que permite que **toda la suite de pruebas corra
    sin audio**, y lo que hace verificable de forma trivial que el audio crudo
    nunca llega al Supervisor (`RF-03`). Tambien permite probar el sistema
    completo en integracion continua, sin modelo y sin microfono.
    """

    def __init__(self, texto: str = "analiza el proyecto y corrige los errores", confianza: float = 0.92):
        self._texto = texto
        self._confianza = confianza

    def transcribe(self, audio: bytes, *, vocabulary: list[str] | None = None) -> Transcript:
        return Transcript(
            text=self._texto,
            language="es",
            confidence=self._confianza,
            duration_s=round(max(len(audio), 1) / 16_000.0, 3),
            provider="fake:deterministic",
            segments=[Segment(start_s=0.0, end_s=1.0, text=self._texto)],
        )

    def health(self) -> bool:
        return True


class FasterWhisperAdapter:
    """Implementacion local por defecto. **Pendiente: fase M5.**

    Se deja declarada con su motivo: el sistema debe poder ejecutarse sin ella, y
    la fase M5 es la penultima precisamente por eso.
    """

    def __init__(self, modelo: str = "large-v3", idioma: str = "es") -> None:
        self._modelo = modelo
        self._idioma = idioma

    def transcribe(self, audio: bytes, *, vocabulary: list[str] | None = None) -> Transcript:
        raise NotImplementedError(
            "el adaptador local de Speech-to-Text llega en la fase M5; "
            "hasta entonces se usa FakeAdapter o se envia texto"
        )

    def health(self) -> bool:
        return False
