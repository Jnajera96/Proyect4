"""Catalogo de herramientas y matriz de permisos.

La matriz es **dato**, no comentarios ni instrucciones en un prompt. Esto es lo
que la hace verificable: tests/test_policy.py afirma los conjuntos exactos, de
modo que ampliar un permiso por descuido rompe la suite.

Invariantes que se comprueban en pruebas:
  - `run_shell` no existe en el catalogo.
  - `git_push` no existe en el catalogo.
  - El Researcher y el Reviewer no pueden escribir.
"""

from __future__ import annotations

from ai_swe.contracts.tasks import AgentRole
from ai_swe.contracts.tools import RiskLevel, ToolSpec

# ------------------------------------------------------------------ catalogo
TOOLS: dict[str, ToolSpec] = {
    "list_files": ToolSpec(
        name="list_files",
        description="Lista archivos bajo una ruta, con glob y profundidad acotados.",
        risk=RiskLevel.NONE,
    ),
    "read_file": ToolSpec(
        name="read_file",
        description="Lee un archivo, opcionalmente un rango de lineas. Rechaza binarios.",
        risk=RiskLevel.NONE,
    ),
    "search_text": ToolSpec(
        name="search_text",
        description="Busca texto literal o expresion regular en el repositorio.",
        risk=RiskLevel.NONE,
    ),
    "git_status": ToolSpec(name="git_status", description="Estado del worktree.", risk=RiskLevel.NONE),
    "git_log": ToolSpec(name="git_log", description="Historial de confirmaciones.", risk=RiskLevel.NONE),
    "git_diff": ToolSpec(
        name="git_diff",
        description="Diff unificado. Es la fuente de verdad del Reviewer.",
        risk=RiskLevel.NONE,
    ),
    "write_file": ToolSpec(
        name="write_file",
        description="Escribe un archivo dentro del worktree de la ejecucion.",
        risk=RiskLevel.HIGH,
        writes=True,
        inside_worktree=True,
    ),
    "apply_patch": ToolSpec(
        name="apply_patch",
        description="Aplica un parche unificado dentro del worktree. Preferida sobre write_file.",
        risk=RiskLevel.HIGH,
        writes=True,
        inside_worktree=True,
    ),
    "run_tests": ToolSpec(
        name="run_tests",
        description="Ejecuta un objetivo de prueba de la lista permitida. No acepta comandos libres.",
        risk=RiskLevel.MEDIUM,
        requires_target_allowlist=True,
    ),
    "git_commit": ToolSpec(
        name="git_commit",
        description="Crea una confirmacion. Requiere aprobacion humana.",
        risk=RiskLevel.HIGH,
        writes=True,
    ),
    "install_dependency": ToolSpec(
        name="install_dependency",
        description="Instala una dependencia. Fuera de alcance del prototipo; requiere aprobacion.",
        risk=RiskLevel.HIGH,
        writes=True,
        requires_target_allowlist=True,
    ),
    "delete_file": ToolSpec(
        name="delete_file",
        description="Elimina un archivo. Requiere aprobacion humana.",
        risk=RiskLevel.HIGH,
        writes=True,
        inside_worktree=True,
    ),
}

# Nombre del argumento que se valida contra la lista permitida.
ALLOWLIST_ARGS: dict[str, str] = {
    "run_tests": "target",
    "install_dependency": "package",
}

# ------------------------------------------------------------------- permisos
# Conjuntos DISJUNTOS en lo que importa: el Researcher y el Reviewer no tienen
# ninguna herramienta de escritura.
ROLE_TOOLS: dict[AgentRole, frozenset[str]] = {
    AgentRole.RESEARCHER: frozenset(
        {"list_files", "read_file", "search_text", "git_status", "git_log", "git_diff"}
    ),
    AgentRole.CODER: frozenset(
        {
            "list_files",
            "read_file",
            "search_text",
            "git_status",
            "git_log",
            "git_diff",
            "write_file",
            "apply_patch",
            "run_tests",
        }
    ),
    AgentRole.REVIEWER: frozenset(
        {"list_files", "read_file", "search_text", "git_status", "git_log", "git_diff", "run_tests"}
    ),
    # El Supervisor no ejecuta herramientas de codigo: solo puede proponer
    # acciones con efectos, y todas exigen aprobacion.
    AgentRole.SUPERVISOR: frozenset(),
}

# Herramientas que un rol puede solicitar pero que nunca se ejecutan sin
# aprobacion humana explicita.
ROLE_APPROVAL_TOOLS: dict[AgentRole, frozenset[str]] = {
    AgentRole.RESEARCHER: frozenset(),
    AgentRole.CODER: frozenset(),
    AgentRole.REVIEWER: frozenset(),
    AgentRole.SUPERVISOR: frozenset({"git_commit", "install_dependency", "delete_file"}),
}


def tools_for(role: AgentRole) -> frozenset[str]:
    """Herramientas efectivas de un rol: las libres mas las que exigen aprobacion.

    La asignacion efectiva de una subtarea es la **interseccion** de este
    conjunto con `subtask.allowed_tools`, nunca la union.
    """
    return ROLE_TOOLS[role] | ROLE_APPROVAL_TOOLS[role]
