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

## Límites y pendientes

- CUDA float16 sigue fallando; no se considera validado.
- El audio está en inglés: español y micrófono siguen pendientes.
- No se cambió la selección automática del dispositivo ni se añadió fallback silencioso.
- La factoría de aplicación aún no permite seleccionar CPU/int8 mediante Settings.
- La prueba de archivo no cierra la fase de voz ni acredita producción.

Evidencia local ignorada: `_tmp/voice-assets/real-stt-report.json` y
`_tmp/voice-assets/small/manifest.json` en el repositorio principal.
El entorno aislado contiene la dependencia corregida; el entorno principal
debe sincronizarse con el nuevo lockfile antes de repetir la prueba.
