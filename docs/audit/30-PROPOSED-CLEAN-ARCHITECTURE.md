# 30 — Arquitectura limpia propuesta

> **NO SE HA MOVIDO NI BORRADO NADA.** Propuesta. Commit `065db452`.

## 1. Árbol actual (raíz)

```
ai-swe/
├── .env.example  .gitattributes  .gitignore  .python-version
├── Dockerfile  docker-compose.yml  pyproject.toml  uv.lock  README.md
├── PROJECT_SNAPSHOT.json
├── _api_check.txt  _audit_suite.log  _f10_*.xml  ... (~74 ficheros scratch)
├── tmp8g9yx7zt/  tmpq6zgqajo/          (2 directorios temporales olvidados)
├── .pytest_cache/  .pytest_tmp/
├── data/tasks/README.md                 (huérfano)
├── docs/  (44 ficheros: diseño + 7 BASELINE + 2 AUDITORIA + 17 auditoria-2026-10-06)
├── frontend/  (12 fuente + dist + node_modules)
├── src/ai_swe/  (48 ficheros)
├── tests/  (22 ficheros)
├── tools/  (6 ficheros)
└── var/  (state.sqlite3 + workspaces + evaluation_results.json)
```

## 2. Árbol propuesto

```
ai-swe/
├── README.md                       ← reescrito: qué es, estado REAL, arranque
├── pyproject.toml  uv.lock
├── .env.example  .gitignore  .gitattributes  .python-version
├── Dockerfile  docker-compose.yml
├── PROJECT_SNAPSHOT.json
│
├── src/ai_swe/
│   ├── contracts/       (7)   ← sin cambios
│   ├── graph/           (5)   ← nodes.py se divide (ver §4)
│   ├── models/         (11)   ← sin cambios
│   ├── tools/           (5)   ← sin cambios
│   ├── api/             (2)   ← sin cambios
│   ├── state/           (2)   ← sin cambios
│   ├── security/        (3)   ← sin cambios
│   ├── stt/             (2)   ← sin cambios
│   ├── evaluation/      (3)   ← sin cambios
│   ├── sandbox.py  config.py  __init__.py  __main__.py
│   └── (agents/, mcp/, observability/  → decisión del Arquitecto)
│
├── tests/              (22)   ← sin cambios + el frontend entra en pytest (AUD-07)
├── tools/               (6)   ← verify_redaction_mutations se fusiona
│
├── docs/
│   ├── README.md                       ← índice único
│   ├── 01-ARCHITECTURE.md              ← fusión de 01-arquitectura + 03-flujo
│   ├── 02-CONTRACTS.md                 ← fusión de 02-tecnologias + 02-CONTRACTS
│   ├── 03-SECURITY.md                  ← fusión de 03-SECURITY + 19-THREAT-MODEL
│   ├── 04-OPERATIONS.md                ← NUEVO
│   ├── 05-EVALUATION.md                ← GENERADO (hoy 06-EVALUATION.md)
│   ├── 06-ROADMAP.md                   ← NUEVO (fases cerradas + pendientes)
│   ├── assets/                         ← diagrama.svg, diagrama.png
│   ├── audit/                          ← ESTA auditoría (35 ficheros)
│   └── history/                        ← 7 BASELINE + 2 AUDITORIA + auditoria-2026-10-06/ (17)
│
├── frontend/  (sin cambios)
└── var/       (ignorado salvo evaluation_results.json)
```

## 3. Qué desaparece / se fusiona / se mueve

| Elemento | Acción | Motivo |
|---|---|---|
| ~74 `_*` scratch + 2 `tmp*` | **Desaparece** (borrar) | Scratch de sesión |
| `.pytest_cache/`, `.pytest_tmp/` | **Desaparece** | Caché regenerable |
| `data/tasks/README.md` | **Mueve a `docs/history/`** o borra | Sin referencias |
| 6 índices `0X-*.md` (inglés) | **Se fusiona** con los `0X-*.md` (español) | Doble nomenclatura |
| 7 `BASELINE-*.md` | **Mueve a `docs/history/`** | Actas de fase cerrada |
| 2 `AUDITORIA-*.md` | **Mueve a `docs/history/`** | Consumidos |
| `auditoria-2026-10-06/` (17) | **Mueve a `docs/history/`** | Origen histórico |
| `docs/diagrama-*` | **Mueve a `docs/assets/`** | Orden |
| `agents/`, `mcp/`, `observability/` | **Decisión del Arquitecto** | Ver §5 |
| `verify_redaction_mutations.py` | **Se fusiona** con `mutation_check.py` | Solape |
| `answer_direct`, `route_after_research`, `_ruta_estatica_m1`, `route_intent` | **Candidatos a retirar** | Fragmento huérfano de M1 |

## 4. El punto de concentración: `graph/nodes.py`

**2.500+ líneas** con los 4 agentes, la revisión, las guardas, la promoción, la
limpieza y todo el enrutado. Es el 40 % del código de dominio.

**Propuesta (refactor, no limpieza):**

```
graph/
├── nodes/
│   ├── __init__.py        (reexporta)
│   ├── interpret.py       Requirements Analyst
│   ├── plan.py            Supervisor
│   ├── researcher.py      Researcher (determinista)
│   ├── coder.py           Coder
│   ├── reviewer.py        Reviewer + guardas
│   ├── gates.py           Las dos puertas HITL
│   ├── sandbox_nodes.py   apply_sandbox, promote_changes
│   ├── terminal.py        finalize, escalate*, explain_limits
│   └── routing.py         todos los `route_after_*`
├── workflow.py  engine.py  worker.py
```

**Beneficio**: cada agente con sus pruebas al lado; el enrutado en un solo fichero.
**Riesgo**: alto (toca el corazón del sistema y 601 pruebas dependen de él).
**Cuándo**: **después** de cerrar la entrega, no antes.

## 5. Los tres placeholders: recomendación

| Módulo | Recomendación | Razón |
|---|---|---|
| `observability/` | **Retirar** y dejar la observabilidad en `docs/` como trabajo futuro | Sin código, sin consumidores |
| `mcp/` | **Conservar y documentar como no implementado** | **MCP está en el temario del curso**; retirarlo debilita la defensa |
| `agents/` | **Retirar** y añadir una nota en `graph/` explicando dónde viven los agentes | El nombre induce a error |

## 6. Qué permanece intacto

- `src/ai_swe/contracts/` — la fuente única de verdad.
- `frontend/contracts.json` — GENERATED, versionado a propósito.
- `var/evaluation_results.json` — evidencia cruda del informe.
- Los 7 `BASELINE-*` — se archivan, no se borran: son la prueba de que cada fase se cerró.
- El diagrama arquitectónico — es un entregable.

## 7. Secuencia recomendada

```
Paso 1  Borrar scratch y temporales                     (0 riesgo)
Paso 2  Reescribir README + docstring de __init__.py     (0 riesgo)
Paso 3  Resolver la doble nomenclatura de docs/          (bajo)
Paso 4  Archivar docs/history/                           (bajo)
Paso 5  Decidir placeholders + fusionar verify_redaction (bajo)
Paso 6  Retirar el fragmento huérfano de M1              (medio)
Paso 7  Dividir graph/nodes.py                           (ALTO — solo tras la entrega)
```

**Los pasos 1-5 son de riesgo nulo o bajo y mejoran mucho la legibilidad del
repositorio.** El paso 7 es un refactor real y no debe hacerse antes de entregar.
