"""Contratos del Proyecto 4 - AI Software Engineering System.

Este paquete define las **interfaces entre componentes** como modelos Pydantic.
Es la fuente unica de verdad: de aqui salen el JSON Schema del tool calling, el
contrato HTTP y la validacion de las salidas del modelo.

Regla de frontera: lo que no tiene contrato ni validacion no cruza un borde.
"""

from ai_swe.contracts.api import (
    EVENTO_POR_NODO,
    EventKind,
    Project,
    ProjectRequest,
    RunEvent,
    RunSummary,
)
from ai_swe.contracts.outputs import (
    Approval,
    ApprovalDecision,
    CodeChange,
    CodeProposal,
    FileChange,
    FileOperation,
    FileProposal,
    FinalReport,
    Finding,
    ResearchOutput,
    ReviewDecision,
    ReviewVerdict,
    Severity,
    TestRun,
)
from ai_swe.contracts.state import (
    Artifacts,
    Budget,
    Evidence,
    Instruction,
    InstructionSource,
    Outputs,
    RunError,
    RunOptions,
    RunState,
    RunStatus,
    TranscriptMeta,
)
from ai_swe.contracts.tasks import (
    AgentRole,
    Intent,
    RunPlan,
    Scope,
    Subtask,
    SubtaskStatus,
    TaskInterpretation,
)
from ai_swe.contracts.tools import (
    PolicyDecision,
    PolicyEffect,
    RiskLevel,
    ToolCall,
    ToolResult,
    ToolSpec,
)

__all__ = [
    "AgentRole",
    "Approval",
    "ApprovalDecision",
    "Artifacts",
    "Budget",
    "CodeChange",
    "CodeProposal",
    "EventKind",
    "EVENTO_POR_NODO",
    "Project",
    "ProjectRequest",
    "Evidence",
    "FileChange",
    "FileOperation",
    "FileProposal",
    "FinalReport",
    "Finding",
    "Instruction",
    "InstructionSource",
    "Intent",
    "Outputs",
    "PolicyDecision",
    "PolicyEffect",
    "ResearchOutput",
    "ReviewDecision",
    "ReviewVerdict",
    "RiskLevel",
    "RunError",
    "RunEvent",
    "RunOptions",
    "RunPlan",
    "RunState",
    "RunStatus",
    "RunSummary",
    "Scope",
    "Severity",
    "Subtask",
    "SubtaskStatus",
    "TaskInterpretation",
    "TestRun",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
    "TranscriptMeta",
]
