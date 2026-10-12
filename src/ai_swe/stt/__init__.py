"""Adaptador de Speech-to-Text.

Es el modulo **prescindible por diseno**: si se elimina, el sistema sigue completo
(docs/01-arquitectura.md, seccion 0).

Desde F13 hay **dos** implementaciones utilizables y se eligen por configuracion
(`crear_adaptador_stt`): `FakeAdapter`, determinista y sin audio (pruebas), y
`FasterWhisperAdapter`, transcripcion local real. La dependencia de esta ultima es
**opcional** (extra `voice`): si no esta instalada, el sistema sigue funcionando por
texto.
"""

from ai_swe.stt.base import (
    FakeAdapter,
    FasterWhisperAdapter,
    Segment,
    STTAdapter,
    STTError,
    STTNotAvailable,
    Transcript,
    crear_adaptador_stt,
)

__all__ = [
    "FakeAdapter",
    "FasterWhisperAdapter",
    "STTAdapter",
    "STTError",
    "STTNotAvailable",
    "Segment",
    "Transcript",
    "crear_adaptador_stt",
]
