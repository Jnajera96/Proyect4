"""Nodos del grafo de orquestacion.

En la fase M1 los nodos son **deterministas y sin modelo**. Eso no significa que
sean simulados: el Researcher enumera el repositorio de verdad, el Policy Engine
decide de verdad, y el registro de eventos es real. Lo que falta es el
razonamiento del modelo, y cada nodo lo declara en el campo de texto que le
corresponde en lugar de inventar un resultado.

Regla que se respeta en todo el modulo: **no se fabrica evidencia**. El nodo de
pruebas registra un error tipado diciendo que no hay ejecutor, en vez de devolver
un `TestRun` con exito falso. Un sistema que se inventa que las pruebas pasaron es
peor que uno que admite que no las ejecuto.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from langgraph.types import interrupt

from ai_swe.contracts import (
    AgentRole,
    Approval,
    ApprovalDecision,
    Budget,
    CodeChange,
    FinalReport,
    Finding,
    Intent,
    Outputs,
    PolicyEffect,
    ResearchOutput,
    ReviewDecision,
    ReviewVerdict,
    RunError,
    RunState,
    RunStatus,
    Scope,
    Severity,
    TaskInterpretation,
)
from ai_swe.tools.policy import DecisionContext, decide

# --------------------------------------------------------------- vocabulario

# Clasificador determinista. Es un marcador de posicion honesto: en M2 lo
# sustituye el modelo. Se mantiene determinista en M1 porque asi `MET-13` es
# medible sin depender de la latencia ni del coste de una llamada.
_FUERA_DE_ALCANCE = (
    "push", "sube", "subir", "publica", "publicar", "despliega", "deploy",
    "produccion", "producción", "github", "pull request", " merge",
)
_MODIFICAR = (
    "corrige", "corregir", "arregla", "arreglar", "modifica", "modificar",
    "cambia", "cambiar", "añade", "anade", "añadir", "implementa", "implementar",
    "refactoriza", "refactorizar", "crea", "crear", "elimina", "borra",
)
_PREGUNTA = (
    "¿", "?", "que hace", "qué hace", "como ", "cómo ", "donde ", "dónde ",
    "explica", "explicar", "por que", "por qué", "cual ", "cuál ",
)
_INSPECCIONAR = (
    "analiza", "analizar", "revisa", "revisar", "inspecciona", "inspeccionar",
    "lista", "listar", "enumera", "enumerar", "describe", "describir",
)

_EXTENSIONES = {".py", ".md", ".toml", ".cfg", ".txt", ".json", ".yaml", ".yml"}
_MAX_ARCHIVOS = 20
_MAX_LINEAS_POR_ARCHIVO = 4000


def _ahora() -> datetime:
    return datetime.now(UTC)


def _clasificar(texto: str) -> Intent:
    """Clasificacion determinista de la intencion.

    El orden importa. Las acciones con efectos se detectan primero: "sube los
    cambios a GitHub" no debe clasificarse como modificacion local, porque el
    sistema no puede hacerlo y decirlo es parte de su comportamiento correcto
    (`RF-15`).
    """
    plano = texto.lower()
    if any(pista in plano for pista in _FUERA_DE_ALCANCE):
        return Intent.OUT_OF_SCOPE
    if any(pista in plano for pista in _MODIFICAR):
        return Intent.MODIFY
    if any(pista in plano for pista in _PREGUNTA):
        return Intent.QUESTION
    if any(pista in plano for pista in _INSPECCIONAR):
        return Intent.INSPECT
    return Intent.INSPECT  # por defecto, la opcion sin efectos


# ------------------------------------------------------------- constructores


def _con_salidas(state: RunState, **cambios) -> Outputs:
    datos = state.outputs.model_dump()
    datos.update(cambios)
    return Outputs.model_validate(datos)


def _con_presupuesto(state: RunState, **cambios) -> Budget:
    datos = state.budget.model_dump()
    datos.update(cambios)
    return Budget.model_validate(datos)


def _error(
    state: RunState, clase: str, agente: str, mensaje: str, *, recuperable: bool
) -> list[RunError]:
    return [
        *state.errors,
        RunError(
            error_class=clase,
            agent=agente,
            message=mensaje,
            recoverable=recuperable,
            occurred_at=_ahora(),
        ),
    ]


def _escalar(state: RunState, errores: list[RunError]) -> dict:
    return {
        "errors": errores,
        "status": RunStatus.NEEDS_HUMAN,
        "next_step": None,
        "updated_at": _ahora(),
    }


# -------------------------------------------------------------------- nodos


def interpret(state: RunState) -> dict:
    """Interpreta la instruccion y produce un plan. Sin modelo en M1."""
    intencion = _clasificar(state.instruction.text)
    opciones = state.options
    alcance = Scope(
        repo_path=opciones.repo_path or "(sin repositorio configurado)",
        allowed_paths=opciones.allowed_paths,
        protected_paths=opciones.protected_paths,
    )
    interpretacion = TaskInterpretation(
        intent=intencion,
        scope=alcance,
        constraints=["M1: la interpretacion es determinista; el modelo llega en M2"],
        confidence=0.5,
        rationale=(
            f"clasificacion determinista por vocabulario -> {intencion.value}"
            + ("" if opciones.repo_path else "; no se configuro repositorio")
        ),
    )
    return {
        "interpretation": interpretacion,
        "status": RunStatus.RUNNING,
        "next_step": intencion.value,
        "updated_at": _ahora(),
    }


def researcher(state: RunState) -> dict:
    """Enumera el repositorio autorizado. Lectura real, sin modelo.

    Se confina cada ruta resuelta dentro de la raiz autorizada (`RNF-S2`): un
    enlace simbolico que apunte fuera no debe poder ampliar el alcance.
    """
    hallazgos: list[Finding] = []
    leidos: list[str] = []
    incognitas = [
        "M1: el Researcher enumera el repositorio; la seleccion semantica de "
        "evidencia relevante llega en M2 con el modelo conectado"
    ]

    raiz_texto = state.options.repo_path
    if not raiz_texto:
        incognitas.append("no se configuro repositorio, no hay nada que inspeccionar")
    else:
        raiz = Path(raiz_texto).resolve()
        if not raiz.is_dir():
            incognitas.append(f"la ruta configurada no es un directorio: {raiz_texto}")
        else:
            for ruta in sorted(raiz.rglob("*")):
                if len(hallazgos) >= _MAX_ARCHIVOS:
                    incognitas.append(
                        f"listado truncado a {_MAX_ARCHIVOS} archivos; el resto no se reviso"
                    )
                    break
                if not ruta.is_file() or ruta.suffix.lower() not in _EXTENSIONES:
                    continue
                resuelta = ruta.resolve()
                if not _dentro_de(raiz, resuelta):
                    continue  # enlace simbolico que sale del area autorizada
                relativa = resuelta.relative_to(raiz).as_posix()
                leidos.append(relativa)
                hallazgos.append(
                    Finding(
                        severity=Severity.INFO,
                        path=relativa,
                        explanation=f"archivo presente en el repositorio ({resuelta.suffix})",
                        evidence=_primera_linea(resuelta),
                    )
                )

    salida = ResearchOutput(findings=hallazgos, unknowns=incognitas, files_read=leidos)
    return {
        "outputs": _con_salidas(state, researcher_output=salida),
        "next_step": "coder" if state.interpretation and state.interpretation.intent is Intent.MODIFY else "finalize",
        "updated_at": _ahora(),
    }


def _dentro_de(raiz: Path, candidata: Path) -> bool:
    """Comprueba que una ruta resuelta sigue dentro del area autorizada (`RNF-S2`).

    Se resuelve **antes** de comparar: es lo que hace que un enlace simbolico que
    apunte fuera del repositorio no pueda ampliar el alcance. Se extrae a una
    funcion propia para poder comprobarla directamente, en lugar de confiar en que
    el bucle que la usa la ejercite.
    """
    try:
        return candidata.resolve().is_relative_to(raiz.resolve())
    except (OSError, ValueError):
        return False


def _primera_linea(ruta: Path) -> str:
    try:
        with ruta.open("r", encoding="utf-8", errors="replace") as fh:
            for _ in range(_MAX_LINEAS_POR_ARCHIVO):
                linea = fh.readline()
                if not linea:
                    break
                limpia = linea.strip()
                if limpia:
                    return limpia[:200]
    except OSError as exc:
        return f"(no se pudo leer: {type(exc).__name__})"
    return "(archivo vacio)"


def answer_direct(state: RunState) -> dict:
    """Responde a una pregunta con la evidencia reunida. Sin modelo en M1."""
    investigacion = state.outputs.researcher_output
    rutas = investigacion.files_read if investigacion else []
    informe = FinalReport(
        summary=(
            "M1: no hay modelo conectado, asi que el sistema no puede redactar una "
            "respuesta. Lo que si puede hacer ya es reunir la evidencia sobre la que "
            "se respondera en M2."
        ),
        changes_applied=[],
        tests_executed=[],
        review="no aplica: la intencion era responder, no modificar",
        pending=[
            "M2: conectar el modelo para redactar la respuesta a partir de la evidencia",
            *([f"archivos considerados: {len(rutas)}"] if rutas else []),
        ],
    )
    return {"final_report": informe, "status": RunStatus.COMPLETED, "next_step": None,
            "updated_at": _ahora()}


def explain_limits(state: RunState) -> dict:
    """Rechaza una instruccion fuera de alcance explicando el limite (`RF-15`).

    No es un fallo: es el comportamiento correcto. Por eso termina en `completed`
    y no registra error. Un sistema que intenta `git push` "a ver que pasa" esta
    peor disenado que uno que explica por que no lo hace.
    """
    informe = FinalReport(
        summary=(
            "La instruccion pide una accion fuera del alcance declarado del sistema. "
            "El prototipo no realiza operaciones remotas ni publica cambios."
        ),
        changes_applied=[],
        tests_executed=[],
        review="no aplica",
        pending=[
            "fuera de alcance: publicar en un remoto, git push, o cualquier accion externa",
            "el sistema si puede preparar el cambio y dejarlo confirmado en local con aprobacion",
        ],
    )
    return {"final_report": informe, "status": RunStatus.COMPLETED, "next_step": None,
            "updated_at": _ahora()}


def coder(state: RunState) -> dict:
    """Propone un parche. Sin modelo en M1, asi que no propone ninguno."""
    cambio = CodeChange(
        files_changed=[],
        diff="",
        rationale=(
            "M1: nodo determinista sin modelo conectado. El Coder no genera parches "
            "todavia; la generacion real llega en M2. Se devuelve un cambio vacio en "
            "lugar de un parche inventado."
        ),
        diff_sha256=hashlib.sha256(b"").hexdigest(),
    )
    return {
        "outputs": _con_salidas(state, coder_output=cambio),
        "next_step": "run_tests",
        "updated_at": _ahora(),
    }


def run_tests(state: RunState) -> dict:
    """Solicita ejecutar pruebas.

    Pasa por el Policy Engine de verdad, y despues comprueba si existe un
    ejecutor. En M1 no lo hay, asi que registra un error tipado. **No se devuelve
    un `TestRun` con exito**: inventar evidencia de pruebas es el peor fallo
    posible en un sistema cuyo valor es precisamente la evidencia.
    """
    objetivo = "pytest.unit"
    decision = decide(
        "run_tests",
        {"target": objetivo},
        DecisionContext(
            run_id=state.run_id,
            agent=AgentRole.CODER,
            allowed_test_targets=("pytest.unit",),
            budget_exhausted=state.budget.exhausted,
        ),
    )
    if decision.effect is not PolicyEffect.ALLOW:
        return _escalar(
            state,
            _error(
                state,
                "POLICY_DENIED",
                AgentRole.CODER.value,
                f"el Policy Engine no permitio ejecutar pruebas: {decision.reason}",
                recuperable=False,
            ),
        )

    return _escalar(
        state,
        _error(
            state,
            "TEST_EXECUTOR_NOT_IMPLEMENTED",
            AgentRole.CODER.value,
            "el Policy Engine autorizo la ejecucion, pero M1 no incluye ejecutor de "
            "pruebas. No se registra evidencia de pruebas porque no se ejecuto ninguna.",
            recuperable=False,
        ),
    )


def reviewer(state: RunState) -> dict:
    """Juzga el resultado con la evidencia disponible."""
    pruebas = state.evidence.test_runs

    if not pruebas:
        veredicto = ReviewVerdict(
            decision=ReviewDecision.ESCALATE,
            findings=[],
            summary="no hay evidencia de pruebas que revisar; no se puede aceptar ni rechazar",
        )
    elif all(p.passed for p in pruebas):
        veredicto = ReviewVerdict(
            decision=ReviewDecision.ACCEPT,
            findings=[
                Finding(
                    severity=Severity.INFO,
                    path="(pruebas)",
                    explanation="todas las ejecuciones de prueba registradas pasaron",
                    evidence="; ".join(f"{p.target} -> exit {p.exit_code}" for p in pruebas),
                )
            ],
            summary="el cambio pasa las pruebas registradas",
        )
    else:
        fallidas = [p.target for p in pruebas if not p.passed]
        veredicto = ReviewVerdict(
            decision=ReviewDecision.REQUEST_CHANGES,
            findings=[
                Finding(
                    severity=Severity.HIGH,
                    path="(pruebas)",
                    explanation="hay ejecuciones de prueba con codigo de salida distinto de cero",
                    evidence=f"objetivos fallidos: {', '.join(fallidas)}",
                )
            ],
            required_fixes=[f"corregir el fallo en {t}" for t in fallidas],
            summary=f"{len(fallidas)} objetivo(s) de prueba en rojo",
        )

    return {
        "outputs": _con_salidas(state, reviewer_output=veredicto),
        "budget": _con_presupuesto(state, review_cycles_used=state.budget.review_cycles_used + 1),
        "next_step": "approval_gate" if veredicto.decision is ReviewDecision.ACCEPT else "escalate",
        "updated_at": _ahora(),
    }


def mark_awaiting(state: RunState) -> dict:
    """Marca la ejecucion como pendiente de aprobacion.

    Es un nodo aparte a proposito: `interrupt()` no confirma las escrituras
    parciales del nodo en el que se llama, porque el nodo se reejecuta al
    reanudar. Sin este nodo previo, el estado persistido nunca mostraria
    `awaiting_approval` y una interfaz no podria saber que hay que aprobar algo.
    """
    return {"status": RunStatus.AWAITING_APPROVAL, "next_step": "approval_gate",
            "updated_at": _ahora()}


def approval_gate(state: RunState) -> dict:
    """Solicita aprobacion humana y reanuda con la decision."""
    veredicto = state.outputs.reviewer_output
    decision = interrupt(
        {
            "pregunta": "¿promover los cambios del worktree al repositorio del usuario?",
            "run_id": state.run_id,
            "resumen_revision": veredicto.summary if veredicto else "(sin revision)",
        }
    )

    try:
        eleccion = ApprovalDecision(str(decision))
    except ValueError:
        eleccion = ApprovalDecision.REJECTED

    aprobacion = Approval(
        action="promote_changes",
        actor="usuario",
        decided_at=_ahora(),
        content_sha256=state.outputs.coder_output.diff_sha256
        if state.outputs.coder_output
        else hashlib.sha256(b"").hexdigest(),
        decision=eleccion,
        reason="" if eleccion is ApprovalDecision.APPROVED else "rechazado por el usuario",
    )

    if eleccion is not ApprovalDecision.APPROVED:
        return {
            "approvals": [*state.approvals, aprobacion],
            "errors": _error(
                state,
                "APPROVAL_REJECTED",
                AgentRole.SUPERVISOR.value,
                "el usuario rechazo la promocion de cambios",
                recuperable=False,
            ),
            "status": RunStatus.NEEDS_HUMAN,
            "next_step": None,
            "updated_at": _ahora(),
        }

    return {
        "approvals": [*state.approvals, aprobacion],
        "status": RunStatus.RUNNING,
        "next_step": "finalize",
        "updated_at": _ahora(),
    }


def escalate(state: RunState) -> dict:
    """Escala al humano. Se usa cuando un nodo ya dejo un error sin resolver."""
    return _escalar(state, state.errors or _error(
        state,
        "UNSPECIFIED_ESCALATION",
        AgentRole.SUPERVISOR.value,
        "se escalo sin un error registrado; es un fallo del propio orquestador",
        recuperable=False,
    ))


def escalate_no_changes(state: RunState) -> dict:
    """El Coder no produjo cambios, asi que no hay nada que probar ni revisar."""
    return _escalar(
        state,
        _error(
            state,
            "CODER_PRODUCED_NO_CHANGES",
            AgentRole.CODER.value,
            "el Coder no produjo ningun cambio; en M1 es lo esperado al no haber modelo",
            recuperable=False,
        ),
    )


def finalize(state: RunState) -> dict:
    """Cierra la ejecucion.

    Respeta un estado terminal ya fijado: si un nodo anterior escalo, finalizar no
    debe convertir ese `needs_human` en un `completed` exitoso.
    """
    if state.status.is_terminal:
        return {"updated_at": _ahora()}

    cambios = [f"{c.path} (+{c.added}/-{c.removed})" for c in state.artifacts.changed_files]
    pruebas = [
        f"{p.target}: exit {p.exit_code} en {p.duration_s:.2f}s" for p in state.evidence.test_runs
    ]
    revision = state.outputs.reviewer_output
    pendientes = list(
        state.outputs.researcher_output.unknowns if state.outputs.researcher_output else []
    )

    informe = FinalReport(
        summary=(
            f"ejecucion completada con intencion "
            f"'{state.interpretation.intent.value if state.interpretation else 'desconocida'}'"
        ),
        changes_applied=cambios,
        tests_executed=pruebas,
        review=revision.summary if revision else "no se ejecuto revision",
        pending=pendientes,
    )
    return {
        "final_report": informe,
        "status": RunStatus.COMPLETED,
        "next_step": None,
        "updated_at": _ahora(),
    }


# ------------------------------------------------------------------ enrutado


def route_intent(state: RunState) -> str:
    intencion = state.interpretation.intent if state.interpretation else Intent.INSPECT
    return {
        Intent.QUESTION: "researcher",
        Intent.INSPECT: "researcher",
        Intent.MODIFY: "researcher",
        Intent.OUT_OF_SCOPE: "explain_limits",
    }[intencion]


def route_after_research(state: RunState) -> str:
    intencion = state.interpretation.intent if state.interpretation else Intent.INSPECT
    if intencion is Intent.MODIFY:
        return "coder"
    if intencion is Intent.QUESTION:
        return "answer_direct"
    return "finalize"


def route_after_coder(state: RunState) -> str:
    salida = state.outputs.coder_output
    return "run_tests" if salida and salida.files_changed else "escalate_no_changes"


def route_after_tests(state: RunState) -> str:
    return "finalize" if state.status.is_terminal else "reviewer"


def route_after_review(state: RunState) -> str:
    veredicto = state.outputs.reviewer_output
    if veredicto is None:
        return "escalate"
    if veredicto.decision is ReviewDecision.REQUEST_CHANGES:
        return "coder" if state.budget.review_cycles_used < state.budget.max_review_cycles else "escalate"
    if veredicto.decision is ReviewDecision.ACCEPT:
        return "mark_awaiting"
    return "escalate"
