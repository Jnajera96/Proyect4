# Validación de voz local — 2026-10-26

## Resultado comprobado

Transcripción real por CPU con faster-whisper 1.2.1, CTranslate2 4.8.2,
PyAV 18.1.0 y cómputo int8. Modelo local Systran/faster-whisper-small,
revisión `536b0662742c02347bc0e980a01041f333bce120`.

Audio público de 11 segundos: https://raw.githubusercontent.com/openai/whisper/main/tests/jfk.flac

Texto reconocido: “And so my fellow Americans, ask not what your country can do
for you, ask what you can do for your country.” Tiempo observado: 15.785 segundos.
La confianza heurística fue 0.818; no es una probabilidad calibrada.
No se hicieron llamadas de inferencia de pago.

## Defecto reproducido y corrección

Con PyAV 19.0.1, tanto CPU como CUDA fallaban antes de reconocer audio:
`TypeError: open() got an unexpected keyword argument 'metadata_errors'`.
faster-whisper usa ese argumento, eliminado en PyAV 19:
https://pyav.basswood.io/docs/stable/development/changelog.html

El extra opcional `voice` ahora limita `av<19`; el lockfile resuelve 18.1.0.
Tras sincronizar el entorno aislado, la misma transcripción CPU pasó.
`tests/test_f13_stt.py`: 23 pruebas aprobadas y una omitida (real optativa).

## Continuación: configuración, español y UI

El entorno principal se sincronizó con `uv sync --locked --inexact --extra dev
--extra voice`: PyAV 18.1.0, sin modificar el lockfile ni eliminar extras existentes.

`Settings.stt_device` y `Settings.stt_compute_type` se transmiten al constructor
perezoso del modelo mediante la factoría. Windows usa `cpu` / `int8` por defecto;
otras plataformas conservan `auto` / `default`. También se pueden seleccionar con
`AI_SWE_STT_DEVICE` y `AI_SWE_STT_COMPUTE_TYPE`, documentados en `.env.example`.
Valores desconocidos se rechazan al cargar Settings. CUDA explícito no se sustituye
por CPU: conserva el error tipado. En este equipo falta `cublas64_12.dll`.
El modelo predeterminado general no se cambió; estas pruebas usan small local
explícitamente, sin descargar large-v3.

### Español real, CPU/int8

Se generó exclusivamente una muestra sintética de validación con Windows SAPI,
voz Microsoft Sabina (es-MX). No se añadió TTS al producto ni se usó un servicio
remoto. WAV de 385378 bytes, duración 8.7376875 s, SHA256
`34270c7184e56e26a82f379df7762838030b7014efcbe47f991d435240eac71c`.

Texto esperado y reconocido completo:
«Analiza el proyecto y muestra un resumen. No modifiques archivos. Quiero revisar
el texto antes de ejecutar.» La factoría real con small y CPU/int8 tardó 5.122 s;
idioma es, confianza heurística 0.8471. Esto acredita reconocimiento de esta
muestra, no una evaluación general de acentos o ruido.

### Navegador y confirmación

`tools/verify_real_voice.cjs` ejecutó Chromium instalado, frontend construido,
FastAPI, SQLite y adaptador STT real, usando exclusivamente un repositorio
descartable. El dispositivo de captura del navegador se alimentó con el WAV
español: `getUserMedia` → `MediaRecorder` → multipart `/transcriptions` → UI.
También se comprobó la selección de archivo. El dispositivo era sintético;
no demuestra funcionamiento del micrófono físico.

- Ambos caminos devolvieron transcripción española real editable.
- Vaciar el texto deshabilitó «Usar como instrucción».
- Transcribir y confirmar el texto produjeron cero POST `/runs` y cero ejecuciones.
- Solo pulsar «Ejecutar» creó una ejecución (HTTP 202), con texto corregido,
  `source=voice`, metadatos y `confirmed_by_user=true`.
- La ejecución quedó en `awaiting_human_requirements_confirmation`.
- El repositorio descartable siguió limpio. No hubo errores de ejecución JS.
- Sin inferencia remota de pago. La UI no necesitó cambios.

Repetición opt-in: `node tools/verify_real_voice.cjs <modelo-local> <audio-es.wav>
<directorio-nuevo-evidencia>`. Requiere Playwright existente y frontend construido.
`AI_SWE_BROWSER_EXECUTABLE` permite elegir el Chromium ya instalado.
El verificador usa la factoría real configurada por entorno, sin inyectar FakeAdapter.
Los intentos de preparación 01–05 detectaron navegador ausente, recursos de build
ausentes durante pruebas y supuestos de navegación del arnés. Se corrigió el arnés;
no se cambiaron aserciones de seguridad ni el frontend. La corrida final 06 pasó.

### Verificación y estado de F

Seis pruebas nuevas verifican defaults Windows, variables de entorno, paso de
cpu/int8 y cuda/float16 al motor, carga perezosa, fallo sin fallback y rechazo de
valores inválidos. Suite completa: **751 PASS, 3 SKIP, 0 FAIL**, 183.107 s.
Frontend: TypeScript y build aprobados. Ruff focalizado aprobado; el E501 histórico
de `FakeAdapter.__init__` no se modificó.

**Fase F cerrada para Windows, small local y CPU/int8.** La validación automatizada
se completa con la prueba física y confirmación humana descritas a continuación.
CUDA es opcional y sigue no disponible; no bloquea el perfil CPU validado.

### Comprobación física reportada por el usuario

El usuario probó el dictado en la sesión local y confirmó: «fue tal cual lo que
dicte». Esto acredita reconocimiento fiel según validación humana; no se conservó
su audio como evidencia ni se inventó una medición de exactitud o latencia.

Al revisar la sesión se encontraron tres ejecuciones de origen `text`, todas en
`awaiting_human_requirements_confirmation`, sin metadatos de voz. El usuario aclaró:
«Sí, pulsé Ejecutar; el dictado no lanzó nada solo», en respuesta a la comprobación
de lanzamiento manual y revisión/edición del texto. Las tres ejecuciones se
registran como acciones manuales según su confirmación, no como creación automática
del dictado. No se afirma cero ejecuciones en esa sesión. La procedencia `voice`
del camino de confirmación del dictado quedó comprobada en el E2E automatizado.

El cierre combina evidencia automatizada (captura simulada, archivo, edición,
confirmación, procedencia y puerta de requisitos) con evidencia humana (micrófono
físico, fidelidad del reconocimiento y ausencia de lanzamiento automático).
No equivale a validar CUDA, todos los acentos/entornos acústicos ni producción.

Evidencia consolidada versionada: `REAL-STT-EVIDENCE.json`.
Evidencia local ignorada: `_tmp/voice-assets/spanish-stt-report.json`,
`_tmp/voice-assets/small/manifest.json`, `_tmp/phase-f-browser-06/report.json`,
`_tmp/phase-f-browser-06/editable-transcript.png` en el checkout principal;
suite en `_tmp/phase-f-suite.xml` del worktree de validación.
