# Baseline post-limpieza

> **Fase 1 del plan de evolución controlada.** Acta de cierre. Commit
> `chore: clean repository and consolidate documentation`.
> Commit padre: `9a477d8 audit: preserve final project audit baseline`.

## 1. Qué se hizo

Eliminar el ruido del árbol de trabajo, consolidar la documentación duplicada y
corregir las descripciones de estado que no correspondían a la realidad.
**Cero cambios de comportamiento**: el conteo de pruebas es idéntico antes y después.

## 2. Qué se borró (verificado antes de borrar)

| Elemento | Cantidad | Verificación previa |
|---|---|---|
| Ficheros scratch `_*.txt` / `_*.xml` / `_*.log` / `_repro_*.py` | **73** | Ninguno versionado; todos cubiertos por `.gitignore`; **0 referencias desde código** |
| Directorios temporales olvidados | **2** (`tmp8g9yx7zt/`, `tmpq6zgqajo/`) | Restos de la prueba de confinamiento de F7 (`secreto.txt`, `repo/`, `fuera/`); ignorados; sin referencias |
| Cachés regenerables | **2** (`.pytest_cache/`, `.pytest_tmp/`) | Regenerables; ignoradas |
| `src/ai_swe/agents/` | **1 fichero** | Paquete **vacío** (solo docstring, 13 líneas); **0 importadores**; el nombre era engañoso — los agentes viven en `graph/nodes.py` |
| `data/` | **1 fichero + 2 directorios** | `data/tasks/README.md` archivado (ver §3); el directorio quedó vacío |

> **Nota de método.** El número de ficheros scratch **no era 74** como decía la
> auditoría: era **73**. La auditoría los contó antes de que yo borrara los dos
> suyos al terminar. Por eso la instrucción «no confíes en el número» era correcta.

**Total: la raíz pasó de ~90 entradas a 13.**

## 3. Qué se archivó (no se borró)

Todo con `git mv`, de modo que **la historia de cada fichero se conserva**.

| Movido a `docs/history/` | Qué es |
|---|---|
| `01-ARCHITECTURE.md`, `02-CONTRACTS.md`, `03-SECURITY.md`, `04-ROADMAP.md`, `05-DECISIONS.md` | **Índices de nomenclatura en inglés**, duplicados de los canónicos en español |
| `BASELINE-M1-POST-DOCUMENTACION.md`, `BASELINE-PRE-M2.md`, `BASELINE-MODEL-GATEWAY.md`, `BASELINE-F3-…`, `BASELINE-F4-…`, `BASELINE-F6-…`, `BASELINE-F7-…` | Actas de cierre de fases anteriores |
| `AUDITORIA-EXTERNA.md`, `AUDITORIA-F2-PARA-ARQUITECTO.md` | Auditoría externa del 2026-10-06 y entrega de F2 |
| `auditoria-2026-10-06/` (17 ficheros) | Conjunto documental original |
| `data/tasks/README.md` → `DATA-TASKS-FORMAT.md` | **Diseño de un formato de tareas YAML que F14 no siguió** (se implementó en `evaluation/tasks.py`). Se conserva porque contiene la categoría `adversarial`, que sigue siendo una idea válida para `EXP-06` |

**Total: 33 ficheros renombrados, 16 entradas en `docs/history/`.**

## 4. Qué se conservó aunque pareciera innecesario

**Éste es el apartado que más importa**, porque es donde una limpieza descuidada
habría hecho daño.

| Elemento | Por qué parecía eliminable | Por qué **no** se eliminó |
|---|---|---|
| `tools/verify_redaction_mutations.py` | «Solapa con `mutation_check.py`» (auditoría) | **Verificado: NO solapa.** `mutation_check.py` tiene **0 mutaciones** sobre `security/redaction.py`; solo tiene 2 sobre *puntos de llamada* (`models/errors.py`, `state/store.py`). Las 8 mutaciones del redactor son **cobertura única**. Fusionar habría perdido cobertura |
| `_ruta_estatica_m1` | La auditoría lo llamó «huérfano» | **Es alcanzable**: lo llama `route_after_execution` (línea 2391) cuando no hay plan, y tiene una mutación que lo protege (`mutation_check.py:514`) |
| `answer_direct` | La auditoría lo llamó «nodo inalcanzable» | **Es alcanzable**: `_ruta_estatica_m1` lo devuelve con intención `question` sin plan, y `tests/test_f5_plan_driven_execution.py:179` lo afirma |
| `route_intent` | No es una arista del grafo | **Tiene prueba** (`tests/test_workflow.py:420`) y es el mapa canónico intención→nodo |
| `src/ai_swe/mcp/` | Placeholder vacío | **Se implementará en la Fase 9** y **MCP forma parte del temario** |
| `src/ai_swe/observability/` | Placeholder vacío | **Se implementará en la Fase 8** (el plan lo convierte en funcionalidad real) |
| `06-EVALUATION.md` | Podría renumerarse | **Es GENERADO** por `evaluation/runner.py`, que escribe en esa ruta exacta |
| `01-arquitectura.md`, `02-tecnologias.md`, `03-flujo-e-implementacion.md`, `MODEL-GATEWAY-DESIGN.md` | Nombres en español frente al objetivo en inglés | **Están citados desde el código**: `src/` (≈15 comentarios), `frontend/contracts.json` (generado), `pyproject.toml`, `Dockerfile`, `docker-compose.yml`. Renombrarlos obligaría a tocar 20+ referencias sin beneficio funcional |
| `BASELINE-*.md` | «Histórico» | Son la **prueba** de que cada fase se cerró. Se archivan, no se borran |

## 5. Lo único que se eliminó por ser código muerto

| Elemento | Evidencia reunida |
|---|---|
| `route_after_research()` (10 líneas, `graph/nodes.py`) | **No está cableado**: `workflow.py` conecta `researcher` → `route_after_execution`. **0 consumidores** (`grep` en `src/`, `tests/`, `tools/`, `frontend/`). **Sin imports dinámicos** (verificado: no hay `getattr(nodes, …)` ni `importlib` sobre el módulo). **Suite verde tras eliminarlo**, con el mismo conteo |

> **Corrección de la auditoría.** La auditoría afirmó que el «fragmento huérfano de
> M1» eran **cuatro** elementos (`answer_direct`, `route_after_research`,
> `_ruta_estatica_m1`, `route_intent`). La verificación de esta fase demuestra que
> **tres de los cuatro están vivos** y solo uno está muerto. Se deja constancia
> porque es exactamente el falso positivo que la regla del proyecto prohíbe.

## 6. Documentación

| Acción | Detalle |
|---|---|
| `docs/README.md` **reescrito** | Ahora es el **índice único**: documentación vigente, generados, `audit/`, `history/`, cómo decidir qué consultar y regla ante contradicción |
| `README.md` raíz **corregido** | Decía «Fases M0, M1, F1 y F2 completadas» y que F3–F16 no existían. Ahora declara las **14 fases** reales, con la tabla de capacidades verificadas y lo que **no** está listo |
| `src/ai_swe/__init__.py` **corregido** | Decía «Estado: **fase M0 (diseño)**». Ahora declara M0+M1+F1–F14 y el alcance real |
| `docs/06-contrato-frontend-backend.md` → `docs/07-…` | Resuelto el **choque de número 06** con el documento generado |
| `pyproject.toml` | Corregida una **referencia muerta preexistente**: citaba `docs/auditoria-2026-10-06/12-ter_POLITICA_VERSIONES.md`, un fichero que **nunca existió** |

## 7. Verificación

| Comprobación | Antes | Después |
|---|---|---|
| Tests recogidos | 601 | **601** |
| Fallos / errores | 0 / 0 | **0 / 0** |
| Saltos | 2 | **2** |
| Duración | ~970 s | 991,9 s |
| **Veredicto (JUnit XML)** | GREEN | **GREEN** |
| Referencias `docs/…` desde código | 13 válidas + 1 muerta | **13 válidas, 0 muertas** |
| Entradas en la raíz | ~90 | **13** |

*(El proceso de pytest termina con `EXIT=1` por el guardia `safe-delete` del
entorno, que aborta la limpieza del temporal al cerrar. El veredicto se lee del XML:
0 fallos, 0 errores, y la salida de progreso no contiene ni una `F` ni una `E`.)*

## 8. Riesgos

- **Ningún riesgo de seguridad cerrado en esta fase.** Los 15 `SEC-*` y `TD-01`
  siguen abiertos. La Fase 2 abordará `SEC-03` (aprobación por defecto) y `SEC-04`
  (allowlist); la Fase 3, `SEC-01`/`SEC-05`/`SEC-06`/`SEC-09`/`SEC-10`/`SEC-11`.
- **Riesgo introducido: ninguno detectable.** El único borrado de código
  (`route_after_research`) está demostrado como muerto y la suite no cambia.
- `src/ai_swe/mcp/` y `src/ai_swe/observability/` **siguen siendo placeholders**
  hasta las Fases 9 y 8.

## 9. Próxima fase

| | |
|---|---|
| **Fase** | 2 — Contratos y configuración efectiva |
| **Objetivo** | `ApproveRequest.decision` obligatorio; aplicar o retirar los 5 ajustes declarados y no usados; unificar la lectura de `state_db_path`; `Budget` construido desde `Settings`; resolver los campos muertos |
| **Riesgo** | **MEDIO** — toca contratos y arranque; hay que actualizar `frontend/contracts.json` (GENERADO) y las pruebas que dependan de los defaults |
| **Condición de parada** | Autorización humana explícita |

## 10. Veredicto

**PHASE_1_READY = YES**
