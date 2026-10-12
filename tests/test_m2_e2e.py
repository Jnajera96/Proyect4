"""Pruebas de integracion de extremo a extremo del Milestone 2 (M2).

**Que protege este fichero.** La cadena completa del DoD de M2, recorrida de verdad
sobre el grafo de produccion:

    interpret -> confirm_requirements_gate -> plan -> researcher -> coder
      -> apply_sandbox -> run_tests -> reviewer -> approval_gate -> finalize

Ninguna pieza se sustituye por un doble salvo el **modelo** (no hay credenciales) y
el **humano** (se responde con `Command(resume=...)`, que es exactamente lo que
hace la API). Todo lo demas es produccion: el sandbox crea un `git worktree` real,
pytest se ejecuta en un subproceso real, y el Reviewer juzga la evidencia real.

**Las dos puertas humanas se ejercitan.** M2 tiene dos y en momentos distintos:
`confirm_requirements_gate` confirma lo que el sistema **entendio** (antes de
planificar) y `approval_gate` aprueba lo que el sistema **hizo** (despues de
probarlo). Una prueba que solo reanudara una de las dos no probaria el flujo de M2,
probaria medio flujo.

**Escenarios cubiertos** (los tres que pide el cierre de M2):

  a) `ACCEPT` directo: el Reviewer aprueba y las pruebas pasan -> puerta de
     aprobacion -> promocion -> `completed`.
  b) `REQUEST_CHANGES`: el Reviewer pide cambios, el Coder rehace y el Reviewer
     acepta -> el ciclo Coder<->Reviewer funciona y converge.
  c) Veto por fallos de tests: el modelo aprueba pero la evidencia esta en rojo ->
     veto determinista -> se agota el ciclo -> `needs_human`.

Ninguna prueba toca la red, las credenciales ni el repositorio del proyecto.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from ai_swe.contracts import (
    Budget,
    Instruction,
    InstructionSource,
    Intent,
    RunOptions,
    RunState,
    RunStatus,
    TaskInterpretation,
)
from ai_swe.graph import nodes
from ai_swe.graph.workflow import construir_grafo
from ai_swe.models import ModelGateway, ModelUsage, ProviderResponse

# --------------------------------------------------------------- utilidades

TEST_QUE_PASA = "def test_pasa():\n    assert 1 == 1\n"
TEST_QUE_FALLA = "def test_falla():\n    assert 1 == 2\n"
CONTENIDO_NUEVO = "def f():\n    return 42\n"


def _git(repo: Path, *args: str) -> str:
    resultado = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, shell=False
    )
    assert resultado.returncode == 0, f"git {' '.join(args)} fallo: {resultado.stderr}"
    return resultado.stdout


def _crear_repo(raiz: Path, *, test: str) -> Path:
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "test@localhost")
    _git(raiz, "config", "user.name", "Test")
    (raiz / "src").mkdir()
    (raiz / "src" / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (raiz / "tests").mkdir()
    (raiz / "tests" / "test_ok.py").write_text(test, encoding="utf-8")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "inicial")
    return raiz


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repositorio git real cuyo `tests/` **pasa**."""
    return _crear_repo(tmp_path / "repo_ok", test=TEST_QUE_PASA)


@pytest.fixture
def repo_roto(tmp_path: Path) -> Path:
    """Repositorio git real cuyo `tests/` **falla** siempre."""
    return _crear_repo(tmp_path / "repo_roto", test=TEST_QUE_FALLA)


# --------------------------------------------------- dobles: modelo y humano


class _AdapterPorContrato:
    """Adapter de prueba que responde segun el **contrato** que se le pide.

    El gateway deriva el JSON Schema del contrato (`response_model`) y lo deja en
    `request.json_schema`, cuyo `title` es el nombre del modelo Pydantic. Es el
    unico discriminador fiable: `agent_role` no sirve porque `interpret` y `plan`
    son los dos del Supervisor, y un adapter que devolviera siempre lo mismo no
    podria alimentar cuatro nodos con cuatro contratos distintos.

    Cada contrato puede llevar una **lista** de respuestas, que se consumen en
    orden. Es lo que permite decir "el Reviewer pide cambios primero y acepta
    despues" sin tocar el codigo del nodo entre llamadas.
    """

    def __init__(self, por_titulo: dict[str, object]) -> None:
        self._por_titulo = por_titulo
        self.calls: list = []

    @property
    def name(self) -> str:
        return "por-contrato"

    def generate(self, request):
        self.calls.append(request)
        titulo = (request.json_schema or {}).get("title", "")
        respuesta = self._por_titulo.get(titulo)
        if isinstance(respuesta, list):
            datos = respuesta.pop(0) if respuesta else None
        else:
            datos = respuesta
        return ProviderResponse(
            content=json.dumps(datos) if datos is not None else "{}",
            model=request.model or "por-contrato",
            finish_reason="stop",
            usage=ModelUsage(input_tokens=10, output_tokens=5),
            provider_request_id="por-contrato-1",
        )


def _interpretacion() -> dict:
    return {
        "intent": "modify",
        "scope": {"repo_path": ".", "allowed_paths": [], "protected_paths": []},
        "constraints": ["no toques la base de datos"],
        "confidence": 0.9,
        "rationale": "el usuario pide un cambio concreto en el codigo",
    }


def _plan() -> dict:
    """Plan de dos subtareas: investigar y luego cambiar. Es la forma que recorre
    el camino completo que pide el DoD (`plan -> researcher -> coder`)."""
    return {
        "subtasks": [
            {
                "id": "investigar",
                "description": "localizar el valor de retorno actual",
                "agent": "researcher",
                "allowed_tools": ["list_files", "read_file"],
                "done_criteria": "se conoce el contenido de src/app.py",
            },
            {
                "id": "cambiar",
                "description": "ajustar el valor de retorno",
                "agent": "coder",
                "depends_on": ["investigar"],
                "allowed_tools": ["read_file", "write_file"],
                "done_criteria": "src/app.py devuelve 42",
            },
        ],
        "max_review_cycles": 2,
        "rationale": "investigar antes de cambiar",
    }


def _propuesta() -> dict:
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


def _veredicto(decision: str, *, fixes: list[str] | None = None) -> dict:
    return {
        "decision": decision,
        "findings": [],
        "required_fixes": fixes or [],
        "summary": f"juicio del modelo: {decision}",
    }


def _gateway(veredictos: object, *, propuesta: dict | None = None) -> _AdapterPorContrato:
    adapter = _AdapterPorContrato(
        {
            "TaskInterpretation": _interpretacion(),
            "RunPlan": _plan(),
            "CodeProposal": propuesta if propuesta is not None else _propuesta(),
            "ReviewVerdict": veredictos,
        }
    )
    nodes.usar_gateway(ModelGateway([adapter]))
    return adapter


@pytest.fixture(autouse=True)
def _inyeccion_limpia(tmp_path: Path):
    """Deja gateway, modelo del Reviewer y raiz de worktrees limpios al terminar."""
    nodes.usar_workspace_root(tmp_path / "workspaces")
    nodes.usar_targets_permitidos(("pytest.unit",))
    yield
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    nodes.usar_modelo_reviewer(None)
    nodes.usar_workspace_root(None)
    nodes.usar_targets_permitidos(None)


# --------------------------------------------------------------- motor de la prueba


def _estado(repo: Path, *, run_id: str, max_ciclos: int = 2) -> RunState:
    ahora = datetime.now(UTC)
    return RunState(
        run_id=run_id,
        trace_id=f"trace-{run_id}",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text="corrige el valor de retorno de f",
            source=InstructionSource.TEXT,
            confirmed_by_user=True,
        ),
        options=RunOptions(repo_path=str(repo)),
        budget=Budget(max_review_cycles=max_ciclos),
    )


def _app():
    return construir_grafo().compile(checkpointer=InMemorySaver())


def _estado_de(app, cfg) -> RunState:
    return RunState.model_validate(app.get_state(cfg).values)


def _arrancar_hasta_confirmar_requisitos(app, estado: RunState):
    """Lanza el grafo y comprueba que se detiene en la **primera** puerta humana.

    Devuelve el estado pausado. Que se detenga aqui es en si mismo una asercion:
    si la puerta de requisitos no existiera, la ejecucion habria seguido hasta la
    puerta de aprobacion sin que nadie confirmara la interpretacion.
    """
    cfg = {"configurable": {"thread_id": estado.run_id}}
    app.invoke(estado, cfg)
    pausado = _estado_de(app, cfg)
    assert pausado.status is RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION, (
        f"no se detuvo en la puerta de requisitos, sino en '{pausado.status.value}'"
    )
    assert pausado.interpretation is not None
    assert pausado.interpretation.confirmed_by_user is False
    return cfg


# ==================================================== a) ACCEPT directo


def test_m2_completo_con_accept_directo(repo: Path) -> None:
    """El camino feliz de M2, de punta a punta.

    Recorre las 15 estaciones del DoD: entrada, analista de requisitos, confirmacion
    humana, plan valido, researcher con evidencia, coder con `CodeChange`, cambio en
    worktree aislado, ejecucion de pruebas, revision, aceptacion, HITL, aprobacion,
    estado terminal, y persistencia del estado en cada paso.
    """
    _gateway(_veredicto("accept"))
    app = _app()
    estado = _estado(repo, run_id="run-m2-aceptar")

    # --- Estaciones 1-3: entrada, analista y confirmacion humana -------------
    cfg = _arrancar_hasta_confirmar_requisitos(app, estado)

    # El humano confirma. A partir de aqui el sistema planifica lo que entendio.
    app.invoke(Command(resume="approved"), cfg)

    pausado = _estado_de(app, cfg)
    # --- Estaciones 4-13: plan, investigacion, cambio, pruebas, revision, HITL
    assert pausado.status is RunStatus.AWAITING_APPROVAL, (
        f"no se llego a la puerta de aprobacion, sino a '{pausado.status.value}'"
    )
    assert pausado.interpretation.confirmed_by_user is True
    assert pausado.plan is not None and len(pausado.plan.subtasks) == 2
    assert pausado.evidence.findings, "el researcher no dejo evidencia"
    assert pausado.outputs.coder_output is not None
    assert pausado.outputs.coder_output.files_changed
    assert pausado.artifacts.worktree_path, "no se creo el worktree"
    assert Path(pausado.artifacts.worktree_path).is_dir()
    # La evidencia de pruebas es real, no fabricada.
    assert pausado.evidence.test_runs
    assert pausado.evidence.test_runs[-1].exit_code == 0
    assert "1 passed" in pausado.evidence.test_runs[-1].stdout
    assert pausado.outputs.reviewer_output is not None
    assert pausado.outputs.reviewer_output.decision.value == "accept"
    # El repositorio del usuario sigue intacto: todo ocurrio en el worktree.
    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == "def f():\n    return 1\n"

    # --- Estaciones 13-15: aprobacion humana, estado terminal ----------------
    app.invoke(Command(resume="approved"), cfg)
    final = _estado_de(app, cfg)

    assert final.status is RunStatus.COMPLETED
    assert final.status.is_terminal
    assert final.final_report is not None
    assert final.approvals, "la aprobacion humana no quedo registrada"
    assert final.approvals[-1].decision.value == "approved"


def test_el_repositorio_del_usuario_solo_se_toca_al_aprobar(repo: Path) -> None:
    """F12: el arbol del usuario queda intacto **hasta** que el humano aprueba.

    Hasta F11 esta prueba afirmaba que el repositorio **nunca** se tocaba, porque
    aprobar no promovia nada. F12 cierra ese tramo: aprobar escribe el cambio. Lo
    que sigue siendo cierto -y es lo que de verdad protege- es que **antes** de la
    aprobacion el repositorio esta limpio: todo ocurre en el worktree aislado.
    """
    _gateway(_veredicto("accept"))
    app = _app()
    estado = _estado(repo, run_id="run-m2-limpio")
    cfg = _arrancar_hasta_confirmar_requisitos(app, estado)

    app.invoke(Command(resume="approved"), cfg)
    pausado = _estado_de(app, cfg)
    assert pausado.status is RunStatus.AWAITING_APPROVAL
    # Nada se ha tocado todavia: el cambio vive en el worktree.
    assert _git(repo, "status", "--porcelain").strip() == ""
    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == "def f():\n    return 1\n"

    app.invoke(Command(resume="approved"), cfg)
    final = _estado_de(app, cfg)

    assert final.status is RunStatus.COMPLETED
    # Tras aprobar, el cambio esta en el repositorio del usuario.
    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == CONTENIDO_NUEVO


def test_un_rechazo_de_requisitos_no_planifica(repo: Path) -> None:
    """Rechazar la interpretacion cierra la ejecucion en lugar de planificar sobre ella."""
    _gateway(_veredicto("accept"))
    app = _app()
    estado = _estado(repo, run_id="run-m2-rechazo")
    cfg = _arrancar_hasta_confirmar_requisitos(app, estado)

    app.invoke(Command(resume="rejected"), cfg)
    final = _estado_de(app, cfg)

    assert final.status is RunStatus.NEEDS_HUMAN
    assert final.plan is None, "se planifico sobre unos requisitos rechazados"
    assert final.interpretation.confirmed_by_user is False
    assert any(e.error_class == "REQUIREMENTS_REJECTED" for e in final.errors)


def test_una_modificacion_humana_corrige_los_requisitos(repo: Path) -> None:
    """El humano puede **corregir** la interpretacion, no solo aceptarla o rechazarla."""
    _gateway(_veredicto("accept"))
    app = _app()
    estado = _estado(repo, run_id="run-m2-modifica")
    cfg = _arrancar_hasta_confirmar_requisitos(app, estado)

    app.invoke(
        Command(
            resume={
                "decision": "modified",
                "constraints": ["no toques la base de datos", "anade una prueba"],
            }
        ),
        cfg,
    )
    final = _estado_de(app, cfg)

    assert final.interpretation.confirmed_by_user is True
    assert "anade una prueba" in final.interpretation.constraints


def test_una_reanudacion_irreconocible_no_confirma(repo: Path) -> None:
    """Ante una respuesta que no se entiende, **no** se confirma en nombre de nadie.

    El sentido del fallo importa: si un valor desconocido se tratara como aprobado,
    un error del cliente confirmaria los requisitos solo, y la puerta seria
    decorativa.
    """
    _gateway(_veredicto("accept"))
    app = _app()
    estado = _estado(repo, run_id="run-m2-desconocida")
    cfg = _arrancar_hasta_confirmar_requisitos(app, estado)

    app.invoke(Command(resume="lo que sea"), cfg)
    final = _estado_de(app, cfg)

    assert final.status is RunStatus.NEEDS_HUMAN
    assert final.interpretation.confirmed_by_user is False
    assert final.plan is None


# ==================================== b) REQUEST_CHANGES (re-iteracion)


def test_m2_reitera_tras_request_changes_y_converge(repo: Path) -> None:
    """El ciclo Coder<->Reviewer: el Reviewer pide cambios, el Coder rehace y se acepta.

    El adapter devuelve `request_changes` en la **primera** revision y `accept` en la
    segunda. Se comprueba que se consumio un ciclo y que la ejecucion llega igualmente
    a la puerta de aprobacion: pedir cambios no es un fallo, es el bucle funcionando.
    """
    _gateway([_veredicto("request_changes", fixes=["el valor de retorno no es 42"]), _veredicto("accept")])
    app = _app()
    estado = _estado(repo, run_id="run-m2-reitera")
    cfg = _arrancar_hasta_confirmar_requisitos(app, estado)

    app.invoke(Command(resume="approved"), cfg)
    pausado = _estado_de(app, cfg)

    assert pausado.status is RunStatus.AWAITING_APPROVAL
    assert pausado.budget.review_cycles_used == 1, "el ciclo de re-trabajo no se contabilizo"
    assert pausado.outputs.reviewer_output.decision.value == "accept"
    # El cambio se aplico dos veces (una por vuelta), pero en el worktree, no en el repo.
    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == "def f():\n    return 1\n"


# ======================================== c) veto por fallos de tests


def test_m2_veta_un_accept_con_pruebas_en_rojo_y_escala(repo_roto: Path) -> None:
    """El modelo aprueba, las pruebas fallan, y el sistema **no** promueve.

    Con `max_review_cycles=1`: la primera revision veta (REGLA 1) y vuelve al Coder;
    la segunda veta otra vez y, sin ciclos, escala (REGLA 2). La ejecucion termina en
    `needs_human` con la evidencia del fallo, que es lo que un humano necesita para
    decidir. Un `accept` del modelo con las pruebas en rojo no promueve nada.
    """
    _gateway(_veredicto("accept"))
    app = _app()
    estado = _estado(repo_roto, run_id="run-m2-veto", max_ciclos=1)
    cfg = _arrancar_hasta_confirmar_requisitos(app, estado)

    app.invoke(Command(resume="approved"), cfg)
    final = _estado_de(app, cfg)

    assert final.status is RunStatus.NEEDS_HUMAN
    assert final.status.is_terminal
    # El veredicto final es un escalado: el modelo dijo `accept` y el codigo no lo permitio.
    assert final.outputs.reviewer_output.decision.value == "escalate"
    # Y el veto por pruebas dejo su rastro en los hallazgos.
    explicaciones = " ".join(f.explanation for f in final.outputs.reviewer_output.findings)
    assert "veto" in explicaciones.lower()
    # La evidencia es real: se ejecuto pytest y fallo.
    assert final.evidence.test_runs
    assert final.evidence.test_runs[-1].exit_code != 0
    # Nunca se llego a la puerta de aprobacion, asi que no hay nada promovido.
    assert final.approvals == []
    assert (repo_roto / "src" / "app.py").read_text(encoding="utf-8") == "def f():\n    return 1\n"


# ==================================================== invariantes de la topologia


def test_la_puerta_de_requisitos_esta_entre_interpret_y_plan() -> None:
    """La posicion del nodo es la que impide planificar sin confirmar.

    Se comprueba sobre el `StateGraph` sin compilar y **ejercitando el router**: un
    nodo colocado en otro sitio seguiria apareciendo en `nodes`, asi que la
    presencia no basta.
    """
    grafo = construir_grafo()
    assert "confirm_requirements_gate" in set(grafo.nodes)
    assert "mark_awaiting_requirements" in set(grafo.nodes)
    # La arista estatica que precede a la puerta.
    assert ("mark_awaiting_requirements", "confirm_requirements_gate") in grafo.edges

    estado = _estado(Path("."), run_id="run-ruta")
    sin_confirmar = estado.model_copy(
        update={
            "interpretation": TaskInterpretation(
                intent=Intent.MODIFY,
                scope={"repo_path": "."},
                confidence=0.9,
                rationale="prueba",
            )
        }
    )
    assert nodes.route_after_interpret(sin_confirmar) == "mark_awaiting_requirements"

    confirmada = sin_confirmar.model_copy(
        update={
            "interpretation": sin_confirmar.interpretation.model_copy(
                update={"confirmed_by_user": True}
            )
        }
    )
    assert nodes.route_after_interpret(confirmada) == "plan"

    # Se construye un `TaskInterpretation` nuevo en lugar de parchear el existente
    # con `model_copy`: `model_copy` **no ejecuta los validadores**, asi que dejaria
    # `intent` como cadena cruda y la comparacion por identidad del router fallaria
    # por un motivo que no tiene nada que ver con lo que se quiere comprobar.
    fuera = estado.model_copy(
        update={
            "interpretation": TaskInterpretation(
                intent=Intent.OUT_OF_SCOPE,
                scope={"repo_path": "."},
                confidence=0.9,
                rationale="prueba",
            )
        }
    )
    assert nodes.route_after_interpret(fuera) == "explain_limits", (
        "no se pide confirmar unos requisitos que el sistema va a rechazar igualmente"
    )


def test_una_espera_humana_no_es_un_camino_sin_salida() -> None:
    """La red de seguridad de `MET-13` distingue esperar de colgarse.

    Sin esto, una ejecucion pausada en la puerta de requisitos se forzaria a
    `needs_human` como si la topologia tuviera un camino sin salida.
    """
    from ai_swe.graph.engine import RunEngine

    estado = _estado(Path("."), run_id="run-espera").model_copy(
        update={"status": RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION}
    )

    assert RunEngine._aplicar_red_de_seguridad(estado).status is (
        RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION
    )
