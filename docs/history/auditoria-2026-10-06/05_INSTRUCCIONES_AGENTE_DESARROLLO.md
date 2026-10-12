> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 05 — Instrucciones para el agente de desarrollo

## Objetivo inmediato
Evolucionar M1 → M2 sin romper la infraestructura validada.

## No reescribir sin evidencia de fallo
- LangGraph.
- `RunState`.
- Persistencia SQLite/checkpointer.
- SSE.
- HITL.
- Policy Engine.
- Contratos existentes.
- Pruebas actuales.

## Prohibiciones
- No MCP todavía.
- No Graphify todavía.
- No STT real todavía.
- No acceso directo del Coder al workspace principal.
- No `shell=True` con comandos generados por LLM.
- No permitir que el LLM decida permisos o seguridad.
- No crear una arquitectura paralela que ignore contratos y State.
- No exponer la API fuera de localhost sin autenticación.

## Regla maestra
**El LLM razona y propone. El sistema determinista valida, autoriza, ejecuta y persiste.**
