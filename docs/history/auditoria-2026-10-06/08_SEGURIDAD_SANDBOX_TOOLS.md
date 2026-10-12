> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 08 — Seguridad, sandbox y herramientas

```text
Agent
  ↓
ToolCall estructurado
  ↓
Policy Engine
  ↓
Allowlist + Path confinement + Budget
  ↓
Tool Executor
  ↓
Worktree / Sandbox
  ↓
ToolResult
```

## Antes de habilitar escritura
- worktree/workspace aislado por run,
- confinamiento de rutas,
- allowlist de comandos/targets,
- timeout,
- límite de tool calls,
- límite de tokens/costo,
- sin shell arbitrario,
- HITL para acciones sensibles.

## HITL obligatorio para
- promover cambios al repo principal,
- borrar archivos críticos,
- instalar paquetes fuera de allowlist,
- acceso de red no previsto,
- Git destructivo,
- deploy.
