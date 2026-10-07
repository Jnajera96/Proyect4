"""Policy Engine: punto unico de decision de seguridad.

Es una funcion **pura y determinista**: no llama a un modelo, no accede a la red
y no toca el sistema de archivos. Por eso se puede probar de forma exhaustiva.

Orden de evaluacion de `decide()`:

  1. La herramienta existe en el catalogo?          (denegar por defecto)
  2. El rol tiene permitida la herramienta?         (minimo privilegio)
  3. Los argumentos son validos?                    (confinamiento de rutas, enumeraciones)
  4. Queda presupuesto?                             (si no, escalar)
  5. La accion exige aprobacion humana?             (acciones con efectos)
  6. Permitir.

La validacion de argumentos ocurre **antes** de la aprobacion a proposito: una
ruta que escapa del worktree se deniega, no se convierte en una solicitud de
aprobacion. Pedir permiso para algo prohibido es una forma de normalizarlo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ai_swe.contracts.tasks import AgentRole
from ai_swe.contracts.tools import PolicyDecision, PolicyEffect
from ai_swe.tools.registry import ALLOWLIST_ARGS, ROLE_APPROVAL_TOOLS, ROLE_TOOLS, TOOLS

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True)
class DecisionContext:
    """Contexto de la decision. Todo lo que el Engine necesita saber, y nada mas."""

    run_id: str
    agent: AgentRole
    allowed_paths: tuple[str, ...] = ()
    protected_paths: tuple[str, ...] = ()
    allowed_test_targets: tuple[str, ...] = ()
    allowed_packages: tuple[str, ...] = ()
    budget_exhausted: bool = False
    subtask_allowed_tools: tuple[str, ...] = field(default=())


def normalize_rel_path(raw: str) -> str | None:
    """Normaliza una ruta relativa.

    Devuelve la ruta normalizada, o `None` si escapa del directorio autorizado
    o si es absoluta. Se rechazan rutas absolutas de forma explicita: el agente
    nunca debe poder nombrar una ubicacion fuera del area de trabajo.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = raw.replace("\\", "/").strip()
    if candidate.startswith("/") or _WINDOWS_DRIVE.match(candidate):
        return None

    segments: list[str] = []
    for segment in candidate.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not segments:
                return None  # escapa por arriba del limite
            segments.pop()
        else:
            segments.append(segment)
    return "/".join(segments)


def path_within_scope(normalized: str, allowed_paths: tuple[str, ...]) -> bool:
    """Comprueba la pertenencia al alcance declarado.

    Un `allowed_paths` vacio significa "todo el repositorio autorizado".
    """
    if not allowed_paths:
        return True
    for allowed in allowed_paths:
        prefix = normalize_rel_path(allowed)
        if prefix is None:
            continue
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    return False


def _deny(reason: str, rule: str) -> PolicyDecision:
    return PolicyDecision(effect=PolicyEffect.DENY, reason=reason, matched_rule=rule)


def _approval(reason: str, rule: str) -> PolicyDecision:
    return PolicyDecision(effect=PolicyEffect.REQUIRE_APPROVAL, reason=reason, matched_rule=rule)


def _allow(reason: str, rule: str) -> PolicyDecision:
    return PolicyDecision(effect=PolicyEffect.ALLOW, reason=reason, matched_rule=rule)


def decide(tool: str, args: dict[str, object], ctx: DecisionContext) -> PolicyDecision:
    """Decide si una llamada a herramienta se permite, se deniega o requiere aprobacion."""

    # 1. Catalogo cerrado. Denegar por defecto (RNF-S5).
    spec = TOOLS.get(tool)
    if spec is None:
        return _deny(
            f"la herramienta '{tool}' no existe en el catalogo; se deniega por defecto",
            "POLICY-DEFAULT-DENY",
        )

    # 2. Minimo privilegio por rol.
    permitted = ROLE_TOOLS[ctx.agent]
    needs_approval = ROLE_APPROVAL_TOOLS[ctx.agent]
    if tool not in permitted and tool not in needs_approval:
        return _deny(
            f"el rol '{ctx.agent}' no tiene permitida la herramienta '{tool}'",
            "POLICY-ROLE-NOT-PERMITTED",
        )

    # 2b. La subtarea solo puede restringir, nunca ampliar.
    if ctx.subtask_allowed_tools and tool not in ctx.subtask_allowed_tools:
        return _deny(
            f"la subtarea no declara '{tool}' en allowed_tools",
            "POLICY-SUBTASK-SCOPE",
        )

    # 3. Validacion de argumentos.
    if spec.inside_worktree:
        raw_path = args.get("path")
        if not isinstance(raw_path, str):
            return _deny(
                f"'{tool}' exige un argumento 'path' de tipo texto",
                "POLICY-MISSING-PATH",
            )
        normalized = normalize_rel_path(raw_path)
        if normalized is None:
            return _deny(
                f"la ruta '{raw_path}' es absoluta o escapa del area autorizada",
                "POLICY-PATH-ESCAPES",
            )
        if not path_within_scope(normalized, ctx.allowed_paths):
            return _deny(
                f"la ruta '{normalized}' queda fuera del alcance declarado",
                "POLICY-PATH-OUTSIDE-SCOPE",
            )
        for protected in ctx.protected_paths:
            protected_norm = normalize_rel_path(protected)
            if protected_norm and (
                normalized == protected_norm or normalized.startswith(protected_norm + "/")
            ):
                return _approval(
                    f"la ruta '{normalized}' esta declarada como protegida",
                    "POLICY-PATH-PROTECTED",
                )

    if spec.requires_target_allowlist:
        arg_name = ALLOWLIST_ARGS.get(tool, "target")
        target = args.get(arg_name)
        allowed = ctx.allowed_test_targets if arg_name == "target" else ctx.allowed_packages
        if not isinstance(target, str) or target not in allowed:
            return _deny(
                f"'{tool}' solo acepta valores de la lista permitida; "
                f"'{target}' no esta en {list(allowed)}",
                "POLICY-TARGET-NOT-ALLOWLISTED",
            )

    # 4. Presupuesto agotado: continuar implica gasto no autorizado.
    if ctx.budget_exhausted:
        return _approval(
            "el presupuesto de la ejecucion esta agotado",
            "POLICY-BUDGET-EXHAUSTED",
        )

    # 5. Acciones con efectos.
    if tool in needs_approval:
        return _approval(
            f"'{tool}' produce efectos y requiere aprobacion humana",
            "POLICY-EFFECT-REQUIRES-APPROVAL",
        )

    # 6. Permitir.
    return _allow(f"'{tool}' permitida para el rol '{ctx.agent}'", "POLICY-ALLOW-BY-ROLE")
