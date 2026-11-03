# Prompt de continuidad para Antigravity

Copia desde «Actúa» hasta el final. No pegues tokens ni contraseñas.

---

Actúa como responsable de documentación y release engineer del repositorio
`C:\Users\jose_\Desktop\repo_proyect\proyecto4-ai-swe`, rama
`feature/v0.2.0-madre-continuity`.

Codex implementó la primera entrega de capacidades locales a partir de `86ce801`.
Localiza el commit que incorpora este handoff y verifica HEAD, rama, status y diff
antes de editar. El segundo worktree es
`C:\Users\jose_\.codex\worktrees\provider-preflight\proyecto4-ai-swe`.
Si hay cambios ajenos, consérvalos y no uses reset/restore/clean para descartarlos.

Lee, en este orden:
1. `docs/LOCAL-CAPABILITIES-VALIDATION-2026-11-02.md`.
2. `docs/LOCAL-CAPABILITIES-EVIDENCE-2026-11-02.json`.
3. `docs/LOCAL-CAPABILITIES-DESIGN-2026-11-02.md`.
4. `README.md` y `docs/PLAN-MAESTRO-CIERRE-v0.2.0.md`.

Tu tarea es conciliar los reportes e índices restantes con esa evidencia, sin
implementar funcionalidades nuevas ni alterar las actas históricas:
- Autenticación local por perfiles, cancelación cooperativa y aislamiento
  Windows Job/Docker ya existen. No deben volver a figurar como «no implementados»
  ni cancelación 501. Mantén sus límites de seguridad y alcance local.
- MCP propio stdio 2025-06-18: cliente/servidor de lectura, handshake, read_file
  y git_status limitado a HEAD (working_tree_inspected=false). El Researcher lo
  consume con cuota, scope y timeout; no habilita servidores arbitrarios ni escritura.
- Observabilidad SQLite: trazas correlacionadas, descarga JSON y tokens/costes
  disponibles. Exportación Langfuse OTLP manual, administrativa y opcional,
  sin prompts/código/secretos. Está probada con dobles; NO consta recepción real.
- Grafo AST nativo de archivos, símbolos e importaciones, con filtro/descarga UI
  y rutas ya seleccionadas por memoria asociativa. NO es Graphify externo.
- TTS voluntario del resultado: voces locales del navegador, botones de reproducir
  y detener, sin fallback remoto. Pruebas de navegador con síntesis simulada;
  NO equivalen a audición física ni compatibilidad certificada en toda PC.
- MCP/TTS/Langfuse se habilitan explícitamente con los flags documentados. No
  cambies el `.env` privado ni añadas claves a archivos, commits, ZIP o capturas.

Actualiza `docs/OPERATIONAL-STATUS-2026-10-30.md`,
`docs/PRODUCTIZATION-PROGRESS.md`, `docs/ROADMAP.md` y los snapshots/índices que
corresponda, revisando sus generadores antes de editar archivos generados.
README y plan maestro ya están conciliados: mejora enlaces/coherencia si hace
falta, sin inventar cierres ni repetir cambios existentes.
Usa las cifras exactas del JSON, separando regresión, pruebas focalizadas y browser;
no sumes suites solapadas. No eleves el porcentaje histórico 91/100 sin nueva
matriz ponderada y criterios de aceptación explícitos.

El usuario pausó nuevo empaquetado y pilotos para priorizar estas capacidades.
Rc25 sigue intacto y NO contiene estos cambios. Deja como pendientes separados:
nuevo portable+smoke, recepción real en Langfuse, voz física, evaluación de Graphify,
Windows independiente, continuidad física y publicación del asistente en GitHub.
No ejecutes esos pilotos ni conviertas una prueba con dobles en evidencia real.

Restricciones: sin APIs pagadas, npm install, ejecución de scripts de proyectos
generados en host, cambios destructivos de Git ni alteración del tag v0.1.0.
El MCP propio y la exportación OTLP no requieren instalar los extras SDK.
Revisa `git diff --check`, enlaces y cifras; si solo cambias documentación,
no hace falta repetir toda la suite sin motivo. Guarda un commit documental,
sincroniza ambos worktrees solo si están limpios y reporta hashes y estado.
Mantén la restricción sin git push; para publicar al remoto pide autorización
explícita a José y muestra primero el commit/diff concreto que se publicaría.
