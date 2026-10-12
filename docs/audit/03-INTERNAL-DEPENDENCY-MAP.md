# 03 — Mapa de dependencias internas

> Medido con `grep` sobre `src/`, `tests/` y `tools/` en el commit `065db452`.
> Método: para cada módulo, número de ficheros que lo importan (excluyendo el
> propio). **Limitación del método**: una importación vía paquete padre
> (`from ai_swe.graph import nodes`) no aparece al buscar el nombre del
> subpaquete; los casos dudosos se verificaron a mano y se anotan.

## 1. Grafo por capas

```
                        ┌──────────────────────────────┐
   ENTRADA              │  __main__.py  │  api/app.py   │
                        └───────┬──────────────┬────────┘
                                │              │
   ORQUESTACIÓN         ┌───────▼──────┐  ┌────▼─────────┐
                        │ graph/worker │  │ graph/engine │
                        └───────┬──────┘  └────┬─────────┘
                                │              │
                        ┌───────▼──────────────▼────────┐
                        │      graph/workflow.py        │
                        └───────────────┬───────────────┘
                                        │
                        ┌───────────────▼───────────────┐
   DOMINIO              │        graph/nodes.py         │◄──── sandbox.py
                        └───┬──────┬──────┬──────┬──────┘
                            │      │      │      │
                   ┌────────▼─┐ ┌──▼───┐ ┌▼─────┐ ┌▼──────────┐
   INFRAESTRUCTURA │ tools/   │ │tools/│ │tools/│ │ tools/    │
                   │ policy   │ │runner│ │patch.│ │ promoter  │
                   └────┬─────┘ └──┬───┘ └──┬───┘ └─────┬─────┘
                        │          │        │           │
                   ┌────▼──────────▼────────▼───────────▼─────┐
                   │  contracts/  (fuente única de verdad)     │
                   └───────────────────┬───────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
   ┌────▼─────┐  ┌──────────┐  ┌───────▼────┐  ┌──────────┐  ┌───────▼─────┐
   │ models/  │  │ state/   │  │ security/  │  │ config   │  │ stt/        │
   │ gateway  │  │ store    │  │ redaction  │  │ Settings │  │ adapters    │
   └──────────┘  └──────────┘  └────────────┘  └──────────┘  └─────────────┘
```

**Dirección de dependencia.** `contracts/` no importa nada del proyecto (34
importadores, 0 dependencias salientes): es la base. `graph/nodes.py` es el
sumidero de dependencias del dominio (importa `contracts`, `sandbox`, `tools/*`,
`models`, `config`). No hay dependencias hacia arriba salvo la conocida y
deliberada: `nodes.py` importa `config.load_settings` de forma **diferida** dentro
de funciones, precisamente para no acoplar la importación.

## 2. Módulos más importados (núcleo estable)

| Módulo | Importadores | Lectura |
|---|---|---|
| `ai_swe.contracts` | 34 | Fuente única de verdad; correcto que sea el más usado |
| `ai_swe.models` | 23 | Fachada del gateway |
| `ai_swe.graph` | 19 | Fachada de orquestación |
| `ai_swe.security` | 12 | Redacción, transversal por diseño |
| `ai_swe.tools` | 10 | Fachada de herramientas |
| `ai_swe.config` | 9 | Ajustes |
| `ai_swe.sandbox` | 9 | Worktree |
| `ai_swe.tools.policy` | 8 | Policy Engine |
| `ai_swe.state` | 8 | Persistencia |
| `ai_swe.graph.workflow` | 8 | Topología |

## 3. Módulos con 0 importadores (verificados a mano)

| Módulo | ¿Huérfano? | Evidencia |
|---|---|---|
| `ai_swe.__main__` | **No** | Punto de entrada: `python -m ai_swe` |
| `ai_swe.graph.nodes` | **No** | Importado como `from ai_swe.graph import nodes` por `workflow.py`, `evaluation/runner.py` y 4 tests |
| `ai_swe.agents` | **Sí** | Ninguna referencia en `src/`, `tests/` ni `tools/` |
| `ai_swe.mcp` | **Sí** | Ninguna referencia |
| `ai_swe.observability` | **Sí** | Ninguna referencia |
| `ai_swe.contracts.validate` | **Test-only** | Solo `tests/test_contracts.py`; es una utilidad de verificación de serializabilidad, correcto que no la use el runtime |

## 4. Acoplamiento y ciclos

| Comprobación | Resultado |
|---|---|
| Ciclos de importación | **Ninguno detectado.** La dirección `contracts → (nada)` y `nodes → todo lo demás` no se cierra en ningún punto |
| Acoplamiento innecesario | `graph/nodes.py` importa **5 módulos de herramientas** (`policy`, `runner`, `patcher`, `promoter`, `registry`). Es el nodo "todo-en-uno" del proyecto: **1.200+ líneas** con los 5 agentes, la revisión, las guardas y el enrutado. Es el principal candidato a refactor estructural |
| Fachadas con valor | `models/__init__.py`, `tools/__init__.py`, `graph/__init__.py` reexportan; **sí aportan** (ocultan la disposición interna) |
| Registries | `tools/registry.py` (herramientas) y `models/registry.py` (proveedores) — ambos son **datos**, no código, y están cubiertos por tests que afirman los conjuntos exactos |
| Adaptadores | `stt/base.py` (2 adaptadores), `models/providers/` (2 adaptadores). Contratos `Protocol`/ABC correctos |
| Repositorios | `state/store.py` concentra todo el acceso a SQLite. Correcto |

## 5. Duplicación funcional detectada

| Duplicado | Ubicación | Veredicto |
|---|---|---|
| `RunSummary` definido **dos veces** | `contracts/api.py` (líneas 106 y 141 en el commit F10; **corregido en F13**) | **RESUELTO** — el duplicado se eliminó en F13. La segunda definición ganaba en silencio |
| `_git()` en `sandbox.py` y en `evaluation/runner.py` | `sandbox.py::git` (público) y `runner.py::_git` (local) | **Duplicación menor deliberada**: el del runner es un envoltorio de test con `assert` en el fallo; el de `sandbox` es el de producción. **No fusionar** sin cambiar el contrato de errores |
| `_confianza_de` (STT) y heurísticas de confianza | Solo en `stt/base.py` | Sin duplicación |
| Serialización de `Budget` a dict | `models/budget.py` + varios nodos (`{**state.budget.model_dump(), ...}`) | **Patrón repetido 3 veces** en `nodes.py`. Candidato a helper |

## 6. Referencias históricas y wrappers sin valor

| Elemento | Veredicto |
|---|---|
| `route_intent()` en `nodes.py` | Se conserva **explícitamente** como "mapa puro intención→nodo"; ya **no es una arista** del grafo. Es código vivo solo por documentación; candidato a `REQUIRES_MANUAL_REVIEW` |
| `_ruta_estatica_m1()` | Referenciada por la topología como respaldo del plan agotado. Viva |
| `tools/verify_m1_assumptions.py` | Arnés **histórico**: verifica 4 supuestos de M1 (5/5). Sigue siendo ejecutable y su resultado está en el snapshot, pero su fase está cerrada |
| `tools/verify_redaction_mutations.py` | Arnés **específico** de redacción (8 mutaciones), anterior a la generalización de `mutation_check.py`. Posible solape con el arnés general |
| `docs/auditoria-2026-10-06/` (17 ficheros) | Conjunto documental **histórico** de la auditoría externa. Ver `05-…` |

## 7. Conclusión del mapa

- **Sin ciclos.** La arquitectura de dependencias es limpia y va en una sola
  dirección.
- **Un punto de concentración**: `graph/nodes.py`. Es el 40% del código de dominio
  y mezcla 5 agentes con enrutado y guardas.
- **Tres módulos muertos** (`agents/`, `mcp/`, `observability/`) que existen solo
  como marcador de fase futura.
- **Ninguna abstracción no utilizada** más allá de las tres anteriores y
  `contracts/validate.py` (test-only legítimo).
