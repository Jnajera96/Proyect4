# BASELINE M1 — Reporte post-integración documental

**Fecha:** 2026-10-06
**Ámbito:** integración de la documentación actualizada, reconciliación contra el
código real, protección del estado M1 y preparación (sin ejecución) de M2.
**Resultado:** línea base **`M1 VERIFIED BASELINE`** creada y congelada.

> **Estado final de esta sesión: DETENIDO.** No se ha iniciado M2. No se ha
> conectado ningún LLM. No se ha implementado `ModelGateway` ni ningún agente.
> No se ha instalado MCP, Graphify ni faster-whisper. La decisión de autorizar M2
> es del usuario.

---

## 1. Estado real actual

El proyecto (raíz real: `proyecto4-ai-swe/`) está en una **fase M1 sólida de
infraestructura y orquestación**. Revalidado en esta sesión contra el código:

**Verificado y funcionando**

- API FastAPI con 8 rutas (`/health`, `/transcriptions`, `/runs` ×2, `/runs/{id}`,
  `/runs/{id}/events` SSE, `/runs/{id}/approve`, `/runs/{id}/cancel`→501).
- LangGraph `StateGraph(RunState)` con 12 nodos y 5 routers, compilado por hilo.
- Persistencia SQLite: checkpointer + estado inicial + índice + registro de eventos.
- Worker en pool de hilos (`ThreadPoolExecutor`, 4 hilos).
- SSE con `id:` por evento y reanudación por `Last-Event-ID`.
- Frontend servido en el mismo origen, verificado en Chrome headless real.
- HITL real: pausa, **aprobación y rechazo** verificados de extremo a extremo.
- Policy Engine con denegación por defecto y confinamiento de rutas.
- Terminación garantizada (`MET-13 = 0`).
- 153 pruebas aprobadas · 24/24 mutaciones cazadas.

**Parcial**

- Researcher: lee el repositorio de verdad, confinado, pero sin recuperación
  semántica (trunca a 20 ficheros).
- Reviewer: determinista, sin evaluación semántica del diff.
- STT: contrato + `FakeAdapter` funcionan; adapter real pendiente.
- Observabilidad: eventos persistentes sí; Langfuse / logs JSON / métricas no.

**No implementado**

LLM · `ModelGateway` · prompts · Requirements Analyst · Supervisor con
razonamiento · Coder real · Test Runner real · Tool Executor · MCP · Graphify ·
memoria semántica · STT real · observabilidad completa · autenticación ·
redacción de secretos · worktree aislado.

---

## 2. Cambios documentales realizados

| # | Cambio | Motivo |
|---|---|---|
| 1 | Integrado el conjunto `docs/auditoria-2026-10-06/` (18 ficheros) | Incorporar la documentación nueva a una ubicación clara, **sin sobrescribir** nada |
| 2 | Creado `docs/auditoria-2026-10-06/_PROCEDENCIA.txt` | Registrar origen y **jerarquía de evidencia** aplicada |
| 3 | Añadida cabecera de procedencia a los 15 documentos `.md` | Que ningún documento se lea fuera de su contexto |
| 4 | Creado `docs/README.md` | Índice con las **dos capas** (estado vigente vs. diseño histórico) y regla de desempate |
| 5 | Aviso `SUPERSEDED` en `docs/01-arquitectura.md` | `RF-14` y `RF-16` documentados como si existieran |
| 6 | Aviso `SUPERSEDED` en `docs/03-flujo-e-implementacion.md` | Traza de ejemplo usa herramientas inexistentes; roadmap §3.11 reemplazado por `F0`–`F16` |
| 7 | Aviso `SUPERSEDED` en `docs/05-graphify-evaluacion.md` | Reforzar que Graphify es propuesta, no implementación |
| 8 | Nota de estado en `docs/02-tecnologias.md` | Señalar que `mcp` estaba mal clasificada |
| 9 | Nota de estado en `docs/06-contrato-frontend-backend.md` | Confirmar vigencia verificada |
| 10 | `README.md`: `151` → `153` pruebas (2 sitios) | Inconsistencia real |
| 11 | `README.md`: tabla de estado ampliada | Separar lo verificado de lo **no implementado** con nombre propio |
| 12 | `README.md`: aviso de "no atribuir lo que no se demuestra" | Que el README no insinúe agentes/MCP/STT inexistentes |
| 13 | `README.md`: aviso de ausencia de lockfile + enlace al plan | Deuda de reproducibilidad declarada |
| 14 | `pyproject.toml`: `mcp` movida a extra opcional | Declarada obligatoria sin estar instalada ni usarse |
| 15 | `.gitignore` endurecido | Añadidos `*.sqlite3-wal/-shm`, temporales, secretos; eliminada línea duplicada |
| 16 | Creado `docs/auditoria-2026-10-06/12-bis_PLAN_REPRODUCIBILIDAD.md` | Plan de lock **documentado antes de ejecutarlo** (exigencia de `F1`) |

**Ninguna decisión arquitectónica correcta fue modificada.** No se tocó
LangGraph, `RunState`, persistencia, SSE, HITL, Policy Engine, contratos, nodos,
routers ni pruebas. Ver §16.

---

## 3. Archivos añadidos

| Ruta | Qué es |
|---|---|
| `docs/README.md` | Índice de documentación y jerarquía de evidencia |
| `docs/auditoria-2026-10-06/` (18 ficheros) | Conjunto documental nuevo + `_PROCEDENCIA.txt` + `12-bis_PLAN_REPRODUCIBILIDAD.md` |
| `.gitattributes` | Normalización LF en el repositorio; binarios excluidos |
| `.python-version` | Fija `3.13` |

## 4. Archivos modificados

| Ruta | Cambio |
|---|---|
| `README.md` | Estado honesto ampliado; `151`→`153`; avisos de lockfile y de no atribuir |
| `pyproject.toml` | `mcp` de dependencia base → extra `[mcp]` |
| `.gitignore` | WAL/SHM, temporales, secretos; duplicado eliminado |
| `docs/01-arquitectura.md` | Cabecera `SUPERSEDED` (parcial) |
| `docs/02-tecnologias.md` | Nota de estado sobre `mcp` |
| `docs/03-flujo-e-implementacion.md` | Cabecera `SUPERSEDED` (parcial) |
| `docs/05-graphify-evaluacion.md` | Cabecera `SUPERSEDED` (parcial) |
| `docs/06-contrato-frontend-backend.md` | Nota de estado vigente |

## 5. Documentos reemplazados o superseded

**Ninguno fue borrado.** La documentación histórica se conserva íntegra.

| Documento | Grado | Qué queda superseded |
|---|---|---|
| `docs/01-arquitectura.md` | **parcial** | El **estado** de `RF-14` y `RF-16`. El diseño y las `DEC-xx` siguen vigentes |
| `docs/03-flujo-e-implementacion.md` | **parcial** | El roadmap de §3.11 (reemplazado por `F0`–`F16`) y la traza-objetivo de §2 |
| `docs/05-graphify-evaluacion.md` | **parcial** | Nada del contenido; se refuerza que es `[PROP]` no implementada |
| `docs/02`, `04`, `06` | **no superseded** | Se añade nota de estado; contenido vigente |

---

## 6. Estado Git

```
$ git rev-parse --show-toplevel
C:/Users/jose_/Desktop/repo_proyect/proyecto4-ai-swe      ← ✔ el proyecto mismo

$ git log --oneline
23a6375 Anadir .gitattributes: normalizacion LF en el repositorio
11a13cb M1 VERIFIED BASELINE

$ git remote -v
(vacío)                                                   ← ✔ sin remoto

$ git status --short
(vacío tras el commit de cierre)                          ← ✔ árbol limpio
```

## 7. Repositorio raíz

- **Antes:** `git rev-parse --show-toplevel` desde el proyecto devolvía
  `<WORKSPACE>` — la raíz del **repo padre perteneciente a OTRO proyecto**
  (`pc_lab.git`, único commit `"Update print statement from 'Hello' to 'Goodbye'"`).
- **Ahora:** el proyecto tiene **su propio** repositorio en `proyecto4-ai-swe/.git`.
- **No se tocó el repositorio padre.** No se borró su historial, no se hizo
  `push`, `pull`, `fetch` ni `clone`, y **no se configuró ningún remote**.
- 75 ficheros versionados. Se verificó con `git check-ignore` que **ningún**
  fichero sensible (`.env`, `var/state.sqlite3*`, `*.mutation_backup`,
  `_mutation_*`, `frontend/_verify*`) entra en el repositorio.

## 8. Estado del lockfile

**🔴 No existe lockfile.** No se generó en esta sesión: la fase `F1` exige
documentar el mecanismo *antes* de ejecutarlo, y eso es exactamente lo que se
hizo.

- Herramienta elegida: **`uv` 0.12.0** (ya disponible, **no instalada** por esta sesión).
- Descartado `pip freeze > requirements.txt` (congelaría ~90 paquetes ajenos al
  proyecto, dando falsa ilusión de reproducibilidad).
- **Punto de decisión pendiente para el usuario:** `langgraph>=0.2` declarado vs.
  `1.2.14` instalado. Ver `12-bis_PLAN_REPRODUCIBILIDAD.md` §4.
- Añadido `.python-version` con `3.13`.
- **Ninguna versión de dependencia fue actualizada ni degradada.**

## 9. Dependencias relevantes

Base declarada (9): `fastapi>=0.115`, `uvicorn[standard]>=0.30`,
`python-multipart>=0.0.9`, `pydantic>=2.9`, `pydantic-settings>=2.5`,
`langgraph>=0.2`, `langgraph-checkpoint-sqlite>=2.0`, `httpx>=0.27`,
`sse-starlette>=2.1`.

Extras (4): `[mcp]`, `[voice]`, `[observability]`, `[dev]`.

**Corrección aplicada:** `mcp>=1.0` era dependencia **base** sin estar instalada
ni importarse. Movida a extra `[mcp]`. La instalación limpia ya no instala un
paquete que nadie usa.

---

## 10. Tests ejecutados

| Suite | Comando | Encontrados |
|---|---|---|
| Pruebas unitarias/integración | `pytest -q` | **153** |
| Supuestos M1 | `tools/verify_m1_assumptions.py` | 5 supuestos + 3 auto-mutaciones |
| Frontend en motor real | `tools/verify_frontend.py` | 11 comprobaciones |
| Mutaciones | `tools/mutation_check.py` | 24 mutaciones |

## 11. Resultado de tests

| Suite | Aprobados | Fallidos | Duración |
|---|---|---|---|
| `pytest -q` | **153** | **0** | ~9 s |
| Supuestos M1 | **5/5** + **3/3** auto-mutaciones | 0 | ~28 s |
| Frontend | **11/11** | 0 | ~16 s |
| Mutaciones | **24/24 cazadas** | 0 | ~108 s |

**Total: 0 fallos.** Distribución de las 153: `test_policy` 46 · `test_workflow` 39
· `test_api` 26 · `test_contracts` 22 · `test_diagram_layout` 13 · `test_store` 7.

## 12. Resultado de mutaciones

**24/24 cazadas** — re-ejecutado en esta sesión, no heredado del informe previo.
`arbol restaurado y suite en verde`. El verificador restauró el árbol
correctamente; `git status` tras la tanda mostró **solo** los dos ficheros nuevos
de esta sesión, ninguna mutación residual.

## 13. Resultado del frontend

**11/11 OK** en Chrome headless real (no un shim de DOM):
`N_ERRORS 0` · `CONTRATOS 15` · `FILAS_TIMELINE 8` ·
`TIPOS run.created,run.started,run.step×3,run.status,run.report,run.done` ·
`CHIP_ESTADO completada` · `SIN_SCROLL_HORIZONTAL true` ·
`almacen arranco aislado y limpio`.

> `verify_frontend.py` ejecuta la comprobación **sobre el código actual**, que es
> lo que la hace válida: una verificación que pasó antes del último cambio no
> prueba nada sobre el árbol actual.

---

## 14. Inconsistencias restantes

| # | Inconsistencia | Estado |
|---|---|---|
| 1 | ~~`README.md` decía 151 pruebas~~ | ✅ **corregido** → 153 |
| 2 | ~~`mcp` como dependencia obligatoria sin usar~~ | ✅ **corregido** → extra |
| 3 | ~~`RF-14`/`RF-16` documentados como existentes~~ | ✅ **marcados `SUPERSEDED`** |
| 4 | ~~`.gitignore` sin `*.sqlite3-wal/-shm` ni secretos~~ | ✅ **corregido** |
| 5 | `langgraph>=0.2` declarado vs. `1.2.14` instalado | 🔴 **pendiente de decisión** (`12-bis` §4) |
| 6 | **Sin lockfile** | 🔴 pendiente (`F1`) |
| 7 | **Docker/Docker Compose sin verificar** | 🟡 no se construyó la imagen en esta sesión |
| 8 | **Suite de evaluación descrita pero sin ficheros**: `data/tasks/README.md` detalla un esquema YAML; hay **0 ficheros YAML** | 🔴 pendiente (`F11`) |
| 9 | Directorios residuales `tmp8g9yx7zt/`, `tmpq6zgqajo/` en la raíz | 🟡 ahora **ignorados por Git**, pero siguen en disco |
| 10 | Cifras de latencia del README ("5 ms", "antes 166 ms") | ⚫ **no re-verificadas** |

## 15. Riesgos restantes

| # | Riesgo | Severidad | Estado |
|---|---|---|---|
| 1 | **Sin autenticación**: cualquiera ve todas las ejecuciones | 🔴🔴🔴 | Mitigado parcialmente: no debe exponerse fuera de localhost |
| 2 | **Sin lockfile**: instalaciones no reproducibles | 🟡🟡 | Plan documentado (`F1`) |
| 3 | **El "AI System" sigue sin IA** hasta `F2`–`F6` | 🔴🔴 | Declarado; es el objeto de M2 |
| 4 | **`RNF-S3` sin implementar**: `model_api_key` no se redacta | 🟡🟡 | No explotable aún (sin LLM); debe resolverse **antes** de `F2` |
| 5 | **`RNF-D2` sin planificar**: sin reintentos ni idempotencia | 🟡🟡 | El `ModelGateway` de `F2` debe incluirlo por diseño |
| 6 | **Clasificador por palabras clave**: frágil | 🟡 | Desaparece en `F4` con el Supervisor real |
| 7 | **SSE sondea la BD cada 50 ms**: ~2.000 consultas/s con 100 clientes | 🟡 | Declarado; primer cuello de botella |
| 8 | **Sin versionado remoto**: el baseline vive solo en disco local | 🟡 | **No se puede resolver sin autorización** (crear remoto) |

> **Riesgo cerrado en esta sesión:** "el proyecto no está versionado" — **ya no
> aplica**. Existe un repositorio propio con línea base. El riesgo residual es que
> el respaldo sigue siendo **local**: un fallo de disco lo destruiría igual.

---

## 16. Componentes protegidos (NO modificados)

Verificado por `git diff` entre el árbol actual y el baseline: **ninguno de estos
ficheros fue alterado** en esta sesión.

| Componente | Fichero | Estado |
|---|---|---|
| LangGraph como orquestador | `graph/workflow.py` | ✅ intacto |
| Nodos y routers | `graph/nodes.py` | ✅ intacto |
| Motor y red MET-13 | `graph/engine.py` | ✅ intacto |
| Worker | `graph/worker.py` | ✅ intacto |
| `RunState` tipado | `contracts/state.py` | ✅ intacto |
| Contratos | `contracts/*.py` | ✅ intactos |
| Persistencia SQLite + checkpointer | `state/store.py` | ✅ intacto |
| API y SSE | `api/app.py` | ✅ intacto |
| HITL | `nodes.py` (`approval_gate`) | ✅ intacto |
| Policy Engine | `tools/policy.py` | ✅ intacto |
| Matriz de permisos | `tools/registry.py` | ✅ intacto |
| Contrato STT | `stt/base.py` | ✅ intacto |
| Exportación de contratos | `tools/export_contracts.py` | ✅ intacto |
| Suite de pruebas | `tests/*.py` (6 ficheros) | ✅ intactas — **no se eliminó ni una prueba** |

**No se refactorizó nada por gusto.** La única modificación a código de
producción fue `pyproject.toml` (clasificación de una dependencia) y `.gitignore`.

---

## 17. Estado de preparación para M2

La infraestructura **puede soportar** el flujo de M2, comprobado contra el código:

| Requisito de M2 | ¿Soportado? | Cómo |
|---|---|---|
| `ModelGateway` como frontera única | ✅ hueco listo | Los campos `model_*` de `config.py` esperan consumidor; `contracts/` valida todo output |
| Requirements Analyst antes del Supervisor | ✅ | `interpret` es el nodo de entrada; se le antepone un nodo |
| `RunPlan` / `Subtask` con dependencias | ✅ **ya existen y están probados** | `contracts/tasks.py` con detección de ciclos (mutación cazada) |
| Coder produce `CodeChange` | ✅ contrato ya existe | `CodeChange` + `FileChange` con `sha256` |
| Cambio aplicado en workspace aislado | ✅ ruta libre | `settings.workspace_root` declarado; **falta el código** |
| Tool Executor con Policy en cada llamada | ✅ política ya existe | `tools/registry.py` + `tools/policy.py` |
| Test Runner | ✅ enumeración ya existe | `allowed_test_targets`; el nodo ya pasa por Policy |
| Reviewer con veredicto estructurado | ✅ contrato ya existe | `ReviewVerdict` con 3 decisiones |
| Ciclo acotado por budget y `max_review_cycles` | ✅ **ya funciona** | `route_after_review`; mutación cazada |
| HITL al aceptar | ✅ **ya funciona** | Verificado end-to-end |
| Estado terminal garantizado | ✅ **ya funciona** | Red MET-13 |
| Budget consumido por cada llamada | 🟡 parcial | `Budget` existe y `policy.py` lo consume; **nadie lo incrementa** — debe hacerlo el `ModelGateway` |

**Conclusión:** la infraestructura está **preparada**. No requiere rediseño: el
trabajo de M2 consiste en **rellenar huecos ya definidos por los contratos**, no
en cambiar la arquitectura.

### Decisiones arquitectónicas de M2 — registradas

Quedan documentadas en `docs/auditoria-2026-10-06/` (05, 06, 07, 08) y en
`13_PROXIMO_PROMPT_AGENTE.md`. Resumen verificado contra el código actual:

1. Los agentes **no** importarán SDKs de proveedor → único `ModelGateway`. ✅ compatible
2. El LLM razona y propone; el código determinista valida esquemas, permisos,
   rutas, budgets, estados, ciclos y terminación. ✅ **ya es el diseño actual**
3. El Coder **no** escribe en el workspace principal: produce `CodeChange` y un
   componente autorizado lo aplica en un worktree aislado. ✅ ruta prevista
4. **Nunca** `shell=True` con contenido generado por un LLM. ✅ coherente con el
   catálogo actual (no existe `run_shell`)
5. Toda tool pasa por `Agent → ToolCall → Policy → Tool Executor → ToolResult`. ✅
6. Graphify, MCP y STT real **no** son requisito del MVP M2. ✅
7. **Autenticación obligatoria antes de exponer fuera de localhost.** ✅

### Budget — verificado contra el contrato real

`contracts/state.py::Budget` contiene hoy:

| Requerido por la documentación | En `Budget` | Nota |
|---|---|---|
| `max_tokens` / `used_tokens` | ✅ | |
| `max_calls` / `used_calls` | 🟡 **parcial** | Hay `max_tool_calls`/`used_tool_calls`. **Falta el par de llamadas al modelo** → añadir en `F2` |
| `max_cost` / `used_cost` | 🔴 **ausente** | Debe añadirse en `F2` |
| `max_seconds` / `deadline` | 🟡 | Hay `max_seconds`/`elapsed_seconds`. `deadline` (absoluto) no; `elapsed` cubre el caso |
| `max_review_cycles` | ✅ | `review_cycles_used` |

Además existe `Budget.exhausted`, que `policy.py` **ya consume**. El punto de
enganche está hecho; falta que el `ModelGateway` **incremente** los contadores.

---

## 18. Acciones pendientes antes de M2

En orden. **Ninguna se ha ejecutado.**

| # | Acción | Fase | Bloquea M2 |
|---|---|---|---|
| 1 | Decidir `langgraph>=0.2` vs `>=1.2` y generar el lockfile con `uv` | `F1` | Sí (reproducibilidad) |
| 2 | **Implementar redacción de secretos** (`RNF-S3`) antes de que exista una clave que redactar | pre-`F2` | **Sí — es más barato antes que después** |
| 3 | Añadir a `Budget`: `max_model_calls`/`used_model_calls` y `max_cost`/`used_cost` | `F2` | No, pero son parte de `F2` |
| 4 | Definir el contrato de `ModelGateway` + adaptador falso determinista para tests | `F2` | No — es `F2` |
| 5 | Decidir política de exposición: si se sale de `localhost`, autenticación primero | `F16` | Sí, si hay exposición |
| 6 | Verificar `Dockerfile`/`docker-compose` o retirar la promesa del README | `F1` | No |
| 7 | Crear las tareas YAML de evaluación o retirar `data/tasks/README.md` | `F11` | No |
| 8 | Autorizar un remoto Git para respaldar la línea base | `F0` | No, pero es protección real |

**Recomendación de orden:** `F1` (lock) → **redacción de secretos** → `F2`
(`ModelGateway`) → `F3` (Requirements Analyst) → `F4` (Supervisor). La redacción de
secretos se recomienda **antes** de `F2` y no con ella, porque es un requisito de
seguridad que se verifica mejor cuando la clave todavía no existe.

---

## Matriz final

Componente | Estado | Evidencia

| Componente | Estado | Evidencia |
|---|---|---|
| **LangGraph** | ✅ Implementado y verificado | `graph/workflow.py`; 153 pruebas; mutación "red MET-13 desactivada" cazada; `verify_m1_assumptions` A1–A4 OK |
| **RunState** | ✅ Implementado y verificado | `contracts/state.py`; round-trip de checkpoint probado; mutación "checkpoint sin tipos de contrato" cazada |
| **Persistencia** | ✅ Implementada y verificada | SQLite WAL; 5 tablas; reanudación **entre procesos** (`verify_m1_assumptions` A3) |
| **SSE** | ✅ Implementado y verificado | 8 eventos en navegador real; cierre en `run.done`; `id:` por evento |
| **Frontend** | ✅ Implementado y verificado | 11/11 en Chrome headless; `N_ERRORS 0`; 4 mutaciones de frontend cazadas |
| **HITL** | ✅ Implementado y verificado | Pausa → `awaiting_approval`; aprobar → `completed`; rechazar → `needs_human` |
| **Policy Engine** | ✅ Implementado y verificado | Denegar por defecto, rutas, presupuesto, allowlist; 4 mutaciones cazadas |
| **Requirements Analyst** | 🔴 Ausente | `interpret` es un clasificador de palabras clave; `interpret` ≠ analista. Fase `F3` |
| **Supervisor** | 🔴 Ausente como agente | Rutas fijas; `RunPlan` existe pero `state.plan` siempre `None`. Fase `F4` |
| **Researcher** | 🟡 Parcial | `nodes.py:168` lee el repo real y confinado; sin recuperación semántica; trunca a 20 |
| **Coder** | 🔴 Ausente | `nodes.py:296`: `files_changed=[]` deliberado; toda tarea MODIFY → `needs_human` |
| **Test Runner** | 🔴 Ausente | `nodes.py:347`: `TEST_EXECUTOR_NOT_IMPLEMENTED`; **no fabrica evidencia** |
| **Reviewer** | 🟡 Parcial | Lógica determinista correcta sobre `exit_code`; sin evaluación del diff |
| **Model Gateway** | 🔴 Ausente | Cero llamadas a LLM; cero imports de proveedor; campos `model_*` sin consumidor |
| **MCP** | 🔴 Ausente | `mcp/__init__.py` = 13 líneas de docstring; cero imports; dependencia movida a extra. Fase `F13` |
| **Graphify** | 🔴 Ausente | `docs/05` es propuesta `[PROP]`; sin código. Fase `F12` |
| **STT** | 🟡 Parcial | `FakeAdapter` funciona (verificado por HTTP); `FasterWhisperAdapter` lanza `NotImplementedError`. Fase `F14` |
| **Observabilidad** | 🟡 Parcial | Eventos persistentes ✅; Langfuse / logs JSON / métricas / redacción 🔴. Fase `F15` |
| **Git** | ✅ Implementado y verificado | Repo propio; commit `11a13cb` `M1 VERIFIED BASELINE`; sin remoto; 75 ficheros; exclusiones verificadas con `git check-ignore` |
| **Reproducibilidad** | 🟡 Parcial | `.python-version` ✅; `.gitignore` endurecido ✅; **lockfile 🔴**; plan documentado en `12-bis` |

---

**Fin del reporte. Sesión detenida.**

No se inicia M2. No se conecta ningún LLM. No se implementa `ModelGateway` ni
nuevos agentes. No se instala Graphify, MCP ni faster-whisper. La línea base
`M1 VERIFIED BASELINE` (commit `11a13cb`) queda congelada para revisión.
