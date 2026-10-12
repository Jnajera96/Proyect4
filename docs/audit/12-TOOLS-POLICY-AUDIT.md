# 12 — Auditoría de herramientas y Policy Engine

> `src/ai_swe/tools/` (registry, policy, runner, patcher, promoter). Commit `065db452`.

## 1. Catálogo de herramientas (11)

| Tool | Propósito | Riesgo | `writes` | `inside_worktree` | `requires_target_allowlist` | Aprobación |
|---|---|---|---|---|---|---|
| `list_files` | Listar con glob y profundidad acotados | NONE | — | — | — | No |
| `read_file` | Leer (rechaza binarios) | NONE | — | — | — | No |
| `search_text` | Buscar literal o regex | NONE | — | — | — | No |
| `git_status` | Estado del worktree | NONE | — | — | — | No |
| `git_log` | Historial | NONE | — | — | — | No |
| `git_diff` | Diff unificado (fuente de verdad del Reviewer) | NONE | — | — | — | No |
| `write_file` | Escribir en el worktree | HIGH | ✅ | ✅ | — | No |
| `apply_patch` | Aplicar parche unificado en el worktree | HIGH | ✅ | ✅ | — | No |
| `run_tests` | Ejecutar target de la lista permitida | MEDIUM | — | — | ✅ | No |
| `git_commit` | Crear confirmación | HIGH | ✅ | — | — | **Sí** |
| `install_dependency` | Instalar dependencia | HIGH | ✅ | — | ✅ | **Sí** |
| `delete_file` | Eliminar archivo | HIGH | ✅ | ✅ | — | **Sí** |

**Invariantes verificadas por `tests/test_policy.py`** (que afirma los conjuntos
**exactos**):
- `run_shell` **no existe** en el catálogo.
- `git_push` **no existe** en el catálogo.
- El Researcher y el Reviewer **no tienen ninguna herramienta de escritura**.

## 2. Matriz de permisos

| Rol | Herramientas libres | Herramientas con aprobación |
|---|---|---|
| `RESEARCHER` | `list_files`, `read_file`, `search_text`, `git_status`, `git_log`, `git_diff` | ∅ |
| `CODER` | las 6 anteriores + `write_file`, `apply_patch`, `run_tests` | ∅ |
| `REVIEWER` | las 6 de lectura + `run_tests` | ∅ |
| `SUPERVISOR` | **∅** | `git_commit`, `install_dependency`, `delete_file` |

El Supervisor **no ejecuta ninguna herramienta**: solo puede *proponer* acciones con
efectos, y todas exigen aprobación humana. Es mínimo privilegio aplicado de verdad.

## 3. Policy Engine

`decide(tool, args, ctx) -> PolicyDecision` — **función pura y determinista**: no
llama a un modelo, no accede a red y no toca el sistema de archivos.

Orden de evaluación (el orden **es** el comportamiento):

| # | Regla | Efecto | `matched_rule` |
|---|---|---|---|
| 1 | La herramienta existe en el catálogo | DENY | `POLICY-DEFAULT-DENY` |
| 2 | El rol la tiene permitida | DENY | `POLICY-ROLE-NOT-PERMITTED` |
| 2b | La subtarea la declara (solo restringe) | DENY | `POLICY-SUBTASK-SCOPE` |
| 3 | Ruta válida (sintaxis + alcance + protegidas) | DENY / APPROVAL | `POLICY-PATH-*` |
| 3b | Target en la lista permitida | DENY | `POLICY-TARGET-NOT-ALLOWLISTED` |
| 4 | Queda presupuesto | APPROVAL | `POLICY-BUDGET-EXHAUSTED` |
| 5 | Acción con efectos | APPROVAL | `POLICY-EFFECT-REQUIRES-APPROVAL` |
| 6 | Permitir | ALLOW | `POLICY-ALLOW-BY-ROLE` |

**Detalle bien resuelto**: la validación de argumentos (3) ocurre **antes** de la
aprobación (5). Una ruta que escapa del worktree se **deniega**, no se convierte en
una solicitud de aprobación — «pedir permiso para algo prohibido es una forma de
normalizarlo».

## 4. Arquitectura Agent → Tool → Policy → Executor

```
Agente (nodo)
   │  decide(tool, args, DecisionContext)
   ▼
Policy Engine  ──►  ALLOW | DENY | REQUIRE_APPROVAL
   │
   ├── DENY            → se registra y no se ejecuta
   ├── REQUIRE_APPROVAL→ se detiene y se pide al humano
   └── ALLOW
          ▼
      Executor (patcher | runner)
          │  · confina la ruta (4 barreras)
          │  · subprocess con shell=False y lista de argumentos
          ▼
      ToolResult (ResultadoAplicacion | TestRun)
```

### ¿Hay bypasses?

| Camino | ¿Pasa por la política? | Evidencia |
|---|---|---|
| `patcher.aplicar` (escritura) | ✅ **Sí**, por archivo: `normalize_rel_path` + `path_within_scope` + `decide` + `resolver_destino` | `tools/patcher.py::_veredicto_de_escritura` |
| `runner.ejecutar_target` (pruebas) | ✅ Sí: el target se valida contra la lista permitida | `tools/runner.py` |
| `promoter.promover` (F12) | ✅ Sí: repositorio autorizado + integridad + `normalize_rel_path` + `path_within_scope` + protegidas | `tools/promoter.py` |
| `sandbox.escribir` | ✅ `resolver_destino` (confinamiento físico) | `sandbox.py` |
| **`sandbox.diff()` / `archivos_modificados()`** | ⚠️ Ejecutan `git` **sin** pasar por la política | Aceptable: son de solo lectura dentro del worktree |
| **`nodes.apply_sandbox` → `sandbox.crear`** | ⚠️ Crea el worktree sin consultar la política | Aceptable: `crear` valida que el destino no esté dentro del repo fuente |

**No se detecta ningún bypass de escritura.** Las cuatro barreras del patcher están
documentadas y probadas (`test_f7_sandbox.py`).

## 5. `run_tests`: la tabla cerrada

`TARGET_COMMANDS` mapea 3 identificadores a **tuplas de argumentos**:

| Target | Comando |
|---|---|
| `pytest.unit` | `[sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "-m", "not real_provider", "tests"]` |
| `pytest.integration` | idem con `-m integration` |
| `ruff.check` | `[sys.executable, "-m", "ruff", "check", "."]` |

**No existe ninguna vía por la que una cadena llegue a una shell**: ni del modelo,
ni de la configuración, ni del estado, ni del usuario. `shell=False` en los tres
puntos de `subprocess` de producción (`sandbox.py`, `tools/runner.py`,
`evaluation/runner.py`). Hay una **mutación** (`F8: el runner lanza el comando con
shell=True`) que lo protege.

## 6. Riesgos

| # | Riesgo | Tipo | Severidad |
|---|---|---|---|
| 1 | `install_dependency` está en el catálogo y **exige aprobación**, pero no está implementado (no hay executor) | PLANNED | INFO |
| 2 | `git_commit` y `delete_file` están en el catálogo como «requieren aprobación» pero **no tienen executor**: nadie los invoca | PLANNED | INFO |
| 3 | `_TIEMPO_GIT_S = 120 s` es global para todas las operaciones de git | HARDENING | BAJA |
| 4 | El Policy Engine no limita el **número** de escrituras dentro de un cambio (lo hace `Scope.max_files_changed`) | — | OK |

> **Precisión.** El catálogo declara 11 herramientas, pero solo **6 tienen executor
> real** (`list_files`, `read_file`, `search_text`, `git_*`, `write_file`,
> `apply_patch`, `run_tests` vía patcher/runner). `git_commit`,
> `install_dependency` y `delete_file` existen como **declaración de política**
> (para que el Supervisor no pueda ejecutarlas sin humano) pero **no hay código que
> las ejecute**. Es correcto que existan: su función es *negar por defecto*.

## 7. Conclusión

**IMPLEMENTED_AND_VERIFIED.** Es la pieza de seguridad mejor construida del
proyecto: catálogo cerrado, mínimo privilegio por rol, política pura y determinista,
orden de reglas justificado, y ejecución sin shell en ningún punto. Los conjuntos de
permisos están afirmados por tests que **romperían** si alguien ampliara un permiso
por descuido.
