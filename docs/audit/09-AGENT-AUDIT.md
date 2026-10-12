# 09 — Auditoría de agentes

> Los agentes **no** viven en `src/ai_swe/agents/` (que es un docstring vacío).
> Viven en `src/ai_swe/graph/nodes.py`. Commit `065db452`.

## Hallazgo estructural previo

`src/ai_swe/agents/__init__.py` (13 líneas, solo docstring) **no contiene código**.
Su docstring describe una estructura («Cada agente escribe solo su propio campo de
salida…») que **sí se cumple**, pero en `graph/nodes.py`. Quien busque los agentes
en `agents/` no los encontrará. → `PLACEHOLDER` + nombre engañoso.

**Verificado**: `grep "_GATEWAY" nodes.py` muestra exactamente **4** puntos de uso:
`interpret` (334), `plan` (558), `coder` (1048) y `reviewer` (1666). El `researcher`
**no llama al modelo**.

---

## 1. Requirements Analyst (`interpret`)

| Campo | Valor |
|---|---|
| Propósito | Clasificar la instrucción (`question`/`inspect`/`modify`/`out_of_scope`) y delimitar el alcance |
| Entrada | `instruction.text`, `options` |
| Salida | `TaskInterpretation` (intent, scope, constraints, confidence, rationale) |
| Prompt | `PROMPT_INTERPRETACION` (español, ~20 líneas) |
| Modelo | Sí, vía `ModelGateway.generate_structured(TaskInterpretation)` |
| Fallback | **Sí**: `_interpretacion_determinista` por vocabulario (`_FUERA_DE_ALCANCE`, `_MODIFICAR`, `_PREGUNTA`, `_INSPECCIONAR`) y **lo declara** en `rationale` + `MODEL_FALLBACK` |
| Herramientas | Ninguna |
| Permisos | Supervisor: conjunto **vacío** en `ROLE_TOOLS` |
| Estado | Lee `instruction`/`options`; escribe `interpretation`, `budget`, `errors` |
| Presupuesto | Consume 1 llamada + tokens |
| Seguridad | El alcance lo fija **el usuario**, no el modelo: `interpretacion.model_copy(update={"scope": _alcance(state)})`. Un modelo no amplía su propio alcance |
| Tests | `test_f3_interpret_analyst.py` |
| **Estado real** | **IMPLEMENTED_AND_VERIFIED** — agente real, con fallback honesto |

## 2. Supervisor (`plan`)

| Campo | Valor |
|---|---|
| Propósito | Producir un `RunPlan` acotado (1..32 subtareas, ids únicos, dependencias acíclicas) |
| Entrada | `interpretation`, `instruction` |
| Salida | `RunPlan` |
| Modelo | Sí |
| Fallback | **Sí**: `_plan_determinista` |
| Herramientas | Ninguna (Supervisor: conjunto vacío) |
| Estado | Escribe `plan`, `budget` |
| Guarda | `_acotar_al_presupuesto_plan`: si el plan pide 5 ciclos y el Budget permite 2, **se recorta y se declara** |
| Tests | `test_f4_supervisor_plan.py` |
| **Estado real** | **IMPLEMENTED_AND_VERIFIED** |

## 3. Researcher (`researcher`)

| Campo | Valor |
|---|---|
| Propósito | Reunir evidencia de solo lectura sobre el repositorio |
| Entrada | `plan.subtasks[plan_index]`, `options.repo_path` |
| Salida | `ResearchOutput` (findings con evidencia, **unknowns obligatorio**, files_read) |
| Modelo | **NO** — determinista |
| Herramientas | `list_files`, `read_file`, `search_text`, `git_status`, `git_log`, `git_diff` |
| Permisos | `ROLE_TOOLS[RESEARCHER]` = 6 de solo lectura; `ROLE_APPROVAL_TOOLS` vacío |
| Estado | Escribe `outputs.researcher_output`, `plan_index` |
| Confinamiento | `_dentro_de(raiz, candidata)` limita el recorrido a `options.repo_path`; extensiones en lista blanca |
| Tests | `test_f5_plan_driven_execution.py` |
| **Estado real** | **IMPLEMENTED_AND_VERIFIED** — **no es un agente de modelo, es lógica determinista de inspección**. Es una decisión de diseño declarada (M1), no un defecto |

## 4. Coder (`coder`)

| Campo | Valor |
|---|---|
| Propósito | Proponer un `CodeProposal` estructurado (archivos + contenido) |
| Entrada | `interpretation`, subtarea actual, hallazgos del Researcher, `human_feedback` (F12) |
| Salida | `CodeChange` **derivado por código**: diff unificado real, conteos y SHA256 |
| Modelo | Sí |
| Fallback | **Sí, pero vacío a propósito**: `_cambio_vacio` — «no hay modelo ⇒ no hay parche». **Nunca inventa un cambio** |
| Herramientas | `read_file`, `write_file`, `apply_patch`, `run_tests`, lectura/git |
| **NO escribe en disco** | El nodo solo produce el objeto; escribir es de `apply_sandbox` (F7) |
| Guarda | `_respetar_limites`: recorta la propuesta al `Scope` (`max_files_changed`, `max_lines_changed`) y **deja rastro** (`SCOPE_TRIMMED`) |
| Estado | Escribe `outputs.coder_output`, `budget`, `plan_index`, `errors` |
| Tests | `test_f6_real_coder.py` |
| **Estado real** | **IMPLEMENTED_AND_VERIFIED** |

## 5. Reviewer (`reviewer`)

| Campo | Valor |
|---|---|
| Propósito | Juzgar el cambio con criterio, **sin escribir** |
| Entrada | Petición, interpretación, subtarea, diff, **evidencia real de pruebas** |
| Salida | `ReviewVerdict` (accept / request_changes / escalate) |
| Modelo | Sí (`reviewer_model` configurable, separado de `model_name`) |
| Fallback | **Sí**: `_veredicto_determinista` — sin pruebas ⇒ `ESCALATE`; todas verdes ⇒ `ACCEPT`; alguna roja ⇒ `REQUEST_CHANGES` |
| **Guardas deterministas** | **REGLA 1** `_guarda_pruebas`: un test en rojo invalida cualquier `ACCEPT`, del modelo o no. **REGLA 2** `_guarda_ciclos`: agotados los ciclos, `REQUEST_CHANGES` → `ESCALATE` |
| Orden de las guardas | **Es la garantía** (REGLA 1 puede *crear* un `REQUEST_CHANGES` que REGLA 2 debe ver). Invertirlas rompe la acotación — hay una mutación que lo demuestra |
| Herramientas | `list_files`, `read_file`, `search_text`, `git_*`, `run_tests`. **Nunca escribe** |
| Estado | Escribe `outputs.reviewer_output`, `budget` |
| Evidencia | Usa `nodes.evidencia_vigente` (F14): la **última** corrida por target, no el histórico. Antes de F14 juzgaba todo el histórico y **el ciclo no podía converger** (`AUD-14`) |
| Tests | `test_f9_reviewer.py`, `test_f14_evaluation.py` |
| **Estado real** | **IMPLEMENTED_AND_VERIFIED** |

## 6. ¿Cuáles son realmente «agentes»?

| Nodo | ¿Llama al modelo? | ¿Es un agente? | Veredicto |
|---|---|---|---|
| `interpret` | Sí | Sí (con fallback) | Agente real |
| `plan` | Sí | Sí (con fallback) | Agente real |
| `researcher` | **No** | **No** | Lógica determinista de inspección |
| `coder` | Sí | Sí (con fallback vacío) | Agente real |
| `reviewer` | Sí | Sí (con fallback + 2 guardas) | Agente real |

**Precisión importante para la defensa.** El sistema tiene **4 puntos de uso del
modelo**, no 5 agentes LLM. El `researcher` es determinista por diseño. Decir «cinco
agentes de IA» sería inexacto; lo correcto es «cuatro agentes asistidos por modelo y
un nodo determinista de inspección, todos coordinados por el grafo».

## 7. Modos de fallo por agente

| Agente | Modo de fallo | Mitigación | ¿Probado? |
|---|---|---|---|
| `interpret` | Proveedor caído / JSON inválido | Fallback determinista + `MODEL_FALLBACK` | Sí |
| `plan` | Plan inválido (ciclos, ids duplicados) | Validadores Pydantic + `_acotar_al_presupuesto_plan` | Sí |
| `researcher` | Repo enorme / binarios | `_MAX_ARCHIVOS=20`, `_MAX_LINEAS_POR_ARCHIVO=4000`, extensión en lista blanca | Sí |
| `coder` | Modelo devuelve cambio vacío | `route_after_coder` → `escalate_no_changes` | Sí |
| `coder` | Modelo propone rutas fuera de alcance | `_respetar_limites` + `patcher` (4 barreras) | Sí |
| `reviewer` | Modelo aprueba con pruebas en rojo | REGLA 1 lo veta | Sí |
| `reviewer` | Bucle sin convergencia | REGLA 2 escala | Sí |

## 8. Riesgos

| Riesgo | Severidad | Comentario |
|---|---|---|
| **Prompt injection indirecta** | MEDIA-ALTA | El Coder y el Reviewer reciben **contenido del repositorio del usuario** (diff, hallazgos). Un repositorio malicioso puede incluir instrucciones en un fichero que el modelo lea. No hay defensa específica (ver `19.7`) |
| **Confianza en la salida del modelo** | BAJA | Mitigada: la salida se valida contra Pydantic, el diff lo genera el código, y las guardas son deterministas |
| **Agencia excesiva** | BAJA | El catálogo no tiene `run_shell` ni `git_push`; la escritura está confinada y la promoción exige humano |
| **Fuga de secretos al prompt** | BAJA | El redactor central + `SecretStr`; los secretos no entran al estado |
