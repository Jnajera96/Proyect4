"""Contratos de interpretacion y planificacion.

Corresponden a la salida del Supervisor: que entendio de la instruccion y que
plan propone. Ambos se validan por esquema antes de propagarse.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator
from pydantic.json_schema import SkipJsonSchema


class Intent(StrEnum):
    """Clasificacion de la instruccion.

    Es lo que permite que una pregunta simple no active el aparato completo de
    agentes (docs/01-arquitectura.md, seccion 9.2).
    """

    QUESTION = "question"
    INSPECT = "inspect"
    MODIFY = "modify"
    OUT_OF_SCOPE = "out_of_scope"


class AgentRole(StrEnum):
    SUPERVISOR = "supervisor"
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"


class SubtaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Scope(BaseModel):
    """Alcance declarado por el usuario. Es lo que hace posible el HITL util:
    lo declarado como libre no vuelve a preguntar (docs/01-arquitectura.md 15.4).
    """

    repo_path: str = Field(description="Raiz del repositorio autorizado.")
    allowed_paths: list[str] = Field(
        default_factory=list,
        description="Rutas relativas donde se permite escribir. Vacio = todo el repo.",
    )
    protected_paths: list[str] = Field(
        default_factory=list,
        description="Rutas relativas donde nunca se escribe sin aprobacion explicita.",
    )
    max_files_changed: int = Field(default=10, ge=1, le=100)
    max_lines_changed: int = Field(default=400, ge=1, le=10_000)


class TaskInterpretation(BaseModel):
    """Salida validada de la fase de interpretacion del Supervisor."""

    intent: Intent
    scope: Scope
    constraints: list[str] = Field(
        default_factory=list,
        description="Prohibiciones o condiciones explicitas del usuario.",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=2000)
    confirmed_by_user: SkipJsonSchema[bool] = Field(
        default=False,
        description=(
            "Confirmacion humana de esta interpretacion (M2, item 3 del DoD). "
            "**Excluido del esquema JSON que se envia al modelo** a proposito: la "
            "confirmacion la da una persona, no el modelo. Si viajara en el esquema, "
            "el modelo podria rellenarla y la puerta de confirmacion seria decorativa "
            "-el sistema se estaria auto-confirmando-. Se marca a `True` solo el nodo "
            "`confirm_requirements_gate`, con el valor de la reanudacion."
        ),
    )


class Subtask(BaseModel):
    """Una unidad de trabajo asignada a un agente."""

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str = Field(min_length=1, max_length=2000)
    agent: AgentRole
    depends_on: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    done_criteria: str = Field(min_length=1, max_length=1000)
    status: SubtaskStatus = SubtaskStatus.PENDING
    attempts: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _agent_is_specialist(self) -> Subtask:
        if self.agent is AgentRole.SUPERVISOR:
            raise ValueError(
                "una subtarea no puede asignarse al supervisor: el supervisor coordina, no ejecuta"
            )
        if not self.allowed_tools:
            raise ValueError(
                f"la subtarea '{self.id}' no declara allowed_tools: la asignacion efectiva "
                "es una interseccion, y un conjunto vacio no ejecuta nada"
            )
        return self


class RunPlan(BaseModel):
    """Plan de ejecucion. Es la salida estructurada central del Supervisor."""

    subtasks: list[Subtask] = Field(min_length=1, max_length=32)
    max_review_cycles: int = Field(default=2, ge=0, le=5)
    rationale: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def _ids_unique(self) -> RunPlan:
        ids = [s.id for s in self.subtasks]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"identificadores de subtarea duplicados: {dupes}")
        return self

    @model_validator(mode="after")
    def _dependencies_exist(self) -> RunPlan:
        known = {s.id for s in self.subtasks}
        for s in self.subtasks:
            unknown = [d for d in s.depends_on if d not in known]
            if unknown:
                raise ValueError(f"la subtarea '{s.id}' depende de subtareas inexistentes: {unknown}")
            if s.id in s.depends_on:
                raise ValueError(f"la subtarea '{s.id}' depende de si misma")
        return self

    @model_validator(mode="after")
    def _dependencies_acyclic(self) -> RunPlan:
        """Un ciclo en el plan es un bucle infinito disfrazado de dependencia."""
        graph = {s.id: list(s.depends_on) for s in self.subtasks}
        state: dict[str, int] = {}

        def visit(node: str) -> None:
            mark = state.get(node, 0)
            if mark == 1:
                raise ValueError(f"ciclo de dependencias detectado en la subtarea '{node}'")
            if mark == 2:
                return
            state[node] = 1
            for dep in graph.get(node, []):
                visit(dep)
            state[node] = 2

        for node in graph:
            visit(node)
        return self
