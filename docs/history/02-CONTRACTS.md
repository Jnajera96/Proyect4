# 02 — Contracts

> **Capa de índice.** Alias de nomenclatura. El contenido canónico vive en los
> documentos y en el código enlazados.

## Principio

**Los contratos Pydantic son la puerta absoluta.** Todo lo que cruza un borde
—modelo, API, estado, herramienta— se valida contra un `BaseModel`. Un contrato
no es documentación: es el código que acepta o rechaza el dato.

Dos reglas del proyecto que se derivan de esto:

1. **El modelo propone; el código deriva los metadatos.** El modelo nunca aporta
   un `sha256`: no puede conocer el hash de un fichero que aún no ha escrito.
   Pedírselo solo produciría un dato inventado.
2. **Los campos nuevos entran con valor por defecto.** Solo eliminar o renombrar
   un campo obligatorio sube `SCHEMA_VERSION`.

## Documentos

| Documento | Qué contiene |
|---|---|
| [`auditoria-2026-10-06/04_CONTRATOS_STATE_BUDGET.md`](auditoria-2026-10-06/04_CONTRATOS_STATE_BUDGET.md) | Reglas de contratos, `RunState` y `Budget` |
| [`06-contrato-frontend-backend.md`](06-contrato-frontend-backend.md) | Contrato frontend ↔ backend (vigente) |
| [`frontend/contracts.json`](../frontend/contracts.json) | Contrato exportado para el frontend, **generado** desde el código |

## Código

| Módulo | Contratos |
|---|---|
| [`contracts/state.py`](../src/ai_swe/contracts/state.py) | `RunState`, `Budget`, `Evidence`, `Artifacts`, `RunError`, `RunStatus`, `Instruction`, `RunOptions` |
| [`contracts/tasks.py`](../src/ai_swe/contracts/tasks.py) | `Intent`, `AgentRole`, `Scope`, `TaskInterpretation`, `Subtask`, `RunPlan` |
| [`contracts/outputs.py`](../src/ai_swe/contracts/outputs.py) | `FileOperation`, `FileProposal`, `CodeProposal`, `FileChange`, `CodeChange`, `TestRun`, `ReviewVerdict`, `FinalReport`, `Approval` |
| [`contracts/tools.py`](../src/ai_swe/contracts/tools.py) | `ToolSpec`, `ToolCall`, `ToolResult`, `PolicyDecision`, `PolicyEffect`, `RiskLevel` |
| [`contracts/api.py`](../src/ai_swe/contracts/api.py) | `RunEvent`, `RunSummary`, `EventKind` |

## Invariantes cruzadas que el contrato hace cumplir

Están codificadas en validadores (`model_validator(mode="after")`), no en
comentarios. Ejemplos:

- `Instruction`: una instrucción de origen `voice` **exige** `transcript_meta` y
  `confirmed_by_user=True`. El audio crudo nunca llega al Supervisor.
- `FileProposal`: `delete` no lleva `new_content`; `create`/`modify` lo exigen.
- `RunPlan`: ids únicos, dependencias existentes, detección de ciclos por DFS,
  ≤32 subtareas, `agent != supervisor`, `allowed_tools` no vacío.
- `ReviewVerdict`: `request_changes` **exige** `required_fixes`; un rechazo tiene
  que decir qué corregir o el ciclo de revisión no converge.
- `RunState`: una ejecución terminal no puede tener `next_step`.

El exportador de contratos es [`tools/export_contracts.py`](../tools/export_contracts.py);
regenerar `frontend/contracts.json` es obligatorio cuando cambia un esquema.
