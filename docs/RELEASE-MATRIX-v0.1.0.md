# Matriz de revisión — candidato v0.1.0

Fecha: 27 de octubre de 2026. Estado: **preparado para revisión, no etiquetado**.
El tag `v0.1.0` no existe. No se solicita ni ejecuta push.

Revisión visual posterior: el candidato actualizado está en
`dist/windows-premium-rc1/`. Consultar `UI-PREMIUM-VALIDATION.md` y
`UI-PREMIUM-EVIDENCE.json` para sus verificaciones y hashes. La suite completa
se volvió a ejecutar sobre `4accb8e`: 785 PASS, 3 SKIP, 0 FAIL en 214.96 s.
El consolidado vigente es `FINAL-RELEASE-EVIDENCE-v0.1.0.json`.

## Controles y alcance de la evidencia

| Control | Resultado | Evidencia / límite |
| --- | --- | --- |
| Suite Python actual | PASS: 785; SKIP: 3; FAIL: 0 | Commit 4accb8e; `_tmp/release-premium-final-suite.xml`, 214.96 s |
| Coherencia de versión | PASS | Python/pyproject, API/OpenAPI, frontend/lock e instalador 0.1.0; regresión nueva |
| Frontend TypeScript/build | PASS | Build nuevo del candidato, sin assets de diagnóstico viejos |
| Estado frontend | PASS: 24 pruebas | `frontend/tests/estados.test.mjs` |
| Navegador actual | PASS: 114 controles | Chromium, fuente final/API real; modos local/auth, voz simulada, puertas y pantallas |
| Modelo real en motor | PASS histórico | E: Qwen2.5-Coder-32B-Instruct:nscale; aprobar/rechazar/cambios, `HYBRID-E2E-EVIDENCE.json` |
| Modelo de pago en instalador final | NO EJECUTADO | No se presenta el fixture local como modelo real; sin gastos nuevos |
| Voz española dentro del EXE final | PASS | small externo, CPU/int8, audio sintético local; `ui-premium-packaged-01` |
| Micrófono físico y edición/confirmación | PASS reportado por usuario en F | `REAL-STT-EVIDENCE.json`; no se repitió captura física en esta sesión |
| EXE final con PATH reducido | PASS: 19 controles | Native frozen/installed, API/UI, persistencia, auth, voz y trabajadores pytest/Ruff |
| Instalador final sin elevación | PASS: 23 controles | Destino/perfil temporal, accesos, API, promoción real, reinicio y desinstalación |
| Preservación al desinstalar | PASS | Comparación byte por byte de todos los archivos de datos de prueba |
| Integridad de artefactos | PASS | SHA256SUMS.txt y hashes en evidencia; ZIP completo junto al instalador |
| Controles nuevos en navegador sobre EXE | PASS: 13 | `ui-premium-frozen-browser-04`; micrófono/audio, estados, materiales y movimiento reducido |
| Ruff focalizado / diff | PASS | Archivos nuevos/modificados relevantes; no se declara lint global limpio |
| VM independiente / Windows limpio | NO EJECUTADO | Windows Sandbox no disponible; mismo host con destinos/PATH aislados |
| Firma/SmartScreen/equipo ajeno | NO VALIDADO | Producto sin firma; no se asimila la firma del compilador a la del instalador |
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
