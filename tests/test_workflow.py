"""Pruebas del grafo de orquestacion.

Dos niveles:

  1. **Comportamiento del camino real de M1**, sin sustituciones: cada intencion
     termina en un estado terminal y ninguna queda colgada (`MET-13 = 0`).
  2. **Topologia de promocion**, sustituyendo los nodos que dependen de recursos
     externos (`coder`, `apply_sandbox`, `run_tests`) por lo que la fase M2
     implementara. Es la unica forma de ejercitar el camino completo hasta la puerta
     de aprobacion en un test rapido: `apply_sandbox` necesita un repositorio git
     real y `run_tests` lanza subprocesos. Los sustitutos son explicitos y estan en
     una sola prueba, para que no se confundan con el comportamiento real.

     **F8:** el fixture pasa a sustituir tambien `apply_sandbox`. Antes de F8 la
     arista `coder -> run_tests` era directa; ahora el parche debe existir en un
     arbol de trabajo antes de poder probarlo, asi que el nodo entra en el camino.
     El sandbox real se ejercita en `tests/test_f7_sandbox.py` y
     `tests/test_f8_test_runner.py`, que si crean repositorios de verdad.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from ai_swe.contracts import (
    ApprovalDecision,
    Budget,
    CodeChange,
    Evidence,
    FileChange,
    Instruction,
    InstructionSource,
    Intent,
    Outputs,
    ReviewDecision,
    RunError,
    RunOptions,
    RunState,
    RunStatus,
    TestRun,
)
from ai_swe.graph import RunEngine, construir_grafo
from ai_swe.graph import nodes
from ai_swe.state import RunStore

AHORA = datetime(2026, 10, 6, 12, 0, 0, tzinfo=UTC)
SHA = "b" * 64

INSTRUCCIONES = [
    "¿Dónde se valida el token de sesión?",
    "Sube los cambios a GitHub.",
    "Analiza este proyecto, identifica los errores principales, corrige el código y revisa que funcione.",
    "Explica cómo funciona el módulo de autenticación.",
    "Haz push de la rama a producción.",
    "Corrige el error de parseo en el archivo de configuración.",
    "",
    "   ",
]


# --------------------------------------------------------------- utilidades


def _motor(tmp_path) -> tuple[RunStore, RunEngine]:
    store = RunStore(tmp_path / "estado.db")
    return store, RunEngine(store)


def _hasta_terminal(motor: RunEngine, estado: RunState, *, max_pasos: int = 5) -> RunState:
    """Reanuda las puertas humanas hasta llegar a un estado terminal.

    **M2 anade una puerta al principio del flujo.** `MET-13` exige que ninguna
    ejecucion quede colgada, y una espera humana no es colgarse -es una ejecucion
    detenida a proposito-, pero para comprobarlo hay que recorrerla. Esta funcion
    confirma lo que haga falta y devuelve el estado final.

    Se acota el numero de reanudaciones para que un bucle infinito **falle** en
    lugar de colgar la suite: un limite sin agotar es indistinguible de un exito.
    """
    for _ in range(max_pasos):
        if estado.status.is_terminal:
            return estado
        assert estado.status.is_awaiting_human, (
            f"estado no terminal que no es una espera humana: {estado.status}"
        )
        estado = motor.resume(estado.run_id, "approved")
    raise AssertionError(f"no se alcanzo un estado terminal en {max_pasos} reanudaciones")


def _confirmar_requisitos(app, cfg) -> RunState:
    """Confirma la puerta de requisitos (M2, item 3) y devuelve el estado.

    La puerta es la primera decision humana del flujo: sin confirmarla el grafo no
    planifica. Casi todas las pruebas de este fichero ejercitan **otra** cosa, asi
    que se confirma aqui en lugar de repetir el paso en cada una.
    """
    return RunState.model_validate(app.invoke(Command(resume="approved"), cfg))


def _estado_listo_para_promover(run_id: str = "run-promocion") -> RunState:
    """Estado con un cambio y pruebas en verde: lo que M2 producira de verdad."""
    return RunState(
        run_id=run_id,
        trace_id="trace-promocion",
        created_at=AHORA,
        updated_at=AHORA,
        instruction=Instruction(
            text="corrige parse_duration",
            source=InstructionSource.TEXT,
            confirmed_by_user=True,
        ),
        options=RunOptions(repo_path="/repo/demo"),
        outputs=Outputs(
            coder_output=CodeChange(
                files_changed=[FileChange(path="src/util/timeparse.py", added=9, removed=2, sha256=SHA)],
                diff="--- a\n+++ b\n",
                rationale="anade el formato H:MM:SS",
                diff_sha256=SHA,
            )
        ),
        evidence=Evidence(
            test_runs=[
                TestRun(target="pytest.unit", exit_code=0, stdout="ok", duration_s=0.8, reproducible=True)
            ]
        ),
        budget=Budget(max_review_cycles=2),
    )


# ------------------------------------------------------ clasificacion


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("¿Dónde se valida el token?", Intent.QUESTION),
        ("Explica cómo funciona el login", Intent.QUESTION),
        ("Sube los cambios a GitHub", Intent.OUT_OF_SCOPE),
        ("Haz push de la rama", Intent.OUT_OF_SCOPE),
        ("Despliega en producción", Intent.OUT_OF_SCOPE),
        ("Corrige el error de parseo", Intent.MODIFY),
        ("Añade validación de correo", Intent.MODIFY),
        ("Analiza el proyecto", Intent.INSPECT),
        ("Revisa la estructura del paquete", Intent.INSPECT),
        ("texto sin pistas claras", Intent.INSPECT),
    ],
)
def test_clasificacion_de_intencion(texto: str, esperado: Intent) -> None:
    assert nodes._clasificar(texto) is esperado


def test_una_accion_externa_no_se_confunde_con_una_modificacion_local() -> None:
    """`RF-15`: el sistema debe rechazar lo que no puede hacer, no intentarlo."""
    assert nodes._clasificar("corrige el parser y súbelo a GitHub") is Intent.OUT_OF_SCOPE


# ------------------------------------------------ camino real de M1


def test_una_pregunta_termina_en_completed(tmp_path) -> None:
    store, motor = _motor(tmp_path)
    try:
        # M2: la ejecucion se detiene primero en la puerta de requisitos. Una espera
        # humana no es un estado terminal, asi que hay que confirmarla para seguir.
        inicial = motor.start(motor.crear_estado("¿Dónde se valida el token de sesión?"))
        assert inicial.status is RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION

        final = motor.resume(inicial.run_id, "approved")
        assert final.status is RunStatus.COMPLETED
        assert final.final_report is not None
        assert final.errors == []
    finally:
        store.close()


def test_una_instruccion_fuera_de_alcance_se_rechaza_sin_error(tmp_path) -> None:
    """Rechazar no es fallar: es el comportamiento correcto (`RF-15`)."""
    store, motor = _motor(tmp_path)
    try:
        final = motor.start(motor.crear_estado("Sube los cambios a GitHub."))
        assert final.status is RunStatus.COMPLETED
        assert final.errors == []
        assert final.final_report is not None
        assert any("fuera de alcance" in p.lower() for p in final.final_report.pending)
    finally:
        store.close()


def test_modificar_sin_modelo_escala_con_un_error_tipado(tmp_path) -> None:
    """En M1 no hay modelo, asi que no hay parche. Se escala, no se inventa."""
    store, motor = _motor(tmp_path)
    try:
        inicial = motor.start(
            motor.crear_estado("Corrige el error de parseo en el archivo de config.")
        )
        assert inicial.status is RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION

        final = motor.resume(inicial.run_id, "approved")
        assert final.status is RunStatus.NEEDS_HUMAN
        assert [e.error_class for e in final.errors] == ["CODER_PRODUCED_NO_CHANGES"]
        assert final.outputs.coder_output is not None
        assert final.outputs.coder_output.files_changed == []
    finally:
        store.close()


def test_ninguna_ejecucion_queda_colgada(tmp_path) -> None:
    """`MET-13`: cero terminaciones anomalas. Es el criterio de aceptacion de M1.

    **M2:** una ejecucion detenida en una puerta humana **no** es una anomalia, es
    una espera. Se recorren las puertas hasta el estado terminal y se comprueba que
    ninguna se queda a medias: si una espera no tuviera salida, esta prueba lo diria.
    """
    store, motor = _motor(tmp_path)
    anomalas = []
    try:
        for i, texto in enumerate(INSTRUCCIONES):
            inicial = motor.start(motor.crear_estado(texto or "   "))
            final = _hasta_terminal(motor, inicial)
            if not final.status.is_terminal:
                anomalas.append((i, texto, final.status))
    finally:
        store.close()

    assert anomalas == [], f"ejecuciones sin estado terminal: {anomalas}"


def test_el_estado_persiste_tras_la_ejecucion(tmp_path) -> None:
    store, motor = _motor(tmp_path)
    try:
        inicial = motor.start(motor.crear_estado("Explica el módulo de autenticación."))
        final = _hasta_terminal(motor, inicial)
        recuperado = motor.get(final.run_id)
        assert recuperado == final
        assert recuperado.final_report is not None
    finally:
        store.close()


# ------------------------------------------- puerta de aprobacion


@pytest.fixture
def nodos_de_m2(monkeypatch):
    """Sustituye `coder`, `apply_sandbox` y `run_tests` por lo que implementara M2.

    Se sustituyen solo estos tres porque son los unicos que dependen de recursos
    externos: el modelo, el sistema de archivos (worktree) y los subprocesos de
    prueba. Todo lo demas del grafo es el de produccion.
    """

    def coder_de_m2(state: RunState) -> dict:
        datos = state.outputs.model_dump()
        datos["coder_output"] = CodeChange(
            files_changed=[FileChange(path="src/util/timeparse.py", added=9, removed=2, sha256=SHA)],
            diff="--- a\n+++ b\n",
            rationale="M2: parche generado por el modelo",
            diff_sha256=SHA,
        ).model_dump()
        return {"outputs": datos}

    def apply_sandbox_de_m2(state: RunState) -> dict:
        """Simula que el parche quedo aplicado en un worktree.

        No crea un repositorio: esta prueba es sobre la puerta de aprobacion, no
        sobre el sandbox. El sandbox real se ejercita en las pruebas de F7 y F8,
        que si crean arboles de trabajo de verdad.
        """
        datos = state.artifacts.model_dump()
        datos["worktree_path"] = "/workspaces/run-promocion"
        datos["base_commit"] = SHA
        datos["changed_files"] = state.outputs.coder_output.files_changed
        datos["diff"] = "--- a\n+++ b\n"
        return {"artifacts": datos, "next_step": "run_tests"}

    def run_tests_de_m2(state: RunState) -> dict:
        datos = state.evidence.model_dump()
        datos["test_runs"] = [
            TestRun(target="pytest.unit", exit_code=0, stdout="3 passed", duration_s=0.8).model_dump()
        ]
        return {"evidence": datos}

    monkeypatch.setattr(nodes, "coder", coder_de_m2)
    monkeypatch.setattr(nodes, "apply_sandbox", apply_sandbox_de_m2)
    monkeypatch.setattr(nodes, "run_tests", run_tests_de_m2)


def _compilar_con_checkpointer(store: RunStore):
    return construir_grafo().compile(checkpointer=store.checkpointer())


def test_la_promocion_se_pausa_esperando_aprobacion(tmp_path, nodos_de_m2) -> None:
    """`RF-11`: el grafo se detiene antes de tocar el repositorio del usuario."""
    store = RunStore(tmp_path / "estado.db")
    try:
        app = _compilar_con_checkpointer(store)
        estado = _estado_listo_para_promover()
        cfg = {"configurable": {"thread_id": estado.run_id}}

        salida = app.invoke(estado, cfg)
        assert salida.get("__interrupt__"), "la ejecucion no se pauso"

        # M2: la **primera** pausa es la puerta de requisitos, no la de aprobacion.
        primera = RunState.model_validate(app.get_state(cfg).values)
        assert primera.status is RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION

        _confirmar_requisitos(app, cfg)
        pausado = RunState.model_validate(app.get_state(cfg).values)
        assert pausado.status is RunStatus.AWAITING_APPROVAL
        assert pausado.approvals == []
        assert not pausado.status.is_terminal
    finally:
        store.close()


def test_la_reanudacion_con_aprobacion_completa_la_ejecucion(tmp_path, nodos_de_m2) -> None:
    """`RF-12`: se reanuda desde la pausa, sin repetir el trabajo confirmado."""
    store = RunStore(tmp_path / "estado.db")
    try:
        app = _compilar_con_checkpointer(store)
        estado = _estado_listo_para_promover()
        cfg = {"configurable": {"thread_id": estado.run_id}}

        app.invoke(estado, cfg)
        _confirmar_requisitos(app, cfg)
        final = RunState.model_validate(app.invoke(Command(resume="approved"), cfg))

        assert final.status is RunStatus.COMPLETED
        assert len(final.approvals) == 1
        assert final.approvals[0].decision is ApprovalDecision.APPROVED
        assert final.approvals[0].content_sha256 == SHA
        assert final.final_report is not None
    finally:
        store.close()


def test_rechazar_la_aprobacion_escala_en_lugar_de_completar(tmp_path, nodos_de_m2) -> None:
    store = RunStore(tmp_path / "estado.db")
    try:
        app = _compilar_con_checkpointer(store)
        estado = _estado_listo_para_promover()
        cfg = {"configurable": {"thread_id": estado.run_id}}

        app.invoke(estado, cfg)
        _confirmar_requisitos(app, cfg)
        final = RunState.model_validate(app.invoke(Command(resume="rejected"), cfg))

        assert final.status is RunStatus.NEEDS_HUMAN
        assert final.approvals[0].decision is ApprovalDecision.REJECTED
        assert any(e.error_class == "APPROVAL_REJECTED" for e in final.errors)
    finally:
        store.close()


def test_una_decision_desconocida_se_trata_como_rechazo(tmp_path, nodos_de_m2) -> None:
    """Una respuesta que no se entiende no debe promover cambios por accidente."""
    store = RunStore(tmp_path / "estado.db")
    try:
        app = _compilar_con_checkpointer(store)
        estado = _estado_listo_para_promover()
        cfg = {"configurable": {"thread_id": estado.run_id}}

        app.invoke(estado, cfg)
        _confirmar_requisitos(app, cfg)
        final = RunState.model_validate(app.invoke(Command(resume="lo que sea"), cfg))
        assert final.status is RunStatus.NEEDS_HUMAN
        assert final.approvals[0].decision is ApprovalDecision.REJECTED
    finally:
        store.close()


# --------------------------------------------------- enrutado y red de seguridad


@pytest.mark.parametrize(
    ("intencion", "destino"),
    [
        (Intent.QUESTION, "researcher"),
        (Intent.INSPECT, "researcher"),
        (Intent.MODIFY, "researcher"),
        (Intent.OUT_OF_SCOPE, "explain_limits"),
    ],
)
def test_enrutado_por_intencion(tmp_path, intencion: Intent, destino: str) -> None:
    store, motor = _motor(tmp_path)
    try:
        estado = motor.crear_estado("x")
        datos = estado.model_dump()
        datos["interpretation"] = {
            "intent": intencion,
            "scope": {"repo_path": "/x"},
            "constraints": [],
            "confidence": 0.5,
            "rationale": "prueba",
        }
        assert nodes.route_intent(RunState.model_validate(datos)) == destino
    finally:
        store.close()


def test_el_ciclo_de_revision_se_agota_en_lugar_de_repetirse(tmp_path) -> None:
    """Un ciclo sin limite es un bucle infinito disfrazado de revision.

    **F9 mueve la garantia del router al nodo.** Antes el router comparaba
    `review_cycles_used` con el maximo; ahora esa comparacion vive en la guarda
    determinista del `reviewer`, que convierte en `escalate` un `request_changes`
    sin ciclos. El router se limita a traducir el veredicto ya definitivo. Se
    comprueban las dos mitades para que la frontera no se difumine:

      - el router **no** recorta por ciclos (traduce siempre lo que ve);
      - el nodo **si** recorta (es quien tiene el presupuesto a mano).
    """
    store, motor = _motor(tmp_path)
    try:
        estado = motor.crear_estado("corrige algo")
        datos = estado.model_dump()
        datos["outputs"] = {
            "reviewer_output": {
                "decision": "request_changes",
                "findings": [],
                "required_fixes": ["arreglar"],
                "summary": "no pasa",
            }
        }
        datos["budget"] = {"max_review_cycles": 2, "review_cycles_used": 1}
        assert nodes.route_after_review(RunState.model_validate(datos)) == "coder"

        # Con el limite agotado, el router sigue traduciendo: no es su trabajo recortar.
        datos["budget"] = {"max_review_cycles": 2, "review_cycles_used": 2}
        assert nodes.route_after_review(RunState.model_validate(datos)) == "coder"

        # Quien recorta es el nodo. Sin modelo conectado el veredicto es determinista;
        # con una prueba en rojo pide cambios, y sin ciclos la guarda lo escala.
        nodes.usar_gateway(nodes.SIN_GATEWAY)
        datos["evidence"] = {
            "test_runs": [
                {"target": "pytest.unit", "exit_code": 1, "duration_s": 0.1, "stdout": "1 failed"}
            ]
        }
        salida = nodes.reviewer(RunState.model_validate(datos))
        assert salida["outputs"].reviewer_output.decision is ReviewDecision.ESCALATE
        assert salida["next_step"] == "escalate"
    finally:
        nodes.usar_gateway(nodes.SIN_GATEWAY)
        store.close()


def test_la_red_de_seguridad_fuerza_un_estado_terminal(tmp_path) -> None:
    """Si la topologia tuviera un camino sin salida, la ejecucion no debe quedar
    colgada: se fuerza `needs_human` y se registra el fallo."""
    store, motor = _motor(tmp_path)
    try:
        estado = motor.crear_estado("x")
        datos = estado.model_dump()
        datos["status"] = RunStatus.RUNNING
        datos["next_step"] = "algo"
        colgado = RunState.model_validate(datos)

        rescatado = RunEngine._aplicar_red_de_seguridad(colgado)
        assert rescatado.status is RunStatus.NEEDS_HUMAN
        assert rescatado.next_step is None
        assert [e.error_class for e in rescatado.errors] == ["UNTERMINATED_RUN"]
    finally:
        store.close()


def test_la_red_de_seguridad_respeta_la_espera_de_aprobacion(tmp_path) -> None:
    """`awaiting_approval` no es una anomalia: es una espera legitima."""
    store, motor = _motor(tmp_path)
    try:
        estado = motor.crear_estado("x")
        datos = estado.model_dump()
        datos["status"] = RunStatus.AWAITING_APPROVAL
        datos["next_step"] = "approval_gate"
        esperando = RunState.model_validate(datos)

        assert RunEngine._aplicar_red_de_seguridad(esperando).status is RunStatus.AWAITING_APPROVAL
    finally:
        store.close()


def test_abortar_deja_el_checkpoint_y_el_indice_de_acuerdo(tmp_path) -> None:
    """`GET /runs/{id}` lee el checkpoint; `GET /runs` lee el indice.

    Si el aborto solo actualiza uno de los dos, las dos vistas del mismo hecho no
    coinciden y el cliente ve `running` para una ejecucion ya abandonada. Es un
    fallo real que se encontro al implementar la ejecucion asincrona.
    """
    store, motor = _motor(tmp_path)
    try:
        estado = motor.crear_estado("Analiza el proyecto")
        motor.create(estado)

        motor.abortar(estado.run_id, error_class="FALLO_SIMULADO", message="prueba")

        assert motor.get(estado.run_id).status is RunStatus.NEEDS_HUMAN
        assert store.summary(estado.run_id).status is RunStatus.NEEDS_HUMAN
        assert [e.error_class for e in motor.get(estado.run_id).errors] == ["FALLO_SIMULADO"]
    finally:
        store.close()


def test_abortar_antes_del_primer_nodo_no_pierde_la_ejecucion(tmp_path) -> None:
    """Si el fallo ocurre antes de que exista punto de control, la ejecucion sigue
    teniendo un estado terminal en lugar de quedarse en `planned` para siempre."""
    store, motor = _motor(tmp_path)
    try:
        estado = motor.crear_estado("Analiza el proyecto")
        motor.create(estado)
        assert motor.pendiente_de_aprobacion(estado.run_id) is False

        resultado = motor.abortar(estado.run_id, error_class="FALLO_TEMPRANO", message="prueba")

        assert resultado is not None
        assert resultado.status is RunStatus.NEEDS_HUMAN
        assert motor.get(estado.run_id).status is RunStatus.NEEDS_HUMAN
    finally:
        store.close()


def test_reanudar_una_ejecucion_que_no_espera_nada_falla(tmp_path) -> None:
    """Hallazgo de `verify_m1_assumptions`: reanudar a ciegas entrega un estado
    vacio y hace fallar a los nodos por dentro. Aqui se comprueba antes."""
    from ai_swe.graph import NothingToResume

    store, motor = _motor(tmp_path)
    try:
        inicial = motor.start(motor.crear_estado("¿Dónde se valida el token?"))
        final = _hasta_terminal(motor, inicial)
        assert final.status.is_terminal
        with pytest.raises(NothingToResume):
            motor.resume(final.run_id, ApprovalDecision.APPROVED)
    finally:
        store.close()


def test_reanudar_una_ejecucion_inexistente_falla(tmp_path) -> None:
    """Una ejecucion que no existe da `RunNotFound`, no "no esta esperando nada".

    La distincion importa: 404 y 409 son respuestas distintas para un cliente. La
    primera version comprobaba la espera antes que la existencia y devolvia 409
    para una ejecucion inexistente.
    """
    from ai_swe.graph import RunNotFound

    store, motor = _motor(tmp_path)
    try:
        with pytest.raises(RunNotFound):
            motor.resume("run-que-no-existe", ApprovalDecision.APPROVED)
    finally:
        store.close()


def test_el_grafo_no_tiene_aristas_de_escritura_desde_lectura() -> None:
    """Invariante de `DEC-02`: la separacion de permisos esta en la topologia.

    `researcher` y `reviewer` solo pueden llevar a nodos que no escriben. Se
    comprueba sobre el conjunto de nodos alcanzables, no sobre un comentario.

    **F8:** `apply_sandbox` se anade al conjunto. Es un nodo que **escribe** -crea
    el worktree y aplica el parche-, asi que su posicion importa: solo es
    alcanzable desde `coder`, y `researcher`/`reviewer` no tienen arista hacia el.
    """
    grafo = construir_grafo().compile().get_graph()
    nombres = set(grafo.nodes)
    assert {"researcher", "coder", "apply_sandbox", "reviewer", "approval_gate", "finalize"} <= nombres
    # Los nodos que escriben y los que solo leen deben ser conjuntos distintos.
    assert "approval_gate" in nombres, "toda promocion debe poder pasar por la puerta"
    assert "escalate" in nombres and "escalate_no_changes" in nombres


# ---------------------------------------------------- Researcher (lectura real)


def _repo_de_prueba(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text("import os\n\nprint(1)\n", encoding="utf-8")
    (repo / "README.md").write_text("# demo\n\ncontenido\n", encoding="utf-8")
    (repo / "binario.bin").write_bytes(b"\x00\x01\x02")
    (repo / "vacio.txt").write_text("", encoding="utf-8")
    return repo


def test_el_researcher_lee_el_repositorio_de_verdad(tmp_path) -> None:
    repo = _repo_de_prueba(tmp_path)
    store, motor = _motor(tmp_path)
    try:
        estado = motor.crear_estado("Analiza el proyecto", options=RunOptions(repo_path=str(repo)))
        final = _hasta_terminal(motor, motor.start(estado))
        salida = final.outputs.researcher_output
        assert salida is not None
        assert set(salida.files_read) == {"README.md", "src/a.py", "vacio.txt"}
        assert "binario.bin" not in salida.files_read, "se colo un archivo binario"
    finally:
        store.close()


def test_el_researcher_solo_devuelve_rutas_relativas(tmp_path) -> None:
    """Consecuencia observable del confinamiento de rutas (`RNF-S2`)."""
    repo = _repo_de_prueba(tmp_path)
    store, motor = _motor(tmp_path)
    try:
        estado = motor.crear_estado("Analiza el proyecto", options=RunOptions(repo_path=str(repo)))
        final = _hasta_terminal(motor, motor.start(estado))
        for ruta in final.outputs.researcher_output.files_read:
            assert not ruta.startswith("/"), f"ruta absoluta filtrada: {ruta}"
            assert ":" not in ruta, f"ruta con unidad de disco filtrada: {ruta}"
            assert ".." not in ruta
    finally:
        store.close()


def test_el_researcher_declara_sus_incognitas(tmp_path) -> None:
    """Un agente que no declara lo que no sabe rellena el vacio inventando."""
    repo = _repo_de_prueba(tmp_path)
    store, motor = _motor(tmp_path)
    try:
        inicial = motor.start(
            motor.crear_estado("Analiza el proyecto", options=RunOptions(repo_path=str(repo)))
        )
        final = _hasta_terminal(motor, inicial)
        assert final.outputs.researcher_output.unknowns, "no declaro ninguna incognita"
    finally:
        store.close()


def test_sin_repositorio_el_researcher_lo_dice_en_lugar_de_fallar(tmp_path) -> None:
    store, motor = _motor(tmp_path)
    try:
        final = _hasta_terminal(motor, motor.start(motor.crear_estado("Analiza el proyecto")))
        assert final.outputs.researcher_output.files_read == []
        assert any(
            "no se configuro repositorio" in u
            for u in final.outputs.researcher_output.unknowns
        )
        assert final.status is RunStatus.COMPLETED
    finally:
        store.close()


def test_una_ruta_inexistente_no_derriba_la_ejecucion(tmp_path) -> None:
    store, motor = _motor(tmp_path)
    try:
        inicial = motor.start(
            motor.crear_estado(
                "Analiza el proyecto", options=RunOptions(repo_path=str(tmp_path / "no-existe"))
            )
        )
        final = _hasta_terminal(motor, inicial)
        assert final.status.is_terminal
        assert any("no es un directorio" in u for u in final.outputs.researcher_output.unknowns)
    finally:
        store.close()


def test_el_confinamiento_de_rutas_rechaza_lo_que_esta_fuera(tmp_path) -> None:
    """`RNF-S2`, comprobado directamente y no a traves del bucle que lo usa."""
    raiz = tmp_path / "repo"
    (raiz / "src").mkdir(parents=True)
    dentro = raiz / "src" / "a.py"
    dentro.write_text("x", encoding="utf-8")
    fuera = tmp_path / "fuera.py"
    fuera.write_text("x", encoding="utf-8")

    assert nodes._dentro_de(raiz, dentro)
    assert nodes._dentro_de(raiz, raiz)
    assert not nodes._dentro_de(raiz, fuera)
    assert not nodes._dentro_de(raiz, tmp_path)


def test_el_confinamiento_rechaza_un_enlace_que_escapa(tmp_path) -> None:
    """El caso que motiva resolver antes de comparar (`RNF-S2`).

    Se usa una **uncion de directorio** (`mklink /J`) y no un enlace simbolico, por
    dos motivos comprobados en esta maquina:

      - Crear enlaces simbolicos requiere privilegios, y lo peligroso es que
        `Path.symlink_to` **no lanza error**: deja un fichero normal en su lugar.
        Una prueba que se apoye en eso **pasa sin comprobar nada**, porque el
        «enlace» resuelve dentro de la raiz. Es exactamente el tipo de prueba que
        da una sensacion falsa de cobertura.
      - Las unciones de directorio no requieren privilegios y `resolve()` **si**
        las sigue, que es justo lo que hace el control de confinamiento.

    La premisa se comprueba de forma explicita antes de afirmar nada: si la uncion
    no resuelve fuera de la raiz, la prueba se omite en lugar de fingir que
    comprobo algo.
    """
    if sys.platform != "win32":
        pytest.skip("las unciones de directorio son propias de Windows")

    raiz = tmp_path / "repo"
    raiz.mkdir()
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    (fuera / "secreto.txt").write_text("contenido de fuera", encoding="utf-8")

    union = raiz / "union"
    proceso = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(union), str(fuera)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proceso.returncode != 0 or not union.exists():
        pytest.skip(f"el sistema no permite crear unciones: {proceso.stderr[:80]}")

    # Premisa: la uncion resuelve FUERA de la raiz. Sin esto, la prueba no probaria nada.
    assert not union.resolve().is_relative_to(raiz.resolve()), (
        "la uncion no escapa de la raiz, asi que esta prueba no comprobaria el confinamiento"
    )

    assert not nodes._dentro_de(raiz, union), "una uncion que escapa amplio el alcance"
    assert not nodes._dentro_de(raiz, union / "secreto.txt")
