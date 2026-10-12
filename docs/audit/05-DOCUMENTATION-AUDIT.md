# 05 — Auditoría de documentación

> 43 ficheros Markdown + 1 SVG + 1 PNG + `PROJECT_SNAPSHOT.json`. Commit `065db452`.

## 1. Clasificación

### CURRENT_SOURCE_OF_TRUTH

| Documento | Por qué |
|---|---|
| `PROJECT_SNAPSHOT.json` | Estado verificado, métricas y deudas. Actualizado en cada fase (F10..F14) |
| `docs/06-EVALUATION.md` | **GENERATED** por `evaluation/runner.py`; no editable a mano |
| `var/evaluation_results.json` | Evidencia cruda del informe anterior |
| `docs/01-arquitectura.md` (1.286 líneas) | Diseño canónico: `MET-01..14`, `EXP-01..08`, permisos, invariantes |
| `docs/02-tecnologias.md` (344) | Selección y justificación de tecnologías |
| `docs/03-flujo-e-implementacion.md` (548) | Topología del grafo y plan |
| `docs/04-defensa.md` (658) | Material de defensa |

### CURRENT

`docs/README.md` (índice, 92), `docs/06-contrato-frontend-backend.md` (288),
`docs/MODEL-GATEWAY.md` (319), `docs/MODEL-GATEWAY-DESIGN.md` (355),
`docs/diagrama-arquitectura.svg/.png`.

### HISTORICAL (actas de fase — correctas, pero de fases cerradas)

`docs/BASELINE-M1-POST-DOCUMENTACION.md`, `BASELINE-PRE-M2.md`,
`BASELINE-MODEL-GATEWAY.md`, `BASELINE-F3-REQUIREMENTS-ANALYST.md`,
`BASELINE-F4-SUPERVISOR.md`, `BASELINE-F6-REAL-CODER.md`, `BASELINE-F7-SANDBOX.md`.

### SUPERSEDED / OBSOLETO

| Documento | Motivo |
|---|---|
| `docs/AUDITORIA-EXTERNA.md` (1.168) | Auditoría externa del 2026-10-06; sus hallazgos se convirtieron en `AUD-01..14`. Histórico |
| `docs/AUDITORIA-F2-PARA-ARQUITECTO.md` (788) | Entrega puntual de la fase F2 |
| `docs/auditoria-2026-10-06/` (17 ficheros) | Conjunto original de la auditoría externa. Contiene `09_ROADMAP.md` y `13_PROXIMO_PROMPT_AGENTE.md`, ya superados por 14 fases |
| `docs/05-graphify-evaluacion.md` (361) | Propuesta `[PROP]` **nunca implementada** |

### DUPLICATE (riesgo real de confusión)

**Dos familias de documentos con el mismo prefijo numérico y contenidos distintos:**

| Nomenclatura A (inglés, corta) | Nomenclatura B (español, larga) | Relación |
|---|---|---|
| `docs/01-ARCHITECTURE.md` (38) | `docs/01-arquitectura.md` (1.286) | A es un **índice** de B |
| `docs/02-CONTRACTS.md` (53) | `docs/02-tecnologias.md` (344) | A apunta a B **y a `contracts/`**; los temas no coinciden |
| `docs/03-SECURITY.md` (54) | `docs/03-flujo-e-implementacion.md` (548) | Temas distintos bajo el mismo número |
| `docs/04-ROADMAP.md` (49) | `docs/04-defensa.md` (658) | Idem |
| `docs/05-DECISIONS.md` (45) | `docs/05-graphify-evaluacion.md` (361) | Idem |
| `docs/06-EVALUATION.md` (141, **generado**) | `docs/06-contrato-frontend-backend.md` (288) | **Idem, y aquí es peligroso**: el número 06 designa a la vez el informe de evaluación y el contrato frontend/backend |

`docs/README.md` documenta que la familia A son «alias de nomenclatura», pero el
efecto práctico es que `docs/06-EVALUATION.md` y `docs/06-contrato-frontend-backend.md`
comparten número y no tienen relación.

### GENERATED

`docs/06-EVALUATION.md`, `docs/diagrama-arquitectura.svg`, `docs/diagrama-arquitectura.png`.

## 2. Contradicciones documentación ↔ código

**Éstas son las que importan.** Todas verificadas contra el código real.

| # | Documento | Afirma | Realidad | Gravedad |
|---|---|---|---|---|
| C1 | `README.md` §«Estado del proyecto» | «Fases M0, M1, F1 y F2 completadas» | F3..**F14** implementadas y verificadas | **ALTA** — el README es lo primero que se lee |
| C2 | `src/ai_swe/__init__.py` (docstring) | «Estado: **fase M0 (diseño)**. El grafo, los agentes, el backend y el frontend corresponden a las fases M1 en adelante» | Todo implementado | **ALTA** — el docstring del paquete miente |
| C3 | `docs/README.md` / `README.md` | La documentación «vigente» está en `docs/auditoria-2026-10-06/` | Ese conjunto es de la fase M1/M2; `PROJECT_SNAPSHOT.json` es el estado real | MEDIA |
| C4 | `README.md` tabla de componentes | No menciona backend, frontend, evaluación, STT ni promoción | Los cinco existen | MEDIA |
| C5 | `docs/06-contrato-frontend-backend.md` | Describe el contrato frontend/backend | Puede estar desalineado con `frontend/contracts.json` (GENERATED). **No verificado línea a línea** | MEDIA |
| C6 | `docs/05-graphify-evaluacion.md` | Propone una capa de contexto con grafo | `[PROP]`, nunca implementada; `not_implemented` del snapshot incluye `knowledge_graph` | BAJA (está marcada) |
| C7 | `README.md` | «Evaluación de Graphify: propuesta no implementada» | Correcto | — |
| C8 | `Dockerfile` | Comentario: «la ejecución de pruebas y la escritura de archivos ocurren aquí dentro, sin salida de red» | No hay `network_mode: none` ni firewall en la imagen; la red del contenedor es la del host por defecto | MEDIA |
| C9 | `docker-compose.yml` | Comentario: «Se declara la ausencia de red en el servicio de ejecución cuando exista (fase M3)» | M3 está cerrada y **no se declaró** | MEDIA |
| C10 | `docker-compose.yml` | `NEXTAUTH_SECRET: cambiar-en-despliegue-real`, `SALT: ...` | Valores placeholder. Están tras el perfil `observability`, pero se arrancarían con credenciales por defecto | BAJA-MEDIA |

## 3. Documentación que falta

| Falta | Por qué importa |
|---|---|
| Guía de instalación y arranque (solo hay `README` de estado) | Un tercero no puede ejecutar el proyecto sin leer 5 documentos |
| Documento de operación (arrancar API, workers, dónde está la BD, cómo se purga) | No existe |
| Política de retención de datos | No existe (ver `27-…`) |
| `docs/06-EVALUATION.md` no explica cómo se regenera **en el propio repo** (sí lo dice en el pie) | Menor |
| Ningún ADR formal de las decisiones grandes (`DEC-07`, `DEC-16`) | Están citadas en comentarios de código; `docs/05-DECISIONS.md` es un índice |

## 4. Propuesta de documentación mínima definitiva

**Siete documentos.** Todo lo demás pasa a `docs/history/`.

| Documento | Contenido | Origen |
|---|---|---|
| `README.md` | Qué es, estado **real**, arranque en 5 líneas, mapa de docs | Reescribir |
| `docs/01-ARCHITECTURE.md` | Arquitectura y topología del grafo | Fusionar `01-arquitectura` + `01-ARCHITECTURE` + `03-flujo-e-implementacion` |
| `docs/02-CONTRACTS.md` | Contratos, estado y presupuesto | Fusionar `02-tecnologias` (parte) + `02-CONTRACTS` |
| `docs/03-SECURITY.md` | Modelo de amenazas, política, sandbox, límites | Fusionar `03-SECURITY` + `03-flujo-e-implementacion` (parte) + `19-THREAT-MODEL` |
| `docs/04-OPERATIONS.md` | Configuración, despliegue, retención, diagnóstico | **Nuevo** |
| `docs/05-EVALUATION.md` | Métricas y resultados | `06-EVALUATION` (generado) |
| `docs/history/` | Actas de fase y auditorías pasadas | Mover los `BASELINE-*`, `AUDITORIA-*` y `auditoria-2026-10-06/` |

**Regla propuesta**: un solo prefijo numérico por documento. La doble nomenclatura
actual (`01-ARCHITECTURE` y `01-arquitectura`) es la causa raíz de las dudas sobre
qué documento manda.

> **No se ha movido ni renombrado nada.** Esta es una propuesta.
