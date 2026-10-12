> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 02 — Arquitectura actual

```mermaid
flowchart TD
    Browser[Frontend HTML/JS] --> API[FastAPI]
    Browser -->|SSE| API
    API --> Worker[RunWorker]
    Worker --> Engine[RunEngine]
    Engine --> Graph[LangGraph StateGraph]
    Graph --> Interpret[interpret]
    Interpret --> Researcher[researcher]
    Researcher --> Coder[coder placeholder]
    Coder --> Tests[run_tests placeholder]
    Tests --> Reviewer[reviewer determinista]
    Reviewer --> Approval[approval_gate / HITL]
    Approval --> Finalize[finalize]
    Graph --> Policy[Policy Engine]
    Graph --> Store[(SQLite / Checkpointer)]
```

## Decisiones a conservar
- LangGraph como orquestador.
- `RunState` tipado.
- Comunicación entre nodos por contratos, no por chat global.
- HITL real.
- Policy Engine determinista.
- Persistencia y eventos.
- Regla de no fabricar evidencia.
