"""Adaptador de Speech-to-Text.

Es el modulo **prescindible por diseno**: si se elimina, el sistema sigue completo
(docs/01-arquitectura.md, seccion 0). En la fase M1 solo `FakeAdapter` funciona;
`FasterWhisperAdapter` llega en M5.
"""

from ai_swe.stt.base import (
    FakeAdapter,
    FasterWhisperAdapter,
    Segment,
    STTAdapter,
    Transcript,
)

__all__ = [
    "FakeAdapter",
    "FasterWhisperAdapter",
    "STTAdapter",
    "Segment",
    "Transcript",
]
