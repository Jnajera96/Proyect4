# 07 — Auditoría de contratos y datos

> `src/ai_swe/contracts/` (7 ficheros) + `frontend/src/lib/contracts.ts` +
> `frontend/contracts.json` (GENERATED). Commit `065db452`.

## 1. Inventario de contratos

| Fichero | Modelos | Estado |
|---|---|---|
| `contracts/state.py` | `RunStatus`, `InstructionSource`, `TranscriptMeta`, `Instruction`, `RunOptions`, `Budget`, `RunError`, `Artifacts`, `Evidence`, `Outputs`, `RunState` | IMPLEMENTED_AND_VERIFIED |
| `contracts/tasks.py` | `Intent`, `AgentRole`, `SubtaskStatus`, `Scope`, `TaskInterpretation`, `Subtask`, `RunPlan` | IMPLEMENTED_AND_VERIFIED |
| `contracts/outputs.py` | `Severity`, `Finding`, `ResearchOutput`, `FileOperation`, `FileProposal`, `CodeProposal`, `FileChange`, `CodeChange`, `TestRun`, `ReviewDecision`, `ReviewVerdict`, `ApprovalDecision`, `FinalReport`, `Approval` | IMPLEMENTED_AND_VERIFIED |
| `contracts/api.py` | `EventKind`, `EVENTO_POR_NODO`, `Project`, `ProjectRequest`, `RunSummary`, `RunEvent` | IMPLEMENTED_AND_VERIFIED |
| `contracts/tools.py` | `RiskLevel`, `ToolSpec`, `PolicyEffect`, `PolicyDecision` | IMPLEMENTED_AND_VERIFIED |
| `contracts/validate.py` | `find_non_serializable` | Test-only (correcto) |
| `frontend/src/lib/contracts.ts` | Tipos derivados de `contracts.json` | IMPLEMENTED_AND_VERIFIED |

## 2. Fuente única de verdad

**Cadena verificada:**

```
Pydantic (src/ai_swe/contracts/*.py)
   └─► tools/export_contracts.py  (PYTHONPATH=src)
          └─► frontend/contracts.json   (15 contratos exportados, GENERATED)
                 └─► frontend/src/lib/contracts.ts  (deriva tipos con `typeof schemas.X.enum[number]`)
                        └─► componentes React
```

Existe una prueba (`test_el_contrato_exportado_esta_al_dia`) que falla si
`contracts.json` se queda obsoleto. **Verificado en la práctica**: en F12, añadir
`RunState.human_feedback` rompió esa prueba hasta regenerar el fichero. Es una
salvaguarda que **funciona**.

## 3. Duplicados

| Duplicado | Estado | Nota |
|---|---|---|
| `RunSummary` **definido dos veces** en `contracts/api.py` | **RESUELTO en F13** | Existía desde F10; la segunda definición (idéntica) ganaba en silencio. Eliminado |
| `Scope` (contrato) vs `RunOptions.allowed_paths/protected_paths` | **Solapamiento deliberado** | `Scope` añade límites de tamaño; `RunOptions` es lo que pidió el usuario. `_alcance()` los unifica. Documentado |
| `TranscriptMeta` (contrato de estado) vs `Transcript` (contrato STT) | **No duplicado** | Uno describe el audio transcrito, el otro la instrucción ya confirmada |
| `FileChange` vs `FileProposal` | **No duplicado** | Separación explícita: contenido (modelo) vs metadatos derivados (código). Bien razonado en el docstring |

## 4. Campos muertos o de riesgo

| Campo | Situación | Veredicto |
|---|---|---|
| `RunState.schema_version` | Se escribe (`default=SCHEMA_VERSION`), **nunca se lee**: `grep schema_version src/` solo encuentra la declaración | `DEAD_FIELD` funcional. No hay migraciones que lo consuman |
| `RunState.plan_index` | Vivo (F5) | OK |
| `RunOptions.dry_run` | **Verificado**: `grep dry_run src/` solo encuentra la declaración en el contrato. Ningún nodo lo lee. Su descripción promete «ejecuta el flujo sin tocar el repositorio», que **no ocurre** | **`DEAD_FIELD` + documentación falsa.** El único uso está en `tests/test_store.py` como dato de relleno |
| `TestRun.reproducible` | **Verificado**: se declara con «El Reviewer re-ejecuta para confirmar que el resultado es reproducible», pero el Reviewer **no lo escribe ni lo lee** | `DEAD_FIELD` + descripción que describe comportamiento inexistente |
| `Budget.used_input_tokens` / `used_output_tokens` | Añadidos en F14; los lee `evaluation/runner.py` | OK |
| `Budget.max_cost` / `used_cost` | Vivos; por defecto `None` (sin límite declarado) | OK |
| `ModelUsage.cached_tokens` / `reasoning_tokens` | Declarados; el proveedor `fake` no los rellena | OK (opcionales por contrato) |
| `RunSummary.awaiting_approval` | Atajo para el panel | Vivo en la API |
| `ResearchOutput.unknowns` | Obligatorio a propósito | OK |
| `Transcript.low_confidence` | Vivo (umbral STT) | OK |

## 5. Defaults peligrosos

| Default | Riesgo | Valoración |
|---|---|---|
| `RunOptions.dry_run = False` | Un run toca el repositorio por defecto | **Correcto por diseño**: la escritura está confinada al worktree y la promoción exige aprobación humana |
| `RunOptions.allowed_paths = []` | **Vacío = todo el repositorio** | Deliberado y documentado, pero es un default **permisivo** |
| `Scope.max_files_changed = 10`, `max_lines_changed = 400` | Acotan el daño | Correcto |
| `Budget.max_review_cycles = 2` | Acota el bucle | Correcto |
| `Settings.authorized_repos = []` | **Vacío = ninguno autorizado**, pero **no se aplica** | **HIGH**: un control de seguridad declarado que no existe en runtime |
| `ApprovalDecision.APPROVED` como default de `ApproveRequest.decision` | **Un cliente que envíe `{}` aprueba** | **MEDIA-ALTA**: el default de una decisión humana es «sí». Debería ser obligatorio |

## 6. Datos sensibles serializados

| Dato | ¿Se serializa? | Protección |
|---|---|---|
| `Settings.model_api_key` (`SecretStr`) | **No** en `RunState` | `SecretStr` + redactor central |
| Instrucción del usuario | Sí, en `RunState.instruction.text` | Es el dato de trabajo |
| `Transcripción` | Sí, como `Instruction.text` de origen `voice` + `TranscriptMeta` | El audio **nunca** se persiste |
| Rutas del sistema de ficheros | Sí (`repo_path`, `worktree_path`) | Se sirven al cliente en `GET /runs/{id}` |
| Errores del proveedor | Sí, en `RunError.message` (truncado a 4.000) | Redacción en el punto de escritura de eventos |
| Eventos SSE | Sí | `store.append_event` **redacta** antes de persistir (mutación F10 lo protege) |

## 7. Compatibilidad backend ↔ frontend

| Comprobación | Resultado |
|---|---|
| `contracts.json` al día | **Sí** (prueba que lo vigila) |
| Tipos del frontend derivados del contrato | **Sí** (`contracts.ts` usa `typeof schemas.EventKind.enum[number]`) |
| Campos que el frontend lee y el backend no envía | **No detectado** |
| Campos que el backend envía y el frontend ignora | **Sí, varios**: `budget` (tokens, coste, ciclos), `approvals`, `artifacts.diff`, `evidence.test_runs`, `final_report`, `plan`, `errors`. El frontend consume sobre todo `status`, `interpretation` y `outputs.coder_output` |
| `RunState` sin esquema de versión efectivo | Riesgo bajo hoy (un solo cliente), alto si se despliega y evoluciona |

## 8. Conclusión

Los contratos son **la parte más sólida del proyecto**: invariantes cruzados con
`model_validator`, exportación verificada, campos nuevos con default (regla del
proyecto respetada), y una prueba que impide que `contracts.json` se desincronice.

**Debilidades concretas:**
1. `ApproveRequest.decision` con default `APPROVED` — el default de una decisión
   humana es «sí».
2. `authorized_repos` declarado y no aplicado.
3. `schema_version` sin mecanismo de migración.
4. Campos muertos: `TestRun.reproducible`, `RunState.schema_version` (funcionalmente),
   `RunOptions.dry_run` (por verificar).
