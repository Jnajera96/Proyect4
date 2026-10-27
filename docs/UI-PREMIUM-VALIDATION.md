# Interfaz premium — validación del candidato

Fecha: 27 de octubre de 2026. Baseline: `0f50ae7`, rama `productization/v0.1.0`.
Rediseño visual autorizado expresamente por el usuario después de preparar I/J.

## Resultado

Materiales claros/oscuros, tipografía nativa, cabecera con estado del proveedor,
proyectos y corridas en sidebar, compositor con herramientas de micrófono/audio,
transcripción editable destacada, pipeline, puertas humanas y diffs. Foco visible
y movimiento reducido. Sin dependencias de CDN.

Se conservan selectores, botones críticos y HTTP/SSE. No cambian el backend,
`frontend/contracts.json` ni las 24 pruebas de estado. La onda solo aparece durante
grabación/transcripción. No se inventan duraciones de etapas. «Proveedor preparado»
indica configuración presente; no acredita credencial, saldo ni conectividad.

## Evidencia ejecutada

| Verificación | Resultado | Reporte local |
| --- | --- | --- |
| `npm test` | 24/24 PASS | Pruebas de estado existentes, sin modificaciones |
| `npm run build` | PASS | TypeScript y Vite; CSS `index-BMho5vFC.css`, JS `index-BAgdLqe-.js` |
| Navegador fuente final | 114 PASS | `_tmp/ui-premium-browser-final/1793105774775/report.json` |
| Configuración instalada | 8 PASS | `_tmp/ui-premium-config-01/report.json` |
| Voz española CPU/int8 | 16 PASS | `_tmp/ui-premium-voice-01/report.json` |
| EXE real | 19 PASS | `_tmp/ui-premium-packaged-01/report.json` |
| Instalación/desinstalación | 23 PASS | `_tmp/ui-premium-installer-01/report.json` |
| Navegador sobre EXE real | 13 PASS | `_tmp/ui-premium-frozen-browser-04/report.json` |

El navegador fuente cubre local/auth, gates, SSE, teclado, voz y responsive entre
390 y 1920 px, sin overflow y con contraste AA en los elementos evaluados en ambos
temas. Se inspeccionaron capturas y ajustó el aviso de configuración en móvil.

Voz: MediaRecorder con dispositivo sintético alimentado por WAV español y STT
real small CPU/int8. Se verifica edición, confirmación sin ejecución automática,
ejecución explícita y procedencia. El EXE verifica runtime frozen/installed,
SQLite, reinicio, autenticación, voz y workers sin Python/Node externos.

El smoke adicional verifica botones de micrófono y selector nativo de audio,
ausencia de ejecución automática, materiales/fuentes y movimiento reducido.
Offline/configured son fixtures HTTP de presentación, no credenciales validadas.
Se conservan intentos 01–03 del arnés: timeout de arranque, espera incompleta y
selector ambiguo. Se corrigieron esperas/selector y drenaje de stderr; 04 pasó
sin cambiar el producto ni debilitar las aserciones funcionales.

Instalador: promoción real tras aprobación sobre repositorio descartable, modelo
HTTP determinista local, reinicio en puerta y desinstalación conservando datos
byte por byte. Sin inferencia pagada. Configuración/voz se probaron antes del
último ajuste solo de CSS; navegador final, EXE e instalador usan assets finales.

## Entrega nueva y reproducción

- Instalador: `dist/windows-premium-rc1/AISWESystem-v0.1.0-setup.exe`.
- Portable: `dist/windows-premium-rc1/AISWESystem-premium-rc1.zip`.
- Carpeta completa: `dist/windows-premium-rc1/AISWESystem/`; conservar `_internal`.
- Build: `_tmp/ui-premium-build-01/build-report.json`.
- Hashes/resultados: `UI-PREMIUM-EVIDENCE.json`.

Se usan los scripts existentes `tools/build_windows.py`, `verify_packaged_app.py`,
`build_installer.py`, `verify_installer.py` y los verificadores de navegador.
El nuevo `node tools/verify_premium_ui.cjs <exe> <evidencia-nueva>` comprueba el EXE
en Chromium. `AI_SWE_BROWSER_EXECUTABLE` selecciona un navegador ya instalado;
delivery usa `AI_SWE_TEST_BROWSER`. Usar siempre directorios nuevos de evidencia.
No se copian secretos ni pesos al paquete. Los candidatos anteriores se conservan.

## Límites

No se repitió la suite Python completa: 785 PASS/3 SKIP pertenece al baseline.
No se repitió micrófono físico; se conserva el reporte humano de F como histórico.
Sin gastos nuevos de API, VM independiente o firma del producto. Sin tag final,
push ni declaración de producción multiusuario. La evidencia previa de release
no describe los hashes nuevos. Se preservan los documentos académicos pendientes.
