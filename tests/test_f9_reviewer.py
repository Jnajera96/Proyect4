"""Pruebas de F9: Reviewer semantico con guardas deterministas.

**Que protege este fichero.** Cuatro cosas sin las cuales F9 seria un riesgo en
lugar de una mejora:

  1. **El modelo juzga de verdad.** El Reviewer recibe la peticion, los requisitos
     interpretados, la subtarea, el diff y la evidencia real de pruebas, y su salida
     se valida contra `ReviewVerdict`. No se sustituye por un reflejo del
     `exit_code`: eso era F8, y un semaforo no es un criterio.
  2. **Un test en rojo no se aprueba nunca (REGLA 1).** Aunque el modelo diga
     `accept`, el codigo lo convierte en `request_changes`. Es la garantia que hace
     util tener un modelo aqui: se le permite discrepar, no equivocarse en esto.
  3. **El ciclo de revision esta acotado (REGLA 2).** Agotados los ciclos, un
     `request_changes` se convierte en `escalate`. Sin esto, un Coder que no
     converge y un Reviewer que siempre pide cambios se turnan hasta agotar el
     presupuesto.
  4. **Sin modelo, el sistema sigue revisando (REGLA 3).** El fallback determinista
     no es un andamio: es la via por la que la suite offline y el arranque sin
     credenciales funcionan.

**Por que se prueba la guarda con el modelo diciendo `accept`.** Es el unico caso
que distingue la guarda de la casualidad: si las pruebas ya fallan y el veredicto
determinista ya pide cambios, un test no probaria nada sobre la guarda. Hay que
poner al modelo a aprobar algo roto para comprobar que el codigo no se lo permite.

Ninguna prueba toca la red, las credenciales ni el repositorio del proyecto.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_swe.contracts import (
    AgentRole,
    Budget,
    CodeChange,
    Evidence,
    Finding,
    Instruction,
    InstructionSource,
    Intent,
    Outputs,
    ReviewDecision,
    ReviewVerdict,
    RunOptions,
    RunPlan,
    RunState,
    RunStatus,
    Scope,
    Severity,
    Subtask,
    TaskInterpretation,
    TestRun,
)
from ai_swe.graph import nodes
from ai_swe.models import (
    FakeModelAdapter,
    ModelGateway,
    ModelUsage,
    ProviderResponse,
)

# --------------------------------------------------------------- utilidades

CONTENIDO_NUEVO = "def f():\n    return 42\n"
TEST_QUE_PASA = "def test_pasa():\n    assert 1 == 1\n"
TEST_QUE_FALLA = "def test_falla():\n    assert 1 == 2\n"


def _git(repo: Path, *args: str) -> str:
    resultado = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, shell=False
    )
    assert resultado.returncode == 0, f"git {' '.join(args)} fallo: {resultado.stderr}"
    return resultado.stdout


def _prueba(target: str = "pytest.unit", *, exit_code: int = 0, salida: str = "") -> TestRun:
    return TestRun(
        target=target,
        exit_code=exit_code,
        stdout=salida,
        stderr=salida,
        duration_s=0.1,
        argv=["python", "-m", "pytest"],
    )


def _propuesta() -> dict:
    """El `CodeProposal` que un modelo bien portado devolveria (F6)."""
    return {
        "files": [
            {
                "path": "src/app.py",
                "operation": "modify",
                "new_content": CONTENIDO_NUEVO,
                "rationale": "ajusta el valor de retorno",
            }
        ],
        "rationale": "cambio minimo y verificable",
    }


def _veredicto(
    decision: str, *, fixes: list[str] | None = None, summary: str = "juicio del modelo"
) -> dict:
    """Un `ReviewVerdict` como dict, tal como lo devolveria un modelo."""
    return {
        "decision": decision,
        "findings": [],
        "required_fixes": fixes or [],
        "summary": summary,
    }


def _estado(
    *,
    pruebas: list[TestRun] | None = None,
    ciclos: int = 0,
    max_ciclos: int = 2,
    con_plan: bool = False,
    repo: Path | None = None,
) -> RunState:
    """Estado minimo para ejercitar el nodo `reviewer` sin tocar disco ni red."""
    ahora = datetime.now(UTC)
    plan = None
    if con_plan:
        plan = RunPlan(
            subtasks=[
                Subtask(
                    id="s1",
                    description="corregir el parseo de fechas",
                    agent=AgentRole.CODER,
                    allowed_tools=["read_file", "write_file"],
                    done_criteria="el parseo devuelve una fecha valida",
                )
            ],
            rationale="plan de prueba",
        )
    return RunState(
        run_id="run-f9",
        trace_id="trace-run-f9",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text="corrige el parseo de fechas",
            source=InstructionSource.TEXT,
            confirmed_by_user=True,
        ),
        options=RunOptions(repo_path=str(repo) if repo else ""),
        interpretation=TaskInterpretation(
            intent=Intent.MODIFY,
            scope=Scope(repo_path=str(repo) if repo else "(sin repositorio)"),
            constraints=["no toques la base de datos"],
            confidence=0.9,
            rationale="prueba",
        ),
        plan=plan,
        outputs=Outputs(),
        budget=Budget(review_cycles_used=ciclos, max_review_cycles=max_ciclos),
        evidence=Evidence(test_runs=pruebas or []),
    )


class _AdapterPorRol:
    """Adapter de prueba que responde **segun el rol** que pide.

    `FakeModelAdapter` devuelve la misma salida para cualquier esquema, y en F9 el
    `coder` y el `reviewer` llaman al mismo gateway pidiendo contratos distintos.
    Este doble despacha por `agent_role` para poder decir "el Coder propone esto y
    el Reviewer juzga aquello" en la misma ejecucion.

    Se registran las peticiones para poder afirmar **que** recibio el modelo.
    """

    def __init__(self, por_rol: dict[str, dict]) -> None:
        self._por_rol = por_rol
        self.calls: list = []

    @property
    def name(self) -> str:
        return "por-rol"

    def generate(self, request):
        self.calls.append(request)
        rol = request.agent_role.value if request.agent_role else ""
        datos = self._por_rol.get(rol)
        return ProviderResponse(
            content=json.dumps(datos) if datos is not None else "{}",
            model=request.model or "por-rol",
            finish_reason="stop",
            usage=ModelUsage(input_tokens=10, output_tokens=5),
            provider_request_id="por-rol-1",
        )


@pytest.fixture(autouse=True)
def _inyeccion_limpia():
    """Deja el gateway, el modelo del Reviewer y la raiz de worktrees limpios.

    Son atributos de modulo: sin restaurarlos, una prueba dejaria a las siguientes
    con un gateway falso o una raiz de worktrees que ya no existe.
    """
    yield
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    nodes.usar_modelo_reviewer(None)
    nodes.usar_workspace_root(None)
    nodes.usar_targets_permitidos(None)


def _con_gateway(structured: dict | None) -> None:
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=structured)]))


# ============================================== 1. el modelo juzga (camino feliz)


def test_acepta_cuando_el_modelo_aprueba_y_las_pruebas_pasan() -> None:
    """Escenario (a): el LLM aprueba y las pruebas pasan -> `ACCEPT`.

    El veredicto es **del modelo**, no del `exit_code`: se comprueba que el `summary`
    es el que dijo el modelo, lo que demuestra que su salida llego al estado.
    """
    _con_gateway(_veredicto("accept", summary="el cambio cumple la peticion"))

    delta = nodes.reviewer(_estado(pruebas=[_prueba()]))
    veredicto = delta["outputs"].reviewer_output

    assert veredicto.decision is ReviewDecision.ACCEPT
    assert veredicto.summary == "el cambio cumple la peticion"
    assert delta["next_step"] == "mark_awaiting"


def test_un_accept_no_consume_ciclo_de_revision() -> None:
    """Aprobar no es iterar: `review_cycles_used` solo cuenta vueltas al Coder."""
    _con_gateway(_veredicto("accept"))

    delta = nodes.reviewer(_estado(pruebas=[_prueba()], ciclos=0))

    assert delta["budget"].review_cycles_used == 0


def test_el_modelo_puede_pedir_cambios_aunque_las_pruebas_pasen() -> None:
    """El criterio es del modelo: unas pruebas verdes sobre el cambio equivocado no son exito."""
    _con_gateway(_veredicto("request_changes", fixes=["corregir el alcance del cambio"]))

    delta = nodes.reviewer(_estado(pruebas=[_prueba()]))
    veredicto = delta["outputs"].reviewer_output

    assert veredicto.decision is ReviewDecision.REQUEST_CHANGES
    assert delta["next_step"] == "coder"
    assert delta["budget"].review_cycles_used == 1, "una vuelta al Coder debe consumir un ciclo"


# ================================ 2. REGLA 1: un test en rojo invalida un ACCEPT


def test_el_modelo_no_puede_aprobar_con_pruebas_en_rojo() -> None:
    """Escenario (b): el LLM aprueba pero las pruebas fallan -> veto determinista.

    **Es la prueba central de F9.** El modelo dice `accept` y el codigo lo convierte
    en `request_changes`. Si la guarda no existiera, este cambio se promoveria con
    las pruebas en rojo.
    """
    _con_gateway(_veredicto("accept", summary="me parece correcto"))

    delta = nodes.reviewer(
        _estado(pruebas=[_prueba(exit_code=1, salida="1 failed")])
    )
    veredicto = delta["outputs"].reviewer_output

    assert veredicto.decision is ReviewDecision.REQUEST_CHANGES
    assert delta["next_step"] == "coder"
    assert veredicto.required_fixes, "un rechazo tiene que decir que corregir"
    assert any("pytest.unit" in f for f in veredicto.required_fixes)


def test_el_veto_anade_el_resumen_del_fallo_a_los_hallazgos() -> None:
    """El veto no solo cambia la decision: explica **que** fallo."""
    _con_gateway(_veredicto("accept"))

    delta = nodes.reviewer(
        _estado(pruebas=[_prueba(exit_code=1, salida="1 failed")])
    )
    veredicto = delta["outputs"].reviewer_output

    evidencia = " ".join(f.evidence for f in veredicto.findings)
    assert "pytest.unit" in evidencia
    assert "exit 1" in evidencia
    assert any(f.severity is Severity.HIGH for f in veredicto.findings)


def test_el_veto_no_toca_un_request_changes_del_modelo() -> None:
    """La guarda es un veto, no un reformateo: si el modelo ya pide cambios, no cambia nada."""
    _con_gateway(
        _veredicto("request_changes", fixes=["arregla el retorno"], summary="falta el caso nulo")
    )

    delta = nodes.reviewer(_estado(pruebas=[_prueba(exit_code=1)]))
    veredicto = delta["outputs"].reviewer_output

    assert veredicto.decision is ReviewDecision.REQUEST_CHANGES
    assert veredicto.summary == "falta el caso nulo"
    assert veredicto.required_fixes == ["arregla el retorno"]


def test_un_escalate_del_modelo_sobrevive_a_la_guarda_de_pruebas() -> None:
    """`escalate` no es `accept`: la guarda de pruebas no lo toca."""
    _con_gateway(_veredicto("escalate", summary="no puedo juzgar esto"))

    delta = nodes.reviewer(_estado(pruebas=[_prueba(exit_code=1)]))
    veredicto = delta["outputs"].reviewer_output

    assert veredicto.decision is ReviewDecision.ESCALATE
    assert veredicto.summary == "no puedo juzgar esto"


# ============================== 3. REGLA 2: el limite de ciclos fuerza el escalado


def test_los_ciclos_agotados_convierten_request_changes_en_escalate() -> None:
    """Escenario (c): se excede el limite de ciclos -> veto determinista -> `ESCALATE`.

    El modelo pide cambios y **todavia** tiene razon, pero no queda ciclo para
    intentarlo. La decision pasa a un humano en lugar de iterar sin fin.
    """
    _con_gateway(_veredicto("request_changes", fixes=["otra vez lo mismo"]))

    delta = nodes.reviewer(
        _estado(pruebas=[_prueba(exit_code=1)], ciclos=2, max_ciclos=2)
    )
    veredicto = delta["outputs"].reviewer_output

    assert veredicto.decision is ReviewDecision.ESCALATE
    assert delta["next_step"] == "escalate"
    assert delta["budget"].review_cycles_used == 2, "un escalado no consume ciclo"


def test_con_cero_ciclos_permitidos_el_primer_rechazo_escala() -> None:
    """`max_review_cycles = 0` significa "no se admite rehacer": se escala de inmediato."""
    _con_gateway(_veredicto("request_changes", fixes=["x"]))

    delta = nodes.reviewer(_estado(pruebas=[_prueba(exit_code=1)], ciclos=0, max_ciclos=0))

    assert delta["outputs"].reviewer_output.decision is ReviewDecision.ESCALATE
    assert delta["next_step"] == "escalate"


def test_un_ciclo_disponible_todavia_vuelve_al_coder() -> None:
    """El limite es estricto: con un ciclo libre, se rehace; no se escala antes de tiempo."""
    _con_gateway(_veredicto("request_changes", fixes=["x"]))

    delta = nodes.reviewer(_estado(pruebas=[_prueba(exit_code=1)], ciclos=1, max_ciclos=2))

    assert delta["outputs"].reviewer_output.decision is ReviewDecision.REQUEST_CHANGES
    assert delta["budget"].review_cycles_used == 2


def test_la_guarda_de_ciclos_ve_el_veto_por_pruebas() -> None:
    """**El orden de las guardas importa.** Un `ACCEPT` con pruebas en rojo no es un
    `REQUEST_CHANGES` hasta que actua la REGLA 1; si la REGLA 2 se aplicara antes, no
    lo veria y el veto se colaria sin pasar por el limite de ciclos.

    Se comprueba el caso que distingue el orden: sin ciclos disponibles y con el
    modelo aprobando un cambio roto, el resultado debe ser `ESCALATE`, no
    `REQUEST_CHANGES`.
    """
    _con_gateway(_veredicto("accept"))

    delta = nodes.reviewer(
        _estado(pruebas=[_prueba(exit_code=1)], ciclos=2, max_ciclos=2)
    )
    veredicto = delta["outputs"].reviewer_output

    assert veredicto.decision is ReviewDecision.ESCALATE
    assert delta["budget"].review_cycles_used == 2


# ================================== 4. REGLA 3: el fallback determinista sin modelo


def test_sin_modelo_conectado_usa_el_veredicto_determinista() -> None:
    """Sin gateway, el sistema sigue revisando: no se inventa un `ACCEPT` sin mirar."""
    nodes.usar_gateway(nodes.SIN_GATEWAY)

    delta = nodes.reviewer(_estado(pruebas=[_prueba(exit_code=1)]))
    veredicto = delta["outputs"].reviewer_output

    assert veredicto.decision is ReviewDecision.REQUEST_CHANGES
    assert "determinista" in veredicto.summary, "el fallback debe declararse como tal"


def test_sin_modelo_y_sin_evidencia_se_escala() -> None:
    """Sin pruebas no se puede juzgar: ni aceptar ni rechazar. Se escala."""
    nodes.usar_gateway(nodes.SIN_GATEWAY)

    delta = nodes.reviewer(_estado(pruebas=[]))
    veredicto = delta["outputs"].reviewer_output

    assert veredicto.decision is ReviewDecision.ESCALATE
    assert delta["next_step"] == "escalate"


def test_un_fallo_del_modelo_cae_al_fallback_con_error_tipado() -> None:
    """Si el modelo falla (timeout, reintentos agotados), se degrada **y se declara**."""
    nodes.usar_gateway(
        ModelGateway([FakeModelAdapter(fault="timeout")], max_retries=0, sleep=lambda _s: None)
    )

    delta = nodes.reviewer(_estado(pruebas=[_prueba()]))
    veredicto = delta["outputs"].reviewer_output

    assert veredicto.decision is ReviewDecision.ACCEPT, "las pruebas pasan: el fallback aprueba"
    assert "determinista" in veredicto.summary
    assert any(e.error_class == "MODEL_FALLBACK" for e in delta["errors"])


def test_una_respuesta_que_no_cumple_el_contrato_cae_al_fallback() -> None:
    """Un JSON que no valida contra `ReviewVerdict` no pasa: se degrada, no se acepta."""
    _con_gateway({"decision": "quizas", "summary": "no es un veredicto valido"})

    delta = nodes.reviewer(_estado(pruebas=[_prueba(exit_code=1)]))
    veredicto = delta["outputs"].reviewer_output

    assert veredicto.decision is ReviewDecision.REQUEST_CHANGES
    assert any(e.error_class == "MODEL_FALLBACK" for e in delta["errors"])


def test_el_fallback_tambien_respeta_el_limite_de_ciclos() -> None:
    """Las guardas se aplican al veredicto venga de donde venga."""
    nodes.usar_gateway(nodes.SIN_GATEWAY)

    delta = nodes.reviewer(_estado(pruebas=[_prueba(exit_code=1)], ciclos=2, max_ciclos=2))

    assert delta["outputs"].reviewer_output.decision is ReviewDecision.ESCALATE


# ================================================= 5. que recibe el modelo


def test_el_modelo_recibe_el_contexto_estructurado_completo() -> None:
    """El Reviewer no juzga a ciegas: recibe peticion, requisitos, subtarea, diff y evidencia.

    Se afirma sobre la **peticion registrada por el adapter**, no sobre el prompt: es
    lo unico que prueba que el contexto llego de verdad al modelo.
    """
    adapter = _AdapterPorRol({"reviewer": _veredicto("accept")})
    nodes.usar_gateway(ModelGateway([adapter]))

    estado = _estado(pruebas=[_prueba(exit_code=1, salida="AssertionError: 1 != 2")], con_plan=True)
    estado = estado.model_copy(
        update={
            "outputs": Outputs(
                coder_output=CodeChange(
                    files_changed=[],
                    diff="--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-return 1\n+return 42\n",
                    rationale="prueba",
                    diff_sha256="a" * 64,
                )
            )
        }
    )

    nodes.reviewer(estado)

    peticion = adapter.calls[-1]
    texto = "\n".join(m.content for m in peticion.messages)
    assert "corrige el parseo de fechas" in texto, "falta la peticion del usuario"
    assert "modify" in texto, "falta la intencion interpretada"
    assert "no toques la base de datos" in texto, "faltan las restricciones"
    assert "corregir el parseo de fechas" in texto, "falta la subtarea"
    assert "return 42" in texto, "falta el diff propuesto"
    assert "pytest.unit" in texto and "exit 1" in texto, "falta la evidencia de pruebas"


def test_el_reviewer_pide_su_propio_modelo() -> None:
    """El modelo asignado al Reviewer viaja en la peticion (`reviewer_model`)."""
    adapter = _AdapterPorRol({"reviewer": _veredicto("accept")})
    nodes.usar_gateway(ModelGateway([adapter]))
    nodes.usar_modelo_reviewer("modelo-de-revision")

    nodes.reviewer(_estado(pruebas=[_prueba()]))

    assert adapter.calls[-1].model == "modelo-de-revision"


def test_sin_modelo_asignado_la_peticion_no_impone_ninguno() -> None:
    """Vacio significa "usa el general": la peticion deja el campo a `None`."""
    adapter = _AdapterPorRol({"reviewer": _veredicto("accept")})
    nodes.usar_gateway(ModelGateway([adapter]))
    nodes.usar_modelo_reviewer("")

    nodes.reviewer(_estado(pruebas=[_prueba()]))

    assert adapter.calls[-1].model is None


def test_el_prompt_prohibe_aprobar_con_pruebas_en_rojo() -> None:
    """La regla se le dice al modelo, ademas de imponerla en codigo.

    No sustituye a la guarda -un prompt se ignora-, pero un modelo al que no se le
    dice la regla la incumple mas, y cada incumplimiento gasta un ciclo.
    """
    assert "No apruebes con pruebas en rojo" in nodes.PROMPT_REVISION


# =========================================== 6. el router (fuente unica de ruta)


def test_el_router_traduce_el_veredicto_a_una_ruta() -> None:
    """El router es una traduccion pura: no recalcula el limite de ciclos."""
    base = _estado(pruebas=[_prueba()])

    def con(decision: ReviewDecision) -> RunState:
        return base.model_copy(
            update={
                "outputs": Outputs(
                    reviewer_output=ReviewVerdict(
                        decision=decision,
                        required_fixes=["x"] if decision is ReviewDecision.REQUEST_CHANGES else [],
                        summary="juicio",
                    )
                )
            }
        )

    assert nodes.route_after_review(con(ReviewDecision.ACCEPT)) == "mark_awaiting"
    assert nodes.route_after_review(con(ReviewDecision.REQUEST_CHANGES)) == "coder"
    assert nodes.route_after_review(con(ReviewDecision.ESCALATE)) == "escalate"


def test_sin_veredicto_el_router_escala() -> None:
    """Un estado sin revision no puede aprobar nada."""
    assert nodes.route_after_review(_estado()) == "escalate"


def test_el_nodo_y_el_router_no_pueden_divergir() -> None:
    """`next_step` del nodo y la ruta del router salen de la **misma** funcion.

    Se comprueba sobre los tres veredictos. Si alguien duplicara la logica en el
    router, esta prueba lo detectaria en cuanto una de las dos cambiara.
    """
    casos = {
        "accept": ReviewDecision.ACCEPT,
        "request_changes": ReviewDecision.REQUEST_CHANGES,
        "escalate": ReviewDecision.ESCALATE,
    }
    for crudo, esperada in casos.items():
        _con_gateway(_veredicto(crudo, fixes=["x"] if crudo == "request_changes" else None))
        delta = nodes.reviewer(_estado(pruebas=[_prueba()]))
        estado = _estado(pruebas=[_prueba()]).model_copy(
            update={"outputs": delta["outputs"]}
        )
        assert delta["next_step"] == nodes.route_after_review(estado), (
            f"el nodo y el router divergen para {crudo}"
        )


# ==================================================== 7. integracion con el grafo


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repositorio git real con un `tests/` que pytest puede ejecutar."""
    raiz = tmp_path / "repo_usuario"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "test@localhost")
    _git(raiz, "config", "user.name", "Test")

    (raiz / "src").mkdir()
    (raiz / "src" / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (raiz / "tests").mkdir()
    (raiz / "tests" / "test_ok.py").write_text(TEST_QUE_PASA, encoding="utf-8")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "inicial")
    return raiz


@pytest.fixture
def repo_roto(tmp_path: Path) -> Path:
    """Repositorio git real cuyo `tests/` **falla** de forma permanente."""
    raiz = tmp_path / "repo_roto"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "test@localhost")
    _git(raiz, "config", "user.name", "Test")

    (raiz / "src").mkdir()
    (raiz / "src" / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (raiz / "tests").mkdir()
    (raiz / "tests" / "test_ok.py").write_text(TEST_QUE_FALLA, encoding="utf-8")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "inicial con test rojo")
    return raiz


def _estado_grafo(repo: Path, *, max_ciclos: int = 2) -> RunState:
    ahora = datetime.now(UTC)
    return RunState(
        run_id=f"run-f9-{repo.name}",
        trace_id="trace-f9",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text="corrige el valor de retorno",
            source=InstructionSource.TEXT,
            confirmed_by_user=True,
        ),
        options=RunOptions(repo_path=str(repo)),
        budget=Budget(max_review_cycles=max_ciclos),
    )


def test_el_grafo_aprueba_y_llega_a_la_aprobacion_humana(
    repo: Path, tmp_path: Path
) -> None:
    """Escenario (a) de punta a punta: `ACCEPT` -> `mark_awaiting` -> puerta HITL.

    El unico sustituto es el modelo. El sandbox, las pruebas y la revision por
    guardas son los de produccion: el grafo crea un worktree real, ejecuta pytest de
    verdad y acepta el cambio porque la evidencia lo respalda.
    """
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command

    from ai_swe.graph.workflow import construir_grafo

    nodes.usar_workspace_root(tmp_path / "workspaces")
    nodes.usar_targets_permitidos(("pytest.unit",))
    # El modelo propone el cambio; el Reviewer recibira esa misma salida, no cumplira
    # `ReviewVerdict` y caera al veredicto determinista, que con las pruebas en verde
    # aprueba. El camino ACCEPT -> HITL se ejercita entero.
    _con_gateway(_propuesta())

    app = construir_grafo().compile(checkpointer=InMemorySaver())
    estado = _estado_grafo(repo)
    cfg = {"configurable": {"thread_id": estado.run_id}}

    # M2: la primera parada es la puerta de requisitos, no la de aprobacion.
    primera = app.invoke(estado, cfg)
    assert primera.get("__interrupt__"), "no se pauso en la puerta de requisitos"
    salida = app.invoke(Command(resume="approved"), cfg)

    assert salida.get("__interrupt__"), "no se llego a la puerta de aprobacion"
    pausado = RunState.model_validate(app.get_state(cfg).values)
    assert pausado.status is RunStatus.AWAITING_APPROVAL
    assert pausado.outputs.reviewer_output is not None
    assert pausado.outputs.reviewer_output.decision is ReviewDecision.ACCEPT
    assert pausado.evidence.test_runs[-1].exit_code == 0


def test_el_grafo_veta_y_escala_cuando_las_pruebas_no_se_arreglan(
    repo_roto: Path, tmp_path: Path
) -> None:
    """Escenarios (b) y (c) de punta a punta: veto por pruebas y luego escalado.

    El repositorio tiene un test que falla y el cambio propuesto no lo arregla, asi
    que la evidencia siempre esta en rojo. Con `max_review_cycles=1`:

      1. El Reviewer veta (las pruebas fallan) y vuelve al Coder: `REQUEST_CHANGES`.
      2. Al agotarse el ciclo, la guarda de ciclos convierte el siguiente rechazo en
         `ESCALATE`, y la ejecucion termina en `needs_human`.

    Prueba las dos guardas y las dos rutas de una vez, sobre el grafo real.
    """
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command

    from ai_swe.graph.workflow import construir_grafo

    nodes.usar_workspace_root(tmp_path / "workspaces")
    nodes.usar_targets_permitidos(("pytest.unit",))
    _con_gateway(_propuesta())

    app = construir_grafo().compile(checkpointer=InMemorySaver())
    estado = _estado_grafo(repo_roto, max_ciclos=1)
    cfg = {"configurable": {"thread_id": estado.run_id}}

    # M2: hay que confirmar los requisitos antes de que empiece el trabajo.
    primera = app.invoke(estado, cfg)
    assert primera.get("__interrupt__"), "no se pauso en la puerta de requisitos"
    app.invoke(Command(resume="approved"), cfg)
    final = RunState.model_validate(app.get_state(cfg).values)

    assert final.status is RunStatus.NEEDS_HUMAN
    assert final.outputs.reviewer_output is not None
    assert final.outputs.reviewer_output.decision is ReviewDecision.ESCALATE
    assert final.budget.review_cycles_used == 1, "se consumio el unico ciclo disponible"
    # La evidencia es real: se ejecuto pytest y fallo.
    assert final.evidence.test_runs
    assert final.evidence.test_runs[-1].exit_code != 0


def test_el_reviewer_no_escribe_en_el_repositorio_del_usuario(
    repo: Path, tmp_path: Path
) -> None:
    """Revisar es juzgar: el nodo no toca el arbol del usuario.

    Se confirman los requisitos y se comprueba que la ejecucion **llego de verdad** a
    la puerta de aprobacion antes de afirmar que el repositorio esta intacto. Sin
    eso, la prueba pasaria por un motivo falso: un grafo detenido en la puerta de
    requisitos no ha tocado nada simplemente porque no ha hecho nada.
    """
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command

    from ai_swe.graph.workflow import construir_grafo

    antes = (repo / "src" / "app.py").read_text(encoding="utf-8")

    nodes.usar_workspace_root(tmp_path / "workspaces")
    nodes.usar_targets_permitidos(("pytest.unit",))
    _con_gateway(_propuesta())

    app = construir_grafo().compile(checkpointer=InMemorySaver())
    estado = _estado_grafo(repo)
    cfg = {"configurable": {"thread_id": estado.run_id}}
    app.invoke(estado, cfg)
    app.invoke(Command(resume="approved"), cfg)

    final = RunState.model_validate(app.get_state(cfg).values)
    assert final.status is RunStatus.AWAITING_APPROVAL, (
        "la ejecucion no llego a trabajar, asi que no probo nada"
    )
    assert final.artifacts.worktree_path, "no hubo sandbox: no se ejercito la escritura"

    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == antes
    assert _git(repo, "status", "--porcelain").strip() == ""
