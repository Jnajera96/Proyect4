"""Capa de herramientas: catalogo, matriz de permisos y Policy Engine."""

from ai_swe.tools.policy import DecisionContext, decide, normalize_rel_path, path_within_scope
from ai_swe.tools.registry import (
    ALLOWLIST_ARGS,
    ROLE_APPROVAL_TOOLS,
    ROLE_TOOLS,
    TOOLS,
    tools_for,
)

__all__ = [
    "ALLOWLIST_ARGS",
    "ROLE_APPROVAL_TOOLS",
    "ROLE_TOOLS",
    "TOOLS",
    "DecisionContext",
    "decide",
    "normalize_rel_path",
    "path_within_scope",
    "tools_for",
]
