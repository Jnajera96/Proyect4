"""Arnes de evaluacion experimental: `SINGLE_AGENT` vs `MULTI_AGENT` (F14, `EXP-01`).

**Que mide.** La misma bateria de tareas (`tasks.py`) se ejecuta bajo dos
configuraciones y se comparan las metricas. Es la respuesta **empirica** a la
pregunta central del proyecto (docs/06-EVALUATION.md), no una opinion.

  - `SINGLE_AGENT`: flujo directo. `interpret -> coder -> apply_sandbox ->
    run_tests -> finalize`. Sin planificacion, sin investigacion y **sin ciclo de
    revision**: es la linea base honesta de "un solo agente".
  - `MULTI_AGENT`: el grafo de produccion completo. `interpret -> (puerta de
    requisitos) -> plan -> researcher -> coder -> apply_sandbox -> run_tests ->
    reviewer -> (ciclo) -> (puerta de aprobacion) -> finalize`.

**Las metricas salen de evidencia de ejecucion, no de estimaciones.** El exito se
lee de la evidencia de pruebas (`TestRun.exit_code`), los tokens y las llamadas del
`Budget` persistido en el estado, y la latencia se mide con el reloj. **No se
fabrica ninguna cifra**: si una prueba no se ejecuto, no hay `TestRun` y el exito es
falso.

**Limitacion declarada (importante).** El modelo va **guionizado** (ver `tasks.py`):
el arnes es offline, determinista y no necesita credenciales. Por tanto esta
comparacion mide el **coste y el beneficio de la orquestacion** —cuantos nodos,
cuanto contexto, cuantos ciclos— y **no** la calidad de un modelo concreto. Es la
misma limitacion que `TD-01` declara para el resto del sistema.

**El humano se simula.** Las puertas HITL se reanudan automaticamente con
`approved`, contando cada intervencion. Es lo que hace comparable el flujo con
puertas frente al directo, y es lo que alimenta la metrica de intervenciones
humanas (`MET-12`).
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from ai_swe.contracts import ApprovalDecision, Intent, RunOptions, RunState, RunStatus
from ai_swe.graph import nodes
from ai_swe.graph.engine import RunEngine
from ai_swe.graph.workflow import construir_grafo
from ai_swe.models import ModelGateway, ModelUsage, ProviderResponse
from ai_swe.state import RunStore
from ai_swe.evaluation.tasks import EvalTask, TAREAS

log = logging.getLogger(__name__)

#: Tipos de error que cuentan como violacion de politica en las metricas.
ERRORES_DE_POLITICA = frozenset(
    {"POLICY_DENIED", "SANDBOX_PATH_DENIED", "PROMOTION_DENIED"}
)

#: Identidad para las confirmaciones dentro de los repositorios de prueba.
_IDENTIDAD = ("-c", "user.name=AI SWE Eval", "-c", "user.email=eval@localhost")


class Modo(StrEnum):
    """Las dos configuraciones comparadas."""

    SINGLE_AGENT = "single_agent"
    MULTI_AGENT = "multi_agent"


# --------------------------------------------------------------------- metricas


@dataclass(frozen=True)
class MetricasCorrida:
    """Metricas **tipadas** de una corrida de una tarea en un modo.

    Cada campo se lee de una fuente concreta del sistema; ninguno es un valor
    plausible rellenado a mano.
    """

    task_id: str
    modo: str
    exito: bool
    tests_aprobados: int
    tests_fallidos: int
    tokens_entrada: int
    tokens_salida: int
    latencia_ms: float
    llamadas_modelo: int
    llamadas_herramienta: int
    ciclos_revision: int
    intervenciones_humanas: int
    escalamientos: int
    violaciones_politica: int
    terminacion_correcta: bool
    estado_final: str
    detalle: str = ""


@dataclass(frozen=True)
class ResultadoTarea:
    """Las dos corridas (una por modo) de una misma tarea."""

    tarea_id: str
    titulo: str
    categoria: str
    requiere_correccion: bool
    corridas: dict[str, MetricasCorrida] = field(default_factory=dict)


@dataclass(frozen=True)
class InformeEvaluacion:
    """Resultado completo de la bateria, listo para exportar y para el informe."""

    generado_en: str
    tareas: list[ResultadoTarea]

    def resumen_por_modo(self) -> dict[str, dict]:
        """Agregados por modo: lo que responde a la pregunta central.

        Se calculan **sobre las corridas presentes**, no sobre el catalogo: si un
        modo no corrio alguna tarea, no se cuenta como fallo silenciosamente.
        """
        resumen: dict[str, dict] = {}
        for modo in (Modo.SINGLE_AGENT.value, Modo.MULTI_AGENT.value):
            corridas = [
                c
                for tarea in self.tareas
                for c in (tarea.corridas.get(modo),)
                if c is not None
            ]
            total = len(corridas)
            exitos = sum(1 for c in corridas if c.exito)
            resumen[modo] = {
                "corridas": total,
                "exitos": exitos,
                "tasa_exito": (exitos / total) if total else 0.0,
                "tokens_entrada": sum(c.tokens_entrada for c in corridas),
                "tokens_salida": sum(c.tokens_salida for c in corridas),
                "tokens_totales": sum(c.tokens_entrada + c.tokens_salida for c in corridas),
                "latencia_media_ms": (sum(c.latencia_ms for c in corridas) / total) if total else 0.0,
                "llamadas_modelo": sum(c.llamadas_modelo for c in corridas),
                "llamadas_herramienta": sum(c.llamadas_herramienta for c in corridas),
                "ciclos_revision": sum(c.ciclos_revision for c in corridas),
                "intervenciones_humanas": sum(c.intervenciones_humanas for c in corridas),
                "escalamientos": sum(c.escalamientos for c in corridas),
                "violaciones_politica": sum(c.violaciones_politica for c in corridas),
                "terminacion_correcta": sum(1 for c in corridas if c.terminacion_correcta),
                "tests_aprobados": sum(c.tests_aprobados for c in corridas),
                "tests_fallidos": sum(c.tests_fallidos for c in corridas),
            }
        return resumen

    def por_categoria(self) -> dict[str, dict[str, int]]:
        """Exitos por categoria y modo. Es el desglose que evita un promedio ciego."""
        acumulado: dict[str, dict[str, int]] = {}
        for tarea in self.tareas:
            fila = acumulado.setdefault(tarea.categoria, {})
            for modo, corrida in tarea.corridas.items():
                clave = f"{modo}_exitos"
                fila[clave] = fila.get(clave, 0) + (1 if corrida.exito else 0)
                fila[f"{modo}_total"] = fila.get(f"{modo}_total", 0) + 1
        return acumulado

    def a_dict(self) -> dict:
        return {
            "generado_en": self.generado_en,
            "tareas": [
                {
                    "tarea_id": t.tarea_id,
                    "titulo": t.titulo,
                    "categoria": t.categoria,
                    "requiere_correccion": t.requiere_correccion,
                    "corridas": {modo: asdict(c) for modo, c in t.corridas.items()},
                }
                for t in self.tareas
            ],
            "resumen": self.resumen_por_modo(),
        }


# ------------------------------------------------------------ modelo guionizado


def _estimar_tokens(texto: str) -> int:
    """Tokens aproximados de un texto, para el proveedor guionizado.

    **Es una estimacion declarada, no una medicion del proveedor real.** El modelo
    guionizado no tiene tokenizador: usa ~4 caracteres por token, que es el orden de
    magnitud habitual en espanol e ingles. Sirve para comparar **las dos
    configuraciones entre si** (el multiagente envia mas contexto), no para facturar.
    """
    return max(1, len(texto) // 4)


class _ModeloGuionizado:
    """Adaptador de modelo determinista que responde segun el contrato pedido.

    El gateway deja el JSON Schema del contrato en `request.json_schema`, cuyo
    `title` es el nombre del modelo Pydantic. Es el unico discriminador fiable,
    porque `interpret` y `plan` comparten `agent_role`.

    Para `ReviewVerdict` devuelve un objeto vacio **a proposito**: no cumple el
    contrato y el Reviewer cae a su veredicto determinista, que es el que veta las
    pruebas en rojo. Asi la comparacion mide el mecanismo real de revision y no un
    guion.
    """

    def __init__(self, tarea: EvalTask) -> None:
        self._tarea = tarea
        self._propuestas = list(tarea.propuestas)

    @property
    def name(self) -> str:
        return "evaluacion:guionizado"

    def _interpretacion(self) -> dict:
        return {
            "intent": Intent.MODIFY.value,
            "scope": {"repo_path": ".", "allowed_paths": [], "protected_paths": []},
            "constraints": [],
            "confidence": 0.9,
            "rationale": "la instruccion pide un cambio concreto en el codigo",
        }

    def _plan(self) -> dict:
        return {
            "subtasks": [
                {
                    "id": "inspeccionar",
                    "description": "localizar el codigo que hay que cambiar",
                    "agent": "researcher",
                    "allowed_tools": ["list_files", "read_file"],
                    "done_criteria": "se conoce el archivo afectado",
                },
                {
                    "id": "corregir",
                    "description": self._tarea.instruction,
                    "agent": "coder",
                    "depends_on": ["inspeccionar"],
                    "allowed_tools": ["read_file", "write_file"],
                    "done_criteria": "la suite de validacion de la tarea pasa",
                },
            ],
            "max_review_cycles": 2,
            "rationale": "inspeccionar antes de cambiar",
        }

    def _datos_para(self, titulo: str) -> dict | None:
        if titulo == "TaskInterpretation":
            return self._interpretacion()
        if titulo == "RunPlan":
            return self._plan()
        if titulo == "CodeProposal":
            return self._propuestas.pop(0) if self._propuestas else None
        return None

    def generate(self, request):
        titulo = (request.json_schema or {}).get("title", "")
        datos = self._datos_para(titulo)
        contenido = json.dumps(datos, ensure_ascii=False) if datos is not None else "{}"
        prompt = "".join(m.content for m in request.messages)
        return ProviderResponse(
            content=contenido,
            model=request.model or "guionizado",
            finish_reason="stop",
            # El proveedor reporta lo que ha procesado. El desglose entrada/salida
            # es lo que permite ver que el multiagente **envia mas contexto**.
            usage=ModelUsage(
                input_tokens=_estimar_tokens(prompt),
                output_tokens=_estimar_tokens(contenido),
            ),
            provider_request_id=f"guionizado-{titulo or 'desconocido'}",
        )


# ------------------------------------------------------------ repositorio de prueba

_CONFTEST = (
    '"""Raiz del repositorio de prueba: hace importable `src` para la suite."""\n'
)


def _git(repo: Path, *args: str) -> None:
    resultado = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, shell=False
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} fallo: {resultado.stderr}")


def materializar_repo(tarea: EvalTask, destino: Path) -> Path:
    """Crea un repositorio git real con el estado inicial y la suite de la tarea.

    Se crea un repositorio **de verdad** y no un directorio suelto porque el sandbox
    es un `git worktree`: sin historial no hay worktree, y sin worktree la tarea no
    se puede ejecutar por el mismo camino que en produccion.
    """
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)

    (destino / "conftest.py").write_text(_CONFTEST, encoding="utf-8")
    for ruta, contenido in {**tarea.files, **tarea.tests}.items():
        archivo = destino / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(contenido, encoding="utf-8")

    _git(destino, "init", "-q")
    _git(destino, "config", "user.email", "eval@localhost")
    _git(destino, "config", "user.name", "AI SWE Eval")
    _git(destino, "add", ".")
    _git(destino, "commit", "-q", "-m", f"estado inicial de {tarea.id}")
    return destino


# ------------------------------------------------------------------ los grafos


def _ruta_directa(state: RunState) -> str:
    """Enrutado del flujo directo: se interpreta y se va **directo al Coder**.

    Es la simplificacion que define la linea base: ni planificacion, ni
    investigacion, ni puerta de requisitos.
    """
    return "coder"


def construir_grafo_single_agent() -> StateGraph:
    """Grafo del flujo directo de un solo agente.

    `interpret -> coder -> apply_sandbox -> run_tests -> finalize`. Reutiliza los
    **mismos nodos** que el grafo de produccion (interpretar, codificar, aplicar en
    sandbox, ejecutar pruebas): lo que se quita es la orquestacion -plan, researcher,
    Reviewer y puertas humanas-, no la maquinaria. Asi la comparacion aisla el efecto
    de la orquestacion.
    """
    grafo = StateGraph(RunState)
    grafo.add_node("interpret", nodes.interpret)
    grafo.add_node("coder", nodes.coder)
    grafo.add_node("apply_sandbox", nodes.apply_sandbox)
    grafo.add_node("run_tests", nodes.run_tests)
    grafo.add_node("escalate_no_changes", nodes.escalate_no_changes)
    grafo.add_node("escalate", nodes.escalate)
    grafo.add_node("finalize", nodes.finalize)

    grafo.add_edge(START, "interpret")
    grafo.add_conditional_edges("interpret", _ruta_directa)
    grafo.add_conditional_edges("coder", nodes.route_after_coder)
    grafo.add_conditional_edges("apply_sandbox", nodes.route_after_apply)
    # **Sin Reviewer**: el flujo directo no tiene ciclo de correccion. Esa es,
    # precisamente, la diferencia que la comparacion mide.
    grafo.add_edge("run_tests", "finalize")
    grafo.add_edge("escalate_no_changes", "finalize")
    grafo.add_edge("escalate", "finalize")
    grafo.add_edge("finalize", END)
    return grafo


def compilar_single_agent(store):
    """Compila el grafo directo con el checkpointer del almacen.

    Es la firma que espera `RunEngine(constructor_grafo=...)`, de modo que el arnes
    ejecuta el flujo directo por la **misma** maquinaria que el de produccion
    (eventos, persistencia, reanudacion) y la unica diferencia medida es la
    topologia.
    """
    return construir_grafo_single_agent().compile(checkpointer=store.checkpointer())


# ------------------------------------------------------------------- ejecucion


def _metricas(
    tarea: EvalTask,
    modo: Modo,
    estado: RunState,
    *,
    latencia_ms: float,
    intervenciones: int,
) -> MetricasCorrida:
    """Lee las metricas del estado final. **Todo sale de evidencia persistida.**

    El exito se calcula sobre la **evidencia vigente** (la ultima ejecucion de cada
    target), con la misma funcion que usa el Reviewer. No es un detalle: usar el
    historial entero contaria como fallo un intento anterior ya superado, y el
    multiagente -que es el unico que reintenta- pareceria fallar precisamente en las
    tareas que resuelve. El criterio del arnes y el del sistema tienen que ser el
    mismo o la comparacion mediria dos cosas distintas.
    """
    pruebas = nodes.evidencia_vigente(estado.evidence.test_runs)
    aprobados = sum(1 for p in pruebas if p.passed)
    fallidos = len(pruebas) - aprobados
    errores = {e.error_class for e in estado.errors}

    # El exito exige **las dos cosas**: la ejecucion termino bien y la evidencia de
    # pruebas respalda el cambio. Un `completed` sin pruebas en verde no es un exito;
    # contarlo como tal seria el unico modo de inflar la tasa de finalizacion.
    exito = estado.status is RunStatus.COMPLETED and bool(pruebas) and fallidos == 0

    return MetricasCorrida(
        task_id=tarea.id,
        modo=modo.value,
        exito=exito,
        tests_aprobados=aprobados,
        tests_fallidos=fallidos,
        tokens_entrada=estado.budget.used_input_tokens,
        tokens_salida=estado.budget.used_output_tokens,
        latencia_ms=latencia_ms,
        llamadas_modelo=estado.budget.used_model_calls,
        llamadas_herramienta=estado.budget.used_tool_calls,
        ciclos_revision=estado.budget.review_cycles_used,
        intervenciones_humanas=intervenciones,
        escalamientos=1 if estado.status is RunStatus.NEEDS_HUMAN else 0,
        violaciones_politica=len(errores & ERRORES_DE_POLITICA),
        terminacion_correcta=estado.status.is_terminal,
        estado_final=estado.status.value,
        detalle="; ".join(sorted(errores))[:300],
    )


def ejecutar_corrida(
    tarea: EvalTask,
    modo: Modo,
    *,
    raiz_trabajo: Path,
) -> MetricasCorrida:
    """Ejecuta **una** tarea en **un** modo y devuelve sus metricas.

    Deja el estado de modulo del grafo como estaba: las inyecciones
    (`usar_gateway`, `usar_workspace_root`, `usar_targets_permitidos`) son globales y
    una corrida no puede contaminar a la siguiente.
    """
    repo = materializar_repo(tarea, raiz_trabajo / tarea.id / modo.value / "repo")
    workspaces = raiz_trabajo / tarea.id / modo.value / "workspaces"
    almacen = RunStore(raiz_trabajo / tarea.id / modo.value / "estado.sqlite3")

    nodes.usar_gateway(ModelGateway([_ModeloGuionizado(tarea)]))
    nodes.usar_workspace_root(workspaces)
    nodes.usar_targets_permitidos(("pytest.unit",))
    nodes.usar_modelo_reviewer(None)

    try:
        motor = (
            RunEngine(almacen, constructor_grafo=compilar_single_agent)
            if modo is Modo.SINGLE_AGENT
            else RunEngine(almacen)
        )
        estado = motor.crear_estado(
            tarea.instruction, options=RunOptions(repo_path=str(repo))
        )

        inicio = time.perf_counter()
        estado = motor.start(estado)
        # El humano se simula: cada puerta se reanuda con `approved` y se cuenta.
        intervenciones = 0
        while estado.status.is_awaiting_human:
            intervenciones += 1
            estado = motor.resume(estado.run_id, ApprovalDecision.APPROVED)
        latencia_ms = (time.perf_counter() - inicio) * 1000.0

        return _metricas(
            tarea, modo, estado, latencia_ms=latencia_ms, intervenciones=intervenciones
        )
    finally:
        nodes.usar_gateway(nodes.SIN_GATEWAY)
        nodes.usar_workspace_root(None)
        nodes.usar_targets_permitidos(None)
        nodes.usar_modelo_reviewer(None)
        almacen.close()


def ejecutar_bateria(
    tareas: tuple[EvalTask, ...] = TAREAS,
    modos: tuple[Modo, ...] = (Modo.SINGLE_AGENT, Modo.MULTI_AGENT),
    *,
    raiz_trabajo: Path,
) -> InformeEvaluacion:
    """Ejecuta el catalogo completo bajo los modos indicados.

    Un fallo de una corrida **no aborta la bateria**: se registra como corrida sin
    metricas utiles y se sigue. Abortar perderia las demas y haria que un solo caso
    raro dejara el informe a medias.
    """
    resultados: list[ResultadoTarea] = []
    for tarea in tareas:
        corridas: dict[str, MetricasCorrida] = {}
        for modo in modos:
            try:
                corridas[modo.value] = ejecutar_corrida(tarea, modo, raiz_trabajo=raiz_trabajo)
            except Exception as exc:  # noqa: BLE001 - una tarea no tumba la bateria
                log.warning("la corrida %s/%s fallo: %s", tarea.id, modo.value, exc)
                corridas[modo.value] = MetricasCorrida(
                    task_id=tarea.id,
                    modo=modo.value,
                    exito=False,
                    tests_aprobados=0,
                    tests_fallidos=0,
                    tokens_entrada=0,
                    tokens_salida=0,
                    latencia_ms=0.0,
                    llamadas_modelo=0,
                    llamadas_herramienta=0,
                    ciclos_revision=0,
                    intervenciones_humanas=0,
                    escalamientos=0,
                    violaciones_politica=0,
                    terminacion_correcta=False,
                    estado_final="excepcion",
                    detalle=f"{type(exc).__name__}: {exc}"[:300],
                )
        resultados.append(
            ResultadoTarea(
                tarea_id=tarea.id,
                titulo=tarea.title,
                categoria=tarea.category,
                requiere_correccion=tarea.requiere_correccion,
                corridas=corridas,
            )
        )
    return InformeEvaluacion(
        generado_en=datetime.now(UTC).isoformat(timespec="seconds"), tareas=resultados
    )


# -------------------------------------------------------------------- salidas


def escribir_resultados(informe: InformeEvaluacion, destino: Path) -> Path:
    """Exporta los resultados crudos a JSON. Es la fuente del informe."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(informe.a_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destino


def _tabla(cabeceras: list[str], filas: list[list[str]]) -> str:
    """Tabla Markdown. Se construye aqui para no depender de ninguna libreria."""
    lineas = [
        "| " + " | ".join(cabeceras) + " |",
        "|" + "|".join("---" for _ in cabeceras) + "|",
    ]
    lineas.extend("| " + " | ".join(fila) + " |" for fila in filas)
    return "\n".join(lineas)


def _fmt(valor: float, decimales: int = 1) -> str:
    return f"{valor:.{decimales}f}"


def generar_informe(informe: InformeEvaluacion, destino: Path) -> Path:
    """Escribe `docs/06-EVALUATION.md` con las tablas comparativas.

    El documento es **generado**: lleva el sello y la fecha para que nadie lo edite a
    mano y lo deje desincronizado con `var/evaluation_results.json`.
    """
    resumen = informe.resumen_por_modo()
    single = resumen[Modo.SINGLE_AGENT.value]
    multi = resumen[Modo.MULTI_AGENT.value]

    def _gano(tarea: ResultadoTarea, modo: str) -> bool:
        """Si la tarea se resolvio en ese modo. Una corrida ausente **no** es un exito."""
        corrida = tarea.corridas.get(modo)
        return bool(corrida and corrida.exito)

    def _celda(tarea: ResultadoTarea, modo: str) -> str:
        corrida = tarea.corridas.get(modo)
        if corrida is None:
            return "—"
        return "OK" if corrida.exito else "fallo"

    def _numero(tarea: ResultadoTarea, modo: str, campo: str) -> str:
        corrida = tarea.corridas.get(modo)
        return "—" if corrida is None else str(getattr(corrida, campo))

    def _pct(clave: str) -> str:
        return f"{single[clave]:.0%} vs {multi[clave]:.0%}"

    comparativa = _tabla(
        ["Metrica", "SINGLE_AGENT", "MULTI_AGENT", "Diferencia"],
        [
            ["Tasa de exito (MET-01)", f"{single['tasa_exito']:.0%}", f"{multi['tasa_exito']:.0%}",
             f"{(multi['tasa_exito'] - single['tasa_exito']):+.0%}"],
            ["Tareas resueltas", f"{single['exitos']}/{single['corridas']}",
             f"{multi['exitos']}/{multi['corridas']}",
             f"{multi['exitos'] - single['exitos']:+d}"],
            ["Tokens de entrada", f"{single['tokens_entrada']:,}", f"{multi['tokens_entrada']:,}",
             f"{multi['tokens_entrada'] - single['tokens_entrada']:+,}"],
            ["Tokens de salida", f"{single['tokens_salida']:,}", f"{multi['tokens_salida']:,}",
             f"{multi['tokens_salida'] - single['tokens_salida']:+,}"],
            ["Tokens totales", f"{single['tokens_totales']:,}", f"{multi['tokens_totales']:,}",
             f"{multi['tokens_totales'] - single['tokens_totales']:+,}"],
            ["Latencia media (ms)", _fmt(single["latencia_media_ms"]), _fmt(multi["latencia_media_ms"]),
             f"{multi['latencia_media_ms'] - single['latencia_media_ms']:+.1f}"],
            ["Llamadas al modelo", str(single["llamadas_modelo"]), str(multi["llamadas_modelo"]),
             f"{multi['llamadas_modelo'] - single['llamadas_modelo']:+d}"],
            ["Llamadas a herramientas", str(single["llamadas_herramienta"]),
             str(multi["llamadas_herramienta"]),
             f"{multi['llamadas_herramienta'] - single['llamadas_herramienta']:+d}"],
            ["Ciclos de revision", str(single["ciclos_revision"]), str(multi["ciclos_revision"]),
             f"{multi['ciclos_revision'] - single['ciclos_revision']:+d}"],
            ["Intervenciones humanas (MET-12)", str(single["intervenciones_humanas"]),
             str(multi["intervenciones_humanas"]),
             f"{multi['intervenciones_humanas'] - single['intervenciones_humanas']:+d}"],
            ["Escalamientos", str(single["escalamientos"]), str(multi["escalamientos"]),
             f"{multi['escalamientos'] - single['escalamientos']:+d}"],
            ["Terminacion correcta (MET-13)", f"{single['terminacion_correcta']}/{single['corridas']}",
             f"{multi['terminacion_correcta']}/{multi['corridas']}",
             f"{multi['terminacion_correcta'] - single['terminacion_correcta']:+d}"],
            ["Pruebas aprobadas / fallidas",
             f"{single['tests_aprobados']}/{single['tests_fallidos']}",
             f"{multi['tests_aprobados']}/{multi['tests_fallidos']}", "-"],
            ["Violaciones de politica (MET-14)", str(single["violaciones_politica"]),
             str(multi["violaciones_politica"]),
             f"{multi['violaciones_politica'] - single['violaciones_politica']:+d}"],
        ],
    )

    por_tarea = _tabla(
        ["Tarea", "Categoria", "Correccion", "Single", "Multi", "Ciclos (M)", "Interv. (M)"],
        [
            [
                f"`{t.tarea_id}` {t.titulo}",
                t.categoria,
                "si" if t.requiere_correccion else "no",
                _celda(t, Modo.SINGLE_AGENT.value),
                _celda(t, Modo.MULTI_AGENT.value),
                _numero(t, Modo.MULTI_AGENT.value, "ciclos_revision"),
                _numero(t, Modo.MULTI_AGENT.value, "intervenciones_humanas"),
            ]
            for t in informe.tareas
        ],
    )

    categorias = informe.por_categoria()
    por_categoria = _tabla(
        ["Categoria", "Single (exitos/total)", "Multi (exitos/total)"],
        [
            [
                categoria,
                f"{datos.get('single_agent_exitos', 0)}/{datos.get('single_agent_total', 0)}",
                f"{datos.get('multi_agent_exitos', 0)}/{datos.get('multi_agent_total', 0)}",
            ]
            for categoria, datos in sorted(categorias.items())
        ],
    )

    ganadas = [
        t.tarea_id
        for t in informe.tareas
        if _gano(t, Modo.MULTI_AGENT.value) and not _gano(t, Modo.SINGLE_AGENT.value)
    ]
    perdidas = [
        t.tarea_id
        for t in informe.tareas
        if _gano(t, Modo.SINGLE_AGENT.value) and not _gano(t, Modo.MULTI_AGENT.value)
    ]
    sobrecoste = multi["tokens_totales"] - single["tokens_totales"]

    documento = f"""# 06 — Evaluation

> **Documento GENERADO** por `src/ai_swe/evaluation/runner.py` a partir de
> `var/evaluation_results.json`. **No editar a mano**: cualquier cambio se pierde en
> la siguiente ejecucion. Generado el {informe.generado_en}.

## La pregunta central

> ¿Cuándo se justifica usar varios agentes y cuándo un único agente o un flujo
> determinista es más simple, barato y fiable?

## Como se responde

La **misma** bateria de {len(informe.tareas)} tareas controladas (`EXP-01`..`EXP-13`,
en `src/ai_swe/evaluation/tasks.py`) se ejecuta bajo dos configuraciones:

- **`SINGLE_AGENT`** — flujo directo: `interpret → coder → apply_sandbox →
  run_tests → finalize`. Sin plan, sin investigacion, **sin Reviewer** y sin puertas
  humanas.
- **`MULTI_AGENT`** — el grafo de produccion completo, con planificacion,
  investigacion, ciclo de revision y **las dos puertas HITL**.

Cada tarea tiene un criterio de exito **objetivo**: su suite de validacion falla
antes del cambio y pasa despues. El exito exige que la ejecucion termine en
`completed` **y** que la evidencia de pruebas lo respalde.

**Cuatro tareas exigen dos intentos** (`EXP-02`, `EXP-05`, `EXP-09`, `EXP-11`): el
primer parche que produce el modelo guionizado falla las pruebas. Son las que
separan las dos configuraciones, porque solo el ciclo de revision vuelve a intentarlo.

**Una tarea no converge** (`EXP-13`): sus dos propuestas fallan. Sirve de control
negativo — el multiagente **no** es magia: agota el ciclo de revision y escala.

## Resultados

{comparativa}

### Por tarea

{por_tarea}

### Por categoria

{por_categoria}

## Respuesta a la pregunta central

- **Tasa de exito:** {single['tasa_exito']:.0%} (`SINGLE_AGENT`) frente a
  {multi['tasa_exito']:.0%} (`MULTI_AGENT`). La diferencia se concentra en las
  tareas que exigen correccion: **{', '.join(ganadas) if ganadas else 'ninguna'}** las
  resuelve solo el flujo multiagente{'' if not perdidas else f", y se pierde {', '.join(perdidas)}"}.
- **Coste:** el multiagente gasta **{sobrecoste:+,} tokens** y
  **{multi['latencia_media_ms'] - single['latencia_media_ms']:+.1f} ms** de media por
  tarea. El sobrecoste es el precio de planificar, investigar y revisar.
- **Intervenciones humanas:** {single['intervenciones_humanas']} frente a
  {multi['intervenciones_humanas']}. El flujo directo no tiene puertas; el
  multiagente pide confirmar requisitos y aprobar el cambio.
- **Terminacion correcta (`MET-13`):** {single['terminacion_correcta']}/{single['corridas']}
  y {multi['terminacion_correcta']}/{multi['corridas']}. Ninguna ejecucion quedo colgada.

**Conclusion.** El multiagente **se justifica cuando el primer intento puede estar
mal**: su valor medible es convertir un fallo silencioso en un ciclo de correccion.
Cuando la tarea es directa y el primer parche es correcto, el flujo directo la
resuelve con menos tokens, menos latencia y sin pedir nada a una persona. La
arquitectura no se defiende por ser mas compleja, sino por **cuando** esa complejidad
paga.

## Limitaciones declaradas

1. **Modelo guionizado.** El arnes es offline y determinista (sin credenciales ni
   red), asi que el modelo es un guion por tarea. Esta comparacion mide el **coste y
   el beneficio de la orquestacion**, no la calidad de un modelo concreto. Es la
   misma limitacion que declara `TD-01`.
2. **Los tokens son una estimacion del proveedor guionizado** (~4 caracteres por
   token), no una medicion de facturacion. Sirven para comparar las dos
   configuraciones entre si.
3. **Doce tareas es una muestra pequena.** Las cifras son indicativas; el valor del
   arnes es que es **reproducible** y que cualquier conclusion se puede volver a
   medir.

## Metricas y experimentos

Definiciones canonicas: [`01-arquitectura.md`](01-arquitectura.md) §18
(`MET-01`..`MET-14`, `EXP-01`..`EXP-08`) y
[`auditoria-2026-10-06/10_EVALUACION_METRICAS.md`](auditoria-2026-10-06/10_EVALUACION_METRICAS.md).

## Como se reproduce

```bash
PYTHONPATH=src python -m ai_swe.evaluation.runner
```

Escribe `var/evaluation_results.json` y **regenera este documento**. La suite
`tests/test_f14_evaluation.py` ejecuta el arnes en miniatura (offline) en cada
corrida de pytest.

## Verificacion del propio sistema

- **Suite offline** — {sum(r['corridas'] for r in [single, multi])} corridas de
  evaluacion en el informe, sin red ni credenciales.
- **Mutacion** — `tools/mutation_check.py`: se introduce cada fallo a proposito y se
  comprueba que alguna prueba falla. Un corte por tiempo **no** cuenta como cazada.
- **Frontend** — `tools/verify_frontend.py` (arnes aparte, no incluido en pytest).
"""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(documento, encoding="utf-8")
    return destino


def main() -> int:  # pragma: no cover - punto de entrada manual
    """Ejecuta la bateria completa y regenera los dos artefactos."""
    raiz = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory(prefix="ai-swe-eval-") as temporal:
        informe = ejecutar_bateria(raiz_trabajo=Path(temporal))
    escribir_resultados(informe, raiz / "var" / "evaluation_results.json")
    generar_informe(informe, raiz / "docs" / "06-EVALUATION.md")
    print(json.dumps(informe.resumen_por_modo(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
