# 11 — Auditoría de Speech-to-Text

> `src/ai_swe/stt/base.py` (284 líneas) + `POST /transcriptions`. Commit `065db452`.

## 1. Componentes

| Componente | Estado | Evidencia |
|---|---|---|
| `STTAdapter` (Protocol `runtime_checkable`) | IMPLEMENTED_AND_VERIFIED | `stt/base.py` |
| `Transcript` / `Segment` (contratos) | IMPLEMENTED_AND_VERIFIED | Pydantic con `text` obligatorio (`min_length=1`) |
| `STTError` / `STTNotAvailable` | IMPLEMENTED_AND_VERIFIED | Dos tipos: avería vs capacidad no instalada |
| `FakeAdapter` (determinista, sin audio) | IMPLEMENTED_AND_VERIFIED | Sostiene toda la suite |
| `FasterWhisperAdapter` (local, real) | IMPLEMENTED_AND_VERIFIED (F13) | 24 pruebas herméticas + 1 opt-in |
| `crear_adaptador_stt(settings)` | IMPLEMENTED_AND_VERIFIED | Sin fallback silencioso |
| Endpoint `POST /transcriptions` | IMPLEMENTED_AND_VERIFIED | 503 si falta el extra `voice` |
| `MediaRecorder` / UI de voz | **NOT_IMPLEMENTED** | No existe en `frontend/src` |
| TTS | PLANNED | `tts_enabled` declarado, sin implementación |

## 2. La invariante crítica: `RF-03`

> **El audio crudo nunca llega al Supervisor ni al modelo.**

**Verificado en tres capas independientes:**

1. **El adaptador no puede devolverlo.** `transcribe(audio: bytes) -> Transcript`.
   El audio entra como `bytes`, se entrega al motor como `io.BytesIO` y **se
   descarta**. No se escribe en disco, no se registra y no se adjunta a nada.
   `Transcript` contiene texto, idioma, confianza, duración y segmentos — **ni un
   byte de audio**. Probado por `test_el_resultado_no_contiene_audio`, que recorre
   el objeto buscando `bytes`/`bytearray`/`memoryview`.
2. **El contrato lo hace cumplir.** `Instruction` tiene un `model_validator`: si
   `source is VOICE`, exige `transcript_meta` **y** `confirmed_by_user=True`. Una
   instrucción de voz sin confirmación **no se puede construir**.
3. **La API lo mapea a 422.** `POST /runs` captura el `ValidationError` y devuelve
   422 con el detalle. Probado en `tests/test_api.py::test_una_instruccion_de_voz_sin_confirmar_es_rechazada`.

### El flujo de voz

```
audio (navegador)
   │  POST /transcriptions  (multipart)
   ▼
adaptador_stt.transcribe()          ← en run_in_threadpool
   │
   ▼
Transcript {text, language, confidence, duration_s, low_confidence}
   │  ← el audio ya no existe
   ▼
USUARIO CONFIRMA (obligatorio)
   │
   ▼
POST /runs  {instruction: <texto>, source: "voice",
             transcript_meta: {...}, confirmed_by_user: true}
   │  ← el validador rechaza el envío sin confirmación
   ▼
Supervisor (recibe TEXTO)
```

**No existe el camino `voz → ejecución automática`.** Verificado: el único punto de
entrada de una ejecución es `POST /runs`, y ese endpoint valida el contrato.

## 3. Carga perezosa y salud

| Aspecto | Implementación | Por qué |
|---|---|---|
| Carga del modelo | **Perezosa y una sola vez** (`_modelo_cargado` con `self._cargado`) | Cargar `large-v3` cuesta segundos y cientos de MB |
| `health()` | **No carga el modelo**: solo comprueba que `faster_whisper` se puede importar | Una sonda barata no puede convertirse en una descarga |
| `crear_app()` | No carga nada | Construir la app es barato |
| `crear_adaptador_stt` | Sin fallback silencioso: proveedor desconocido ⇒ `STTError` | Un `wspher` mal escrito no debe dar transcripciones de otro motor |

## 4. Audio: ciclo de vida y privacidad

| Aspecto | Situación |
|---|---|
| Persistencia del audio | **Nunca se escribe en disco.** Entra por multipart, vive en memoria, se descarta |
| Persistencia de la transcripción | Sí, como `Instruction.text` de origen `voice` (es el dato de trabajo) |
| Borrado | No aplica al audio (no se guarda). La transcripción sigue el ciclo de vida del `RunState` (que hoy **no se purga**, ver `27-…`) |
| Validación de tipo de fichero | **NO EXISTE**: se acepta cualquier `UploadFile`; no se comprueba extensión ni MIME |
| Límite de tamaño | **NO EXISTE**: `await audio.read()` carga todo en memoria |
| Formato | El adaptador real entrega un `BytesIO` a `faster-whisper`, que decodifica con FFmpeg/av. Un fichero corrupto produce `STTError` (422) |

## 5. Riesgos

| # | Riesgo | Tipo | Severidad |
|---|---|---|---|
| 1 | **Sin límite de tamaño de subida** ⇒ un cliente puede agotar memoria | SECURITY_WEAKNESS (DoS) | **MEDIA** |
| 2 | **Sin validación de tipo/MIME** ⇒ se entrega contenido arbitrario al decodificador de audio | SECURITY_WEAKNESS | MEDIA |
| 3 | Sin UI de voz: la capacidad existe en el backend pero **no es usable** por un humano | FUNCTIONAL_GAP | MEDIA |
| 4 | `AI_SWE_STT_PROVIDER` por defecto = `faster-whisper`; sin el extra `voice`, toda transcripción da 503 | HARDENING_RECOMMENDATION | BAJA |
| 5 | El modelo se descarga de Hugging Face en el primer uso (requiere red; no hay `HF_TOKEN` documentado) | INFRA | BAJA |

## 6. Conclusión

**IMPLEMENTED_AND_VERIFIED.** El adaptador es correcto y la invariante `RF-03` está
protegida en tres capas — contrato, adaptador y API —, lo que la hace difícil de
romper por accidente.

**Lo que falta para que sea usable**: la UI de voz en el frontend, un límite de
tamaño de subida y la validación del tipo de fichero.
