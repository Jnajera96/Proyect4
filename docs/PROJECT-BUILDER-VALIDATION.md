# Validación integrada del builder — 2026-10-28

Código empaquetado: checkpoint `60edbc8`, rama `feature/v0.2.0-madre-continuity`.

- Suite Python completa: 893 casos, 889 aprobados, 4 omitidos, 0 fallos y 0 errores; 452.353 segundos. XML local: `_tmp/project-builder-final-suite.xml`.
- Frontend: 32 pruebas aprobadas; TypeScript y Vite compilan correctamente.
- Portable firmado: smoke completo aprobado, manifiesto consistente, ausencia de archivos de secretos/estado de desarrollo, frontend integrado, registro y aislamiento inicial de perfil, ejecución determinista con confirmación humana, cierre, reinicio y persistencia de perfil/SQLite/checkpoint. Informe local: `_tmp/project-builder-portable-smoke/report.json`.
- Revisión local del guard de rutas: rechaza `.git` normalizado por puntos/espacios, componentes ambiguos y ADS antes de mutaciones. La segunda revisión independiente sigue pendiente; no se presenta esta inspección como independiente.
- Worktree secundario `C:/Users/jose_/.codex/worktrees/provider-preflight/proyecto4-ai-swe` avanzado desde `2a666df` hasta `60edbc8` mediante fast-forward, tras verificar que estaba limpio.

## Candidato portable

ZIP: `dist/windows-v0.2.0-project-builder-rc1/AISWESystem-windows-x64.zip`.

SHA256: `552bd8a44e70375440d88234b6aed1c6899d955e753c92138930ef60b88cd410`.

Extraer la carpeta completa y ejecutar `AISWESystem/AISWESystem.cmd`. Python 3.13.14 incluido; ejecutables oficiales con firma válida. Git sigue siendo necesario para proyectos. No reemplaza el portable canónico v0.1.0.

Calendario y calorías tienen integración E2E offline documentada en `docs/evidence/project-builder-checkpoint/`; las respuestas de modelos son fixtures. No hubo nuevas llamadas pagadas ni se certifica generación remota de cualquier proyecto. El smoke de este paquete usa ejecución determinista; no sustituye la comprobación manual completa del nuevo formulario sobre otra PC.

Estado: candidato para probar en otro equipo, no cierre de producción. Pendientes: revisión independiente final, validación en otra PC y problemas conocidos de continuidad/importación/auto-respaldo. No hay nueva autorización de gasto: se mantiene el ledger anterior de 3 USD.
