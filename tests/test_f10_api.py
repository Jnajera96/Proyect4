"""Pruebas de F10: superficie REST y flujo de eventos SSE.

**Que protege este fichero.** Cuatro cosas que la fase M3 necesita y que hasta
ahora no existian o no estaban comprobadas:

  1. **Un proyecto es una ruta validada.** El alta comprueba el repositorio, de modo
     que una ruta inexistente o que no sea git se rechaza **en el alta** y no dentro
     de una ejecucion ya en marcha. Se comprueba que un run que apunta a un proyecto
     usa *su* ruta.
  2. **Las dos puertas humanas tienen su endpoint.** Se reanudan por separado porque
     son decisiones distintas en momentos distintos, y la respuesta a la de
     requisitos puede **corregir** lo que el sistema entendio, no solo aprobarlo.
  3. **Los hitos llegan por SSE.** El nombre del nodo pasa de ser un dato dentro de
     `run.step` a ser un tipo de evento, que es lo que permite un `switch`
     exhaustivo en el cliente. Y la espera humana distingue **que** puerta espera.
  4. **Los errores de dominio no salen como 500 con traza.** Se mapean a 4xx
     estructurados, con `error_class` para que el cliente ramifique sin leer texto.

Se comprueba ademas que **todo evento pasa por el redactor**: el flujo SSE es una
salida al navegador y una clave en claro ahi es una fuga, aunque el logging este
filtrado.

El servidor se ejercita con `TestClient`; no se abre ningun puerto de red.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_swe.api import crear_app
from ai_swe.api.app import registrar_manejadores_de_error
from ai_swe.contracts import EventKind
from ai_swe.graph import nodes
from ai_swe.graph.engine import NothingToResume, RunNotFound
from ai_swe.models import BudgetExceededError, ModelGateway
from ai_swe.sandbox import SandboxError
from ai_swe.state import RunStore

# --------------------------------------------------------------- utilidades

TEST_QUE_PASA = "def test_pasa():\n    assert 1 == 1\n"
CONTENIDO_NUEVO = "def f():\n    return 42\n"


def _git(repo: Path, *args: str) -> str:
    resultado = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, shell=False
    )
    assert resultado.returncode == 0, f"git {' '.join(args)} fallo: {resultado.stderr}"
    return resultado.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repositorio git real, con un `tests/` que pasa."""
    raiz = tmp_path / "repo"
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
def cliente(tmp_path: Path):
    store = RunStore(tmp_path / "estado.db")
    app = crear_app(store=store)
    try:
        with TestClient(app) as c:
            yield c
    finally:
        store.close()


@pytest.fixture(autouse=True)
def _inyeccion_limpia(tmp_path: Path):
    """Deja el estado de modulo que comparten API y grafo como estaba.

    El motor de la API usa el **mismo** modulo `nodes` que las pruebas, asi que
    inyectar aqui un modelo falso o una raiz de worktrees afecta al servidor que se
    esta ejercitando. Es justo lo que se quiere para una prueba de punta a punta,
    pero hay que deshacerlo o contaminaria a las demas.

    **Se limpia antes y despues.** Solo al final no basta: si el proceso se
    interrumpe a mitad, o si alguien anade una prueba que depende del estado por
    defecto, la suciedad se arrastra. Limpiar al entrar hace que cada prueba
    **empiece** desde cero, que es la propiedad que se quiere, en lugar de confiar
    en que la anterior se porto bien.
    """
    _limpiar_inyecciones()
    yield
    _limpiar_inyecciones()


def _limpiar_inyecciones() -> None:
    """Devuelve el modulo `nodes` a su estado por defecto.

    Cubre el gateway -y con el, cualquier `FakeModelAdapter` y su cola de
    respuestas-, el modelo del Reviewer y las dos inyecciones del sandbox. Se llama
    en el `setup` y en el `teardown` de cada prueba.
    """
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    nodes.usar_modelo_reviewer(None)
    nodes.usar_workspace_root(None)
    nodes.usar_targets_permitidos(None)


def _esperar_estado(cliente: TestClient, run_id: str, objetivo: str, timeout: float = 25.0) -> dict:
    limite = time.perf_counter() + timeout
    cuerpo = cliente.get(f"/runs/{run_id}").json()
    while time.perf_counter() < limite:
        cuerpo = cliente.get(f"/runs/{run_id}").json()
        if cuerpo["status"] == objetivo:
            return cuerpo
        time.sleep(0.02)
    clases = [e["error_class"] for e in cuerpo.get("errors", [])]
    raise AssertionError(
        f"{run_id} no llego a '{objetivo}': se quedo en '{cuerpo['status']}' (errores: {clases})"
    )


def _esperar_cierre(cliente: TestClient, run_id: str, timeout: float = 25.0) -> None:
    """Espera a que el registro de eventos termine en `run.done`.

    **Hace falta esperar al evento, no al estado.** `GET /runs/{id}` lee el
    **checkpoint**, que se actualiza antes de que `_persistir` escriba los eventos.
    Una prueba que lea el registro en cuanto ve el estado terminal puede pillar la
    historia a medias y afirmar sobre un final que todavia no se ha escrito; es una
    carrera real, y hacia fallar estas afirmaciones de forma intermitente.

    El cierre de verdad es el evento, que es lo que el propio flujo SSE usa como
    senal.
    """
    limite = time.perf_counter() + timeout
    while time.perf_counter() < limite:
        eventos = cliente.app.state.store.events(run_id)
        if eventos and eventos[-1].kind is EventKind.RUN_DONE:
            return
        time.sleep(0.02)
    raise AssertionError(f"{run_id}: el registro de eventos no cerro con run.done")


def _leer_eventos(
    cliente: TestClient, run_id: str, *, after: int = 0
) -> list[tuple[str, dict]]:
    """Lee **un tramo** del flujo SSE: desde `after` hasta que el servidor cierra.

    Lo que viaja en `data:` es el `RunEvent` **entero** (`seq`, `at`, `kind`, `data`),
    no solo su carga: el sobre es lo que permite al cliente ordenar y deduplicar por
    `seq`. Aqui se devuelve ya la carga interna, que es sobre lo que afirman las
    pruebas.

    **El servidor cierra en cada `run.done`**, y una ejecucion de M2 tiene varios
    (uno por pausa humana). Este ayudante lee un tramo, que es lo que hace un
    navegador entre reconexiones. Para la historia completa esta
    `_todos_los_eventos`, y la razon esta explicada alli.
    """
    salida: list[tuple[str, dict]] = []
    nombre: str | None = None
    with cliente.stream("GET", f"/runs/{run_id}/events", params={"after": after}) as flujo:
        for linea in flujo.iter_lines():
            if linea.startswith("event:"):
                nombre = linea.split(":", 1)[1].strip()
            elif linea.startswith("data:") and nombre is not None:
                sobre = json.loads(linea.split(":", 1)[1].strip())
                salida.append((nombre, sobre["data"]))
    return salida


def _todos_los_eventos(cliente: TestClient, run_id: str) -> list[tuple[str, dict]]:
    """Historia completa y ordenada de eventos, leida del registro.

    **Por que no por SSE.** Encadenar tramos con `after` se cuelga: entre pausas la
    ejecucion **no es terminal**, y el servidor no cierra el flujo hasta agotar su
    `timeout_s` (300 s), porque su red de seguridad solo cierra cuando el indice ya
    esta en terminal. Y una sola lectura tampoco vale: el flujo cierra en el primer
    `run.done` **del lote**, de modo que si el cliente se conecta mientras la
    ejecucion avanza se pierde lo posterior -una carrera real, y la causa de que
    estas afirmaciones fallaran de forma intermitente-.

    Lo que el flujo SSE sirve es **exactamente** este registro, en este orden; los
    tramos se comprueban por SSE en las demas pruebas de esta seccion. Aqui se lee
    la fuente para poder afirmar sobre el final sin depender de cuando llego el
    cliente, y se espera al `run.done` de cierre antes de leer.
    """
    _esperar_cierre(cliente, run_id)
    eventos = cliente.app.state.store.events(run_id)
    return [(e.kind.value, e.data) for e in eventos]


def _con_modelo_falso() -> None:
    """Inyecta un modelo que propone un cambio valido y un Reviewer que aprueba."""
    adapter = _AdapterPorContrato()
    nodes.usar_gateway(ModelGateway([adapter]))


class _AdapterPorContrato:
    """Devuelve una salida distinta segun el contrato pedido.

    El gateway deja el JSON Schema del contrato en `request.json_schema`, cuyo
    `title` es el nombre del modelo Pydantic. Es el unico discriminador fiable:
    `interpret` y `plan` comparten `agent_role`.
    """

    def __init__(self) -> None:
        self.calls: list = []

    @property
    def name(self) -> str:
        return "f10"

    def generate(self, request):
        from ai_swe.models import ModelUsage, ProviderResponse

        titulo = (request.json_schema or {}).get("title", "")
        datos = {
            "TaskInterpretation": {
                "intent": "modify",
                "scope": {"repo_path": ".", "allowed_paths": [], "protected_paths": []},
                "constraints": [],
                "confidence": 0.9,
                "rationale": "el usuario pide un cambio concreto",
            },
            "RunPlan": {
                "subtasks": [
                    {
                        "id": "investigar",
                        "description": "localizar el valor de retorno",
                        "agent": "researcher",
                        "allowed_tools": ["list_files", "read_file"],
                        "done_criteria": "se conoce src/app.py",
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
            },
            "CodeProposal": {
                "files": [
                    {
                        "path": "src/app.py",
                        "operation": "modify",
                        "new_content": CONTENIDO_NUEVO,
                        "rationale": "ajusta el valor de retorno",
                    }
                ],
                "rationale": "cambio minimo",
            },
            "ReviewVerdict": {
                "decision": "accept",
                "findings": [],
                "required_fixes": [],
                "summary": "el cambio cumple la peticion",
            },
        }.get(titulo)
        self.calls.append(request)
        return ProviderResponse(
            content=json.dumps(datos) if datos is not None else "{}",
            model=request.model or "f10",
            finish_reason="stop",
            usage=ModelUsage(input_tokens=10, output_tokens=5),
            provider_request_id="f10-1",
        )


# ============================================================== proyectos


def test_crear_proyecto_valida_el_repositorio(cliente, repo: Path) -> None:
    """El alta comprueba la ruta y guarda la **resuelta**."""
    respuesta = cliente.post("/projects", json={"name": "Mi Repo", "repo_path": str(repo)})

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["name"] == "Mi Repo"
    assert cuerpo["project_id"].startswith("mi-repo-")
    assert Path(cuerpo["repo_path"]) == repo.resolve()
    assert cuerpo["created_at"]


def test_un_repositorio_que_no_es_git_se_rechaza_en_el_alta(cliente, tmp_path: Path) -> None:
    """**En el alta, no dentro de una ejecucion.** Es la razon de que el proyecto exista."""
    carpeta = tmp_path / "no-es-repo"
    carpeta.mkdir()

    respuesta = cliente.post("/projects", json={"name": "Roto", "repo_path": str(carpeta)})

    assert respuesta.status_code == 422, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["error_class"] == "SANDBOX_ERROR"
    assert "no es un repositorio git" in cuerpo["detail"]
    # Y no quedo registrado nada a medias.
    assert cliente.get("/projects").json() == []


def test_obtener_y_listar_proyectos(cliente, repo: Path) -> None:
    creado = cliente.post("/projects", json={"name": "uno", "repo_path": str(repo)}).json()

    assert cliente.get(f"/projects/{creado['project_id']}").json() == creado
    assert [p["project_id"] for p in cliente.get("/projects").json()] == [creado["project_id"]]


def test_un_proyecto_inexistente_da_404(cliente) -> None:
    respuesta = cliente.get("/projects/no-existe")

    assert respuesta.status_code == 404
    assert "no existe el proyecto" in respuesta.json()["detail"]


def test_eliminar_proyecto_sin_borrar_archivos(cliente, repo: Path) -> None:
    creado = cliente.post("/projects", json={"name": "eliminar", "repo_path": str(repo)}).json()
    pid = creado["project_id"]

    # 1. Dar de baja devuelve 204
    resp = cliente.delete(f"/projects/{pid}")
    assert resp.status_code == 204

    # 2. Ya no figura en la lista ni en get
    assert cliente.get(f"/projects/{pid}").status_code == 404
    assert all(p["project_id"] != pid for p in cliente.get("/projects").json())

    # 3. Eliminar de nuevo devuelve 404
    assert cliente.delete(f"/projects/{pid}").status_code == 404

    # 4. El directorio local y el repositorio git siguen existiendo intactos
    assert repo.exists()
    assert (repo / ".git").exists()


def test_un_run_puede_apuntar_a_un_proyecto(cliente, repo: Path) -> None:
    """El `repo_path` del proyecto manda: es la ruta validada en el alta."""
    proyecto = cliente.post("/projects", json={"name": "uno", "repo_path": str(repo)}).json()

    creada = cliente.post(
        "/runs",
        json={
            "instruction": "¿Dónde se define f?",
            "project_id": proyecto["project_id"],
            "options": {"repo_path": "/ruta/que/no/existe"},
        },
    )

    assert creada.status_code == 202, creada.text
    assert creada.json()["options"]["repo_path"] == proyecto["repo_path"]


def test_un_run_con_proyecto_inexistente_da_404(cliente) -> None:
    respuesta = cliente.post(
        "/runs", json={"instruction": "¿Dónde se define f?", "project_id": "no-existe"}
    )

    assert respuesta.status_code == 404
    assert "no existe el proyecto" in respuesta.json()["detail"]


# ========================================================= puertas humanas


def test_la_puerta_de_requisitos_se_reanuda_por_su_endpoint(cliente, repo: Path) -> None:
    creada = cliente.post(
        "/runs", json={"instruction": "corrige f", "options": {"repo_path": str(repo)}}
    ).json()
    run_id = creada["run_id"]

    pausado = _esperar_estado(cliente, run_id, "awaiting_human_requirements_confirmation")
    assert pausado["interpretation"]["confirmed_by_user"] is False

    respuesta = cliente.post(f"/runs/{run_id}/confirm-requirements", json={"decision": "approved"})

    assert respuesta.status_code == 200, respuesta.text
    final = _esperar_estado(cliente, run_id, "needs_human")
    assert final["interpretation"]["confirmed_by_user"] is True


def test_la_puerta_de_requisitos_acepta_correcciones(cliente, repo: Path) -> None:
    """El humano corrige lo que el sistema entendio, no solo lo aprueba."""
    creada = cliente.post(
        "/runs", json={"instruction": "corrige f", "options": {"repo_path": str(repo)}}
    ).json()
    run_id = creada["run_id"]
    _esperar_estado(cliente, run_id, "awaiting_human_requirements_confirmation")

    cliente.post(
        f"/runs/{run_id}/confirm-requirements",
        json={
            "decision": "modified",
            "intent": "inspect",
            "constraints": ["no toques la base de datos"],
        },
    )

    final = _esperar_estado(cliente, run_id, "completed")
    assert final["interpretation"]["intent"] == "inspect"
    assert final["interpretation"]["constraints"] == ["no toques la base de datos"]
    assert final["interpretation"]["confirmed_by_user"] is True


def test_confirmar_requisitos_en_una_ejecucion_que_no_espera_da_409(cliente, repo: Path) -> None:
    creada = cliente.post(
        "/runs", json={"instruction": "corrige f", "options": {"repo_path": str(repo)}}
    ).json()
    run_id = creada["run_id"]
    _esperar_estado(cliente, run_id, "awaiting_human_requirements_confirmation")
    cliente.post(f"/runs/{run_id}/confirm-requirements", json={"decision": "approved"})
    _esperar_estado(cliente, run_id, "needs_human")

    respuesta = cliente.post(f"/runs/{run_id}/confirm-requirements", json={"decision": "approved"})

    assert respuesta.status_code == 409
    assert respuesta.json()["error_class"] == "NOTHING_TO_RESUME"


def test_las_puertas_humanas_sobre_una_ejecucion_inexistente_dan_404(cliente) -> None:
    for ruta in ("confirm-requirements", "approve"):
        respuesta = cliente.post(f"/runs/run-fantasma/{ruta}", json={"decision": "approved"})
        assert respuesta.status_code == 404, ruta
        assert respuesta.json()["error_class"] == "RUN_NOT_FOUND"


def test_dos_confirmaciones_concurrentes_solo_reanudan_una_vez(cliente, repo: Path) -> None:
    """Una sola reanudacion por puerta, aunque llegue el doble de peticiones.

    Era un fallo real: la ruta comprobaba `pendiente_de_aprobacion` y luego
    encolaba la reanudacion, y la ejecucion corre en un trabajador. Dos peticiones
    concurrentes -dos pestanas, un doble clic, un reintento del navegador- pasaban
    ambas la comprobacion antes de que ninguna hubiera reanudado, y **las dos
    devolvian 200**; la segunda pisaba la decision de la primera. El contrato dice
    que una ejecucion que ya no espera da 409, y no lo hacia.

    Se replica sin depender de una carrera de milisegundos: se lanzan las dos
    peticiones desde dos hilos con una barrera. El arreglo (`reclamar_reanudacion`)
    reserva el derecho de forma atomica con la comprobacion.
    """
    import threading

    creada = cliente.post(
        "/runs", json={"instruction": "corrige f", "options": {"repo_path": str(repo)}}
    ).json()
    run_id = creada["run_id"]
    _esperar_estado(cliente, run_id, "awaiting_human_requirements_confirmation")

    codigos: list[int] = []
    barrera = threading.Barrier(2)

    def disparar() -> None:
        barrera.wait()
        respuesta = cliente.post(
            f"/runs/{run_id}/confirm-requirements", json={"decision": "approved"}
        )
        codigos.append(respuesta.status_code)

    hilos = [threading.Thread(target=disparar) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert sorted(codigos) == [200, 409], (
        f"las dos reanudaciones se aceptaron: {sorted(codigos)} "
        "(una ejecucion se reanudo dos veces)"
    )


# --------------------------------------- el cuerpo vacio no es una decision humana


def test_un_cuerpo_vacio_no_es_una_decision_humana(cliente, repo: Path) -> None:
    """`{}` no puede significar "adelante".

    Aprobar la puerta de aprobacion **escribe en el repositorio del usuario**.
    Mientras `decision` tuvo un valor por defecto afirmativo, un cuerpo mal formado
    -un `{}`, un campo con el nombre mal escrito, un cliente que olvido el campo- se
    convertia en una promocion silenciosa. La decision la toma una persona: el
    sistema no puede suponerla. Se comprueba en las **dos** puertas, porque las dos
    toman una decision humana.

    Que la respuesta sea **422 y no 409** es la prueba de que la validacion ocurre
    *antes* del manejador: la ejecucion espera en la puerta de requisitos, asi que
    si el manejador de `/approve` llegara a ejecutarse reclamaria la reanudacion de
    la puerta equivocada y devolveria 409.
    """
    creada = cliente.post(
        "/runs", json={"instruction": "corrige f", "options": {"repo_path": str(repo)}}
    ).json()
    run_id = creada["run_id"]
    _esperar_estado(cliente, run_id, "awaiting_human_requirements_confirmation")

    for ruta in ("confirm-requirements", "approve"):
        respuesta = cliente.post(f"/runs/{run_id}/{ruta}", json={})
        assert respuesta.status_code == 422, (
            f"{ruta} acepto un cuerpo vacio ({respuesta.status_code}): "
            "un cliente mal formado decidiria por el humano"
        )

    # Y la ejecucion sigue exactamente donde estaba: no se confirmo ni se aprobo.
    assert cliente.get(f"/runs/{run_id}").json()["status"] == (
        "awaiting_human_requirements_confirmation"
    )


def test_una_decision_explicita_sigue_funcionando(cliente, repo: Path) -> None:
    """El contrato cambia en lo que **falta**, no en lo que se manda bien."""
    creada = cliente.post(
        "/runs", json={"instruction": "corrige f", "options": {"repo_path": str(repo)}}
    ).json()
    run_id = creada["run_id"]
    _esperar_estado(cliente, run_id, "awaiting_human_requirements_confirmation")

    respuesta = cliente.post(
        f"/runs/{run_id}/confirm-requirements", json={"decision": "approved"}
    )

    assert respuesta.status_code == 200


# --------------------------- la lista blanca de repositorios se aplica en la API


def test_un_repositorio_fuera_de_la_lista_blanca_es_403(
    monkeypatch, tmp_path: Path, repo: Path
) -> None:
    """`AI_SWE_AUTHORIZED_REPOS` no es decorativo: la API lo hace cumplir.

    El ajuste se documento como un limite y ningun codigo lo leia. Ahora se aplica
    en **dos** puntos, y se comprueban los dos: el alta del proyecto y el arranque de
    una ejecucion. El segundo importa porque una ejecucion tambien puede declarar
    `repo_path` directamente, sin proyecto; si el control viviera solo en el alta,
    lanzar contra un repositorio fuera de alcance seguiria funcionando y el limite se
    creeria aplicado.

    La aplicacion se monta **despues** de fijar la variable: la configuracion se lee
    al construirla, no en cada peticion.
    """
    permitido = tmp_path / "permitido"
    permitido.mkdir()
    monkeypatch.setenv("AI_SWE_AUTHORIZED_REPOS", json.dumps([str(permitido)]))

    store = RunStore(tmp_path / "estado.db")
    app = crear_app(store=store)
    try:
        with TestClient(app) as cliente:
            alta = cliente.post(
                "/projects", json={"name": "fuera", "repo_path": str(repo)}
            )
            assert alta.status_code == 403, alta.text

            directa = cliente.post(
                "/runs",
                json={"instruction": "corrige f", "options": {"repo_path": str(repo)}},
            )
            assert directa.status_code == 403, directa.text
    finally:
        store.close()


def test_un_repositorio_dentro_de_la_lista_blanca_se_acepta(
    monkeypatch, tmp_path: Path, repo: Path
) -> None:
    """Control positivo: sin el, un 403 permanente pasaria por confinamiento.

    Se autoriza la **raiz** que contiene al repositorio y se comprueba que el alta
    pasa. Una lista que rechaza todo no protege nada: solo rompe el sistema.
    """
    monkeypatch.setenv("AI_SWE_AUTHORIZED_REPOS", json.dumps([str(tmp_path)]))

    store = RunStore(tmp_path / "estado.db")
    app = crear_app(store=store)
    try:
        with TestClient(app) as cliente:
            alta = cliente.post(
                "/projects", json={"name": "dentro", "repo_path": str(repo)}
            )
            assert alta.status_code == 201, alta.text
    finally:
        store.close()


# ==================================================================== SSE


def test_los_hitos_por_nodo_llegan_por_sse(cliente, repo: Path, tmp_path: Path) -> None:
    """La cadena completa, a traves de HTTP, con hitos nombrados por nodo.

    Es la prueba central de F10: el modelo, el sandbox y las pruebas son reales, y
    el progreso se lee por el flujo de eventos como lo haria un navegador.
    """
    nodes.usar_workspace_root(tmp_path / "workspaces")
    nodes.usar_targets_permitidos(("pytest.unit",))
    _con_modelo_falso()

    proyecto = cliente.post("/projects", json={"name": "demo", "repo_path": str(repo)}).json()
    creada = cliente.post(
        "/runs",
        json={"instruction": "corrige f", "project_id": proyecto["project_id"]},
    ).json()
    run_id = creada["run_id"]

    _esperar_estado(cliente, run_id, "awaiting_human_requirements_confirmation")
    cliente.post(f"/runs/{run_id}/confirm-requirements", json={"decision": "approved"})
    _esperar_estado(cliente, run_id, "awaiting_approval")

    # El endpoint de confirmacion de requisitos no puede consumir la puerta de
    # aprobacion. La ruta debe identificar la puerta exacta, no solo cualquier
    # interrupt pendiente.
    respuesta_equivocada = cliente.post(
        f"/runs/{run_id}/confirm-requirements", json={"decision": "approved"}
    )
    assert respuesta_equivocada.status_code == 409
    assert respuesta_equivocada.json()["error_class"] == "NOTHING_TO_RESUME"

    cliente.post(f"/runs/{run_id}/approve", json={"decision": "approved"})
    _esperar_estado(cliente, run_id, "completed")

    # El hito se emite: historia completa del registro.
    tipos = [nombre for nombre, _ in _todos_los_eventos(cliente, run_id)]
    for esperado in (
        "run.started",
        "requirements.completed",
        "plan.completed",
        "coder.completed",
        "tests.completed",
        "run.awaiting_human",
        "run.completed",
    ):
        assert esperado in tipos, f"falta el evento '{esperado}': {tipos}"

    # Y **llega por SSE**: el primer tramo del flujo ya trae los hitos del nodo.
    tramo = [nombre for nombre, _ in _leer_eventos(cliente, run_id)]
    for esperado in ("run.created", "run.started", "requirements.completed", "run.awaiting_human"):
        assert esperado in tramo, f"el flujo SSE no entrego '{esperado}': {tramo}"

    # El hito de pruebas lleva la evidencia real, no un latido vacio.
    pruebas = [d for n, d in _todos_los_eventos(cliente, run_id) if n == "tests.completed"]
    assert pruebas and pruebas[0]["node"] == "run_tests"


def test_la_espera_humana_distingue_que_puerta_espera(cliente, repo: Path) -> None:
    """Con dos puertas, la espera se anuncia una vez y **cual** se lee del estado.

    Hasta F10 habia un evento aparte para la puerta de aprobacion
    (`run.awaiting_approval`). F11 lo retiro (AUD-11): `run.awaiting_human` es el
    unico evento de espera, y **que** puerta espera se lee del estado
    (`RunStatus`), que es la vista autoritativa. Esta prueba fija esa decision: la
    espera se anuncia con el evento general y el estado dice en cual esta.
    """
    creada = cliente.post(
        "/runs", json={"instruction": "corrige f", "options": {"repo_path": str(repo)}}
    ).json()
    run_id = creada["run_id"]
    _esperar_estado(cliente, run_id, "awaiting_human_requirements_confirmation")

    # El endpoint de aprobacion no puede saltarse la confirmacion de requisitos.
    respuesta_equivocada = cliente.post(
        f"/runs/{run_id}/approve", json={"decision": "approved"}
    )
    assert respuesta_equivocada.status_code == 409
    assert respuesta_equivocada.json()["error_class"] == "NOTHING_TO_RESUME"

    tipos = [nombre for nombre, _ in _leer_eventos(cliente, run_id)]

    assert "run.awaiting_human" in tipos
    # El evento de la puerta concreta ya no existe: el estado es quien distingue.
    assert "run.awaiting_approval" not in tipos
    assert "run.step" not in tipos

    # El estado dice **en cual** de las dos puertas esta.
    estado = cliente.get(f"/runs/{run_id}").json()
    assert estado["status"] == "awaiting_human_requirements_confirmation"


def test_el_resultado_se_emite_antes_del_cierre_del_flujo(cliente, repo: Path) -> None:
    """El resultado va **inmediatamente antes** del `run.done` que cierra el tramo.

    El orden importa: lo que se escriba despues del evento de cierre puede caer en
    el lote siguiente y perderse, porque el flujo se cierra al verlo.

    Se mira el **ultimo** `run.done`, no el primero: una ejecucion con pausa humana
    tiene uno por tramo, y el primero cierra el tramo de la puerta de requisitos.
    """
    creada = cliente.post(
        "/runs", json={"instruction": "¿Dónde se define f?", "options": {"repo_path": str(repo)}}
    ).json()
    run_id = creada["run_id"]
    _esperar_estado(cliente, run_id, "awaiting_human_requirements_confirmation")
    cliente.post(f"/runs/{run_id}/confirm-requirements", json={"decision": "approved"})
    _esperar_estado(cliente, run_id, "completed")

    tipos = [nombre for nombre, _ in _todos_los_eventos(cliente, run_id)]

    assert tipos[-1] == "run.done", f"el flujo no cerro con run.done: {tipos}"
    assert tipos[-2] == "run.completed", (
        f"el resultado no quedo justo antes del cierre: {tipos[-3:]}"
    )
    assert "run.failed" not in tipos


def test_una_pausa_humana_no_se_marca_como_fallo(cliente, repo: Path) -> None:
    """Una espera **no** es un resultado: ni `run.completed` ni `run.failed`.

    Es el fallo que tenia la primera version de F10: `_persistir` se ejecuta tambien
    al detenerse en una puerta, y marcar eso como `run.failed` le decia al cliente
    que algo habia salido mal justo cuando el sistema pedia una decision.
    """
    creada = cliente.post(
        "/runs", json={"instruction": "corrige f", "options": {"repo_path": str(repo)}}
    ).json()
    run_id = creada["run_id"]
    _esperar_estado(cliente, run_id, "awaiting_human_requirements_confirmation")

    tipos = [nombre for nombre, _ in _leer_eventos(cliente, run_id)]

    assert "run.awaiting_human" in tipos
    assert "run.failed" not in tipos, "una pausa humana se marco como fallo"
    assert "run.completed" not in tipos, "una pausa humana se marco como exito"


def test_una_ejecucion_escalada_emite_run_failed(cliente, repo: Path) -> None:
    """Un final no feliz tambien se declara con su propio tipo."""
    # Un run de modificacion sin modelo: el Coder no produce cambio y se escala.
    creada = cliente.post(
        "/runs", json={"instruction": "corrige f", "options": {"repo_path": str(repo)}}
    ).json()
    run_id = creada["run_id"]
    _esperar_estado(cliente, run_id, "awaiting_human_requirements_confirmation")
    cliente.post(f"/runs/{run_id}/confirm-requirements", json={"decision": "approved"})
    _esperar_estado(cliente, run_id, "needs_human")

    eventos = _todos_los_eventos(cliente, run_id)
    tipos = [nombre for nombre, _ in eventos]

    assert "run.failed" in tipos
    assert "run.completed" not in tipos
    fallo = [d for n, d in eventos if n == "run.failed"][0]
    assert fallo["status"] == "needs_human"


def test_los_eventos_se_redactan_antes_de_salir(cliente, repo: Path) -> None:
    """Una clave en la instruccion no puede llegar al navegador en claro.

    El flujo SSE es una salida al exterior: el filtro de logging no la cubre,
    porque esto no pasa por el logging. La redaccion tiene que estar en el punto
    por el que pasan **todos** los eventos.
    """
    secreto = "sk-live-abcdefghijklmnopqrstuvwxyz012345"
    creada = cliente.post(
        "/runs",
        json={
            "instruction": f"usa la clave {secreto} y corrige f",
            "options": {"repo_path": str(repo)},
        },
    ).json()
    run_id = creada["run_id"]

    with cliente.stream("GET", f"/runs/{run_id}/events") as flujo:
        crudo = "".join(flujo.iter_lines())

    assert secreto not in crudo, "la clave viajo en claro por el flujo de eventos"
    assert "[REDACTED]" in crudo


def test_los_eventos_se_pueden_reanudar_desde_un_punto(cliente, repo: Path) -> None:
    """El cliente que se reconecta recibe **solo** lo que le falta.

    Se reanuda por `after`, que es la forma explicita de decir "desde este `seq`"; el
    endpoint acepta tambien `Last-Event-ID` para el caso del navegador, que lo manda
    solo.
    """
    creada = cliente.post(
        "/runs", json={"instruction": "¿Dónde se define f?", "options": {"repo_path": str(repo)}}
    ).json()
    run_id = creada["run_id"]
    _esperar_estado(cliente, run_id, "awaiting_human_requirements_confirmation")

    todos = _leer_eventos(cliente, run_id)
    assert len(todos) >= 3, f"el tramo fue demasiado corto para probar nada: {todos}"
    corte = 2
    restantes = _leer_eventos(cliente, run_id, after=corte)

    assert restantes == todos[corte:], "la reanudacion no devolvio exactamente lo que faltaba"


# ======================================================= mapeo de errores


def test_los_errores_de_dominio_se_mapean_a_http_estructurado() -> None:
    """Cada excepcion tipada tiene su codigo, y el cuerpo lleva `error_class`.

    Se monta un app minimo con **el mismo registro de manejadores** que usa la API
    real: lo que se comprueba es el mapeo, que es codigo de produccion, no la ruta
    de prueba que lo dispara.
    """
    app = FastAPI()
    registrar_manejadores_de_error(app)

    @app.get("/sandbox")
    def _sandbox() -> None:
        raise SandboxError("crear", "'/x' no es un repositorio git")

    @app.get("/presupuesto")
    def _presupuesto() -> None:
        raise BudgetExceededError("presupuesto agotado")

    @app.get("/nada")
    def _nada() -> None:
        raise NothingToResume("la ejecucion no esta esperando aprobacion")

    @app.get("/fuera")
    def _fuera() -> None:
        raise RunNotFound("run-que-no-existe")

    esperado = {
        "/sandbox": (422, "SANDBOX_ERROR"),
        "/presupuesto": (429, "BUDGET_EXCEEDED"),
        "/nada": (409, "NOTHING_TO_RESUME"),
        "/fuera": (404, "RUN_NOT_FOUND"),
    }
    with TestClient(app, raise_server_exceptions=False) as c:
        for ruta, (codigo, clase) in esperado.items():
            respuesta = c.get(ruta)
            assert respuesta.status_code == codigo, f"{ruta}: {respuesta.text}"
            assert respuesta.json()["error_class"] == clase


def test_un_error_de_programacion_no_se_disfraza_de_error_de_dominio() -> None:
    """Un `TypeError` no esta mapeado: sigue siendo un 500, como debe.

    Es la comprobacion de que el mapeo es **por tipo** y no un `except Exception`
    que convertiria cualquier defecto del servidor en un 4xx que parece culpa del
    cliente.
    """
    app = FastAPI()
    registrar_manejadores_de_error(app)

    @app.get("/defecto")
    def _defecto() -> None:
        raise TypeError("un defecto de programacion")

    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.get("/defecto").status_code == 500


# ======================================================== binding local


def test_el_servidor_solo_escucha_en_bucle_local() -> None:
    """`AUD-06`: sin autenticacion, escuchar en la red publicaria ejecutar codigo."""
    from ai_swe import __main__ as arranque

    assert arranque.HOST == "127.0.0.1"
    assert arranque.HOST not in {"0.0.0.0", "::", ""}


def test_el_puerto_configurable_se_valida(monkeypatch) -> None:
    """Un puerto invalido no se ignora en silencio: se dice y se para."""
    from ai_swe import __main__ as arranque

    monkeypatch.delenv("AI_SWE_PORT", raising=False)
    assert arranque.puerto() == arranque.PUERTO_POR_DEFECTO

    monkeypatch.setenv("AI_SWE_PORT", "9123")
    assert arranque.puerto() == 9123

    for invalido in ("no-es-un-numero", "0", "70000"):
        monkeypatch.setenv("AI_SWE_PORT", invalido)
        with pytest.raises(SystemExit):
            arranque.puerto()


# ===================================================== contrato de eventos


def test_los_tipos_de_evento_nuevos_estan_declarados() -> None:
    """El contrato exportado al frontend incluye los hitos de F10.

    Y desde F11 (AUD-11) **ya no incluye los nombres heredados**: se retiraron al
    reescribirse el frontend, que era la condicion para poder quitarlos. Aqui se
    comprueba en los dos sentidos: los canonicos estan y los heredados **no**.
    """
    from ai_swe.contracts import EVENTO_POR_NODO

    valores = {k.value for k in EventKind}
    for esperado in (
        "requirements.completed",
        "plan.completed",
        "coder.completed",
        "tests.completed",
        "run.awaiting_human",
        "run.completed",
        "run.failed",
    ):
        assert esperado in valores, f"falta el tipo de evento '{esperado}'"

    # Los heredados se retiraron en F11. Si alguno volviera, seria una regresion de
    # AUD-11: el conjunto cerrado dejaria de serlo.
    for retirado in ("run.step", "run.status", "run.report", "run.error",
                     "run.awaiting_approval"):
        assert retirado not in valores, f"volvio un evento heredado retirado: '{retirado}'"

    # Estos se conservan: marcas de arranque y la senal de cierre del flujo.
    for conservado in ("run.created", "run.started", "run.done"):
        assert conservado in valores, f"se retiro un evento que sigue en uso: '{conservado}'"

    assert set(EVENTO_POR_NODO) == {"interpret", "plan", "coder", "run_tests"}
