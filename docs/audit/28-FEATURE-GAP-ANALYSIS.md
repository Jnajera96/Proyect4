# 28 — Análisis de brechas funcionales

> Commit `065db452`. Clasificación pedida: **A** planeada y nunca implementada ·
> **B** parcialmente implementada · **C** necesaria para cerrar el producto ·
> **D** eliminable del alcance · **E** opcional.

## A — Planeada y nunca implementada

| # | Funcionalidad | Dónde se prometió | Evidencia de ausencia |
|---|---|---|---|
| A1 | **MCP** (cliente + 2 servidores) | `mcp/__init__.py`, `docs/01-arquitectura.md` §12.3, temario del curso | Placeholder de 13 líneas; 0 importadores; extra `mcp` declarado y no usado |
| A2 | **Observabilidad / Langfuse** | `observability/__init__.py` (M6), `AI_SWE_LANGFUSE_*` | Placeholder; 0 importadores; los ajustes nunca se leen |
| A3 | **Cancelación de ejecución** (`RF-16`) | `POST /runs/{id}/cancel` | Devuelve **501** explícito |
| A4 | **Capa de contexto con grafo (Graphify)** | `docs/05-graphify-evaluacion.md` | Marcada `[PROP]`; `knowledge_graph` en `not_implemented` |
| A5 | **TTS** | `AI_SWE_TTS_ENABLED` | Declarado, 0 consumidores |
| A6 | **`EXP-02`..`EXP-08`** | `docs/01-arquitectura.md` §18.3 | Solo `EXP-01` implementado |
| A7 | **Autenticación** | `AUD-06` | No existe |
| A8 | **`GET /runs/{id}/trace`** | `api/__init__.py` | No existe la ruta |
| A9 | **Migraciones de esquema** | `ESQUEMA_VERSION` | El campo se escribe y no se lee |
| A10 | **`dry_run`** | `RunOptions.dry_run` (descripción explícita) | Ningún nodo lo lee |

## B — Parcialmente implementada

| # | Funcionalidad | Qué falta |
|---|---|---|
| B1 | **`AUD-07`: verificación del frontend** | Es un arnés aparte (`tools/verify_frontend.py`), **fuera de pytest** |
| B2 | **Lista blanca de repositorios** | Declarada en `Settings`, **no aplicada** |
| B3 | **Límites de red del sandbox** | `network_egress_enabled` declarado, no aplicado |
| B4 | **Presupuesto configurable** | `max_tokens/tool_calls/seconds_per_run` declarados, **no aplicados**; el `Budget` usa defaults del contrato |
| B5 | **Contabilidad de coste** | `pricing.py` existe; `AI_SWE_MODEL_PRICING` vacío ⇒ coste `None` |
| B6 | **STT usable** | El backend funciona; **no hay UI de voz** |
| B7 | **`answer_direct`** | Nodo implementado pero **inalcanzable** |
| B8 | **`git_commit` / `install_dependency` / `delete_file`** | En el catálogo con «requiere aprobación», **sin executor** |
| B9 | **Rutas de excepción del motor** | No limpian el worktree |
| B10 | **Purga/retención** | No existe |

## C — Necesaria para cerrar el producto

| # | Funcionalidad | Por qué |
|---|---|---|
| C1 | **Router + URLs en el frontend** | Sin él no hay enlace a una ejecución ni estado persistente al recargar |
| C2 | **Historial de ejecuciones visible** | El backend ya lo devuelve; la UI lo descarta |
| C3 | **Panel de presupuesto (tokens/coste/ciclos)** | Es la métrica `MET-06`; ya viaja en el estado |
| C4 | **Formulario de alcance** (`allowed_paths`/`protected_paths`) | Es una capacidad de **seguridad** que el usuario no puede ejercer |
| C5 | **Trazabilidad de aprobaciones** | `RNF-T2`; ya viaja en el estado |
| C6 | **UI de voz** | El STT funciona y no es alcanzable por un humano |
| C7 | **Aviso de que el código sale al proveedor** | Carencia de privacidad |
| C8 | **Corregir `README` y `__init__.py`** | Dicen «fase M0/F2»; es lo primero que se lee |
| C9 | **Limpiar los artefactos scratch** | 74 ficheros + 2 directorios |
| C10 | **Aplicar o retirar los 5 ajustes declarados y no usados** | Un control declarado que no existe crea confianza injustificada |

## D — Eliminable del alcance

| # | Elemento | Motivo |
|---|---|---|
| D1 | `agents/`, `mcp/`, `observability/` (placeholders) | No aportan; el código real está en otro sitio |
| D2 | `route_intent`, `route_after_research`, `_ruta_estatica_m1`, `answer_direct` | Fragmento huérfano de M1 |
| D3 | `TestRun.reproducible` | Campo muerto con descripción falsa |
| D4 | `RunOptions.dry_run` | Campo muerto con descripción falsa |
| D5 | `pytest-asyncio` | Declarado sin consumidor |
| D6 | `langfuse` (extra) | Sin consumidor |
| D7 | `data/tasks/README.md` | Sin referencias |
| D8 | `tools/verify_redaction_mutations.py` | Solapa con `mutation_check.py` |

> **Aviso sobre D1**: `mcp/` puede interesar **conservarlo** si MCP forma parte de la
> defensa académica. Es una decisión del Arquitecto, no técnica.

## E — Opcional / futuro

| # | Funcionalidad | Nota |
|---|---|---|
| E1 | `EXP-02`..`EXP-08` | Extienden la evaluación |
| E2 | Observabilidad con Langfuse | Ya hay ajustes |
| E3 | MCP | Placeholder listo |
| E4 | Grafo de contexto | Propuesta documentada |
| E5 | Selección de modelo desde la UI | Requiere `GET /config` |
| E6 | Multi-usuario | Requiere auth + aislamiento de datos |
| E7 | Cancelación real | Requiere señalizar al trabajador |
| E8 | Exportación de informes (PDF/Markdown) | `FinalReport` ya está estructurado |
| E9 | Reintentos con backoff en el gateway | Mejora la robustez |

## Resumen cuantitativo

| Categoría | Nº |
|---|---|
| A (planeada, no implementada) | 10 |
| B (parcial) | 10 |
| C (necesaria para cerrar) | 10 |
| D (eliminable) | 8 |
| E (opcional/futuro) | 9 |

**Lectura**: hay **10 funcionalidades declaradas que no existen** y **10 a medias**.
La mayor parte de las de la categoría B son **controles declarados y no aplicados**
(configuración) o **capacidades sin UI**. Ninguna de las categorías A/B bloquea el
uso local actual; varias (B2, B3, B4) sí crean una **falsa sensación de control**.
