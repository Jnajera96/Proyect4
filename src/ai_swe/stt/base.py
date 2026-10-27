"""Adaptador de Speech-to-Text: contrato e implementaciones.

El STT es un **adaptador de borde** (docs/01-arquitectura.md, seccion 0). Su unica
responsabilidad es producir texto con metadatos. No conoce agentes, ni planes, ni
herramientas, y el sistema funciona sin el.

**El audio crudo no cruza esta frontera.** Ninguna implementacion devuelve el audio,
ni una referencia a el: lo que sale es un `Transcript` -texto, idioma, confianza y
segmentos-. Es lo que hace cumplir `RF-03` por construccion: el Supervisor y el
modelo reciben texto, y no existe una via por la que puedan recibir otra cosa.
"""

from __future__ import annotations

import io
import math
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


class STTError(RuntimeError):
    """Fallo al transcribir. Tipado y accionable: dice que fallo y por que.

    **Una transcripcion fallida nunca se sustituye por un texto inventado.** Devolver
    una frase de relleno seria fabricar la peticion del usuario, que es justo lo que
    este sistema no hace. El fallo se declara.
    """


class STTNotAvailable(STTError):
    """La dependencia `faster-whisper` no esta instalada (extra `voice`).

    Se separa de `STTError` a proposito: no es una averia, es una **capacidad no
    instalada**, y la accion que sugiere es distinta -instalar el extra, o seguir
    trabajando por texto-.
    """


class FakeAdapter:
    """Adaptador determinista, sin audio real.

    No es un detalle menor: es lo que permite que **toda la suite de pruebas corra
    sin audio**, y lo que hace verificable de forma trivial que el audio crudo
    nunca llega al Supervisor (`RF-03`). Tambien permite probar el sistema
    completo en integracion continua, sin modelo y sin microfono.

    **No es el adaptador de produccion.** Devuelve un texto fijo con independencia de
    lo que reciba: usarlo fuera de una prueba seria fabricar transcripciones.
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


def _confianza_de(segmentos: list) -> float:
    """Confianza en `[0, 1]` derivada de `avg_logprob` de los segmentos.

    **Es una heuristica, no una probabilidad calibrada**, y se declara como tal.
    `faster-whisper` no expone una probabilidad por transcripcion: expone la
    log-probabilidad media de cada segmento. `exp(avg_logprob)` la lleva al rango
    `(0, 1]` y se promedia sobre los segmentos. Sirve para decidir si hay que
    **avisar** al usuario (umbral), no para afirmar una certeza.

    El suelo de `-20` es para no desbordar: `exp(-20)` ya es ~2e-9, indistinguible de
    cero a efectos del umbral, y evita un `OverflowError` con log-probabilidades muy
    negativas.
    """
    valores = [
        math.exp(max(-20.0, float(getattr(segmento, "avg_logprob", 0.0) or 0.0)))
        for segmento in segmentos
    ]
    if not valores:
        return 0.0
    return min(1.0, max(0.0, sum(valores) / len(valores)))


class FasterWhisperAdapter:
    """Transcripcion local con `faster-whisper` (F13).

    **Sin red y sin nube.** El modelo se ejecuta en la maquina del usuario y el audio
    no sale de ella. Es la razon de que este adaptador exista: el sistema tiene que
    poder usarse sin enviar la voz a un tercero.

    **El modelo se carga de forma perezosa.** Cargarlo cuesta segundos y cientos de
    megabytes; hacerlo en el constructor convertiria `crear_app()` en una operacion
    pesada y romperia cualquier prueba que solo quiera construir la aplicacion. Se
    carga la primera vez que se transcribe y se reutiliza en las siguientes.

    **El audio crudo no sale de aqui.** El unico resultado es un `Transcript`. El
    adaptador no guarda el audio, no lo registra y no lo adjunta a nada: entra como
    bytes, se entrega al modelo como flujo en memoria (`io.BytesIO`) y se descarta.
    No se escribe en disco, asi que no queda una copia tirada por ahi.

    **La dependencia es opcional** (`faster-whisper` vive en el extra `voice`). Si no
    esta instalada, `health()` devuelve `False` y `transcribe` lanza
    `STTNotAvailable`; el sistema sigue funcionando por texto, que es el diseno.
    """

    def __init__(
        self,
        modelo: str = "large-v3",
        idioma: str = "es",
        *,
        umbral_confianza: float = 0.75,
        dispositivo: str = "auto",
        tipo_computo: str = "default",
    ) -> None:
        self._modelo = modelo
        self._idioma = idioma
        self._umbral = umbral_confianza
        self._dispositivo = dispositivo
        self._tipo_computo = tipo_computo
        # `None` = todavia no cargado. Se carga en la primera transcripcion.
        self._cargado = None

    # ------------------------------------------------------------------ modelo
    def _modelo_cargado(self):
        """Carga el modelo **una sola vez**, o lanza un error tipado."""
        if self._cargado is not None:
            return self._cargado
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise STTNotAvailable(
                "falta la dependencia 'faster-whisper': instala el extra `voice` "
                "(pip install -e '.[voice]') o trabaja por texto"
            ) from exc
        try:
            self._cargado = WhisperModel(
                self._modelo,
                device=self._dispositivo,
                compute_type=self._tipo_computo,
            )
        except Exception as exc:  # noqa: BLE001 - se degrada a un error tipado
            raise STTError(
                f"no se pudo cargar el modelo '{self._modelo}': {type(exc).__name__}: {exc}"
            ) from exc
        return self._cargado

    # ---------------------------------------------------------------- contrato
    def transcribe(self, audio: bytes, *, vocabulary: list[str] | None = None) -> Transcript:
        """Transcribe audio **en memoria** y devuelve texto con metadatos.

        `vocabulary` se pasa como `initial_prompt`, que **sesga** el decodificador
        hacia esos terminos (nombres de proyecto, jerga del dominio). Es una pista,
        no una restriccion: el modelo puede producir palabras fuera de la lista.
        """
        if not audio:
            raise STTError("el audio esta vacio: no hay nada que transcribir")

        modelo = self._modelo_cargado()
        pista = ", ".join(vocabulary) if vocabulary else None

        try:
            segmentos, info = modelo.transcribe(
                io.BytesIO(audio),
                language=self._idioma or None,
                initial_prompt=pista,
                vad_filter=True,
            )
            # El generador es **perezoso**: el trabajo ocurre al consumirlo, asi que
            # un fallo del modelo aparece aqui y no en la llamada de arriba. Hay que
            # consumirlo dentro del `try`.
            recogidos = list(segmentos)
        except STTError:
            raise
        except Exception as exc:  # noqa: BLE001 - se degrada a un error tipado
            raise STTError(
                f"faster-whisper fallo al transcribir: {type(exc).__name__}: {exc}"
            ) from exc

        texto = " ".join(s.text.strip() for s in recogidos if s.text.strip()).strip()
        if not texto:
            # `Transcript.text` exige longitud >= 1: un audio sin voz no es una
            # transcripcion valida, es un resultado que hay que declarar como fallo.
            raise STTError(
                "la transcripcion quedo vacia: el audio no contiene voz reconocible"
            )

        confianza = _confianza_de(recogidos)
        idioma = getattr(info, "language", None) or self._idioma or "und"
        duracion = float(getattr(info, "duration", 0.0) or 0.0)

        return Transcript(
            text=texto,
            language=idioma,
            confidence=confianza,
            duration_s=duracion,
            provider=f"faster-whisper:{self._modelo}",
            segments=[
                Segment(start_s=float(s.start), end_s=float(s.end), text=s.text)
                for s in recogidos[:2000]
            ],
            low_confidence=confianza < self._umbral,
        )

    def health(self) -> bool:
        """Si la dependencia esta disponible. **No carga el modelo.**

        Cargarlo para responder a `/health` convertiria una sonda barata en una
        descarga de cientos de megabytes. Se comprueba que el paquete se puede
        importar, que es lo que `transcribe` necesita para intentarlo.
        """
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return False
        return True


def crear_adaptador_stt(settings=None) -> STTAdapter:
    """Selecciona el adaptador segun la configuracion. **Sin fallback silencioso.**

    Un proveedor desconocido **falla** en vez de caer a otro adaptador: si alguien
    escribe `AI_SWE_STT_PROVIDER=wspher`, un fallback silencioso le daria
    transcripciones de otro motor sin decirlo, y el error apareceria lejos de su
    causa.

    `settings` se inyecta para poder probar la seleccion sin tocar el entorno. Sin
    argumento se leen los ajustes reales.
    """
    if settings is None:
        from ai_swe.config import Settings

        settings = Settings()

    proveedor = (getattr(settings, "stt_provider", "") or "").strip().lower()
    if proveedor in {"fake", "deterministic"}:
        return FakeAdapter()
    if proveedor in {"faster-whisper", "faster_whisper", "local"}:
        from ai_swe.config import Settings

        return FasterWhisperAdapter(
            modelo=settings.stt_model,
            idioma=settings.stt_language,
            umbral_confianza=settings.stt_confidence_warn_threshold,
            dispositivo=getattr(
                settings, "stt_device", Settings.model_fields["stt_device"].default
            ),
            tipo_computo=getattr(
                settings, "stt_compute_type", Settings.model_fields["stt_compute_type"].default
            ),
        )
    raise STTError(
        f"proveedor de STT desconocido: {proveedor!r}; se esperaba 'faster-whisper' o 'fake'"
    )
