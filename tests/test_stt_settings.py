"""Configuracion efectiva de dispositivo, sin descargas ni hardware requerido."""

import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ai_swe.config import Settings
from ai_swe.stt import STTError, crear_adaptador_stt


def test_windows_defaults_are_cpu_int8():
    settings = Settings(_env_file=None)
    if sys.platform == "win32":
        assert (settings.stt_device, settings.stt_compute_type) == ("cpu", "int8")


@pytest.mark.parametrize("device,compute", [("cpu", "int8"), ("cuda", "float16")])
def test_factory_forwards_explicit_device_and_compute(monkeypatch, device, compute):
    calls = []

    def model(name, **kwargs):
        calls.append((name, kwargs))
        raise RuntimeError("hardware unavailable")

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=model))
    settings = Settings(
        _env_file=None, stt_model="small", stt_device=device, stt_compute_type=compute
    )
    adapter = crear_adaptador_stt(settings)
    assert calls == [], "la factoria debe mantener la carga perezosa"
    with pytest.raises(STTError, match="hardware unavailable"):
        adapter.transcribe(b"audio")
    assert calls == [("small", {"device": device, "compute_type": compute})]


def test_environment_can_select_cpu_int8(monkeypatch):
    monkeypatch.setenv("AI_SWE_STT_DEVICE", "cpu")
    monkeypatch.setenv("AI_SWE_STT_COMPUTE_TYPE", "int8")
    settings = Settings(_env_file=None)
    assert (settings.stt_device, settings.stt_compute_type) == ("cpu", "int8")


@pytest.mark.parametrize("field,value", [("stt_device", "gpu"), ("stt_compute_type", "typo")])
def test_invalid_hardware_configuration_is_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
