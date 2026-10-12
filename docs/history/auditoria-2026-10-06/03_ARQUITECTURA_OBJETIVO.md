> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 03 — Arquitectura objetivo

```mermaid
flowchart TD
    U[Usuario] --> IN[Texto / Voz]
    IN --> STT[Speech-to-Text]
    STT --> RA[Requirements Analyst]
    RA --> HV[Validación humana]
    HV --> SUP[Supervisor]
    SUP --> RES[Researcher]
    SUP --> COD[Coder]
    SUP --> REV[Reviewer]
    RA --> MG[Model Gateway]
    SUP --> MG
    RES --> MG
    COD --> MG
    REV --> MG
    COD --> POL[Policy Engine]
    POL --> WT[Worktree / Sandbox]
    WT --> TOOLS[Tool Executor]
    TOOLS --> TEST[Test Runner]
    TEST --> REV
    REV -->|REQUEST_CHANGES| COD
    REV -->|ACCEPT| HITL[Human Approval]
    HITL --> FINAL[Resultado final]
    SUP --> STATE[(RunState / Checkpoint)]
    RES --> STATE
    COD --> STATE
    REV --> STATE
    STATE -. contexto opcional .-> KG[Graphify / Knowledge Graph]
```

Graphify y MCP no son requisitos del MVP M2. Se integran después de demostrar el flujo principal.
