"""Pruebas de F13: transcripcion local con `FasterWhisperAdapter`.

**Que protege este fichero.** El adaptador de STT es la frontera por la que entra la
voz, y de ella dependen dos promesas:

  1. **El audio crudo no sale del adaptador.** Lo unico que devuelve es un
     `Transcript` -texto y metadatos-. Si el audio pudiera viajar mas alla, el
     Supervisor o el modelo lo recibirian, y `RF-03` dejaria de cumplirse.
  2. **Una transcripcion fallida se declara, no se inventa.** Un audio sin voz, un
     motor que revienta o una dependencia que falta producen un error **tipado**;
     nunca un texto de relleno, que seria fabricar la peticion del usuario.

Ademas se comprueba que la dependencia es opcional (su ausencia se declara), que el
audio se entrega al motor **en memoria** (no como fichero temporal) y que la
seleccion por configuracion no tiene fallback silencioso.

**Sin descargas.** `faster_whisper` se sustituye por un doble inyectado en
`sys.modules`: la suite normal no baja ningun modelo. La transcripcion real es
opt-in (`@pytest.mark.real_stt`), con el mismo criterio que `real_provider`.
"""

from __future__ import annotations

import io
import os
import sys
import types
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_swe.api import crear_app
from ai_swe.state import RunStore
from ai_swe.stt import (
    FakeAdapter,
    FasterWhisperAdapter,
    STTAdapter,
    STTError,
    STTNotAvailable,
    crear_adaptador_stt,
)

AUDIO = b"RIFF....WAVEfmt " + bytes(range(64))


# --------------------------------------------------------------- dobles del motor


class _SegmentoFalso:
    """Un segmento como el que devuelve `faster-whisper`."""

    def __init__(self, start: float, end: float, text: str, avg_logprob: float = -0.2) -> None:
        self.start = start
        self.end = end
        self.text = text
        self.avg_logprob = avg_logprob


class _InfoFalsa:
    def __init__(self, language: str = "es", duration: float = 3.5) -> None:
        self.language = language
        self.duration = duration


def _instalar_doble(
    monkeypatch: pytest.MonkeyPatch,
    *,
    segmentos: list | None = None,
    info: _InfoFalsa | None = None,
    falla: BaseException | None = None,
) -> dict:
    """Sustituye `faster_whisper` por un doble y devuelve el registro de llamadas.

    El doble imita la forma real de la API: `WhisperModel(nombre, device=...,
    compute_type=...)` y `modelo.transcribe(...) -> (generador_de_segmentos, info)`.
    Que el generador sea **perezoso** importa: es lo que hace que un fallo del motor
    aparezca al consumirlo y no en la llamada.
    """
    registro: dict = {"construcciones": [], "transcribe": None}

    class WhisperModel:  # noqa: N801 - imita el nombre real del paquete
        def __init__(self, nombre: str, device: str | None = None, compute_type: str | None = None):
            registro["construcciones"].append(
                {"nombre": nombre, "device": device, "compute_type": compute_type}
            )

        def transcribe(self, audio, language=None, initial_prompt=None, vad_filter=False):
            registro["transcribe"] = {
                "audio": audio,
                "language": language,
                "initial_prompt": initial_prompt,
                "vad_filter": vad_filter,
            }
            if falla is not None:
                raise falla
            recogidos = segmentos if segmentos is not None else [_SegmentoFalso(0.0, 1.5, " corrige el error ")]
            return iter(recogidos), (info or _InfoFalsa())

    modulo = types.ModuleType("faster_whisper")
    modulo.WhisperModel = WhisperModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", modulo)
    return registro


def _sin_dependencia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simula que `faster-whisper` no esta instalado.

    Poner `None` en `sys.modules` hace que `import faster_whisper` lance
    `ImportError`, que es exactamente lo que pasa cuando falta el extra `voice`.
    """
    monkeypatch.setitem(sys.modules, "faster_whisper", None)


class _AjustesFalsos:
    """Ajustes minimos para probar la seleccion sin tocar el entorno."""

    def __init__(self, provider: str, *, modelo: str = "large-v3", idioma: str = "es", umbral: float = 0.75):
        self.stt_provider = provider
        self.stt_model = modelo
        self.stt_language = idioma
        self.stt_confidence_warn_threshold = umbral


# =============================================== 1. contrato y forma del resultado


def test_el_adaptador_cumple_el_contrato() -> None:
    """`STTAdapter` es `runtime_checkable`: la conformidad se comprueba de verdad."""
    assert isinstance(FasterWhisperAdapter(), STTAdapter)
    assert isinstance(FakeAdapter(), STTAdapter)


def test_transcribe_devuelve_texto_con_metadatos(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar_doble(monkeypatch, info=_InfoFalsa(language="es", duration=3.5))
    resultado = FasterWhisperAdapter(modelo="small").transcribe(AUDIO)

    assert resultado.text == "corrige el error"
    assert resultado.language == "es"
    assert resultado.duration_s == 3.5
    assert resultado.provider == "faster-whisper:small"
    assert resultado.segments
    assert resultado.segments[0].start_s == 0.0
    assert resultado.segments[0].end_s == 1.5


def test_el_idioma_del_motor_manda_sobre_el_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    """El motor detecta el idioma; solo si no lo dice se usa el configurado."""
    _instalar_doble(monkeypatch, info=_InfoFalsa(language="en"))
    resultado = FasterWhisperAdapter(idioma="es").transcribe(AUDIO)
    assert resultado.language == "en"


def test_sin_idioma_detectado_se_usa_el_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar_doble(monkeypatch, info=_InfoFalsa(language=""))
    resultado = FasterWhisperAdapter(idioma="es").transcribe(AUDIO)
    assert resultado.language == "es"


# =============================================== 2. el audio crudo no sale de aqui


def test_el_resultado_no_contiene_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lo que sale es texto y numeros: ni bytes, ni referencias al audio."""
    _instalar_doble(monkeypatch)
    adaptador = FasterWhisperAdapter()
    resultado = adaptador.transcribe(AUDIO)

    def _hay_bytes(valor) -> bool:
        if isinstance(valor, (bytes, bytearray, memoryview)):
            return True
        if isinstance(valor, dict):
            return any(_hay_bytes(v) for v in valor.values())
        if isinstance(valor, (list, tuple)):
            return any(_hay_bytes(v) for v in valor)
        return False

    assert not _hay_bytes(resultado.model_dump()), "el Transcript transporta bytes de audio"

    # Y el adaptador **no se queda con el audio**: tras transcribir, no hay ningun
    # atributo del objeto que lo retenga. Si lo retuviera, sobreviviria a la
    # peticion y podria acabar en un registro o en el estado.
    assert not _hay_bytes(vars(adaptador)), "el adaptador retuvo el audio tras transcribir"


def test_el_audio_se_entrega_al_motor_en_memoria(monkeypatch: pytest.MonkeyPatch) -> None:
    """El motor recibe un flujo en memoria, **no** una ruta a un fichero temporal.

    Escribir el audio en disco dejaria una copia del audio del usuario tirada por
    ahi; entregarlo como `BytesIO` la evita.
    """
    registro = _instalar_doble(monkeypatch)
    FasterWhisperAdapter().transcribe(AUDIO)

    entregado = registro["transcribe"]["audio"]
    assert isinstance(entregado, io.BytesIO), f"se entrego {type(entregado).__name__}, no un flujo"
    assert entregado.getvalue() == AUDIO
    assert registro["transcribe"]["vad_filter"] is True


# =============================================== 3. vocabulario (pista, no filtro)


def test_el_vocabulario_se_pasa_como_pista(monkeypatch: pytest.MonkeyPatch) -> None:
    registro = _instalar_doble(monkeypatch)
    FasterWhisperAdapter().transcribe(AUDIO, vocabulary=["WhisperModel", "AI SWE"])
    assert registro["transcribe"]["initial_prompt"] == "WhisperModel, AI SWE"


def test_sin_vocabulario_no_se_pasa_pista(monkeypatch: pytest.MonkeyPatch) -> None:
    registro = _instalar_doble(monkeypatch)
    FasterWhisperAdapter().transcribe(AUDIO)
    assert registro["transcribe"]["initial_prompt"] is None


# =============================================== 4. la confianza y el aviso


def test_una_confianza_alta_no_marca_aviso(monkeypatch: pytest.MonkeyPatch) -> None:
    # `avg_logprob = 0.0` -> `exp(0) = 1.0`: confianza maxima.
    _instalar_doble(monkeypatch, segmentos=[_SegmentoFalso(0.0, 1.0, "hola", avg_logprob=0.0)])
    resultado = FasterWhisperAdapter(umbral_confianza=0.75).transcribe(AUDIO)
    assert resultado.confidence == pytest.approx(1.0)
    assert resultado.low_confidence is False


def test_una_confianza_baja_marca_aviso(monkeypatch: pytest.MonkeyPatch) -> None:
    # `exp(-5) ~ 0.0067`: muy por debajo del umbral.
    _instalar_doble(monkeypatch, segmentos=[_SegmentoFalso(0.0, 1.0, "xxx", avg_logprob=-5.0)])
    resultado = FasterWhisperAdapter(umbral_confianza=0.75).transcribe(AUDIO)
    assert resultado.confidence < 0.75
    assert resultado.low_confidence is True


# =============================================== 5. errores declarados


def test_el_audio_vacio_es_un_error_y_no_carga_el_modelo(monkeypatch: pytest.MonkeyPatch) -> None:
    registro = _instalar_doble(monkeypatch)
    with pytest.raises(STTError):
        FasterWhisperAdapter().transcribe(b"")
    assert registro["construcciones"] == [], "se cargo el modelo para un audio vacio"


def test_una_transcripcion_vacia_es_un_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un audio sin voz no es un `Transcript` vacio valido: es un fallo que se declara."""
    _instalar_doble(monkeypatch, segmentos=[_SegmentoFalso(0.0, 1.0, "   ", avg_logprob=-1.0)])
    with pytest.raises(STTError):
        FasterWhisperAdapter().transcribe(AUDIO)


def test_un_fallo_del_motor_se_convierte_en_error_tipado(monkeypatch: pytest.MonkeyPatch) -> None:
    """El motor puede fallar al consumir el generador; eso no puede escapar crudo."""
    _instalar_doble(monkeypatch, falla=RuntimeError("el backend de audio exploto"))
    with pytest.raises(STTError) as excinfo:
        FasterWhisperAdapter().transcribe(AUDIO)
    assert "exploto" in str(excinfo.value)
    assert not isinstance(excinfo.value, STTNotAvailable)


def test_sin_la_dependencia_se_declara_no_disponible(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falta el extra `voice`: se dice, no se disfraza."""
    _sin_dependencia(monkeypatch)
    adaptador = FasterWhisperAdapter()
    assert adaptador.health() is False
    with pytest.raises(STTNotAvailable):
        adaptador.transcribe(AUDIO)


def test_health_no_carga_el_modelo(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/health` no puede convertirse en una descarga de cientos de MB."""
    registro = _instalar_doble(monkeypatch)
    assert FasterWhisperAdapter().health() is True
    assert registro["construcciones"] == []


# =============================================== 6. carga perezosa y reutilizacion


def test_el_modelo_se_carga_una_sola_vez(monkeypatch: pytest.MonkeyPatch) -> None:
    registro = _instalar_doble(monkeypatch)
    adaptador = FasterWhisperAdapter(modelo="base")
    adaptador.transcribe(AUDIO)
    adaptador.transcribe(AUDIO)
    assert len(registro["construcciones"]) == 1, "el modelo se cargo mas de una vez"
    assert registro["construcciones"][0]["nombre"] == "base"


def test_construir_el_adaptador_no_carga_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Construir la aplicacion no puede pagar el coste del modelo."""
    registro = _instalar_doble(monkeypatch)
    FasterWhisperAdapter()
    assert registro["construcciones"] == []


# =============================================== 7. seleccion por configuracion


def test_la_configuracion_elige_el_adaptador() -> None:
    assert isinstance(crear_adaptador_stt(_AjustesFalsos("fake")), FakeAdapter)
    assert isinstance(crear_adaptador_stt(_AjustesFalsos("faster-whisper")), FasterWhisperAdapter)


def test_la_configuracion_llega_al_adaptador(monkeypatch: pytest.MonkeyPatch) -> None:
    registro = _instalar_doble(monkeypatch)
    adaptador = crear_adaptador_stt(
        _AjustesFalsos("faster-whisper", modelo="tiny", idioma="en", umbral=0.5)
    )
    assert isinstance(adaptador, FasterWhisperAdapter)
    resultado = adaptador.transcribe(AUDIO)
    assert registro["construcciones"][0]["nombre"] == "tiny"
    assert resultado.provider == "faster-whisper:tiny"


def test_un_proveedor_desconocido_no_cae_a_otro_adaptador() -> None:
    """Sin fallback silencioso: un proveedor mal escrito falla y lo dice."""
    with pytest.raises(STTError) as excinfo:
        crear_adaptador_stt(_AjustesFalsos("wspher"))
    assert "wspher" in str(excinfo.value)


# =============================================== 8. la frontera HTTP


def _cliente(tmp_path: Path, adaptador) -> TestClient:
    store = RunStore(tmp_path / "estado.db")
    app = crear_app(store=store, stt=adaptador)
    return TestClient(app)


def test_la_api_mapea_la_dependencia_ausente_a_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """503 y no 500: es una capacidad no instalada, no un defecto del servidor."""
    _sin_dependencia(monkeypatch)
    with _cliente(tmp_path, FasterWhisperAdapter()) as cliente:
        r = cliente.post("/transcriptions", files={"audio": ("a.webm", AUDIO, "audio/webm")})
    assert r.status_code == 503
    assert r.json()["error_class"] == "STT_NOT_AVAILABLE"


def test_la_api_mapea_un_fallo_de_transcripcion_a_422(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar_doble(monkeypatch, segmentos=[_SegmentoFalso(0.0, 1.0, "  ")])
    with _cliente(tmp_path, FasterWhisperAdapter()) as cliente:
        r = cliente.post("/transcriptions", files={"audio": ("a.webm", AUDIO, "audio/webm")})
    assert r.status_code == 422
    assert r.json()["error_class"] == "STT_ERROR"


def test_la_api_sigue_transcribiendo_con_el_adaptador_determinista(tmp_path: Path) -> None:
    """El sistema funciona sin STT real: el adaptador se inyecta por parametro."""
    with _cliente(tmp_path, FakeAdapter(texto="corrige el error de parseo")) as cliente:
        r = cliente.post("/transcriptions", files={"audio": ("a.webm", AUDIO, "audio/webm")})
    assert r.status_code == 200
    assert r.json()["text"] == "corrige el error de parseo"


# =============================================== 9. transcripcion real (opt-in)


def _wav_silencio(segundos: float = 1.0, frecuencia: int = 16_000) -> bytes:
    """WAV mono de silencio, en memoria. Sirve para ejercitar el camino real."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as salida:
        salida.setnchannels(1)
        salida.setsampwidth(2)
        salida.setframerate(frecuencia)
        salida.writeframes(b"\x00\x00" * int(frecuencia * segundos))
    return buffer.getvalue()


@pytest.mark.real_stt
def test_transcripcion_real_opt_in() -> None:
    """Ejercita `faster-whisper` de verdad. **No** corre en la suite normal.

    Requiere el extra `voice` y descarga un modelo (por defecto `tiny`, para que la
    prueba sea viable). Un WAV de silencio debe llegar al modelo y salir por el
    camino declarado -transcripcion vacia-, que demuestra que el cableado real
    funciona sin afirmar nada sobre el contenido.
    """
    if os.environ.get("AI_SWE_RUN_REAL_STT_TESTS") != "1":
        pytest.skip("opt-in: define AI_SWE_RUN_REAL_STT_TESTS=1 (descarga un modelo)")
    pytest.importorskip("faster_whisper")

    modelo = os.environ.get("AI_SWE_STT_TEST_MODEL", "tiny")
    adaptador = FasterWhisperAdapter(modelo=modelo, idioma="es")
    assert adaptador.health() is True

    with pytest.raises(STTError):
        adaptador.transcribe(_wav_silencio(segundos=1.0))
