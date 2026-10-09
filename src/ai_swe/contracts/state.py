"""Contrato del Shared State.

El estado es de **una ejecucion** (State), no conocimiento entre ejecuciones
(Memory). Es serializable, versionado y persistido por punto de control.

Invariante central codificado aqui: **el audio crudo no puede llegar al
Supervisor**. Una instruccion de origen `voice` exige metadatos de transcripcion
y confirmacion explicita del usuario (RF-03).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from ai_swe.contracts.outputs import (
    Approval,
    CodeChange,
    FileChange,
    FinalReport,
    Finding,
    ResearchOutput,
    ReviewVerdict,
    TestRun,
)
from ai_swe.contracts.tasks import RunPlan, TaskInterpretation

SCHEMA_VERSION = "1.0.0"


class RunStatus(StrEnum):
    """Estados de una ejecucion.

    **Dos estados de espera, no uno.** `AWAITING_APPROVAL` espera la aprobacion de
    un cambio ya aplicado y probado; `AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION`
    espera la confirmacion de lo que el sistema **entendio** de la peticion, antes
    de planificar nada. Son decisiones distintas y en momentos distintos, asi que no
    comparten estado: fusionarlos haria que un cliente no pudiera saber que se le
    esta pidiendo. Ninguno de los dos es terminal: la ejecucion espera y debe
    sobrevivir a la caida del proceso (RF-11, RF-12).
    """

    PLANNED = "planned"
    RUNNING = "running"
    AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION = "awaiting_human_requirements_confirmation"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_HUMAN = "needs_human"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.NEEDS_HUMAN,
            RunStatus.CANCELLED,
        }

    @property
    def is_awaiting_human(self) -> bool:
        """Si la ejecucion esta detenida esperando una decision humana.

        Se usa en la red de seguridad de `MET-13`: una espera legitima no es una
        anomalia, y sin esta distincion un grafo pausado en la puerta de requisitos
        se forzaria a `needs_human` como si se hubiera quedado colgado.
        """
        return self in {
            RunStatus.AWAITING_APPROVAL,
            RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION,
        }


class InstructionSource(StrEnum):
    TEXT = "text"
    VOICE = "voice"


class TranscriptMeta(BaseModel):
    """Metadatos de la transcripcion. El audio en si nunca entra al sistema."""

    provider: str = Field(min_length=1, description="p. ej. 'faster-whisper:large-v3'")
    language: str = Field(min_length=2, max_length=16)
    confidence: float = Field(ge=0.0, le=1.0)
    duration_s: float = Field(ge=0.0)
    low_confidence_warned: bool = Field(
        default=False,
        description="Se aviso al usuario de que la confianza estaba bajo el umbral.",
    )


class Instruction(BaseModel):
    """La instruccion tal como entra al sistema: siempre texto confirmado."""

    text: str = Field(min_length=1, max_length=20_000)
    source: InstructionSource
    transcript_meta: TranscriptMeta | None = None
    confirmed_by_user: bool

    @model_validator(mode="after")
    def _voice_requires_confirmation(self) -> Instruction:
        if self.source is InstructionSource.VOICE:
            if self.transcript_meta is None:
                raise ValueError(
                    "una instruccion de origen 'voice' exige transcript_meta: sin metadatos "
                    "no se puede saber si la transcripcion es fiable"
                )
            if not self.confirmed_by_user:
                raise ValueError(
                    "una instruccion de origen 'voice' exige confirmed_by_user=True: "
                    "el audio crudo nunca llega al Supervisor (RF-03)"
                )
        if self.source is InstructionSource.TEXT and self.transcript_meta is not None:
            raise ValueError("una instruccion de texto no debe llevar metadatos de transcripcion")
        return self


class RunOptions(BaseModel):
    """Lo que el usuario **pidio**. Distinto de `TaskInterpretation`, que es lo que
    el Supervisor **entendio**.

    Mantenerlos separados permite comparar ambos y detectar una interpretacion que
    se desvio de la peticion, cosa imposible si se funden en un solo objeto.
    """

    repo_path: str | None = Field(
        default=None, description="Repositorio autorizado sobre el que trabajar."
    )
    allowed_paths: list[str] = Field(
        default_factory=list, description="Rutas relativas donde se permite escribir."
    )
    protected_paths: list[str] = Field(
        default_factory=list, description="Rutas que exigen aprobacion explicita."
    )
    dry_run: bool = Field(
        default=False,
        description="Ejecuta el flujo sin tocar el repositorio. Util para demostrar el grafo.",
    )


class Budget(BaseModel):
    """Presupuesto de la ejecucion. Agotarlo corta y escala, no continua (RNF-C1).

    **Por que estan los contadores aqui y no en el futuro `ModelGateway`.** El
    presupuesto es parte del estado persistido, no del cliente del modelo. Si el
    limite viviera solo en quien llama, una reanudacion tras un corte arrancaria
    con los contadores a cero y volveria a gastar lo ya gastado. Al vivir en el
    estado, el checkpoint los conserva y el limite sobrevive a un reinicio.

    **Compatibilidad.** Los campos nuevos entran con valor por defecto, de modo
    que un estado serializado antes de existir se deserializa sin error y sin
    necesidad de tocar `ESQUEMA_VERSION`. Solo un cambio que *elimine* o *renombre*
    un campo obligaria a subir la version.
    """

    # --- Tokens ---------------------------------------------------------------
    max_tokens: int = Field(default=200_000, ge=1)
    used_tokens: int = Field(default=0, ge=0)
    # --- Llamadas a herramienta ----------------------------------------------
    max_tool_calls: int = Field(default=60, ge=1)
    used_tool_calls: int = Field(default=0, ge=0)
    # --- Llamadas al modelo (M2) ---------------------------------------------
    # Se separan de las llamadas a herramienta porque el coste y el riesgo son
    # distintos: una herramienta toca el mundo, una llamada al modelo gasta dinero.
    max_model_calls: int = Field(default=120, ge=1)
    used_model_calls: int = Field(default=0, ge=0)
    # --- Tiempo ---------------------------------------------------------------
    max_seconds: float = Field(default=900.0, gt=0)
    elapsed_seconds: float = Field(default=0.0, ge=0)
    # --- Coste ----------------------------------------------------------------
    # En unidades de la moneda del proveedor. Se deja abierto a `None` como "sin
    # limite declarado", que es distinto de cero: cero significa "no se permite
    # gastar nada".
    max_cost: float | None = Field(default=None, ge=0)
    used_cost: float = Field(default=0.0, ge=0)
    # --- Ciclos de revision ---------------------------------------------------
    max_review_cycles: int = Field(default=2, ge=0, le=5)
    review_cycles_used: int = Field(default=0, ge=0)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.used_tokens)

    @property
    def remaining_tool_calls(self) -> int:
        return max(0, self.max_tool_calls - self.used_tool_calls)

    @property
    def remaining_model_calls(self) -> int:
        return max(0, self.max_model_calls - self.used_model_calls)

    @property
    def remaining_cost(self) -> float | None:
        """Coste restante, o `None` si no se declaro limite de coste."""
        if self.max_cost is None:
            return None
        return max(0.0, self.max_cost - self.used_cost)

    @property
    def exhausted(self) -> bool:
        return self.exhausted_reasons() != ()

    def exhausted_reasons(self) -> tuple[str, ...]:
        """Motivos por los que el presupuesto esta agotado. Vacio = queda margen.

        Se devuelve la lista de motivos, no un booleano, porque cuando el sistema
        se detiene hay que poder decir **por que** se detuvo. Un `True` obliga a
        adivinar cual de los seis limites salto.
        """
        motivos: list[str] = []
        if self.remaining_tokens == 0:
            motivos.append("tokens")
        if self.remaining_tool_calls == 0:
            motivos.append("tool_calls")
        if self.remaining_model_calls == 0:
            motivos.append("model_calls")
        if self.elapsed_seconds >= self.max_seconds:
            motivos.append("seconds")
        if self.remaining_cost == 0:
            motivos.append("cost")
        if self.review_cycles_used > self.max_review_cycles:
            motivos.append("review_cycles")
        return tuple(motivos)


class RunError(BaseModel):
    """Error tipado. La taxonomia esta en docs/01-arquitectura.md, seccion 9.8."""

    error_class: str = Field(min_length=1, max_length=80)
    agent: str = Field(min_length=1, max_length=40)
    message: str = Field(min_length=1, max_length=4000)
    recoverable: bool
    occurred_at: datetime
    subtask_id: str | None = None


class Artifacts(BaseModel):
    """Artefactos producidos por la ejecucion."""

    worktree_path: str | None = None
    base_commit: str | None = None
    changed_files: list[FileChange] = Field(default_factory=list, max_length=500)
    diff: str | None = Field(default=None, max_length=500_000)


class Evidence(BaseModel):
    """Evidencia verificable: lo que permite decir 'esto se comprobo'."""

    test_runs: list[TestRun] = Field(default_factory=list, max_length=200)
    findings: list[Finding] = Field(default_factory=list, max_length=500)


class Outputs(BaseModel):
    """Salidas de los agentes. Cada agente escribe solo su propio campo."""

    researcher_output: ResearchOutput | None = None
    coder_output: CodeChange | None = None
    reviewer_output: ReviewVerdict | None = None


class RunState(BaseModel):
    """Estado completo de una ejecucion.

    Debe ser serializable: se verifica estructuralmente en tests/test_contracts.py.
    """

    schema_version: str = Field(default=SCHEMA_VERSION)
    run_id: str = Field(min_length=1, max_length=64)
    trace_id: str = Field(min_length=1, max_length=64)
    created_at: datetime
    updated_at: datetime

    instruction: Instruction
    options: RunOptions = Field(default_factory=RunOptions)
    interpretation: TaskInterpretation | None = None
    plan: RunPlan | None = None

    outputs: Outputs = Field(default_factory=Outputs)
    artifacts: Artifacts = Field(default_factory=Artifacts)
    evidence: Evidence = Field(default_factory=Evidence)
    approvals: list[Approval] = Field(default_factory=list, max_length=200)
    errors: list[RunError] = Field(default_factory=list, max_length=500)
    budget: Budget = Field(default_factory=Budget)
    final_report: FinalReport | None = None

    status: RunStatus = RunStatus.PLANNED
    next_step: str | None = Field(default=None, max_length=120)

    # F5: indice de progreso en el plan. Es **cuanto se ha hecho**, no *que se va
    # a hacer* (eso es `plan`). Separar ambas cosas evita que dos fuentes de
    # verdad se desincronicen.
    plan_index: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _timestamps_consistent(self) -> RunState:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at anterior a created_at")
        return self

    @model_validator(mode="after")
    def _terminal_requires_no_next_step(self) -> RunState:
        if self.status.is_terminal and self.next_step is not None:
            raise ValueError(
                f"una ejecucion en estado terminal ({self.status}) no debe tener next_step"
            )
        return self

    def subtask(self, subtask_id: str):
        """Devuelve la subtarea indicada, o None si el plan aun no existe."""
        if self.plan is None:
            return None
        for s in self.plan.subtasks:
            if s.id == subtask_id:
                return s
        return None
