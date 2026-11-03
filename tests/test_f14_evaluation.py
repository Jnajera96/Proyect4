"""Pruebas de F14: el arnes de evaluacion experimental (`EXP-01`).

**Que protege este fichero.** Que la comparacion `SINGLE_AGENT` vs `MULTI_AGENT` sea
evidencia y no una tabla escrita a mano:

  1. **El catalogo es un criterio objetivo.** Cada tarea declara su suite de
     validacion, y se comprueba que esa suite **falla en el estado inicial**: una
     tarea cuya suite ya pasa no mide nada.
  2. **El criterio de exito es el declarado.** El ultimo intento del modelo deja la
     suite en verde si y solo si la tarea converge; `EXP-13` existe para el control
     negativo.
  3. **Las metricas salen de evidencia.** La tasa de exito, los tokens y los ciclos
     se leen del estado y del `Budget`, no se estiman.
  4. **La diferencia entre modos es real.** La tarea que exige correccion la resuelve
     el multiagente y **no** el flujo directo; si eso dejara de ser cierto, la
     respuesta a la pregunta central del proyecto dejaria de sostenerse.

Ninguna prueba toca la red ni credenciales: el modelo va guionizado.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_swe.contracts import (
    Evidence,
    Instruction,
    InstructionSource,
    ReviewDecision,
    ReviewVerdict,
    RunState,
    RunStatus,
    TestRun,
)
from ai_swe.evaluation.runner import (
    InformeEvaluacion,
    MetricasCorrida,
    Modo,
    ResultadoTarea,
    _metricas,
    construir_grafo_single_agent,
    ejecutar_bateria,
    escribir_resultados,
    generar_informe,
    materializar_repo,
)
from ai_swe.evaluation.tasks import TAREAS, EvalTask, tarea_por_id
from ai_swe.graph import nodes
from ai_swe.graph.workflow import construir_grafo


def _correr_suite(repo: Path) -> int:
    """Ejecuta la suite de validacion del repositorio. Devuelve el codigo de salida."""
    resultado = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "tests"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        shell=False,
    )
    return resultado.returncode


def _aplicar_propuesta(repo: Path, propuesta: dict) -> None:
    """Escribe en el repositorio el contenido de la ultima propuesta de una tarea."""
    for archivo in propuesta["files"]:
        destino = repo / archivo["path"]
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(archivo["new_content"], encoding="utf-8")


def _falsa(exito: bool) -> MetricasCorrida:
    """Una corrida sintetica, para probar la agregacion sin ejecutar el arnes."""
    return MetricasCorrida(
        task_id="T",
        modo="m",
        exito=exito,
        tests_aprobados=1 if exito else 0,
        tests_fallidos=0 if exito else 1,
        tokens_entrada=10,
        tokens_salida=2,
        latencia_ms=1.0,
        llamadas_modelo=1,
        llamadas_herramienta=0,
        ciclos_revision=0,
        intervenciones_humanas=0,
        escalamientos=0,
        violaciones_politica=0,
        terminacion_correcta=True,
        estado_final="completed",
    )


# ================================================= 1. el catalogo es un criterio


def test_el_catalogo_tiene_al_menos_diez_tareas_con_identificadores_unicos() -> None:
    assert len(TAREAS) >= 10
    ids = [t.id for t in TAREAS]
    assert len(ids) == len(set(ids)), f"identificadores repetidos: {ids}"


def test_el_catalogo_cubre_las_categorias_de_la_documentacion() -> None:
    """Las ocho categorias que pide `10_EVALUACION_METRICAS.md`."""
    esperadas = {
        "bugfix",
        "endpoint",
        "validacion",
        "prueba",
        "refactor",
        "documentacion",
        "configuracion",
        "revision de seguridad",
    }
    assert {t.category for t in TAREAS} == esperadas


def test_cada_tarea_declara_archivos_pruebas_y_propuestas() -> None:
    for tarea in TAREAS:
        assert tarea.files, f"{tarea.id} no declara archivos iniciales"
        assert tarea.tests, f"{tarea.id} no declara suite de validacion"
        assert tarea.propuestas, f"{tarea.id} no declara ninguna propuesta"
        assert tarea.instruction.strip(), f"{tarea.id} no declara instruccion"
        assert all(p.get("files") for p in tarea.propuestas), f"{tarea.id}: propuesta vacia"


def test_hay_tareas_que_exigen_correccion_y_una_que_no_converge() -> None:
    """La bateria tiene que separar los tres casos, o no compararia nada."""
    correccion = [t for t in TAREAS if t.requiere_correccion]
    directas = [t for t in TAREAS if not t.requiere_correccion]
    assert len(correccion) >= 3, "sin tareas que exijan reintento no se mide el ciclo"
    assert directas, "sin tareas directas no hay linea base que comparar"
    assert any(not t.converge for t in TAREAS), "falta el control negativo (modelo que no converge)"


@pytest.mark.parametrize("tarea", TAREAS, ids=[t.id for t in TAREAS])
def test_la_suite_de_validacion_falla_en_el_estado_inicial(tarea: EvalTask, tmp_path: Path) -> None:
    """El criterio de exito tiene que estar **sin cumplir** al empezar.

    Una tarea cuya suite ya pasa antes del cambio no mide nada: seria un exito
    regalado, y contaria igual que uno conseguido.
    """
    repo = materializar_repo(tarea, tmp_path / tarea.id)
    assert _correr_suite(repo) != 0, f"{tarea.id}: la suite ya pasaba antes del cambio"


@pytest.mark.parametrize("tarea", TAREAS, ids=[t.id for t in TAREAS])
def test_el_ultimo_intento_deja_la_suite_en_verde_si_y_solo_si_converge(
    tarea: EvalTask, tmp_path: Path
) -> None:
    """El criterio declarado (`converge`) se corresponde con la realidad."""
    repo = materializar_repo(tarea, tmp_path / tarea.id)
    _aplicar_propuesta(repo, tarea.propuestas[-1])
    verde = _correr_suite(repo) == 0
    assert verde is tarea.converge, (
        f"{tarea.id}: la suite {'pasa' if verde else 'falla'} tras el ultimo intento, "
        f"pero la tarea declara converge={tarea.converge}"
    )


def test_materializar_repo_crea_un_repositorio_git_real(tmp_path: Path) -> None:
    """Sin historial no hay worktree, y sin worktree la tarea no se puede ejecutar."""
    tarea = tarea_por_id("EXP-01")
    repo = materializar_repo(tarea, tmp_path / "repo")

    assert (repo / ".git").is_dir()
    assert (repo / "conftest.py").is_file()
    for ruta in {**tarea.files, **tarea.tests}:
        assert (repo / ruta).is_file(), f"falta {ruta}"

    resultado = subprocess.run(
        ["git", "log", "--oneline"], cwd=str(repo), capture_output=True, text=True, shell=False
    )
    assert resultado.returncode == 0
    assert "EXP-01" in resultado.stdout


def test_tarea_por_id_falla_si_no_existe() -> None:
    with pytest.raises(KeyError):
        tarea_por_id("EXP-99")


# ================================================= 2. los dos grafos comparados


def test_el_grafo_de_un_solo_agente_no_tiene_plan_ni_reviewer() -> None:
    """La linea base tiene que ser de verdad mas simple, no el mismo grafo con otro nombre."""
    nodos_single = set(construir_grafo_single_agent().nodes)
    nodos_multi = set(construir_grafo().nodes)

    assert {"plan", "researcher", "reviewer", "approval_gate"} & nodos_single == set()
    assert {"plan", "researcher", "reviewer"} <= nodos_multi
    # Y comparte la maquinaria: interpretar, codificar, aplicar y probar.
    assert {"interpret", "coder", "apply_sandbox", "run_tests"} <= nodos_single


# ================================================= 3. las metricas son de evidencia


def _estado_con_evidencia(pruebas: list[TestRun], *, status: RunStatus = RunStatus.COMPLETED) -> RunState:
    ahora = datetime.now(UTC)
    return RunState(
        run_id="run-metricas",
        trace_id="trace-metricas",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text="corrige algo", source=InstructionSource.TEXT, confirmed_by_user=True
        ),
        evidence=Evidence(test_runs=pruebas),
        status=status,
    )


def test_el_exito_exige_completed_y_pruebas_en_verde() -> None:
    """Un `completed` con pruebas en rojo no es un exito."""
    tarea = tarea_por_id("EXP-01")
    aprobada = TestRun(target="pytest.unit", exit_code=0, duration_s=0.1)
    fallida = TestRun(target="pytest.unit", exit_code=1, duration_s=0.1)

    verde = _metricas(
        tarea, Modo.SINGLE_AGENT, _estado_con_evidencia([aprobada]), latencia_ms=1.0, intervenciones=0
    )
    rojo = _metricas(
        tarea, Modo.SINGLE_AGENT, _estado_con_evidencia([fallida]), latencia_ms=1.0, intervenciones=0
    )
    sin_pruebas = _metricas(
        tarea, Modo.SINGLE_AGENT, _estado_con_evidencia([]), latencia_ms=1.0, intervenciones=0
    )

    assert verde.exito is True
    assert rojo.exito is False, "un completed con pruebas en rojo se conto como exito"
    assert sin_pruebas.exito is False, "sin evidencia no se puede afirmar exito"
    assert rojo.tests_fallidos == 1
    assert sin_pruebas.terminacion_correcta is True


def test_las_metricas_leen_el_desglose_de_tokens_del_presupuesto() -> None:
    estado = _estado_con_evidencia([TestRun(target="pytest.unit", exit_code=0, duration_s=0.1)])
    datos = estado.budget.model_dump()
    datos.update({"used_input_tokens": 120, "used_output_tokens": 30, "used_tokens": 150})
    estado = RunState.model_validate({**estado.model_dump(), "budget": datos})

    metricas = _metricas(
        tarea_por_id("EXP-01"), Modo.MULTI_AGENT, estado, latencia_ms=5.0, intervenciones=2
    )
    assert metricas.tokens_entrada == 120
    assert metricas.tokens_salida == 30
    assert metricas.intervenciones_humanas == 2


# ============================================ 4. la respuesta a la pregunta central


@pytest.fixture(scope="module")
def bateria_minima(tmp_path_factory: pytest.TempPathFactory) -> InformeEvaluacion:
    """Ejecuta dos tareas en los dos modos: una directa y una que exige correccion."""
    raiz = tmp_path_factory.mktemp("evaluacion")
    # This module-scoped fixture runs before function-scoped opt-ins.
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("AI_SWE_NETWORK_EGRESS_ENABLED", "true")
        return ejecutar_bateria(
            tareas=(tarea_por_id("EXP-01"), tarea_por_id("EXP-02")), raiz_trabajo=raiz
        )


def test_una_tarea_directa_la_resuelven_los_dos_modos(bateria_minima: InformeEvaluacion) -> None:
    resultado = next(t for t in bateria_minima.tareas if t.tarea_id == "EXP-01")
    assert resultado.corridas[Modo.SINGLE_AGENT.value].exito is True
    assert resultado.corridas[Modo.MULTI_AGENT.value].exito is True


def test_una_tarea_que_exige_correccion_la_resuelve_solo_el_multiagente(
    bateria_minima: InformeEvaluacion,
) -> None:
    """**Es la respuesta empirica a la pregunta central.** Si esto dejara de cumplirse,
    la defensa del multiagente se quedaria sin su unica evidencia medible."""
    resultado = next(t for t in bateria_minima.tareas if t.tarea_id == "EXP-02")

    single = resultado.corridas[Modo.SINGLE_AGENT.value]
    multi = resultado.corridas[Modo.MULTI_AGENT.value]

    assert single.exito is False, "el flujo directo no deberia resolver un primer intento fallido"
    assert multi.exito is True, "el ciclo de revision deberia recuperar el fallo"
    assert multi.ciclos_revision >= 1, "el multiagente no gasto ningun ciclo de revision"


def test_el_multiagente_cuesta_mas_y_lo_dice(bateria_minima: InformeEvaluacion) -> None:
    """El coste tiene que salir en las metricas, no solo el beneficio."""
    resumen = bateria_minima.resumen_por_modo()
    single = resumen[Modo.SINGLE_AGENT.value]
    multi = resumen[Modo.MULTI_AGENT.value]

    assert multi["llamadas_modelo"] > single["llamadas_modelo"]
    assert multi["tokens_totales"] > single["tokens_totales"]
    assert multi["intervenciones_humanas"] > single["intervenciones_humanas"]


# ================================================= 5. agregacion y artefactos


def test_el_resumen_calcula_la_tasa_de_exito() -> None:
    corridas = [
        ResultadoTarea("T1", "uno", "bugfix", False, {Modo.SINGLE_AGENT.value: _falsa(True)}),
        ResultadoTarea("T2", "dos", "bugfix", True, {Modo.SINGLE_AGENT.value: _falsa(False)}),
        ResultadoTarea("T3", "tres", "bugfix", False, {Modo.MULTI_AGENT.value: _falsa(True)}),
    ]
    informe = InformeEvaluacion(generado_en="2026-01-01T00:00:00+00:00", tareas=corridas)
    resumen = informe.resumen_por_modo()

    assert resumen[Modo.SINGLE_AGENT.value]["corridas"] == 2
    assert resumen[Modo.SINGLE_AGENT.value]["exitos"] == 1
    assert resumen[Modo.SINGLE_AGENT.value]["tasa_exito"] == pytest.approx(0.5)
    assert resumen[Modo.MULTI_AGENT.value]["corridas"] == 1
    assert resumen[Modo.MULTI_AGENT.value]["tasa_exito"] == pytest.approx(1.0)


def test_el_resumen_sin_corridas_no_divide_por_cero() -> None:
    informe = InformeEvaluacion(generado_en="2026-01-01T00:00:00+00:00", tareas=[])
    resumen = informe.resumen_por_modo()
    assert resumen[Modo.SINGLE_AGENT.value]["corridas"] == 0
    assert resumen[Modo.SINGLE_AGENT.value]["tasa_exito"] == 0.0


def test_escribir_resultados_y_generar_informe(tmp_path: Path) -> None:
    """Los dos artefactos se generan y el informe cita la pregunta central."""
    corridas = [
        ResultadoTarea("T1", "uno", "bugfix", False, {Modo.SINGLE_AGENT.value: _falsa(True)}),
        ResultadoTarea("T1", "uno", "bugfix", False, {Modo.MULTI_AGENT.value: _falsa(False)}),
    ]
    informe = InformeEvaluacion(generado_en="2026-01-01T00:00:00+00:00", tareas=corridas)

    json_destino = escribir_resultados(informe, tmp_path / "resultados.json")
    md_destino = generar_informe(informe, tmp_path / "EVALUATION.md")

    import json as _json

    datos = _json.loads(json_destino.read_text(encoding="utf-8"))
    assert datos["resumen"]["single_agent"]["exitos"] == 1
    assert datos["resumen"]["multi_agent"]["exitos"] == 0

    texto = md_destino.read_text(encoding="utf-8")
    assert "SINGLE_AGENT" in texto and "MULTI_AGENT" in texto
    assert "Documento GENERADO" in texto


# ================================================= 6. regresion del defecto hallado


def test_la_evidencia_vigente_es_la_ultima_por_target() -> None:
    """`evidence.test_runs` es historico; el juicio va sobre la ultima por target."""
    fallida = TestRun(target="pytest.unit", exit_code=1, duration_s=0.1)
    aprobada = TestRun(target="pytest.unit", exit_code=0, duration_s=0.2)
    otra = TestRun(target="pytest.integration", exit_code=0, duration_s=0.3)

    vigentes = nodes.evidencia_vigente([fallida, aprobada, otra])
    assert [p.target for p in vigentes] == ["pytest.unit", "pytest.integration"]
    assert all(p.passed for p in vigentes)


def test_un_fallo_superado_no_veta_el_siguiente_accept() -> None:
    """Regresion del defecto que encontro esta fase.

    Antes de F14, `_guarda_pruebas` miraba **todas** las corridas acumuladas: un fallo
    de una vuelta anterior vetaba para siempre todo `ACCEPT`, asi que el ciclo
    Coder<->Reviewer **no podia converger** y `MET-08` era inalcanzable. Se reprodujo
    con dos tareas de la bateria que no se resolvian en ningun modo.
    """
    fallida = TestRun(target="pytest.unit", exit_code=1, duration_s=0.1)
    aprobada = TestRun(target="pytest.unit", exit_code=0, duration_s=0.2)
    estado = _estado_con_evidencia([fallida, aprobada])

    veredicto = ReviewVerdict(decision=ReviewDecision.ACCEPT, findings=[], summary="cambio correcto")
    resultado = nodes._guarda_pruebas(estado, veredicto)

    assert resultado.decision is ReviewDecision.ACCEPT, (
        "un fallo ya superado sigue vetando el cambio: el ciclo no converge"
    )
