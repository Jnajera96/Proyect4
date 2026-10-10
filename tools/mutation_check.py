"""Comprobacion por mutacion: la suite de pruebas protege de verdad?

Una suite en verde no prueba nada por si sola. Puede estar comprobando cosas que
no se rompen nunca, o afirmando exactamente lo que el codigo ya hace.

Este guion introduce cada defecto **a proposito**, ejecuta las pruebas, restaura
el fichero e informa. Si una mutacion no es cazada, hay un punto ciego: o el
defecto es inocuo, o la suite no lo vigila.

Regla de oro: si la linea base ya falla, el resultado no significa nada. El
guion aborta en ese caso en lugar de informar de mutaciones cazadas sobre un
arbol roto.

Uso:
    python tools/mutation_check.py
"""

from __future__ import annotations

import json
import json
import subprocess
import time
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "ai_swe"
TESTS = RAIZ / "tests"

# Diario de recuperacion. **Un solo fichero, y nunca se borra: se vacia.**
#
# El primer diseno escribia un `.mutation_backup` por mutacion y lo borraba al
# restaurar. Eso disparaba el limite de borrados del entorno (bloquea tras 50 por
# turno), que mataba el proceso a mitad: el verificador se colgaba sin producir ni
# una linea y el fallo parecia de la aplicacion. Un unico fichero que solo se
# escribe elimina esas veinticuatro operaciones de borrado.
DIARIO = RAIZ / "_mutation_journal.json"

# Limite por invocacion de pytest. Una mutacion puede dejar una prueba esperando
# un tiempo de espera largo (los flujos SSE esperan a `run.done`). Sin limite, el
# verificador se cuelga y no hay forma de saber en cual.
#
# Historial: 90 -> 300 (F7) -> 600 (F7, correccion) -> 900 (F10). Motivo del primer
# salto: la suite crecio con las pruebas del sandbox, que crean repositorios git
# **de verdad** y tardan ~36s de base, de modo que la propia linea base se cortaba
# con 90s.
#
# **Por que 600 y no 300.** Con 300 se observo -en la misma ejecucion de F7- que
# varias mutaciones tardaban 300.1-300.2s: es decir, **cortaban**, no fallaban. Con
# el limite justo por encima de la duracion real, el verificador corre el riesgo de
# informar de sus propios cortes como cazadas. Eso ya no puede pasar a partir de
# esta correccion -un corte devuelve `None` y cuenta como NO CONCLUYENTE-, pero el
# limite debe seguir dando margen sobre la suite mutada, que es mas lenta que la
# suite base.
#
# **Por que 900 en F10.** Con 600 el verificador **aborto en la linea base**: la
# suite completa (522 pruebas, con el E2E de la API que crea un sandbox real y lanza
# pytest anidado) supero los 600s. La suite base medida en reposo son **271s**, de
# modo que 600 daba 2,2x -y una mutacion puede casi duplicar la duracion (se midio
# una de 552s en F7)-. 900s da 3,3x sobre la base medida. El limite tiene que
# superar con margen la suite **mutada**, no la base.
LIMITE_PYTEST = 900.0

# Limite para las herramientas de verificacion externas (el navegador).
LIMITE_COMANDO = 180.0


def _leer_diario() -> dict[str, str]:
    if not DIARIO.exists():
        return {}
    try:
        return json.loads(DIARIO.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _escribir_diario(datos: dict[str, str]) -> None:
    DIARIO.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


def _recuperar_pendientes() -> list[str]:
    """Restaura ficheros que quedaron mutados por una ejecucion interrumpida.

    Un `finally` **no protege contra que maten el proceso**. Si eso ocurre, el
    arbol queda con una mutacion aplicada y todas las verificaciones posteriores
    miden el codigo equivocado sin que nada lo indique.

    Paso de verdad: se interrumpio el verificador y el frontend quedo sin pintar
    eventos. La comprobacion del navegador empezo a fallar por un defecto que **no
    existia en el codigo real**, y el fallo apuntaba a la aplicacion en lugar de al
    instrumento.
    """
    diario = _leer_diario()
    restaurados: list[str] = []
    for ruta, contenido in diario.items():
        Path(ruta).write_text(contenido, encoding="utf-8")
        restaurados.append(str(Path(ruta).relative_to(RAIZ)))
    if restaurados:
        _escribir_diario({})
    return restaurados


@dataclass(frozen=True)
class Mutation:
    nombre: str
    fichero: Path
    original: str
    mutado: str
    prueba_esperada: str = ""
    # Si se indica, se ejecuta este comando en lugar de pytest. Lo usan las
    # mutaciones del frontend, que se verifican en un navegador real.
    comando: tuple[str, ...] = ()


MUTACIONES: list[Mutation] = [
    Mutation(
        "el Researcher puede escribir",
        SRC / "tools" / "registry.py",
        '{"list_files", "read_file", "search_text", "git_status", "git_log", "git_diff"}\n    ),\n    AgentRole.CODER',
        '{"list_files", "read_file", "search_text", "git_status", "git_log", "git_diff", "write_file"}\n    ),\n    AgentRole.CODER',
        "test_policy.py",
    ),
    Mutation(
        "write_file pierde el confinamiento al worktree",
        SRC / "tools" / "registry.py",
        'risk=RiskLevel.HIGH,\n        writes=True,\n        inside_worktree=True,\n    ),\n    "apply_patch"',
        'risk=RiskLevel.HIGH,\n        writes=True,\n    ),\n    "apply_patch"',
        "test_policy.py",
    ),
    Mutation(
        "la politica deja de denegar por defecto",
        SRC / "tools" / "policy.py",
        "    if spec is None:\n        return _deny(",
        "    if spec is None:\n        return _allow(",
        "test_policy.py",
    ),
    Mutation(
        "la politica permite rutas que escapan",
        SRC / "tools" / "policy.py",
        '        if normalized is None:\n            return _deny(\n                f"la ruta \'{raw_path}\' es absoluta o escapa del area autorizada",\n                "POLICY-PATH-ESCAPES",\n            )',
        "        if normalized is None:\n            normalized = raw_path",
        "test_policy.py",
    ),
    Mutation(
        "la politica ignora el presupuesto agotado",
        SRC / "tools" / "policy.py",
        '    if ctx.budget_exhausted:\n        return _approval(\n            "el presupuesto de la ejecucion esta agotado",\n            "POLICY-BUDGET-EXHAUSTED",\n        )\n',
        "",
        "test_policy.py",
    ),
    Mutation(
        "la instruccion de voz no exige confirmacion",
        SRC / "contracts" / "state.py",
        "            if not self.confirmed_by_user:\n                raise ValueError(",
        "            if False:\n                raise ValueError(",
        "test_contracts.py",
    ),
    Mutation(
        "el plan acepta ciclos de dependencias",
        SRC / "contracts" / "tasks.py",
        "        for node in graph:\n            visit(node)\n        return self",
        "        return self",
        "test_contracts.py",
    ),
    Mutation(
        "el verificador de serializabilidad se queda ciego",
        SRC / "contracts" / "validate.py",
        '    return [f"{path}: tipo no serializable {annotation!r}"]',
        "    return []",
        "test_contracts.py",
    ),
    Mutation(
        "la leyenda del diagrama deja de validarse",
        RAIZ / "tools" / "build_diagram.py",
        "    for text, lx, ly in LEGEND:\n        lr = free_label_rect(text, lx, ly)",
        "    for text, lx, ly in []:\n        lr = free_label_rect(text, lx, ly)",
        "test_diagram_layout.py",
    ),
    Mutation(
        "el diagrama deja de detectar etiquetas sobre aristas",
        RAIZ / "tools" / "build_diagram.py",
        "            if seg_hits_rect(p, q, lr_i):",
        "            if False:",
        "test_diagram_layout.py",
    ),
    # ---------------------------------------------------------------- fase M1
    Mutation(
        "el checkpoint deja de conocer los tipos de contrato",
        SRC / "state" / "store.py",
        "    return tuple(sorted(pares))",
        "    return ()",
        "test_store.py",
    ),
    Mutation(
        "la red de seguridad de MET-13 se desactiva",
        SRC / "graph" / "engine.py",
        "        if estado.status.is_terminal or estado.status is RunStatus.AWAITING_APPROVAL:\n            return estado",
        "        if True:\n            return estado",
        "test_workflow.py",
    ),
    Mutation(
        "reanudar no comprueba si la ejecucion existe",
        SRC / "graph" / "engine.py",
        "            if self._store.summary(run_id) is None:\n                raise RunNotFound(run_id)",
        "            if False:\n                raise RunNotFound(run_id)",
        "test_workflow.py",
    ),
    Mutation(
        "la puerta de aprobacion aprueba siempre",
        SRC / "graph" / "nodes.py",
        "    if eleccion is not ApprovalDecision.APPROVED:",
        "    if False:",
        "test_workflow.py",
    ),
    Mutation(
        "el confinamiento de rutas del Researcher se elimina",
        SRC / "graph" / "nodes.py",
        "    try:\n        return candidata.resolve().is_relative_to(raiz.resolve())\n    except (OSError, ValueError):\n        return False",
        "    return True",
        "test_workflow.py",
    ),
    Mutation(
        "el ciclo de revision deja de estar acotado",
        SRC / "graph" / "nodes.py",
        '        return "coder" if state.budget.review_cycles_used < state.budget.max_review_cycles else "escalate"',
        '        return "coder"',
        "test_workflow.py",
    ),
    Mutation(
        "los errores de validacion vuelven a romper la serializacion",
        SRC / "api" / "app.py",
        "            raise HTTPException(status_code=422, detail=_detalle_validacion(exc)) from exc",
        "            raise HTTPException(status_code=422, detail=exc.errors()) from exc",
        "test_api.py",
    ),
    Mutation(
        "la creacion vuelve a bloquear hasta que la ejecucion termina",
        SRC / "api" / "app.py",
        "        motor.create(estado)\n        trabajador.submit(estado.run_id)",
        "        motor.start(estado)",
        "test_api.py",
    ),
    Mutation(
        "el estado no se puede consultar antes del primer nodo",
        SRC / "graph" / "engine.py",
        "        try:\n            return self._store.initial_state(run_id)\n        except KeyError as exc:\n            raise RunNotFound(run_id) from exc",
        "        raise RunNotFound(run_id)",
        "test_api.py",
    ),
    Mutation(
        "el checkpoint y el indice vuelven a divergir tras un aborto",
        SRC / "graph" / "engine.py",
        "        self._app.update_state(config, nuevo.model_dump())\n\n        self._store.sync(nuevo)",
        "        self._store.sync(nuevo)",
        "test_workflow.py",
    ),
    # ------------------------------------------------------------- frontend
    # Se verifican en un motor de render real, no con un shim de DOM.
    Mutation(
        "el frontend pierde la suscripcion a los eventos",
        RAIZ / "frontend" / "index.html",
        "fuente = new EventSource(`/runs/${runId}/events`);",
        "fuente = null;",
        comando=(sys.executable, "tools/verify_frontend.py"),
    ),
    Mutation(
        "el frontend deja de cargar los contratos",
        RAIZ / "frontend" / "index.html",
        'const r = await fetch("contracts.json");\n  contratos = await r.json();',
        "contratos = { schemas: { EventKind: { enum: [] } } };",
        comando=(sys.executable, "tools/verify_frontend.py"),
    ),
    Mutation(
        "el frontend deja de mostrar el run_id",
        RAIZ / "frontend" / "index.html",
        '$("run-id").textContent = cuerpo.run_id;',
        '$("run-id").textContent = "";',
        comando=(sys.executable, "tools/verify_frontend.py"),
    ),
    Mutation(
        "el frontend deja de pintar los eventos",
        RAIZ / "frontend" / "index.html",
        "  anadirEvento(ev.kind, detalle, ev.seq);",
        "  /* anadirEvento omitido */",
        comando=(sys.executable, "tools/verify_frontend.py"),
    ),
    # ---------------------------------------------------- F2: Model Gateway
    # Cada una comprueba una propiedad que el sistema afirma tener. No se anade
    # ninguna que no haga caer a una prueba concreta.
    Mutation(
        "el gateway deja de comprobar el presupuesto",
        SRC / "models" / "gateway.py",
        "        if budget is not None:\n            assert_budget_available(budget, provider=solicitado)",
        "        if False:\n            assert_budget_available(budget, provider=solicitado)",
        "test_model_gateway.py",
    ),
    Mutation(
        "el timeout deja de acotarse al presupuesto",
        SRC / "models" / "gateway.py",
        "        if budget is not None:\n            acotado = effective_timeout_s(budget, base)",
        "        if False:\n            acotado = effective_timeout_s(budget, base)",
        "test_model_gateway.py",
    ),
    Mutation(
        "la salida estructurada se acepta sin validar",
        SRC / "models" / "gateway.py",
        "        try:\n            validado = response_model.model_validate(datos)\n        except ValidationError as exc:\n            raise StructuredOutputError(\n                f\"la respuesta no cumple el contrato {response_model.__name__}\",\n                provider=provider,\n                detail=str(exc)[:600],\n            ) from exc\n        return validado.model_dump()",
        "        return datos",
        "test_model_gateway.py",
    ),
    Mutation(
        "la llamada al modelo deja de contarse",
        SRC / "models" / "budget.py",
        '    datos["used_model_calls"] = budget.used_model_calls + 1',
        '    datos["used_model_calls"] = budget.used_model_calls',
        "test_model_gateway.py",
    ),
    Mutation(
        "los tokens dejan de sumarse al presupuesto",
        SRC / "models" / "budget.py",
        "    if usage is not None and usage.known_total is not None:\n        datos[\"used_tokens\"] = budget.used_tokens + usage.known_total",
        "    if False:\n        datos[\"used_tokens\"] = budget.used_tokens + usage.known_total",
        "test_model_gateway.py",
    ),
    Mutation(
        "los errores dejan de redactar el mensaje",
        SRC / "models" / "errors.py",
        "        self.message = redact(message)",
        "        self.message = message",
        "test_model_gateway.py",
    ),
    Mutation(
        "el adapter real deja de registrar su credencial",
        SRC / "models" / "providers" / "openai_compatible.py",
        "        register_secret(api_key)",
        "        pass",
        "test_model_gateway.py",
    ),
    Mutation(
        "una credencial invalida pasa a reintentarse",
        SRC / "models" / "errors.py",
        '    error_class = "MODEL_AUTHENTICATION_ERROR"',
        '    error_class = "MODEL_AUTHENTICATION_ERROR"\n    recoverable = True',
        "test_model_gateway.py",
    ),
    Mutation(
        "el gateway ignora los proveedores de respaldo",
        SRC / "models" / "gateway.py",
        "        for indice, adapter in enumerate(self._adapters):",
        "        for indice, adapter in enumerate(self._adapters[:1]):",
        "test_model_gateway.py",
    ),
    Mutation(
        "el registro resuelve proveedores por import dinamico",
        SRC / "models" / "registry.py",
        '    fabrica = _REGISTRO.get(clave)\n    if fabrica is None:',
        '    import importlib\n\n    try:\n        return importlib.import_module(clave).adapter\n    except Exception:  # noqa: BLE001\n        fabrica = None\n    if fabrica is None:',
        "test_model_gateway.py",
    ),
    Mutation(
        "el .gitignore vuelve a excluir el paquete del gateway",
        RAIZ / ".gitignore",
        "\n/models/\n*.bin",
        "\nmodels/\n*.bin",
        "test_model_gateway.py",
    ),
    # ------------------------------------------------------------------ F3
    Mutation(
        "F3: interpret ignora el modelo aunque este conectado",
        SRC / "graph" / "nodes.py",
        "    resultado = _interpretacion_del_modelo(state)",
        "    resultado = None",
        "test_f3_interpret_analyst.py",
    ),
    Mutation(
        "F3: un fallo del modelo se traga en vez de caer al fallback",
        SRC / "graph" / "nodes.py",
        "        if not _es_fallo_esperado(exc):\n            raise",
        "        pass",
        "test_f3_interpret_analyst.py",
    ),
    Mutation(
        "F3: el modelo puede ampliar el alcance autorizado",
        SRC / "graph" / "nodes.py",
        'interpretacion = interpretacion.model_copy(update={"scope": _alcance(state)})',
        "pass",
        "test_f3_interpret_analyst.py",
    ),
    Mutation(
        "F3: el gasto del modelo no se contabiliza",
        SRC / "graph" / "nodes.py",
        "    nuevo_presupuesto = gateway.consume(state.budget, respuesta)",
        "    nuevo_presupuesto = state.budget",
        "test_f3_interpret_analyst.py",
    ),
    Mutation(
        "F3: el segundo nodo tambien habla con el gateway",
        SRC / "graph" / "nodes.py",
        "def researcher(state: RunState) -> dict:",
        "def researcher(state: RunState) -> dict:\n    from ai_swe.models import ModelGateway  # mutacion: acopla el segundo nodo\n    _ = ModelGateway",
        "test_model_gateway.py",
    ),
    Mutation(
        "F3: el gateway se importa al cargar el modulo (deja de ser perezoso)",
        SRC / "graph" / "nodes.py",
        "def _gateway_por_defecto():",
        "from ai_swe.models import ModelGateway\n\n\ndef _gateway_por_defecto():",
        "test_model_gateway.py",
    ),
    Mutation(
        "F3: la tabla de precios acepta un modelo sin tarifa como 0.0",
        SRC / "models" / "pricing.py",
        "        if precio is None:\n            return None",
        "        if precio is None:\n            return 0.0",
        "test_f3_interpret_analyst.py",
    ),
    Mutation(
        "F3: la interpretacion estructurada se salta la validacion Pydantic",
        SRC / "graph" / "nodes.py",
        "    interpretacion = TaskInterpretation.model_validate(datos)",
        "    interpretacion = TaskInterpretation.model_construct(**datos)",
        "test_f3_interpret_analyst.py",
    ),
    # ------------------------------------------------------------------ F4
    # Cuatro de estas ocho tocan las dos propiedades que el Arquitecto pidio
    # vigilar de forma explicita: **el consumo de presupuesto** (F4-presupuesto-*)
    # y **el comportamiento del fallback** (F4-fallback-*).
    Mutation(
        "F4: plan ignora el modelo aunque este conectado",
        SRC / "graph" / "nodes.py",
        "        resultado = _plan_del_modelo(state)",
        "        resultado = None",
        "test_f4_supervisor_plan.py",
    ),
    Mutation(
        "F4: un fallo del modelo se traga en vez de caer al fallback",
        SRC / "graph" / "nodes.py",
        "        if not _es_fallo_esperado(exc):\n            raise\n        motivo = f\"{type(exc).__name__}: {exc}\"[:500]\n        log.warning(\"plan:",
        "        if False:\n            raise\n        motivo = f\"{type(exc).__name__}: {exc}\"[:500]\n        log.warning(\"plan:",
        "test_f4_supervisor_plan.py",
    ),
    Mutation(
        "F4-fallback: no hay plan cuando no hay modelo",
        SRC / "graph" / "nodes.py",
        "    if resultado is None:\n        plan_fallback = _plan_determinista(state, motivo=\"modelo no conectado\")",
        "    if resultado is None:\n        plan_fallback = RunPlan(subtasks=[]),",
        "test_f4_supervisor_plan.py",
    ),
    Mutation(
        "F4-fallback: el plan de respaldo no encadena investigacion y cambio",
        SRC / "graph" / "nodes.py",
        "    subtareas = [investigar]\n    if intencion is Intent.MODIFY:",
        "    subtareas = [investigar]\n    if False:",
        "test_f4_supervisor_plan.py",
    ),
    Mutation(
        "F4-presupuesto: la planificacion no se contabiliza",
        SRC / "graph" / "nodes.py",
        "    nuevo_presupuesto = gateway.consume(state.budget, respuesta)\n    tokens = nuevo_presupuesto.used_tokens - state.budget.used_tokens\n    return plan, nuevo_presupuesto, tokens",
        "    return plan, state.budget, 0",
        "test_f4_supervisor_plan.py",
    ),
    Mutation(
        "F4-presupuesto: el plan puede pedir mas ciclos de los presupuestados",
        SRC / "graph" / "nodes.py",
        "    if plan.max_review_cycles <= state.budget.max_review_cycles:\n        return plan",
        "    if True:\n        return plan",
        "test_f4_supervisor_plan.py",
    ),
    Mutation(
        "F4: el plan estructurado se salta la validacion Pydantic del nodo",
        SRC / "graph" / "nodes.py",
        "        plan = RunPlan.model_validate(datos)",
        "        plan = RunPlan.model_construct(**datos)",
        "test_f4_supervisor_plan.py",
    ),
    Mutation(
        "F4: una instruccion fuera de alcance se planifica igualmente",
        SRC / "graph" / "nodes.py",
        '    if intencion is Intent.OUT_OF_SCOPE:\n        return "explain_limits"\n    return "plan"',
        '    return "plan"',
        "test_f4_supervisor_plan.py",
    ),
    # ------------------------------------------------------------------ F5
    Mutation(
        "F5: el indice no avanza tras ejecutar researcher",
        SRC / "graph" / "nodes.py",
        '        "evidence": _con_evidencia(state, findings=hallazgos_totales),\n        "plan_index": state.plan_index + 1,\n        "updated_at": _ahora(),',
        '        "evidence": _con_evidencia(state, findings=hallazgos_totales),\n        "plan_index": state.plan_index,\n        "updated_at": _ahora(),',
        "test_f5_plan_driven_execution.py",
    ),
    Mutation(
        "F5: la evidencia se sobrescribe en lugar de acumularse",
        SRC / "graph" / "nodes.py",
        '    hallazgos_previos = list(state.evidence.findings)\n    hallazgos_totales = hallazgos_previos + hallazgos',
        '    hallazgos_totales = hallazgos',
        "test_f5_plan_driven_execution.py",
    ),
    Mutation(
        "F5: el enrutador ignora el plan y usa la ruta estatica",
        SRC / "graph" / "nodes.py",
        '    if state.plan_index < len(state.plan.subtasks):\n        siguiente = state.plan.subtasks[state.plan_index]\n        return siguiente.agent.value',
        '    return _ruta_estatica_m1(state)',
        "test_f5_plan_driven_execution.py",
    ),
    Mutation(
        "F5: el plan agotado no finaliza",
        SRC / "graph" / "nodes.py",
        '    # Plan agotado: se finaliza. El plan ya dicto todo lo que habia que hacer;\n    # la ruta estatica de M1 no aplica porque el plan es la fuente de verdad.\n    return "finalize"',
        '    # Plan agotado: se finaliza.\n    return _ruta_estatica_m1(state)',
        "test_f5_plan_driven_execution.py",
    ),
    Mutation(
        "F5: el indice puede ser negativo",
        SRC / "contracts" / "state.py",
        '    plan_index: int = Field(default=0, ge=0)',
        '    plan_index: int = Field(default=0)',
        "test_f5_plan_driven_execution.py",
    ),
    Mutation(
        "F5: un segundo nodo ejecutor no avanza el indice",
        SRC / "graph" / "nodes.py",
        '        "outputs": _con_salidas(state, coder_output=cambio),\n        "plan_index": state.plan_index + 1,\n        "next_step": "run_tests",',
        '        "outputs": _con_salidas(state, coder_output=cambio),\n        "plan_index": state.plan_index,\n        "next_step": "run_tests",',
        "test_f5_plan_driven_execution.py",
    ),
    # ------------------------------------------------------------------ F6
    Mutation(
        "F6: el sha256 del fichero no se deriva del contenido",
        SRC / "graph" / "nodes.py",
        '        nuevo_sha = hashlib.sha256(contenido.encode("utf-8")).hexdigest()',
        '        nuevo_sha = hashlib.sha256(archivo.path.encode("utf-8")).hexdigest()',
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: el diff no se deriva del contenido del fichero",
        SRC / "graph" / "nodes.py",
        "        trozos_dif.append(_diff_unificado(archivo))",
        '        trozos_dif.append(f"--- a/{archivo.path}\\n+++ b/{archivo.path}\\n")',
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: el sha256 del diff se fabrica en lugar de derivarse",
        SRC / "graph" / "nodes.py",
        '        diff_sha256=hashlib.sha256(diferencias.encode("utf-8")).hexdigest(),',
        '        diff_sha256=hashlib.sha256(b"").hexdigest(),',
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: el conteo de lineas anadidas es siempre cero",
        SRC / "graph" / "nodes.py",
        "            anadidas, eliminadas = _contar_lineas(contenido), 0",
        "            anadidas, eliminadas = 0, 0",
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: el limite de ficheros del alcance no se respeta",
        SRC / "graph" / "nodes.py",
        "    if len(archivos) > scope.max_files_changed:",
        "    if False:",
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: el limite de lineas del alcance no se respeta",
        SRC / "graph" / "nodes.py",
        "    while archivos and _lineas(archivos) > scope.max_lines_changed:",
        "    while False:",
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: el recorte por alcance no se declara",
        SRC / "graph" / "nodes.py",
        "    avisos = [motivo] if motivo else []",
        "    avisos = []",
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: el presupuesto no se consume al proponer el modelo",
        SRC / "graph" / "nodes.py",
        "    nuevo_presupuesto = gateway.consume(state.budget, respuesta)\n    return cambio, nuevo_presupuesto, avisos",
        "    return cambio, state.budget, avisos",
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: el fallo del modelo se traga sin dejar rastro",
        SRC / "graph" / "nodes.py",
        '        return {\n            "outputs": _con_salidas(state, coder_output=cambio),\n            "errors": _error(\n                state,\n                "MODEL_FALLBACK",',
        '        return {\n            "outputs": _con_salidas(state, coder_output=cambio),\n            "errors": list(state.errors) or _error(\n                state,\n                "MODEL_FALLBACK",',
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: el fallback devuelve un parche inventado en lugar de un cambio vacio",
        SRC / "graph" / "nodes.py",
        '    return CodeChange(\n        files_changed=[],\n        diff="",\n        rationale=motivo,\n        diff_sha256=hashlib.sha256(b"").hexdigest(),\n    )',
        '    return CodeChange(\n        files_changed=[FileChange(path="parche.py", added=1, removed=0, sha256=hashlib.sha256(b"x").hexdigest())],\n        diff="--- a/parche.py\\n+++ b/parche.py\\n+print(1)\\n",\n        rationale=motivo,\n        diff_sha256=hashlib.sha256(b"inventado").hexdigest(),\n    )',
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: el coder escribe en disco en lugar de solo proponer",
        SRC / "graph" / "nodes.py",
        '    propuesta, motivo = _respetar_limites(propuesta, _alcance(state))\n    avisos = [motivo] if motivo else []',
        '    propuesta, motivo = _respetar_limites(propuesta, _alcance(state))\n    _base = Path(state.options.repo_path or ".")\n    if _base.is_dir():\n        for _f in propuesta.files:\n            if _f.new_content is not None and _f.operation is not FileOperation.DELETE:\n                (_base / _f.path).parent.mkdir(parents=True, exist_ok=True)\n                (_base / _f.path).write_text(_f.new_content, encoding="utf-8")\n    avisos = [motivo] if motivo else []',
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: el modelo se ignora y siempre se usa el fallback",
        SRC / "graph" / "nodes.py",
        "    resultado = _coder_del_modelo(state)",
        "    resultado = None",
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: una operacion delete sin contenido deja de rechazarse",
        SRC / "contracts" / "outputs.py",
        '        if self.operation is FileOperation.DELETE and self.new_content is not None:\n            raise ValueError(\n                f"\'{self.path}\': una operacion \'delete\' no lleva new_content"\n            )',
        '        if False:\n            raise ValueError(\n                f"\'{self.path}\': una operacion \'delete\' no lleva new_content"\n            )',
        "test_f6_real_coder.py",
    ),
    Mutation(
        "F6: una operacion create/modify sin contenido deja de rechazarse",
        SRC / "contracts" / "outputs.py",
        '        if self.operation is not FileOperation.DELETE and self.new_content is None:\n            raise ValueError(\n                f"\'{self.path}\': la operacion \'{self.operation.value}\' exige new_content"\n            )',
        '        if False:\n            raise ValueError(\n                f"\'{self.path}\': la operacion \'{self.operation.value}\' exige new_content"\n            )',
        "test_f6_real_coder.py",
    ),
    # ------------------------------------------------------------------ F7
    Mutation(
        "F7: el confinamiento deja pasar una ruta que escapa",
        SRC / "sandbox.py",
        "        normalizada = normalize_rel_path(ruta_relativa)\n        if normalizada is None:",
        "        normalizada = ruta_relativa.replace(\"\\\\\", \"/\").strip().strip(\"./\") or ruta_relativa\n        if normalizada is None:",
        "test_f7_sandbox.py",
    ),
    Mutation(
        "F7: la comprobacion fisica de raiz deja de hacerse",
        SRC / "sandbox.py",
        "        if destino != raiz_resuelta and raiz_resuelta not in destino.parents:",
        "        if False:",
        "test_f7_sandbox.py",
    ),
    Mutation(
        "F7: el aplicador escribe sin pasar por el Policy Engine",
        SRC / "tools" / "patcher.py",
        "    decision = decide(herramienta, {\"path\": normalizada}, ctx)\n    if decision.effect is not PolicyEffect.ALLOW:",
        "    decision = decide(herramienta, {\"path\": normalizada}, ctx)\n    if False:",
        "test_f7_sandbox.py",
    ),
    Mutation(
        "F7: el aplicador no comprueba el alcance declarado",
        SRC / "tools" / "patcher.py",
        "    if not path_within_scope(normalizada, allowed_paths):",
        "    if False:",
        "test_f7_sandbox.py",
    ),
    Mutation(
        "F7: el aplicador escribe en el repositorio original en lugar del sandbox",
        SRC / "tools" / "patcher.py",
        "                sandbox.escribir(ruta, contenidos[ruta] or \"\")",
        "                _objetivo = Path(sandbox.repo_original) / ruta\n                _objetivo.parent.mkdir(parents=True, exist_ok=True)\n                _objetivo.write_text(contenidos[ruta] or \"\", encoding=\"utf-8\")",
        "test_f7_sandbox.py",
    ),
    Mutation(
        # **Mutacion corregida en F7.** La version anterior retiraba solo la linea de
        # `prune` y resulto **no observable**: en este git (2.55.0) `worktree remove
        # --force` con ruta absoluta limpia por si solo la entrada administrativa,
        # tanto si el arbol esta como si su directorio ya desaparecio. Ninguna prueba
        # podia cazarla porque el efecto observable no cambiaba -y una mutacion que no
        # se puede cazar no verifica nada, solo infla el recuento-.
        #
        # Se sustituye por una que **si** es observable y protege el mismo contrato
        # (el teardown no deja fantasmas): se retiran `remove` y `prune` a la vez, de
        # modo que el worktree queda registrado aunque su directorio se borre.
        "F7: el teardown deja la entrada de worktree registrada (fantasma)",
        SRC / "sandbox.py",
        "        _git(*orden, cwd=sandbox.repo_original, check=False)\n        _git(\"worktree\", \"prune\", cwd=sandbox.repo_original, check=False)",
        "        pass  # MUTACION: sin remove ni prune",
        "test_f7_sandbox.py",
    ),
    Mutation(
        # **Mutacion corregida en F7.** La version anterior retiraba el bloque
        # `shutil.rmtree` del teardown y resulto **no observable**: `worktree remove
        # --force` ya borra el directorio por si solo, de modo que el `rmtree` es red
        # de seguridad y su ausencia no cambia ningun resultado visible.
        #
        # Se sustituye por una que **si** es observable y protege un invariante
        # distinto del teardown: que un worktree que **no creamos nosotros** no se
        # destruya. Es una salvaguarda real -un `Sandbox` puede construirse a mano
        # para reabrir uno existente-, y retirarla hace que un `destruir` sobre un
        # sandbox ajeno lo borre.
        "F7: el teardown destruye tambien el sandbox que no creamos nosotros",
        SRC / "sandbox.py",
        "    if not sandbox.creado_por_nosotros:\n        return",
        "    if False:\n        return",
        "test_f7_sandbox.py",
    ),
    Mutation(
        "F7: un archivo nuevo no aparece en el diff (falta add -N)",
        SRC / "sandbox.py",
        '        _git("add", "-N", "--", ".", cwd=self.raiz, check=False)\n        result = _git("diff", "HEAD", "--no-color", cwd=self.raiz, check=False)',
        '        result = _git("diff", "HEAD", "--no-color", cwd=self.raiz, check=False)',
        "test_f7_sandbox.py",
    ),
    Mutation(
        "F7: el diff vuelve a ser de lineas completas (ignora el contenido previo)",
        SRC / "graph" / "nodes.py",
        "    elif propuesta.operation is FileOperation.CREATE or contenido_previo is None:\n        viejo = \"\"",
        "    elif propuesta.operation is FileOperation.CREATE or True:\n        viejo = \"\"",
        "test_f7_sandbox.py",
    ),
    Mutation(
        "F7: un borrado puede producir un diff vacio",
        SRC / "graph" / "nodes.py",
        "    if not texto and propuesta.operation is FileOperation.DELETE:",
        "    if False and propuesta.operation is FileOperation.DELETE:",
        "test_f7_sandbox.py",
    ),
    Mutation(
        "F7: el conteo de lineas se toma del contenido entero otra vez",
        SRC / "graph" / "nodes.py",
        "        trozo = _diff_unificado(archivo, previos.get(archivo.path))\n        anadidas, eliminadas = _contar_desde_diff(trozo)",
        "        trozo = _diff_unificado(archivo, previos.get(archivo.path))\n        anadidas, eliminadas = _contar_lineas(archivo.new_content or \"\"), 0",
        "test_f7_sandbox.py",
    ),
    Mutation(
        # **Mutacion corregida en F7.** La version anterior retiraba solo `--detach`
        # dejando `... str(raiz), "HEAD"`, y resulto **no observable**: se comprobo a
        # mano que pasar un commit-ish (`HEAD`) en lugar de un nombre de rama detacha
        # por si solo, asi que la rama no se creaba igualmente.
        #
        # La forma realmente peligrosa es `git worktree add <ruta>` **sin** commit-ish:
        # git crea una rama con el nombre del directorio y la registra en el
        # repositorio del usuario -justo lo que `--detach` y el `HEAD` evitan-. La
        # mutacion ahora quita ambos, que es el fallo de verdad.
        "F7: el sandbox se crea sin --detach ni HEAD (crea una rama en el repo del usuario)",
        SRC / "sandbox.py",
        '    _git("worktree", "add", "--detach", str(raiz), "HEAD", cwd=repo)',
        '    _git("worktree", "add", str(raiz), cwd=repo)',
        "test_f7_sandbox.py",
    ),
    # ---------------------------------------------------------------- F8: runner
    Mutation(
        # El fallo mas grave posible del ejecutor: dejar de comprobar la lista.
        # Un objetivo que no esta permitido se lanzaria igualmente. La mutacion
        # hace que la comprobacion sea un no-op, no que pase a permitir uno en
        # concreto: asi se comprueba la guarda entera, no una entrada.
        "F8: el runner ejecuta un target que no esta permitido",
        SRC / "tools" / "runner.py",
        "    if target not in permitidos:\n        raise TargetNoPermitido(target, permitidos)",
        "    if False:\n        raise TargetNoPermitido(target, permitidos)",
        "test_f8_test_runner.py",
    ),
    Mutation(
        # `shell=True` convierte la lista en una linea de shell: es exactamente el
        # fallo que todo el modulo existe para evitar. La mutacion no puede pasar
        # desapercibida porque ademas una lista con `shell=True` no es un uso
        # valido de subprocess sin `command=`.
        "F8: el runner lanza el comando con shell=True",
        SRC / "tools" / "runner.py",
        "            timeout=timeout,\n            shell=False,",
        "            timeout=timeout,\n            shell=True,",
        "test_f8_test_runner.py",
    ),
    Mutation(
        # Un timeout debe producir evidencia de que se colgo (EXIT_TIMEOUT). Si se
        # deja propagar, el objetivo colgado tumba el grafo en lugar de registrarlo.
        "F8: un timeout del runner se propaga en vez de registrarse",
        SRC / "tools" / "runner.py",
        "    except subprocess.TimeoutExpired as exc:\n        duracion = time.perf_counter() - inicio",
        "    except subprocess.TimeoutExpired as exc:\n        raise\n        duracion = time.perf_counter() - inicio",
        "test_f8_test_runner.py",
    ),
    Mutation(
        # El `PYTHONPATH` mal apuntado es el fallo mas silencioso del modulo: las
        # pruebas importarian el paquete del repositorio original y la evidencia
        # diria "pasa" sobre un codigo que no es el que se va a aprobar.
        "F8: el runner deja el PYTHONPATH del repo original (prueba el codigo equivocado)",
        SRC / "tools" / "runner.py",
        '    raiz_src = sandbox.raiz / "src"\n    if raiz_src.is_dir():\n        entorno["PYTHONPATH"] = str(raiz_src)',
        '    raiz_src = sandbox.raiz / "src"\n    if False:\n        entorno["PYTHONPATH"] = str(raiz_src)',
        "test_f8_test_runner.py",
    ),
    Mutation(
        # Sin avanzar `plan_index`, la ruta de cierre estatica no se alcanza igual;
        # pero el fallo real es que `run_tests` deje de acumular la evidencia: el
        # Reviewer se quedaria sin nada que juzgar.
        "F8: run_tests no acumula la evidencia (el Reviewer juzga a ciegas)",
        SRC / "graph" / "nodes.py",
        "        \"evidence\": _con_evidencia(\n            state, test_runs=[*state.evidence.test_runs, *evidencia]\n        ),",
        "        \"evidence\": _con_evidencia(\n            state, test_runs=[*state.evidence.test_runs]\n        ),",
        "test_f8_test_runner.py",
    ),
    Mutation(
        # Un rechazo de ruta en el sandbox debe escalar a un humano. Si se ignora,
        # la ejecucion continuaria como si el cambio se hubiera aplicado, y el
        # humano aprobaria algo que no existe.
        "F8: apply_sandbox ignora las rutas denegadas",
        SRC / "graph" / "nodes.py",
        "    if resultado.denegados:\n        detalle =",
        "    if False:\n        detalle =",
        "test_f8_test_runner.py",
    ),
    Mutation(
        # Un fallo al aplicar el parche no puede pasar por "aplicado": la ejecucion
        # probaria un arbol que no contiene el cambio.
        "F8: apply_sandbox ignora los fallos de aplicacion",
        SRC / "graph" / "nodes.py",
        "    if resultado.fallos:\n        detalle =",
        "    if False:\n        detalle =",
        "test_f8_test_runner.py",
    ),
    Mutation(
        # El router del Coder debe mandar al sandbox solo si hay cambios. Si manda
        # siempre, un cambio vacio crea un worktree sin nada que aplicar.
        "F8: el router del Coder manda al sandbox aunque no haya cambios",
        SRC / "graph" / "nodes.py",
        '    return "apply_sandbox" if salida and salida.files_changed else "escalate_no_changes"',
        '    return "apply_sandbox"',
        "test_f8_test_runner.py",
    ),
    Mutation(
        # Si el router del sandbox no distingue el estado terminal, un sandbox
        # fallido seguiria a `run_tests`, que escalaria por falta de worktree: el
        # error real (SANDBOX_*) se perderia.
        "F8: el router del sandbox no respeta el estado terminal",
        SRC / "graph" / "nodes.py",
        '    return "finalize" if state.status.is_terminal else "run_tests"',
        '    return "run_tests"',
        "test_f8_test_runner.py",
    ),
    # ------------------------------------------------------- F9: reviewer
    Mutation(
        # REGLA 1 desactivada: el modelo podria aprobar un cambio con las pruebas en
        # rojo y se promoveria. Es el fallo mas grave que F9 puede cometer.
        "F9: el modelo puede aprobar con pruebas en rojo (guarda de pruebas desactivada)",
        SRC / "graph" / "nodes.py",
        "    if not fallidas or veredicto.decision is not ReviewDecision.ACCEPT:\n        return veredicto",
        "    if True:\n        return veredicto",
        "test_f9_reviewer.py",
    ),
    Mutation(
        # REGLA 2 desactivada: un Coder que no converge y un Reviewer que siempre pide
        # cambios se turnarian hasta agotar el presupuesto.
        "F9: los ciclos agotados no escalan (guarda de ciclos desactivada)",
        SRC / "graph" / "nodes.py",
        "    if usados < maximo:\n        return veredicto",
        "    if True:\n        return veredicto",
        "test_f9_reviewer.py",
    ),
    Mutation(
        # El orden de las guardas importa: si el limite de ciclos se evalua antes del
        # veto por pruebas, no ve el `request_changes` que la guarda de pruebas crea,
        # y un `accept` roto se cuela sin pasar por el limite.
        "F9: las guardas se aplican en orden invertido (el veto por pruebas no pasa por el limite)",
        SRC / "graph" / "nodes.py",
        "    return _guarda_ciclos(state, _guarda_pruebas(state, veredicto))",
        "    return _guarda_pruebas(state, _guarda_ciclos(state, veredicto))",
        "test_f9_reviewer.py",
    ),
    Mutation(
        # Un fallback que no se declara es indistinguible de un acierto: no se podria
        # saber que el modelo no llego a usarse.
        "F9: el fallback determinista no deja error tipado (degrada en silencio)",
        SRC / "graph" / "nodes.py",
        '            "MODEL_FALLBACK",\n            AgentRole.REVIEWER.value,',
        '            "MODEL_FALLBACK_SILENCIOSO_NO_USAR",\n            AgentRole.REVIEWER.value,',
        "test_f9_reviewer.py",
    ),
    Mutation(
        # El modelo asignado al Reviewer debe viajar en la peticion; si no, la
        # configuracion `reviewer_model` no tendria ningun efecto.
        "F9: la peticion del Reviewer no lleva su modelo asignado",
        SRC / "graph" / "nodes.py",
        "        model=_modelo_del_reviewer(),",
        "        model=None,",
        "test_f9_reviewer.py",
    ),
    Mutation(
        # Aprobar o escalar no son iterar: contar siempre los ciclos agota el limite
        # sin haber rehecho nada.
        "F9: cualquier veredicto consume un ciclo de revision",
        SRC / "graph" / "nodes.py",
        "    ciclos = presupuesto.review_cycles_used\n    if veredicto.decision is ReviewDecision.REQUEST_CHANGES:\n        ciclos += 1",
        "    ciclos = presupuesto.review_cycles_used + 1",
        "test_f9_reviewer.py",
    ),
    Mutation(
        # El router debe traducir `accept` a la puerta HITL; si no, un cambio aprobado
        # no llegaria nunca a aprobacion humana.
        "F9: un ACCEPT no encamina a la puerta de aprobacion",
        SRC / "graph" / "nodes.py",
        '    if veredicto.decision is ReviewDecision.ACCEPT:\n        return "mark_awaiting"',
        '    if veredicto.decision is ReviewDecision.ACCEPT:\n        return "escalate"',
        "test_f9_reviewer.py",
    ),
    Mutation(
        # El Reviewer debe juzgar con la evidencia delante. Sin ella, revisa el diff
        # a ciegas y su criterio no vale mas que el de F8.
        "F9: el contexto del Reviewer omite la evidencia de pruebas",
        SRC / "graph" / "nodes.py",
        '        f"Evidencia real de pruebas:\\n{_resumen_de_pruebas(state.evidence.test_runs)}"',
        '        "(evidencia de pruebas omitida)"',
        "test_f9_reviewer.py",
    ),
    # ------------------------------ M2 (item 3): puerta de confirmacion de requisitos
    Mutation(
        # Sin la puerta, el sistema planifica sobre lo que entendio sin que nadie lo
        # haya confirmado. Es el fallo que el item 3 del DoD existe para impedir.
        "M2: se planifica sin confirmar los requisitos (puerta saltada)",
        SRC / "graph" / "nodes.py",
        '    if state.interpretation is not None and state.interpretation.confirmed_by_user:\n        return "plan"\n    return "mark_awaiting_requirements"',
        '    return "plan"',
        "test_m2_e2e.py",
    ),
    Mutation(
        # Si el nodo no marca el estado de espera, la ejecucion se interrumpe pero
        # nadie puede saber que esta esperando: la puerta seria invisible.
        "M2: la espera de requisitos no se marca en el estado",
        SRC / "graph" / "nodes.py",
        '        "status": RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION,\n        "next_step": "confirm_requirements_gate",',
        '        "status": RunStatus.RUNNING,\n        "next_step": "confirm_requirements_gate",',
        "test_m2_e2e.py",
    ),
    Mutation(
        # Sin marcar la confirmacion, el estado miente: dice que no esta confirmado
        # aunque el humano ya lo haya hecho.
        "M2: la confirmacion humana no se registra en la interpretacion",
        SRC / "graph" / "nodes.py",
        '    datos["confirmed_by_user"] = True\n',
        '',
        "test_m2_e2e.py",
    ),
    Mutation(
        # Un rechazo que planificara produciria trabajo sobre una premisa que el
        # humano acaba de declarar falsa.
        "M2: un rechazo de requisitos planifica igualmente",
        SRC / "graph" / "nodes.py",
        "    if eleccion is ApprovalDecision.REJECTED:\n        return _escalar(",
        "    if False:\n        return _escalar(",
        "test_m2_e2e.py",
    ),
    Mutation(
        # Ignorar las modificaciones del humano convertiria la reanudacion en un
        # simple "si" y la correccion de los requisitos en un gesto vacio.
        "M2: las modificaciones humanas se descartan",
        SRC / "graph" / "nodes.py",
        "    datos = interpretacion.model_dump()\n    datos.update(cambios)\n",
        "    datos = interpretacion.model_dump()\n",
        "test_m2_e2e.py",
    ),
    Mutation(
        # Una respuesta que no se entiende no puede confirmar en nombre de nadie.
        "M2: una reanudacion irreconocible se trata como aprobada",
        SRC / "graph" / "nodes.py",
        "    except ValueError:\n        return ApprovalDecision.REJECTED, {}",
        "    except ValueError:\n        return ApprovalDecision.APPROVED, {}",
        "test_m2_e2e.py",
    ),
    Mutation(
        # La red de seguridad de MET-13 debe distinguir esperar de colgarse. Si solo
        # reconoce la puerta de aprobacion, una ejecucion detenida en la de
        # requisitos se fuerza a needs_human como si la topologia estuviera rota.
        "M2: la espera de requisitos se confunde con una ejecucion colgada",
        SRC / "graph" / "engine.py",
        "        if estado.status.is_terminal or estado.status.is_awaiting_human:",
        "        if estado.status.is_terminal or estado.status is RunStatus.AWAITING_APPROVAL:",
        "test_m2_e2e.py",
    ),
    # ------------------------------------------------- F10: API REST y SSE
    Mutation(
        # El flujo SSE es una salida al navegador. Sin redactar en el punto por el
        # que pasan todos los eventos, una clave en la instruccion llega en claro al
        # cliente: el filtro de logging no la cubre, porque esto no pasa por logging.
        "F10: los eventos se guardan sin redactar (una clave llega al navegador)",
        SRC / "state" / "store.py",
        "        redactado = redact_deep(data or {})",
        "        redactado = data or {}",
        "test_f10_api.py",
    ),
    Mutation(
        # `_persistir` corre tambien al detenerse en una puerta. Marcar esa espera
        # como fallo le dice al cliente que algo salio mal justo cuando el sistema
        # esta pidiendo una decision, que es lo que debe hacer.
        "F10: una pausa humana se emite como run.failed",
        SRC / "graph" / "engine.py",
        "        if estado.status is RunStatus.COMPLETED:\n            resultado: EventKind | None = EventKind.RUN_COMPLETED\n        elif estado.status.is_terminal:\n            resultado = EventKind.RUN_FAILED\n        else:\n            resultado = None",
        "        if estado.status is RunStatus.COMPLETED:\n            resultado: EventKind | None = EventKind.RUN_COMPLETED\n        else:\n            resultado = EventKind.RUN_FAILED",
        "test_f10_api.py",
    ),
    Mutation(
        # Sin el resultado explicito, el cliente solo sabe que el flujo cerro, no
        # como termino.
        "F10: no se emite el resultado explicito (run.completed / run.failed)",
        SRC / "graph" / "engine.py",
        "        if resultado is not None:\n            self._store.append_event(",
        "        if False:\n            self._store.append_event(",
        "test_f10_api.py",
    ),
    Mutation(
        # Con dos puertas humanas, el evento general no puede llamarse como una de
        # ellas: el cliente que solo conoce la de aprobacion mostraria la pantalla
        # equivocada al parar en la de requisitos.
        "F10: la espera humana se anuncia con el evento de la puerta equivocada",
        SRC / "graph" / "engine.py",
        "                    self._store.append_event(run_id, EventKind.RUN_AWAITING_HUMAN, carga)",
        "                    self._store.append_event(run_id, EventKind.RUN_AWAITING_APPROVAL, carga)",
        "test_f10_api.py",
    ),
    Mutation(
        # Sin hitos nombrados, el progreso vuelve a ser un `run.step` con el nodo
        # como dato, y el cliente pierde el `switch` exhaustivo.
        "F10: no se emiten los hitos por nodo",
        SRC / "graph" / "engine.py",
        '                if hito is not None:\n                    self._store.append_event(run_id, hito, {"node": nodo})',
        '                if False:\n                    self._store.append_event(run_id, hito, {"node": nodo})',
        "test_f10_api.py",
    ),
    Mutation(
        # Convertir a texto un diccionario de correcciones lo vuelve irreconocible y
        # la puerta lo lee como rechazo: corregir los requisitos deja de funcionar.
        "F10: el motor convierte a texto la reanudacion con correcciones",
        SRC / "graph" / "engine.py",
        "            valor = decision.value if isinstance(decision, ApprovalDecision) else decision",
        "            valor = decision.value if isinstance(decision, ApprovalDecision) else str(decision)",
        "test_f10_api.py",
    ),
    Mutation(
        # Validar en el alta es lo que evita que una ruta rota se descubra dentro de
        # una ejecucion ya en marcha.
        "F10: el alta de proyecto no valida el repositorio",
        SRC / "api" / "app.py",
        "        ruta = validar_repositorio(peticion.repo_path)",
        "        ruta = Path(peticion.repo_path)",
        "test_f10_api.py",
    ),
    Mutation(
        # El `repo_path` del proyecto es la ruta **validada**; si una peticion puede
        # sustituirla, la validacion del alta se esquiva.
        "F10: la ruta del proyecto no manda sobre la de la peticion",
        SRC / "api" / "app.py",
        '            opciones = RunOptions.model_validate(\n                {**opciones.model_dump(), "repo_path": proyecto.repo_path}\n            )',
        "            opciones = opciones",
        "test_f10_api.py",
    ),
    Mutation(
        # Un error de dominio que sale como 500 con traza no dice que paso ni de
        # quien es la culpa.
        "F10: SandboxError se mapea a 500 en lugar de a 422",
        SRC / "api" / "app.py",
        '        return JSONResponse(status_code=422, content=_cuerpo(exc, "SANDBOX_ERROR"))',
        '        return JSONResponse(status_code=500, content=_cuerpo(exc, "SANDBOX_ERROR"))',
        "test_f10_api.py",
    ),
    Mutation(
        # Sin autenticacion, escuchar en la red publica la capacidad de ejecutar
        # codigo en la maquina.
        "F10: el servidor escucha en todas las interfaces",
        SRC / "__main__.py",
        'HOST = "127.0.0.1"',
        'HOST = "0.0.0.0"',
        "test_f10_api.py",
    ),
    Mutation(
        # La reclamacion es lo que hace atomica la comprobacion y la reserva del
        # derecho a reanudar. Sin ella, dos peticiones concurrentes pasan ambas y
        # las dos devuelven 200: la segunda pisa la decision de la primera.
        "F10: la reanudacion no reserva el derecho (dos peticiones ganan)",
        SRC / "graph" / "engine.py",
        "            with self._locks_guard:\n                self._reclamadas.add(run_id)",
        "            with self._locks_guard:\n                pass",
        "test_f10_api.py",
    ),
    Mutation(
        # Cada endpoint tiene que reclamar su propia puerta: `confirm-requirements`
        # no puede consumir `approval_gate`.
        "F10: confirm-requirements acepta la puerta de aprobacion",
        SRC / "api" / "app.py",
        'run_id, puerta_esperada="confirm_requirements_gate"',
        'run_id, puerta_esperada="approval_gate"',
        "test_f10_api.py",
    ),
    Mutation(
        # Y a la inversa, `approve` no puede saltarse la confirmacion de requisitos.
        "F10: approve acepta la puerta de requisitos",
        SRC / "api" / "app.py",
        'motor.reclamar_reanudacion(run_id, puerta_esperada="approval_gate")',
        'motor.reclamar_reanudacion(run_id, puerta_esperada="confirm_requirements_gate")',
        "test_f10_api.py",
    ),
]


def _limpiar(bruto: str) -> str:
    return "\n".join(linea for linea in bruto.splitlines() if "safe-delete" not in linea)


def _veredicto_del_informe(ruta: Path, desde_ns: int) -> tuple[bool, str] | None:
    """Lee el veredicto del informe XML que pytest acaba de escribir.

    **Por que no se usa el codigo de salida.** En este entorno, el interceptor de
    borrado de ficheros hace que pytest salga con codigo 1 y **sin resumen** aunque
    no haya fallado ninguna prueba. El codigo de salida y la salida estandar estan
    ambos corrompidos por algo ajeno a las pruebas. El informe XML lo escribe pytest
    a un fichero y no depende de ninguno de los dos.

    **Por que se compara la fecha en lugar de borrar el informe antes.** Borrar
    consume cuota del interceptor de este entorno, que bloquea tras 50 borrados por
    turno y mata el proceso. Con `desde_ns` se distingue un informe nuevo de uno
    viejo sin borrar nada.

    Leccion general: cuando la senal que usas para verificar esta corrompida por el
    entorno, no la rodees con reintentos; **cambia de senal**.
    """
    if not ruta.exists():
        return None
    try:
        if ruta.stat().st_mtime_ns < desde_ns:
            return None  # el informe es de una ejecucion anterior
        arbol = ElementTree.parse(ruta)
    except (OSError, ElementTree.ParseError):
        return None

    pruebas = fallos = errores = 0
    for suite in arbol.iter("testsuite"):
        pruebas += int(suite.get("tests", 0))
        fallos += int(suite.get("failures", 0))
        errores += int(suite.get("errors", 0))

    if pruebas == 0:
        return None  # un informe vacio no distingue "nada malo" de "nada"
    return (fallos == 0 and errores == 0), f"{pruebas} pruebas, {fallos} fallos, {errores} errores"


def _run_pytest(target: str | None = None, intentos: int = 2) -> tuple[bool | None, str]:
    """Ejecuta pytest y devuelve (verde, salida).

    El veredicto sale del **informe XML**, no del codigo de salida (ver
    `_veredicto_del_informe`). El primer miembro del resultado es `True` (verde),
    `False` (rojo) o **`None` cuando no se pudo concluir** -pytest no llego a
    emitir informe, ni siquiera tras los reintentos-.

    **Por que `None` y no `False` en un corte.** Un corte por tiempo de espera no
    es una mutacion cazada: **no se ejecuto ninguna prueba que fallara**. Devolver
    `False` aqui haria que el verificador anunciara "cazada" sin que nada hubiera
    demostrado que la prueba protege el codigo -un falso positivo, y de la peor
    clase, porque infla la confianza-. El llamador trata `None` como NO CONCLUYENTE.
    """
    informe = RAIZ / "_mutation_report.xml"
    cmd = [
        sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
        f"--junitxml={informe}",
    ]
    if target:
        cmd.append(target)

    ultima = ""
    for intento in range(1, intentos + 1):
        desde_ns = time.time_ns()
        try:
            result = subprocess.run(
                cmd, cwd=RAIZ, capture_output=True, text=True, timeout=LIMITE_PYTEST
            )
            salida = _limpiar(result.stdout + result.stderr) + f"\n[returncode={result.returncode}]"
        except subprocess.TimeoutExpired:
            # Un corte por tiempo **no es una cazada**. Se devuelve `None` para que
            # el veredicto quede como NO CONCLUYENTE: no hay prueba que haya fallado.
            return None, f"[la ejecucion supero {LIMITE_PYTEST}s sin emitir informe: NO CONCLUYENTE]"

        veredicto = _veredicto_del_informe(informe, desde_ns)
        if veredicto is not None:
            verde, resumen = veredicto
            return verde, salida + f"\n[informe: {resumen}]"

        ultima = salida + f"\n[sin informe; intento {intento}/{intentos}]"

    return False, ultima


def _run_comando(comando: tuple[str, ...], marcador: str = "RESULTADO:") -> tuple[bool | None, str]:
    """Ejecuta una herramienta de verificacion y devuelve (veredicto, salida).

    Devuelve **`None`** cuando la herramienta no llego a emitir un veredicto. Es la
    distincion mas importante de todo el fichero: si la herramienta **se cae**, su
    codigo de salida no es cero, y confundir eso con «la mutacion se ha cazado»
    produce un falso positivo.

    Paso de verdad: la verificacion del navegador moria a los 1,3 s porque el
    entorno le bloqueaba un borrado, y las tres ultimas mutaciones del frontend se
    reportaron como cazadas sin que la comprobacion llegara a ejecutarse. **Un
    verificador que se cae no ha comprobado nada**, y hay que decirlo.
    """
    try:
        result = subprocess.run(
            list(comando), cwd=RAIZ, capture_output=True, text=True, timeout=LIMITE_COMANDO
        )
    except subprocess.TimeoutExpired:
        return None, f"[la herramienta supero {LIMITE_COMANDO}s sin emitir veredicto]"

    bruto = result.stdout + result.stderr
    salida = _limpiar(bruto) + f"\n[returncode={result.returncode}]"
    if marcador not in bruto:
        return None, salida + f"\n[sin veredicto: no se encontro «{marcador}»]"
    return result.returncode == 0, salida


def _verde(m: Mutation) -> bool | None:
    if m.comando:
        return _run_comando(m.comando)[0]
    return _run_pytest(f"tests/{m.prueba_esperada}" if m.prueba_esperada else None)[0]


def main() -> int:
    restaurados = _recuperar_pendientes()
    if restaurados:
        print("AVISO: se encontro una ejecucion anterior interrumpida y se restauro:")
        for ruta in restaurados:
            print(f"  - {ruta}")
        print("Las verificaciones previas a esta restauracion no eran validas.\n")

    print("== linea base ==", flush=True)
    verde, salida = _run_pytest()
    if verde is None:
        # La linea base no llego a emitir informe. No es "roja": es que no se
        # pudo medir. Abortar es lo unico honesto -una mutacion "cazada" sobre una
        # linea base que no se pudo medir no significa nada.
        print("ABORTADO: la linea base no emitio veredicto (¿corte por tiempo?).")
        print("\n--- salida de la linea base ---")
        print(salida[-3000:])
        return 1
    if not verde:
        print("ABORTADO: la linea base ya falla. Las mutaciones no significarian nada.")
        print("\n--- salida de la linea base ---")
        print(salida[-3000:])
        return 1
    print("linea base verde.\n", flush=True)

    print("== mutaciones ==")
    # Filtro opcional por prefijo de nombre (`python tools/mutation_check.py F3`).
    # Existe porque la verificacion completa ejecuta la suite entera 43 veces y en
    # una maquina lenta supera cualquier limite de tiempo razonable. Un filtro
    # permite verificar **un subconjunto** sin fingir que se verifico el resto: el
    # recuento final dice cuantas se comprobaron, no cuantas existen.
    filtro = sys.argv[1] if len(sys.argv) > 1 else ""
    seleccion = [m for m in MUTACIONES if not filtro or filtro in m.nombre]
    if filtro:
        print(f"  (filtro: {filtro!r} -> {len(seleccion)} de {len(MUTACIONES)} mutaciones)\n")

    cazadas = 0
    no_concluyentes: list[str] = []
    for m in seleccion:
        contenido = m.fichero.read_text(encoding="utf-8")
        if contenido.count(m.original) != 1:
            print(f"  {m.nombre:48s} -> NO APLICABLE (el patron aparece "
                  f"{contenido.count(m.original)} veces)")
            continue

        m.fichero.write_text(contenido.replace(m.original, m.mutado), encoding="utf-8")
        _escribir_diario({str(m.fichero): contenido})
        inicio = time.perf_counter()
        try:
            resultado = _verde(m)
        finally:
            m.fichero.write_text(contenido, encoding="utf-8")
            _escribir_diario({})
        segundos = time.perf_counter() - inicio

        if resultado is None:
            # La herramienta no llego a emitir veredicto. **No cuenta como cazada**:
            # no se puede afirmar que la prueba proteja el codigo si la prueba no
            # llego a ejecutarse.
            no_concluyentes.append(m.nombre)
            print(f"  {m.nombre:48s} -> NO CONCLUYENTE: la herramienta no emitio veredicto"
                  f"  ({segundos:.1f}s)", flush=True)
        elif resultado:
            print(f"  {m.nombre:48s} -> NO CAZADA <<< PUNTO CIEGO  ({segundos:.1f}s)", flush=True)
        else:
            cazadas += 1
            print(f"  {m.nombre:48s} -> cazada  ({segundos:.1f}s)", flush=True)

    print(f"\n{cazadas}/{len(seleccion)} mutaciones cazadas"
          + (f" (de {len(MUTACIONES)} en total; esta ejecucion estaba filtrada)"
             if filtro else ""))
    if no_concluyentes:
        print(f"{len(no_concluyentes)} NO CONCLUYENTES (no cuentan como cazadas):")
        for nombre in no_concluyentes:
            print(f"  - {nombre}")

    print("\n== restauracion ==")
    verde, salida = _run_pytest()
    if not verde:
        print("FALLO AL RESTAURAR: el arbol quedo modificado (o no se pudo verificar).")
        print("\n--- salida tras restaurar ---")
        print(salida[-3000:])
        return 1
    print("arbol restaurado y suite en verde.")

    # Un resultado no concluyente no puede dar salida correcta: significaria que
    # hay mutaciones sin comprobar y el verificador diria que todo esta bien.
    return 0 if cazadas == len(seleccion) and not no_concluyentes else 1


if __name__ == "__main__":
    raise SystemExit(main())
