# Matriz de revisión — candidato v0.1.0

Fecha: 27 de octubre de 2026. Estado: **preparado para revisión, no etiquetado**.
El tag `v0.1.0` no existe. No se solicita ni ejecuta push.

Distribución vigente: `dist/windows-signed-python-rc2/`, CPython oficial firmado
con app/frontend externos. Se resolvió el bloqueo del launcher generado mediante
el cambio de arquitectura, sin modificar SAC. 19 controles de smoke, 21 de E2E
portable y 14 de navegador del paquete aprobados. SAC=1 y sin bloqueos coincidentes.
Evidencia vigente: `SAC-DISTRIBUTION-EVIDENCE.json` y `PACKAGING-REPORT.md`.
`ANTIGRAVITY-EVIDENCE.json` conserva el fallo real del EXE PyInstaller anterior.

Antecedente histórico: `dist/windows-premium-rc1/`, `UI-PREMIUM-EVIDENCE.json`
y `FINAL-RELEASE-EVIDENCE-v0.1.0.json` conservan los controles anteriores a la
distribución SAC. No son los hashes ni los resultados del portable vigente.

## Controles y alcance de la evidencia

| Control | Resultado | Evidencia / límite |
| --- | --- | --- |
| Suite Python actual | PASS: 791; SKIP: 3; FAIL: 0 | `_tmp/signed-python-regression.xml`, 264.18 s; 21 pruebas focalizadas finales también PASS |
| Coherencia de versión | PASS | Python/pyproject, API/OpenAPI, frontend/lock e instalador 0.1.0; regresión nueva |
| Frontend TypeScript/build | PASS | Build nuevo del candidato, sin assets de diagnóstico viejos |
| Estado frontend | PASS: 24 pruebas | `frontend/tests/estados.test.mjs` |
| Navegador | PASS: 134 fuente; 14 paquete | Fuente Antigravity local/auth; paquete firmado con interfaz integrada, sin falsificar llamadas |
| Modelo real en motor | PASS histórico | E: Qwen2.5-Coder-32B-Instruct:nscale; aprobar/rechazar/cambios, `HYBRID-E2E-EVIDENCE.json` |
| Modelo de pago en instalador final | NO EJECUTADO | No se presenta el fixture local como modelo real; sin gastos nuevos |
| Voz española dentro del paquete final | PASS | small externo, CPU/int8, audio sintético local; `signed-python-rc2-smoke` |
| Micrófono físico y edición/confirmación | PASS reportado por usuario en F | `REAL-STT-EVIDENCE.json`; no se repitió captura física en esta sesión |
| Runtime final con PATH reducido | PASS: 19 controles | CPython firmado, installed/frozen=false, API/UI, persistencia, auth, voz y workers |
| Paquete portable final | PASS: 21 controles | Destino/perfil temporal, promoción real, reinicio y retirada; no crea accesos ni registro |
| Preservación al retirar portable | PASS | Todos los archivos de datos idénticos byte por byte; instalador Inno anterior queda histórico |
| Integridad de artefactos | PASS | SHA256SUMS.txt y hashes en evidencia; ZIP completo junto al instalador |
| Controles nuevos sobre paquete firmado | PASS: 14 | `signed-python-rc2-browser`; Antigravity, micrófono/audio, estados, materiales y movimiento reducido |
| Ruff focalizado / diff | PASS | Archivos nuevos/modificados relevantes; no se declara lint global limpio |
| VM independiente / Windows limpio | NO EJECUTADO | Windows Sandbox no disponible; mismo host con destinos/PATH aislados |
| Firma y política en este host | PASS con límites | CPython PSF Valid; SAC activo. App/ZIP no firmados; no todos los binarios de ruedas tienen Authenticode |
| SmartScreen/equipo ajeno | NO VALIDADO | No equivale a aceptación universal ni a firma propia del producto |
| Tag final y publicación | PENDIENTE | Revisión/aprobación del usuario; no se creó tag ni se hizo push |

## Omisiones de la suite, sin convertirlas a PASS

1. `test_transcripcion_real_opt_in`: opt-in no activado. La voz real española del
   EXE final se ejecutó por el arnés separado y tiene evidencia propia.
2. `test_llamada_real_controlada`: opt-in remoto no activado. Se reutiliza el acta
   E y se distingue de la prueba local determinista del instalador final.
3. `test_la_plataforma_no_permite_construir_el_vector_de_enlace`: este Windows
   negó crear el enlace (WinError 1314). No se habilitaron privilegios para falsear
   la cobertura; ese vector no se declara ejercitado en esta máquina.

## Decisión de release

Las comprobaciones funcionales ejecutadas sobre el candidato pasan. I cierra para
el alcance aislado solicitado en este host; no sustituye la VM independiente.
J queda preparada con instalación, producto, limitaciones, artefactos y matriz.
Una matriz sin VM real no se denomina una matriz completa en equipo limpio.

Antes del tag se debe revisar/aceptar el alcance local y las omisiones anteriores,
o completar las verificaciones externas que se exijan. No hay aprobación implícita
ni automatismo que convierta este documento en autorización de etiqueta.
El producto no se declara listo para exposición pública o producción multiusuario.

Los cambios académicos pendientes en el checkout principal se preservan y quedan
fuera del commit del candidato. La entrega portable/instalador no incluye esos
documentos ni archivos de credenciales. Consultar `PRODUCTIZATION-PROGRESS.md`
para commits y contexto; `RELEASE-EVIDENCE-v0.1.0.json` vincula cada capa de evidencia.

La entrega premium posterior se consolida en `FINAL-RELEASE-EVIDENCE-v0.1.0.json`.
La guía `CLEAN-WINDOWS-VALIDATION.md` deja preparada la validación externa pendiente,
sin convertirla en PASS ni alterar el gate de aprobación del tag.
