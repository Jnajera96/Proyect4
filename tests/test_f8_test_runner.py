"""Pruebas de F8: el ejecutor real de pruebas y el cableado del sandbox al grafo.

**Que protege este fichero.** Tres cosas sin las cuales F8 no aporta nada:

  1. **La evidencia es real.** Las pruebas se ejecutan de verdad en un subproceso,
     dentro del sandbox, y el `TestRun` lleva el codigo de salida real, la salida
     capturada y **el comando exacto**. No se sustituye el ejecutor por un doble:
     un doble probaria que el doble devuelve lo que le pedimos.
  2. **No hay comandos libres.** El identificador de la lista permitida se traduce
     con una tabla **cerrada** y se pasa a `subprocess` como **lista** con
     `shell=False`. Un objetivo que no este permitido se rechaza **antes** de
     ejecutar nada.
  3. **El grafo no se cae.** Un fallo del sandbox o del ejecutor se convierte en un
     error tipado en `RunState` y la ejecucion termina en `needs_human`, nunca en
     una traza de LangGraph.

**Por que repositorios git de verdad.** El sandbox es un `git worktree`. Un mock no
prueba que el aislamiento funciona: prueba que el mock responde. Aqui se crea un
repositorio real con un `tests/` real y se ejecuta pytest dentro.

Ninguna prueba toca la red, las credenciales ni el repositorio del proyecto.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_swe.contracts import (
    Budget,
    CodeChange,
    Evidence,
    FileChange,
    FileOperation,
    Instruction,
    InstructionSource,
    Intent,
    Outputs,
    RunOptions,
    RunPlan,
    RunState,
    RunStatus,
    Scope,
    Subtask,
    TaskInterpretation,
    TestRun,
)
from ai_swe.graph import nodes
from ai_swe.models import FakeModelAdapter, ModelGateway
from ai_swe.sandbox import Sandbox, crear, destruir
from ai_swe.tools.runner import (
    EXIT_TIMEOUT,
    TARGET_COMMANDS,
    RunnerError,
    TargetNoPermitido,
    comando_de,
    ejecutar,
    targets_disponibles,
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


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _cambio(*archivos: tuple[str, str], rationale: str = "prueba") -> CodeChange:
    """Un `CodeChange` como el que produce F6, con contenido en el diff."""
    files: list[FileChange] = []
    trozos: list[str] = []
    for ruta, contenido in archivos:
        files.append(
            FileChange(
                path=ruta,
                added=contenido.count("\n") or 1,
                removed=0,
                sha256=_sha(contenido),
            )
        )
        cuerpo = "\n".join(f"+{linea}" for linea in contenido.splitlines())
        trozos.append(f"--- /dev/null\n+++ b/{ruta}\n@@ -0,0 +1 @@\n{cuerpo}\n")
    return CodeChange(
        files_changed=files,
        diff="".join(trozos),
        rationale=rationale,
        diff_sha256=_sha("".join(trozos)),
    )


def _propuesta(**cambios) -> dict:
    """El `CodeProposal` que un modelo bien portado devolveria."""
    base = {
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
    base.update(cambios)
    return base


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repositorio git real con un `tests/` que pytest puede ejecutar.

    El `tests/` es lo que hace que la prueba sea una **prueba de verdad**: sin el,
    `pytest` saldria con codigo 5 ("no se recolectaron pruebas") y estariamos
    midiendo otra cosa.
    """
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
def sandbox(repo: Path, tmp_path: Path) -> Sandbox:
    b = crear(repo, "run-f8", workspace_root=tmp_path / "workspaces")
    yield b
    destruir(b)


@pytest.fixture(autouse=True)
def _inyeccion_limpia(tmp_path: Path):
    """Fija la raiz de worktrees y los targets, y **restaura** al terminar.

    Son atributos de modulo: sin restaurarlos, una prueba dejaria a las siguientes
    con una raiz de worktrees que ya no existe.
    """
    nodes.usar_workspace_root(tmp_path / "workspaces")
    nodes.usar_targets_permitidos(("pytest.unit",))
    yield
    nodes.usar_workspace_root(None)
    nodes.usar_targets_permitidos(None)


def _estado(repo: Path, *, cambio: CodeChange | None = None, run_id: str = "run-f8") -> RunState:
    """Estado minimo con un cambio del Coder, listo para aplicar."""
    ahora = datetime.now(UTC)
    return RunState(
        run_id=run_id,
        trace_id=f"trace-{run_id}",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text="corrige el valor de retorno",
            source=InstructionSource.TEXT,
            confirmed_by_user=True,
        ),
        options=RunOptions(repo_path=str(repo)),
        interpretation=TaskInterpretation(
            intent=Intent.MODIFY,
            scope=Scope(repo_path=str(repo)),
            confidence=0.9,
            rationale="prueba",
        ),
        outputs=Outputs(coder_output=cambio if cambio is not None else _cambio(("src/app.py", CONTENIDO_NUEVO))),
    )


def _estado_con_cambio() -> RunState:
    """Estado con una propuesta del Coder, para ejercitar `route_after_coder`.

    No crea nada en disco: el router del Coder solo lee
    `outputs.coder_output.files_changed`, asi que la ruta del repositorio es
    irrelevante aqui y se deja sin declarar.
    """
    return _estado_sin_repo(coder_output=_cambio(("src/app.py", CONTENIDO_NUEVO)))


def _estado_con_sandbox_ok() -> RunState:
    """Estado ya aplicado en el sandbox: `route_after_apply` debe llevar a pruebas.

    Basta con que `status` **no** sea terminal: `route_after_apply` decide por el
    estado, no por el valor del worktree.
    """
    return _estado_sin_repo(coder_output=_cambio(("src/app.py", CONTENIDO_NUEVO)))


def _estado_sin_repo(*, coder_output: CodeChange | None = None) -> RunState:
    """Estado minimo para ejercitar **routers**: no toca disco ni modelo."""
    ahora = datetime.now(UTC)
    return RunState(
        run_id="run-router",
        trace_id="trace-run-router",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text="corrige el valor de retorno",
            source=InstructionSource.TEXT,
            confirmed_by_user=True,
        ),
        interpretation=TaskInterpretation(
            intent=Intent.MODIFY,
            scope=Scope(repo_path="(sin repositorio)"),
            confidence=0.9,
            rationale="prueba de router",
        ),
        outputs=Outputs(coder_output=coder_output),
    )


# ------------------------------------------------ 1. la tabla cerrada de targets


def test_la_tabla_de_targets_es_cerrada_y_conocida() -> None:
    """El catalogo de comandos es un dato enumerable, no algo que se construya.

    Si alguien anade un objetivo, esta prueba lo dice. Es el mismo criterio que la
    matriz de permisos: un catalogo implicito no es auditable.
    """
    assert targets_disponibles() == ("pytest.integration", "pytest.unit", "ruff.check")
    assert set(TARGET_COMMANDS) == set(targets_disponibles())


def test_ningun_comando_se_ejecuta_a_traves_de_una_shell() -> None:
    """Cada comando es una **lista de argumentos**, no una cadena.

    Es la comprobacion que hace imposible el fallo clasico: si el comando fuera una
    cadena habria que pasar `shell=True` para que funcionara, y entonces cualquier
    caracter de control del texto se interpretaria. Aqui no hay ninguna cadena.
    """
    for target, argv in TARGET_COMMANDS.items():
        assert isinstance(argv, tuple), f"'{target}' no es una tupla"
        assert len(argv) >= 2, f"'{target}' tiene un comando sospechosamente corto"
        for argumento in argv:
            assert isinstance(argumento, str), f"'{target}' tiene un argumento no textual"
        # El interprete es el mismo que ejecuta el sistema, no un "python" del PATH.
        assert argv[0] == sys.executable, f"'{target}' no usa el interprete del sistema"


def test_el_comando_expuesto_coincide_con_el_ejecutado(sandbox: Sandbox) -> None:
    """`argv` en la evidencia es el comando real, no una descripcion."""
    corrida = ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",))

    assert corrida.argv == list(TARGET_COMMANDS["pytest.unit"])
    assert comando_de("pytest.unit") == TARGET_COMMANDS["pytest.unit"]


def test_un_target_desconocido_no_tiene_comando() -> None:
    """No hay comando por defecto ni generico: lo que no esta, no se ejecuta."""
    assert comando_de("pytest.todo") is None
    assert comando_de("") is None


# ------------------------------------------------------- 2. ejecucion real


def test_el_runner_ejecuta_pruebas_de_verdad(sandbox: Sandbox) -> None:
    """Un `tests/` que pasa produce un `TestRun` con codigo de salida 0 real."""
    corrida = ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",))

    assert corrida.target == "pytest.unit"
    assert corrida.exit_code == 0, f"salida:\n{corrida.stdout}\n{corrida.stderr}"
    assert corrida.passed
    assert corrida.duration_s > 0.0
    assert "1 passed" in corrida.stdout, "no se recolecto ninguna prueba: la evidencia seria vacua"


def test_un_test_que_falla_es_un_resultado_no_una_excepcion(repo: Path, tmp_path: Path) -> None:
    """Un fallo de pruebas devuelve evidencia con codigo != 0. **No lanza.**

    Es la distincion central de F8: un fallo de las pruebas es un **resultado** que
    el Reviewer debe juzgar; una excepcion aqui abortaria el ciclo de correccion
    antes de que pudiera empezar.
    """
    (repo / "tests" / "test_ok.py").write_text(TEST_QUE_FALLA, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "test que falla")

    b = crear(repo, "run-falla", workspace_root=tmp_path / "workspaces")
    try:
        corrida = ejecutar(b, "pytest.unit", permitidos=("pytest.unit",))
    finally:
        destruir(b)

    assert corrida.exit_code != 0
    assert not corrida.passed
    assert "1 failed" in corrida.stdout, f"salida inesperada:\n{corrida.stdout}"


def test_un_timeout_produce_evidencia_en_lugar_de_excepcion(sandbox: Sandbox) -> None:
    """Un objetivo colgado se convierte en evidencia, no en un fallo del sistema."""
    corrida = ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=0.001)

    assert corrida.exit_code == EXIT_TIMEOUT
    assert not corrida.passed
    assert "supero" in corrida.stderr
    assert corrida.argv == list(TARGET_COMMANDS["pytest.unit"])


def test_el_runner_llama_a_subprocess_sin_shell(sandbox: Sandbox, monkeypatch) -> None:
    """La llamada real pasa `shell=False` y una **lista**.

    **Por que no basta con mirar la tabla.** `TARGET_COMMANDS` guarda tuplas, pero eso
    no prueba como se **invoca** `subprocess`: alguien podria unir la tupla en una
    cadena y pasar `shell=True`, y la tabla seguiria siendo correcta mientras el
    fallo estaria en la llamada. Aqui se intercepta `subprocess.run` y se afirma
    sobre los argumentos que **de verdad** se pasan.

    Esta prueba existe porque la mutacion que cambia `shell=False` por `shell=True`
    **no era cazada**: la suite comprobaba el dato, no la invocacion.
    """
    import subprocess as sp

    # `sandbox` ya existe (fixture), asi que el unico `subprocess.run` que se
    # observa aqui es el del runner. Aun asi se filtra por `shell`/`env` para no
    # depender de que ningun otro componente llame a subprocess en el intervalo.
    capturado: dict[str, object] = {}
    original = sp.run

    def espia(*args, **kwargs):
        capturado["args"] = args
        capturado["kwargs"] = kwargs
        return original(*args, **kwargs)

    monkeypatch.setattr(sp, "run", espia)
    ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",))

    assert capturado, "no se llamo a subprocess.run"
    assert capturado["kwargs"].get("shell") is False, "el runner invoca con shell habilitada"
    # El primer argumento es la lista de argumentos, no una cadena.
    orden = capturado["args"][0]
    assert isinstance(orden, list), f"el argv no es una lista: {type(orden).__name__}"
    assert orden == list(TARGET_COMMANDS["pytest.unit"])


def test_el_runner_inyecta_el_src_del_sandbox_en_el_pythonpath(
    repo: Path, tmp_path: Path, monkeypatch
) -> None:
    """El hijo debe importar el paquete **del sandbox**, no el del repo original.

    Es el fallo mas silencioso del modulo: con el `PYTHONPATH` del padre, pytest
    importaria el paquete del repositorio original y la evidencia diria "pasa" sobre
    un codigo distinto del que se va a aprobar. Se comprueba que el `env` que recibe
    `subprocess` apunta al `src/` del sandbox, aunque el proceso padre tenga otro.

    Esta prueba existe porque la mutacion que deja el `PYTHONPATH` original **no era
    cazada**.
    """
    import subprocess as sp

    monkeypatch.setenv("PYTHONPATH", "C:/ruta/falsa/del/repo/original")
    b = crear(repo, "run-py", workspace_root=tmp_path / "workspaces")

    # Se registran **todas** las llamadas: `crear` tambien invoca git por
    # `subprocess.run`, y quedarse con la ultima capturaria una llamada de git en
    # lugar de la de pytest. Se busca la que lleva `env`, que es la del runner.
    llamadas: list[dict] = []
    original = sp.run

    def espia(*args, **kwargs):
        llamadas.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(sp, "run", espia)
    try:
        ejecutar(b, "pytest.unit", permitidos=("pytest.unit",))
    finally:
        destruir(b)

    con_entorno = [k for k in llamadas if isinstance(k.get("env"), dict)]
    assert con_entorno, "el runner no paso un entorno explicito al hijo"
    entorno = con_entorno[-1]["env"]
    assert entorno["PYTHONPATH"] == str(b.raiz / "src"), (
        f"el PYTHONPATH no apunta al sandbox: {entorno.get('PYTHONPATH')}"
    )


def test_la_salida_se_recorta_al_limite_del_contrato(sandbox: Sandbox) -> None:
    """El contrato tiene un maximo; el runner no puede producir un `TestRun` invalido."""
    corrida = ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",))

    assert len(corrida.stdout) <= 200_000
    assert len(corrida.stderr) <= 200_000


# ------------------------------------------------- 3. el target no es un comando


def test_un_target_no_permitido_se_rechaza_antes_de_ejecutar(sandbox: Sandbox) -> None:
    """La lista permitida es una puerta, no una sugerencia."""
    with pytest.raises(TargetNoPermitido) as exc:
        ejecutar(sandbox, "ruff.check", permitidos=("pytest.unit",))

    assert "no esta en la lista permitida" in str(exc.value)


def test_un_target_permitido_sin_comando_definido_se_rechaza(sandbox: Sandbox) -> None:
    """Permitido por configuracion pero sin comando: no se inventa uno."""
    with pytest.raises(RunnerError) as exc:
        ejecutar(sandbox, "pytest.inventado", permitidos=("pytest.inventado",))

    assert "no tiene comando definido" in str(exc.value)


def test_el_policy_engine_deniega_un_target_fuera_de_la_lista() -> None:
    """La segunda puerta: aunque alguien llame al runner, la politica ya lo nego."""
    from ai_swe.contracts import AgentRole, PolicyEffect
    from ai_swe.tools.policy import DecisionContext, decide

    decision = decide(
        "run_tests",
        {"target": "rm -rf /"},
        DecisionContext(
            run_id="run-x",
            agent=AgentRole.CODER,
            allowed_test_targets=("pytest.unit",),
        ),
    )

    assert decision.effect is PolicyEffect.DENY
    assert decision.matched_rule == "POLICY-TARGET-NOT-ALLOWLISTED"


# ------------------------------------------------------- 4. nodo apply_sandbox


def test_apply_sandbox_aplica_el_cambio_en_un_worktree(repo: Path, tmp_path: Path) -> None:
    """El parche existe en el sandbox y los artefactos lo declaran."""
    estado = _estado(repo)
    delta = nodes.apply_sandbox(estado)

    ruta = Path(delta["artifacts"].worktree_path)
    assert ruta.is_dir()
    assert ruta != repo
    assert "42" in (ruta / "src" / "app.py").read_text(encoding="utf-8")
    assert delta["artifacts"].base_commit
    assert delta["artifacts"].diff, "un cambio aplicado sin diff no es auditable"
    assert delta["next_step"] == "run_tests"
    assert delta["artifacts"].changed_files[0].path == "src/app.py"


def test_apply_sandbox_no_toca_el_repositorio_original(repo: Path) -> None:
    """**La prueba que da sentido a F7 y F8.** El arbol del usuario queda intacto."""
    antes = (repo / "src" / "app.py").read_text(encoding="utf-8")

    nodes.apply_sandbox(_estado(repo))

    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == antes
    assert _git(repo, "status", "--porcelain").strip() == ""
    assert not (repo / "workspaces").exists()


def test_apply_sandbox_sin_cambio_escala(repo: Path) -> None:
    """Sin propuesta no hay nada que aplicar, y se dice con un error tipado."""
    estado = _estado(repo, cambio=CodeChange(files_changed=[], diff="", rationale="nada", diff_sha256=_sha("")))

    delta = nodes.apply_sandbox(estado)

    assert delta["status"] is RunStatus.NEEDS_HUMAN
    assert delta["errors"][-1].error_class == "SANDBOX_NOTHING_TO_APPLY"


def test_apply_sandbox_sin_repositorio_escala_con_error_tipado(tmp_path: Path) -> None:
    """Un `repo_path` que no existe no revienta: se declara y se escala."""
    ahora = datetime.now(UTC)
    estado = RunState(
        run_id="run-sin-repo",
        trace_id="trace-sin-repo",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text="corrige", source=InstructionSource.TEXT, confirmed_by_user=True
        ),
        options=RunOptions(repo_path=str(tmp_path / "no-existe")),
        outputs=Outputs(coder_output=_cambio(("src/app.py", CONTENIDO_NUEVO))),
    )

    delta = nodes.apply_sandbox(estado)

    assert delta["status"] is RunStatus.NEEDS_HUMAN
    assert delta["errors"][-1].error_class == "SANDBOX_NO_REPO"


def test_apply_sandbox_sobre_algo_que_no_es_git_escala(tmp_path: Path) -> None:
    """Un directorio que no es repositorio git no puede tener worktree."""
    carpeta = tmp_path / "no-es-repo"
    carpeta.mkdir()

    delta = nodes.apply_sandbox(_estado(carpeta))

    assert delta["status"] is RunStatus.NEEDS_HUMAN
    assert delta["errors"][-1].error_class == "SANDBOX_CREATE_FAILED"


def test_apply_sandbox_con_ruta_maliciosa_escala(repo: Path) -> None:
    """Una propuesta que sale del area autorizada **no se aplica y escala**.

    El patcher (F7) no aborta el cambio por una ruta denegada, pero en el grafo un
    rechazo significa que el Coder propuso escribir fuera de lo autorizado. Eso no
    es un resultado normal: va a un humano.
    """
    estado = _estado(repo, cambio=_cambio(("../../fuera.py", "malicioso\n")))

    delta = nodes.apply_sandbox(estado)

    assert delta["status"] is RunStatus.NEEDS_HUMAN
    assert delta["errors"][-1].error_class == "SANDBOX_PATH_DENIED"
    assert not (repo.parent / "fuera.py").exists(), "el escape se escribio fuera"


def test_apply_sandbox_con_fallo_tecnico_escala(repo: Path) -> None:
    """Un fallo de escritura **tecnico** (no de seguridad) tambien escala.

    Se provoca con una ruta cuyo directorio padre es un **archivo** dentro del
    sandbox: el confinamiento la acepta -esta dentro-, pero `mkdir` falla. El nodo
    debe convertir ese fallo en un error tipado y escalar, **no** dejarlo escapar
    como una excepcion cruda que tumbaria el grafo.

    Esta prueba existe porque la mutacion que borra la rama `resultado.fallos` **no
    era cazada**: sin este caso, `fallos` nunca se ejercitaba y una rama muerta
    parecia cubierta. Al construirla se descubrio que un `OSError` de escritura
    escapaba del `except SandboxError` del patcher; se corrigio en `Sandbox.escribir`
    envolviendolo en `SandboxError`.
    """
    # 'src/blocked' es un ARCHIVO, de modo que 'src/blocked/x.py' no puede crearse.
    (repo / "src" / "blocked").write_text("soy un archivo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "bloquea la ruta")

    estado = _estado(repo, cambio=_cambio(("src/blocked/x.py", "y = 2\n")))
    delta = nodes.apply_sandbox(estado)

    assert delta["status"] is RunStatus.NEEDS_HUMAN
    assert delta["errors"][-1].error_class == "SANDBOX_APPLY_FAILED"
    # El repositorio del usuario sigue limpio: el fallo ocurrio en el sandbox.
    assert _git(repo, "status", "--porcelain").strip() == ""


# --------------------------------------------------------- 5. nodo run_tests


def test_run_tests_registra_evidencia_real(repo: Path) -> None:
    """El nodo ejecuta y guarda la evidencia en `RunState.evidence.test_runs`."""
    estado = _estado(repo)
    tras_aplicar = estado.model_copy(
        update={"artifacts": nodes.apply_sandbox(estado)["artifacts"]}
    )

    delta = nodes.run_tests(tras_aplicar)

    corridas = delta["evidence"].test_runs
    assert len(corridas) == 1
    assert corridas[0].target == "pytest.unit"
    assert corridas[0].exit_code == 0
    assert corridas[0].argv, "la evidencia no dice que se ejecuto"
    assert delta["next_step"] == "reviewer"


def test_run_tests_sin_sandbox_escala(repo: Path) -> None:
    """Sin worktree no hay nada que probar: no se inventa evidencia."""
    delta = nodes.run_tests(_estado(repo))

    assert delta["status"] is RunStatus.NEEDS_HUMAN
    assert delta["errors"][-1].error_class == "TEST_NO_SANDBOX"


def test_un_fallo_de_pruebas_no_escala_lo_juzga_el_reviewer(repo: Path) -> None:
    """Un test rojo es **evidencia**, no un error del sistema.

    El nodo sigue a `reviewer` con la evidencia en la mano: escalar aqui impediria
    que el ciclo Coder<->Reviewer hiciera su trabajo.
    """
    estado = _estado(repo)
    tras_aplicar = estado.model_copy(
        update={"artifacts": nodes.apply_sandbox(estado)["artifacts"]}
    )
    # Se rompe el test DENTRO del sandbox, no en el original.
    sandbox = Path(tras_aplicar.artifacts.worktree_path)
    (sandbox / "tests" / "test_ok.py").write_text(TEST_QUE_FALLA, encoding="utf-8")

    delta = nodes.run_tests(tras_aplicar)

    assert delta["evidence"].test_runs[-1].exit_code != 0
    assert delta["next_step"] == "reviewer"
    assert "status" not in delta, "un test rojo no debe cerrar la ejecucion"


def test_el_presupuesto_cuenta_las_ejecuciones(repo: Path) -> None:
    """Ejecutar pruebas es una llamada a herramienta: gasta presupuesto."""
    estado = _estado(repo)
    tras_aplicar = estado.model_copy(
        update={"artifacts": nodes.apply_sandbox(estado)["artifacts"]}
    )
    assert tras_aplicar.budget.used_tool_calls == 0

    delta = nodes.run_tests(tras_aplicar)

    assert delta["budget"].used_tool_calls == 1


def test_los_errores_previos_no_se_pisan(repo: Path) -> None:
    """Un fallo de F8 se **anade** a los errores anteriores, no los sustituye."""
    estado = _estado(repo)
    previo = estado.errors  # vacio
    assert previo == []
    con_error = estado.model_copy(
        update={
            "errors": [
                *estado.errors,
                nodes.RunError(
                    error_class="MODEL_FALLBACK",
                    agent="coder",
                    message="previo",
                    recoverable=True,
                    occurred_at=datetime.now(UTC),
                ),
            ]
        }
    )
    tras_aplicar = con_error.model_copy(
        update={"artifacts": nodes.apply_sandbox(con_error)["artifacts"]}
    )

    delta = nodes.run_tests(tras_aplicar)

    assert len(delta["errors"]) == 1
    assert delta["errors"][0].error_class == "MODEL_FALLBACK"


# ------------------------------------------------------ 6. cableado del grafo


def test_el_grafo_ejecuta_el_camino_completo_hasta_la_aprobacion(
    repo: Path, tmp_path: Path
) -> None:
    """E2E real: coder -> apply_sandbox -> run_tests -> reviewer -> aprobacion.

    El unico sustituto es el **modelo** (`FakeModelAdapter`), porque no hay
    credenciales. Todo lo demas es produccion: el sandbox crea un worktree de
    verdad, las pruebas se ejecutan de verdad en un subproceso, y el Reviewer juzga
    la evidencia real.

    `interpret` y `plan` reciben del fake un objeto que no cumple **su** contrato, y
    por eso degradan a sus fallbacks deterministas. Es exactamente el camino que
    recorrera el sistema sin proveedor: la ejecucion llega igualmente hasta la
    puerta de aprobacion.
    """
    from langgraph.checkpoint.memory import InMemorySaver

    from ai_swe.graph.workflow import construir_grafo

    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=_propuesta())]))
    try:
        app = construir_grafo().compile(checkpointer=InMemorySaver())
        estado = _estado(repo, run_id="run-e2e")
        cfg = {"configurable": {"thread_id": estado.run_id}}

        salida = app.invoke(estado, cfg)
    finally:
        nodes.usar_gateway(nodes.SIN_GATEWAY)

    # El grafo se pausa en la puerta de aprobacion, no antes.
    assert salida.get("__interrupt__"), "no se llego a la puerta de aprobacion"
    pausado = RunState.model_validate(app.get_state(cfg).values)

    assert pausado.status is RunStatus.AWAITING_APPROVAL
    # El sandbox se aplico de verdad y quedo registrado.
    assert pausado.artifacts.worktree_path
    assert Path(pausado.artifacts.worktree_path).is_dir()
    # Y la evidencia es real: se ejecuto pytest y paso.
    assert pausado.evidence.test_runs, "no hay evidencia de pruebas"
    assert pausado.evidence.test_runs[-1].exit_code == 0
    assert "1 passed" in pausado.evidence.test_runs[-1].stdout
    # El veredicto del Reviewer se apoya en esa evidencia.
    assert pausado.outputs.reviewer_output is not None
    # **Y el repositorio del usuario sigue intacto.**
    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == "def f():\n    return 1\n"
    assert _git(repo, "status", "--porcelain").strip() == ""


def test_un_fallo_del_sandbox_no_tumba_el_grafo(tmp_path: Path) -> None:
    """Un `repo_path` invalido produce `needs_human`, no una traza de LangGraph.

    **Se conduce el grafo de verdad, con el modelo sustituido.** No basta con
    sembrar `outputs.coder_output`: el grafo **reejecuta** el nodo `coder`, y sin
    gateway el Coder devuelve un cambio vacio que pisa el sembrado, con lo que la
    ejecucion se desviaria a `escalate_no_changes` y **nunca llegaria al sandbox**.
    Eso convertiria la prueba en un falso positivo: afirmaria sobre
    `SANDBOX_NO_REPO` sin haber ejercitado jamas `apply_sandbox`. Sustituyendo solo
    el modelo por un `FakeModelAdapter` que devuelve una `CodeProposal` valida, el
    Coder produce un cambio real y el camino llega al sandbox, que es lo que se
    quiere probar.
    """
    from langgraph.checkpoint.memory import InMemorySaver

    from ai_swe.graph.workflow import construir_grafo

    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=_propuesta())]))
    try:
        app = construir_grafo().compile(checkpointer=InMemorySaver())
        ahora = datetime.now(UTC)
        estado = RunState(
            run_id="run-sin-repo",
            trace_id="trace-sin-repo",
            created_at=ahora,
            updated_at=ahora,
            instruction=Instruction(
                text="corrige el parseo", source=InstructionSource.TEXT, confirmed_by_user=True
            ),
            options=RunOptions(repo_path=str(tmp_path / "no-existe")),
        )
        cfg = {"configurable": {"thread_id": estado.run_id}}

        salida = app.invoke(estado, cfg)
    finally:
        nodes.usar_gateway(nodes.SIN_GATEWAY)

    final = RunState.model_validate(salida)

    # El Coder SI produjo un cambio: si no, el fallo seria otro y la prueba no
    # mediria lo que dice medir.
    assert final.outputs.coder_output and final.outputs.coder_output.files_changed
    assert final.status is RunStatus.NEEDS_HUMAN
    assert final.status.is_terminal
    assert any(e.error_class == "SANDBOX_NO_REPO" for e in final.errors)


def test_el_grafo_tiene_la_arista_del_sandbox() -> None:
    """La topologia contiene el nodo y el cableado; no se confia en un comentario.

    **Se inspecciona el `StateGraph` sin compilar, no `get_graph()`.** En un grafo
    compilado con aristas condicionales, `get_graph().edges` solo contiene las
    aristas estaticas: `apply_sandbox -> run_tests` es **condicional** y no aparece
    ahi, de modo que afirmar sobre `edges` daria un falso negativo (o, peor, un
    falso positivo si alguien aflojara la asercion). La representacion fiel de la
    topologia son `nodes` y `branches` del grafo sin compilar.

    **Y no basta con que el nodo exista.** Un nodo suelto, sin arista de entrada ni
    salida, tambien "esta en `nodes`". Por eso se comprueba ademas que
    `apply_sandbox` es **origen de una rama** (tiene su router cableado) y que ese
    router **devuelve de verdad** `run_tests` cuando el sandbox aplico el cambio.
    La arista se ejercita, no se supone.
    """
    from ai_swe.graph.workflow import construir_grafo

    grafo = construir_grafo()

    # 1. El nodo existe.
    assert "apply_sandbox" in set(grafo.nodes)
    assert "run_tests" in set(grafo.nodes)

    # 2. Tiene router cableado (si no, seria un nodo huerfano).
    assert "apply_sandbox" in set(grafo.branches)

    # 3. El router lleva a `run_tests` cuando hubo aplicacion, y cierra cuando el
    #    sandbox fallo. Se comprueba sobre el estado, no sobre el nombre.
    estado_ok = _estado_con_sandbox_ok()
    assert nodes.route_after_apply(estado_ok) == "run_tests"

    estado_roto = estado_ok.model_copy(update={"status": RunStatus.NEEDS_HUMAN})
    assert nodes.route_after_apply(estado_roto) == "finalize"

    # 4. El sandbox solo es alcanzable desde el Coder: nadie mas escribe. Esta
    #    arista SI es estatica (`coder --condicional--> apply_sandbox` se declara
    #    como rama desde `coder`), asi que se busca en el router del Coder.
    assert "coder" in set(grafo.branches)
    assert nodes.route_after_coder(_estado_con_cambio()) == "apply_sandbox"


def test_el_router_del_coder_distingue_cambio_vacio_de_cambio_real() -> None:
    """Sin cambios, el Coder **no** va al sandbox: no hay nada que aplicar.

    La distincion importa: un cambio vacio que llegara a `apply_sandbox` crearia un
    worktree sin parche y luego escalaria por falta de contenido, en lugar de
    cerrar con `CODER_PRODUCED_NO_CHANGES`, que es el error correcto y accionable.

    Esta prueba existe porque la mutacion que hace que `route_after_coder` devuelva
    siempre `apply_sandbox` **no era cazada**: solo se ejercitaba el caso con
    cambios, y una rama del ternario quedaba sin cubrir.
    """
    con_cambios = _estado_con_cambio()
    assert nodes.route_after_coder(con_cambios) == "apply_sandbox"

    sin_cambios = con_cambios.model_copy(
        update={
            "outputs": Outputs(
                coder_output=CodeChange(
                    files_changed=[], diff="", rationale="nada", diff_sha256=_sha("")
                )
            )
        }
    )
    assert nodes.route_after_coder(sin_cambios) == "escalate_no_changes"

    # Y sin `coder_output` en absoluto: mismo cierre.
    sin_salida = con_cambios.model_copy(update={"outputs": Outputs(coder_output=None)})
    assert nodes.route_after_coder(sin_salida) == "escalate_no_changes"


def test_el_sandbox_no_se_destruye_al_final_de_la_ejecucion(repo: Path) -> None:
    """`DEC-16`: el worktree sobrevive para que un humano pueda inspeccionarlo.

    Destruirlo antes de la aprobacion destruiria justo lo que se esta aprobando.

    Igual que la prueba anterior, se conduce el grafo con el modelo sustituido: el
    nodo `coder` se reejecuta y solo un Coder que produce un cambio **real** llega
    al sandbox. Sembrar `coder_output` a mano daria una ejecucion que termina sin
    haber creado worktree alguno, y la asercion fallaria por un motivo que no tiene
    nada que ver con lo que se quiere comprobar.
    """
    from langgraph.checkpoint.memory import InMemorySaver

    from ai_swe.graph.workflow import construir_grafo

    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=_propuesta())]))
    try:
        app = construir_grafo().compile(checkpointer=InMemorySaver())
        estado = _estado(repo, run_id="run-persiste")
        cfg = {"configurable": {"thread_id": estado.run_id}}
        app.invoke(estado, cfg)
    finally:
        nodes.usar_gateway(nodes.SIN_GATEWAY)

    final = RunState.model_validate(app.get_state(cfg).values)
    assert final.artifacts.worktree_path, "no se creo worktree: la prueba no midio nada"
    assert Path(final.artifacts.worktree_path).is_dir(), "el sandbox desaparecio"
