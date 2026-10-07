"""Contratos de salida de los agentes especializados.

Cada agente escribe **solo** su propio objeto. La separacion es lo que permite
que el Reviewer no vea el razonamiento del Coder (docs/01-arquitectura.md 10.3).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Finding(BaseModel):
    """Un hallazgo con evidencia. Sin evidencia, un hallazgo es una opinion."""

    severity: Severity
    path: str = Field(min_length=1)
    line: int | None = Field(default=None, ge=1)
    explanation: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(
        min_length=1,
        max_length=2000,
        description="Fragmento de codigo o salida que sustenta el hallazgo.",
    )


class ResearchOutput(BaseModel):
    """Salida del Researcher. Solo lectura: reune evidencia, no modifica nada.

    El campo `unknowns` es obligatorio a proposito: obliga al agente a declarar
    el limite de su conocimiento en lugar de rellenar el vacio.
    """

    findings: list[Finding] = Field(default_factory=list, max_length=200)
    unknowns: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Lo que el agente NO pudo determinar. Debe declararse explicitamente.",
    )
    files_read: list[str] = Field(default_factory=list, max_length=500)


class FileChange(BaseModel):
    path: str = Field(min_length=1)
    added: int = Field(ge=0)
    removed: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)


class CodeChange(BaseModel):
    """Salida del Coder. Aplica en worktree aislado, nunca en el repo del usuario."""

    files_changed: list[FileChange] = Field(default_factory=list, max_length=200)
    diff: str = Field(default="", max_length=500_000)
    rationale: str = Field(
        min_length=1,
        max_length=4000,
        description="Por que este cambio satisface el criterio de la subtarea.",
    )
    diff_sha256: str = Field(
        min_length=64,
        max_length=64,
        description="Permite detectar bucles: el mismo hash dos veces es un bucle.",
    )


class TestRun(BaseModel):
    """Evidencia de una ejecucion de pruebas. Es la senal objetiva del sistema."""

    # `__test__ = False` porque pytest intenta recolectar cualquier clase cuyo
    # nombre empiece por "Test". Sin esto, importar el contrato en un fichero de
    # pruebas produce un aviso de recoleccion en cada ejecucion.
    __test__ = False

    target: str = Field(min_length=1, description="Identificador de la lista permitida.")
    exit_code: int
    stdout: str = Field(default="", max_length=200_000)
    stderr: str = Field(default="", max_length=200_000)
    duration_s: float = Field(ge=0.0)
    reproducible: bool = Field(
        default=False,
        description="El Reviewer re-ejecuta para confirmar que el resultado es reproducible.",
    )

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


class ReviewDecision(StrEnum):
    ACCEPT = "accept"
    REQUEST_CHANGES = "request_changes"
    ESCALATE = "escalate"


class ReviewVerdict(BaseModel):
    """Salida del Reviewer. No escribe: solo juzga con evidencia."""

    decision: ReviewDecision
    findings: list[Finding] = Field(default_factory=list, max_length=200)
    required_fixes: list[str] = Field(default_factory=list, max_length=50)
    summary: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def _request_changes_requires_fixes(self) -> ReviewVerdict:
        if self.decision is ReviewDecision.REQUEST_CHANGES and not self.required_fixes:
            raise ValueError(
                "decision 'request_changes' sin required_fixes: un rechazo tiene que decir "
                "que corregir, o el ciclo de revision no converge"
            )
        return self


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class FinalReport(BaseModel):
    """Informe final. Las cuatro secciones de RF-13 estan separadas a proposito:
    mezclar "lo que cambie", "lo que comprobe" y "lo que queda pendiente" en un
    parrafo es lo que hace que un informe no sea auditable.
    """

    summary: str = Field(min_length=1, max_length=4000)
    changes_applied: list[str] = Field(default_factory=list, max_length=500)
    tests_executed: list[str] = Field(default_factory=list, max_length=200)
    review: str = Field(default="", max_length=2000)
    pending: list[str] = Field(default_factory=list, max_length=200)


class Approval(BaseModel):
    """Registro de una aprobacion humana. Es un requisito de trazabilidad
    (RNF-T2): quien, cuando, que accion y sobre que contenido exacto.
    """

    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    decided_at: datetime
    content_sha256: str = Field(min_length=64, max_length=64)
    decision: ApprovalDecision
    reason: str = Field(default="", max_length=2000)
