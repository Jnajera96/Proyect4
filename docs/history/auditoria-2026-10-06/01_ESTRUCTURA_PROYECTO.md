> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 01 — Estructura actual del proyecto

```text
proyecto4-ai-swe/
├── README.md
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── src/ai_swe/
│   ├── config.py
│   ├── contracts/
│   │   ├── state.py
│   │   ├── outputs.py
│   │   ├── api.py
│   │   ├── tasks.py
│   │   ├── tools.py
│   │   └── validate.py
│   ├── graph/
│   │   ├── workflow.py
│   │   ├── nodes.py
│   │   ├── engine.py
│   │   └── worker.py
│   ├── state/store.py
│   ├── api/app.py
│   ├── tools/policy.py
│   ├── tools/registry.py
│   ├── stt/base.py
│   ├── agents/__init__.py
│   ├── mcp/__init__.py
│   ├── observability/__init__.py
│   └── evaluation/__init__.py
├── tests/
├── tools/
├── frontend/
│   ├── index.html
│   └── contracts.json
├── docs/
├── data/tasks/README.md
└── var/state.sqlite3
```

### Nota
`agents/`, `mcp/`, `observability/` y `evaluation/` eran principalmente andamiaje en la auditoría. `var/state.sqlite3`, `.env`, entornos virtuales y temporales deben quedar fuera de Git.
