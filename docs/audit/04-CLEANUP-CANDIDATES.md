# 04 — Candidatos de limpieza

> **NADA SE HA ELIMINADO.** Este documento es una propuesta. Cada candidato lleva
> evidencia, consumidores y riesgo. Commit `065db452`.

## Regla aplicada

> «No tiene import directo» **no** es evidencia suficiente para borrar. Se han
> comprobado: imports dinámicos, registries, rutas FastAPI, nodos LangGraph,
> descubrimiento de pytest, entrypoints CLI y referencias desde `tools/`.

**Falso positivo evitado (documentado a propósito).** `frontend/src/components/Diff.tsx`
parecía huérfano en una primera pasada (`grep "components/Diff"` no devuelve nada).
La comprobación correcta (`grep "Diff"`) muestra que `PuertaAprobacion.tsx` lo importa
con ruta relativa (`from "./Diff"`). **Está vivo.** Se deja constancia porque es
exactamente el error que la Fase 39 pide evitar.

---

## HIGH CONFIDENCE

| Fichero / módulo | Recomendación | Razón | Dependencias | Riesgo si se elimina |
|---|---|---|---|---|
| `_*.txt`, `_*.xml`, `_*.log` en la raíz (**~70 ficheros**) | **SAFE_DELETE** | Registros de suites y mutaciones de F7..F14. Ya cubiertos por `.gitignore`; son scratch de sesión por decisión propia del proyecto | Ninguna | Ninguno. No están versionados ni se leen |
| `_repro_*.py` (**3 ficheros**) | **SAFE_DELETE** | Sondas de reproducción de fallos concretos, declaradas «se borran al cerrar la fase» en `.gitignore` | Ninguna | Ninguno |
| `tmp8g9yx7zt/`, `tmpq6zgqajo/` | **SAFE_DELETE** | Directorios temporales olvidados por `tmp_path` de pytest. Ignorados por `/tmp*/` | Ninguna | Ninguno (revisar contenido antes) |
| `.pytest_cache/`, `.pytest_tmp/` | **SAFE_DELETE** | Cachés regenerables | Ninguna | Ninguno |

## MEDIUM CONFIDENCE

| Fichero / módulo | Recomendación | Razón | Dependencias | Riesgo |
|---|---|---|---|---|
| `src/ai_swe/agents/__init__.py` | **ARCHIVE o DELETE** | 13 líneas, solo docstring, **0 importadores**. Los agentes viven en `graph/nodes.py`. El nombre «agents/» sugiere una estructura que no existe | Ninguna | Ninguno funcional. Se pierde una nota de diseño (recuperable del historial de git) |
| `src/ai_swe/mcp/__init__.py` | **ARCHIVE** | Idem. Declara MCP como fase futura | Ninguna | Ninguno. **MCP está en el temario del curso**: si se va a defender, conviene conservarlo como marcador explícito |
| `src/ai_swe/observability/__init__.py` | **ARCHIVE** | Idem. Declara observabilidad (M6) | Ninguna | Ninguno |
| `data/tasks/README.md` | **ARCHIVE** | 2.838 bytes sin ninguna referencia desde `src/`, `tests/` ni `tools/` | Ninguna | Ninguno. **Antes de borrar, leerlo**: puede describir un formato de tarea relevante para `evaluation/tasks.py` |
| `tools/verify_m1_assumptions.py` | **KEEP (histórico)** | Arnés de la fase M1, ya cerrada (5/5). Sigue siendo ejecutable | Ninguna | Perder la evidencia de un acto de verificación pasado |
| `tools/verify_redaction_mutations.py` | **MERGE (evaluar)** | Arnés específico de redacción (8 mutaciones) anterior a `mutation_check.py`. Posible solape | `security/redaction.py` | Perder cobertura de mutación del redactor si el arnés general no la incluye (sí la incluye: bloque `redaction 8/8`) |

## MANUAL REVIEW

| Elemento | Motivo |
|---|---|
| `route_intent()` en `graph/nodes.py` | Ya **no es una arista** del grafo. Se conserva como «mapa puro» documentado. ¿Sigue aportando o es deuda? |
| `_ruta_estatica_m1()` | Viva como respaldo, pero su nombre ancla una fase cerrada |
| `docs/AUDITORIA-EXTERNA.md` (1.168 líneas) y `docs/AUDITORIA-F2-PARA-ARQUITECTO.md` (788) | Documentos de auditoría **ya consumidos**. Históricos: ver `05-…` |
| `docs/BASELINE-*.md` (7 ficheros, ~2.500 líneas) | Actas de cierre de fase. Históricas por naturaleza, valiosas como evidencia |
| `docs/01-ARCHITECTURE.md`, `02-CONTRACTS.md`, `03-SECURITY.md`, `04-ROADMAP.md`, `05-DECISIONS.md`, `06-EVALUATION.md` | **Índices de nomenclatura** (38-54 líneas) que apuntan a los documentos en español. **Duplican** la nomenclatura: `01-ARCHITECTURE` vs `01-arquitectura`, `02-CONTRACTS` vs `02-tecnologias`, `03-SECURITY` vs `03-flujo-e-implementacion`, `04-ROADMAP` vs `04-defensa`, `05-DECISIONS` vs `05-graphify-evaluacion`, `06-EVALUATION` vs `06-contrato-frontend-backend`. **Riesgo real de confusión**: dos ficheros con el mismo prefijo numérico y contenidos distintos |
| `frontend/dist/` | GENERATED. Se sirve, pero se regenera con `npm run build`. Correctamente ignorado |

## Tabla corta (Fase 41)

| FILE / MODULE | RECOMMENDATION | CONFIDENCE | REASON | DEPENDENCIES | DELETE RISK |
|---|---|---|---|---|---|
| `_*` raíz (~70) | SAFE_DELETE | HIGH | Scratch de sesión, ignorado | — | Ninguno |
| `_repro_*.py` (3) | SAFE_DELETE | HIGH | Sondas declaradas desechables | — | Ninguno |
| `tmp8g9yx7zt/`, `tmpq6zgqajo/` | SAFE_DELETE | HIGH | Temporales de pytest olvidados | — | Ninguno |
| `.pytest_cache/`, `.pytest_tmp/` | SAFE_DELETE | HIGH | Caché regenerable | — | Ninguno |
| `src/ai_swe/agents/` | ARCHIVE/DELETE | MEDIUM | Placeholder, 0 importadores | — | Ninguno funcional |
| `src/ai_swe/mcp/` | ARCHIVE | MEDIUM | Placeholder, 0 importadores | — | Ninguno funcional |
| `src/ai_swe/observability/` | ARCHIVE | MEDIUM | Placeholder, 0 importadores | — | Ninguno funcional |
| `data/tasks/README.md` | ARCHIVE | MEDIUM | Sin referencias | — | Ninguno |
| `tools/verify_redaction_mutations.py` | MERGE | MEDIUM | Solapa con `mutation_check.py` | redaction | Bajo |
| `docs/0X-*.md` (6 índices) | MERGE | MEDIUM | Duplican nomenclatura con `0X-*.md` en español | — | Bajo (son índices) |
| `route_intent()` | REVIEW | LOW | Sin arista; se conserva como documentación | — | Bajo |

## Beneficio esperado de la limpieza

| Acción | Beneficio |
|---|---|
| Borrar scratch + temporales | `git status` y `ls` dejan de mentir; el árbol de trabajo pasa de ~80 entradas a ~14 |
| Archivar los 3 placeholders | La estructura de `src/ai_swe/` refleja lo que existe |
| Resolver la doble nomenclatura de `docs/` | Elimina la ambigüedad de «¿cuál es el documento vigente?» |

## Lo que NO se debe tocar

- `frontend/contracts.json` — **GENERATED**, pero versionado a propósito (contrato entre capas).
- `var/evaluation_results.json` — evidencia cruda del informe F14.
- `docs/diagrama-arquitectura.svg/.png` — GENERATED por `tools/build_diagram.py`, pero es un entregable.
- Los 7 `docs/BASELINE-*.md` — actas de verificación; son la prueba de que cada fase se cerró.
