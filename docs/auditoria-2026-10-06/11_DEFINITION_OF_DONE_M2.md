> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 11 — Definition of Done de M2

M2 estará terminado cuando una tarea controlada pueda recorrer:

1. Entrada del usuario.
2. Requirements Analyst.
3. Confirmación humana.
4. `RunPlan` válido.
5. Researcher con evidencia.
6. Coder genera `CodeChange`.
7. Cambio aplicado en workspace aislado.
8. Test Runner ejecuta targets autorizados.
9. Reviewer evalúa requisitos + cambio + tests.
10. `REQUEST_CHANGES` vuelve al Coder.
11. El ciclo respeta budget y límite de revisiones.
12. `ACCEPT` conduce a HITL.
13. Aprobación/rechazo humano.
14. Estado terminal válido.
15. Persistencia y trazabilidad completas.

No son obligatorios para M2: Graphify, MCP, STT real, memoria semántica ni despliegue cloud.
