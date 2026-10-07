"""Contratos de herramientas y de decisiones de politica.

El Policy Engine es el punto unico de decision de seguridad. Toda decision es
explicable: siempre hay una regla identificable detras.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from ai_swe.contracts.tasks import AgentRole


class RiskLevel(StrEnum):
    NONE = "none"
    MEDIUM = "medium"
    HIGH = "high"


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class ToolSpec(BaseModel):
    """Especificacion de una herramienta del catalogo.

    `writes` y `requires_target_allowlist` no son documentacion: son las banderas
    que el Policy Engine consulta para decidir.
    """

    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1, max_length=500)
    risk: RiskLevel
    writes: bool = False
    requires_target_allowlist: bool = False
    inside_worktree: bool = Field(
        default=False,
        description="Si escribe, exige que la ruta quede dentro del worktree de la ejecucion.",
    )


class ToolCall(BaseModel):
    """Una llamada propuesta por un agente. Se valida antes de ejecutarse."""

    tool: str = Field(min_length=1)
    args: dict[str, object] = Field(default_factory=dict)
    agent: AgentRole
    subtask_id: str | None = None


class ToolResult(BaseModel):
    """Resultado de una herramienta, con la decision de politica que lo permitio."""

    tool: str
    ok: bool
    output: str = Field(default="", max_length=200_000)
    error_class: str | None = None
    duration_ms: float = Field(ge=0.0)
    policy_effect: PolicyEffect
    matched_rule: str


class PolicyDecision(BaseModel):
    """Decision de politica. Determinista, explicable y testeable."""

    effect: PolicyEffect
    reason: str = Field(min_length=1, max_length=500)
    matched_rule: str = Field(min_length=1, max_length=120)
