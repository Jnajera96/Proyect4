"""Pruebas de F12: promocion de cambios aprobados al repositorio del usuario.

**Que protege este fichero.** El ultimo tramo del sistema: que un cambio que un
humano ha aprobado llegue de verdad al repositorio del usuario, y que **nada mas**
lo haga. Cuatro propiedades, y las cuatro son de seguridad:

  a) **Un cambio aprobado modifica el repositorio.** La promocion ocurre, y ocurre
     sobre el arbol real: se lee el archivo del repositorio del usuario, no un
     informe.
  b) **Rechazar o pedir cambios deja el repositorio intacto.** Se comprueba el
     contenido **y** `git status --porcelain`: no basta con que el archivo este
     igual, el arbol tiene que estar limpio.
  c) **El Policy Engine bloquea una promocion no autorizada.** Promover sobre un
     repositorio distinto del autorizado, o sobre una ruta fuera de alcance o
     protegida, se deniega **sin tocar nada**.
  d) **El sandbox se limpia al finalizar** (`teardown`), y solo entonces: mientras
     la ejecucion espera una decision humana, el worktree sigue ahi para poder
     inspeccionarlo.

**Promocion determinista, sin `shell=True`.** El modulo `promoter` aplica el diff
real del worktree con `git apply` (lista de argumentos, `shell=False`) y verifica
la integridad por SHA256 y por reproduccion archivo a archivo.

Ninguna prueba toca la red, las credenciales ni el repositorio del proyecto.
"""

from __future__ import annotations

import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from ai_swe.contracts import (
    CodeChange,
    FileChange,
    Instruction,
    InstructionSource,
    RunOptions,
    RunState,
    RunStatus,
)
from ai_swe.graph import nodes
from ai_swe.graph.workflow import construir_grafo
from ai_swe.models import FakeModelAdapter, ModelGateway
from ai_swe.sandbox import crear, destruir
from ai_swe.tools.patcher import aplicar
from ai_swe.tools.promoter import PromotionDenied, promover

# --------------------------------------------------------------- utilidades

CONTENIDO_ORIGINAL = "def f():\n    return 1\n"
CONTENIDO_NUEVO = "def f():\n    return 42\n"
TEST_QUE_PASA = "def test_pasa():\n    assert 1 == 1\n"


def _git(repo: Path, *args: str) -> str:
    resultado = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, shell=False
    )
    assert resultado.returncode == 0, f"git {' '.join(args)} fallo: {resultado.stderr}"
    return resultado.stdout


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _crear_repo(raiz: Path) -> Path:
    """Repositorio git real con un `tests/` que pasa y un `src/app.py` conocido."""
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "test@localhost")
    _git(raiz, "config", "user.name", "Test")
    (raiz / "src").mkdir()
    (raiz / "src" / "app.py").write_text(CONTENIDO_ORIGINAL, encoding="utf-8")
    (raiz / "tests").mkdir()
    (raiz / "tests" / "test_ok.py").write_text(TEST_QUE_PASA, encoding="utf-8")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "inicial")
    return raiz


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repositorio del usuario. Es el que la promocion **si** puede tocar."""
    return _crear_repo(tmp_path / "repo_usuario")


@pytest.fixture
def otro_repo(tmp_path: Path) -> Path:
    """Otro repositorio valido, para probar que la promocion no lo toca."""
    return _crear_repo(tmp_path / "otro_repo")


@pytest.fixture(autouse=True)
def _inyeccion_limpia(tmp_path: Path):
    """Restaura el estado de modulo que comparten grafo y pruebas."""
    nodes.usar_workspace_root(tmp_path / "workspaces")
    nodes.usar_targets_permitidos(("pytest.unit",))
    yield
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    nodes.usar_modelo_reviewer(None)
    nodes.usar_workspace_root(None)
    nodes.usar_targets_permitidos(None)


def _cambio(ruta: str = "src/app.py", contenido: str = CONTENIDO_NUEVO) -> CodeChange:
    """Un `CodeChange` como el que produce el Coder: contenido en el diff.

    El diff lleva **todas** las lineas del archivo resultante como `+`, que es la
    forma que el aplicador de parches (F7) sabe reconstruir.
    """
    lineas = contenido.splitlines()
    cuerpo = "\n".join(f"+{linea}" for linea in lineas)
    trozo = f"--- /dev/null\n+++ b/{ruta}\n@@ -0,0 +1,{len(lineas)} @@\n{cuerpo}\n"
    return CodeChange(
        files_changed=[FileChange(path=ruta, added=len(lineas), removed=0, sha256=_sha(contenido))],
        diff=trozo,
        rationale="prueba de promocion",
        diff_sha256=_sha(trozo),
    )


def _estado(repo: Path, *, run_id: str) -> RunState:
    """Estado minimo del grafo, con el repositorio autorizado declarado."""
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
    )


def _app():
    return construir_grafo().compile(checkpointer=InMemorySaver())


def _estado_de(app, cfg) -> RunState:
    return RunState.model_validate(app.get_state(cfg).values)


def _con_modelo_falso() -> None:
    """Un gateway cuyo modelo propone un cambio real y valido.

    El resto de nodos (`interpret`, `plan`, `reviewer`) caen a su version
    determinista, porque el `CodeProposal` no cumple sus contratos. Es justo lo que
    se quiere: el modelo aporta el parche y el codigo decide lo demas.
    """
    propuesta = {
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
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured=propuesta)]))


def _hasta_la_puerta_de_aprobacion(app, estado: RunState):
    """Lanza el grafo y lo lleva hasta la puerta de aprobacion, confirmando requisitos."""
    cfg = {"configurable": {"thread_id": estado.run_id}}
    app.invoke(estado, cfg)
    pausado = _estado_de(app, cfg)
    assert pausado.status is RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION, (
        f"no se detuvo en la puerta de requisitos, sino en '{pausado.status.value}'"
    )
    app.invoke(Command(resume="approved"), cfg)
    pausado = _estado_de(app, cfg)
    assert pausado.status is RunStatus.AWAITING_APPROVAL, (
        f"no se llego a la puerta de aprobacion, sino a '{pausado.status.value}'"
    )
    return cfg


# ============================================================ a) la promocion

# ------------------------------------------------- 1. la funcion, directamente


def test_un_cambio_aprobado_modifica_el_repositorio(repo: Path, tmp_path: Path) -> None:
    """La promocion escribe en el repositorio del usuario. Es el objetivo de F12."""
    sandbox = crear(repo, "run-f12-directo", workspace_root=tmp_path / "ws")
    try:
        aplicar(sandbox, _cambio(), allowed_paths=(), protected_paths=())
        # El worktree tiene el cambio; el repositorio del usuario, todavia no.
        assert (sandbox.raiz / "src" / "app.py").read_text(encoding="utf-8") == CONTENIDO_NUEVO
        assert (repo / "src" / "app.py").read_text(encoding="utf-8") == CONTENIDO_ORIGINAL

        resultado = promover(sandbox, repo_autorizado=repo, expected_diff=sandbox.diff())

        assert resultado.applied is True
        assert resultado.files == ["src/app.py"]
        assert resultado.patch_sha256
        assert (repo / "src" / "app.py").read_text(encoding="utf-8") == CONTENIDO_NUEVO
    finally:
        destruir(sandbox)


def test_un_worktree_sin_cambios_no_promueve_nada(repo: Path, tmp_path: Path) -> None:
    """Sin cambios, la promocion es un no-op explicito, no una escritura vacia."""
    sandbox = crear(repo, "run-f12-vacio", workspace_root=tmp_path / "ws")
    try:
        resultado = promover(sandbox, repo_autorizado=repo)
        assert resultado.applied is False
        assert _git(repo, "status", "--porcelain").strip() == ""
    finally:
        destruir(sandbox)


def test_la_promocion_no_deja_archivos_preparados_en_el_indice(
    repo: Path, tmp_path: Path
) -> None:
    """El cambio se aplica al arbol de trabajo, **no** se prepara ni se confirma.

    Es una decision de producto: el usuario revisa y confirma. Un `git add` aqui
    decidiria por el.
    """
    sandbox = crear(repo, "run-f12-indice", workspace_root=tmp_path / "ws")
    try:
        aplicar(sandbox, _cambio(), allowed_paths=(), protected_paths=())
        promover(sandbox, repo_autorizado=repo, expected_diff=sandbox.diff())

        preparados = _git(repo, "diff", "--cached", "--name-only").strip()
        assert preparados == "", f"la promocion preparo archivos en el indice: {preparados}"
        assert _git(repo, "status", "--porcelain").strip() != ""
    finally:
        destruir(sandbox)


# ------------------------------------------------------- 2. a traves del grafo


def test_aprobar_promueve_el_cambio_y_completa(repo: Path) -> None:
    """El camino completo: grafo real, sandbox real y promocion real."""
    _con_modelo_falso()
    app = _app()
    estado = _estado(repo, run_id="run-f12-aprobar")
    cfg = _hasta_la_puerta_de_aprobacion(app, estado)

    # Antes de aprobar, el repositorio del usuario sigue intacto.
    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == CONTENIDO_ORIGINAL

    app.invoke(Command(resume="approved"), cfg)
    final = _estado_de(app, cfg)

    assert final.status is RunStatus.COMPLETED
    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == CONTENIDO_NUEVO
    assert final.approvals[-1].decision.value == "approved"


def test_el_sandbox_se_limpia_solo_al_finalizar(repo: Path) -> None:
    """El worktree sobrevive a la espera humana y se limpia al cerrar la ejecucion."""
    _con_modelo_falso()
    app = _app()
    estado = _estado(repo, run_id="run-f12-limpieza")
    cfg = _hasta_la_puerta_de_aprobacion(app, estado)

    pausado = _estado_de(app, cfg)
    ruta = Path(pausado.artifacts.worktree_path)
    assert pausado.artifacts.worktree_path, "no se creo worktree: la prueba no midio nada"
    assert ruta.is_dir(), "el worktree desaparecio antes de la decision humana"

    app.invoke(Command(resume="approved"), cfg)
    final = _estado_de(app, cfg)
    assert final.status is RunStatus.COMPLETED
    assert not ruta.exists(), "el sandbox no se limpio al finalizar"


# ================================================= b) el repositorio intacto


def test_rechazar_la_aprobacion_cancela_sin_tocar_el_repositorio(repo: Path) -> None:
    """Un rechazo cierra la ejecucion y deja el repositorio **exactamente** igual."""
    _con_modelo_falso()
    app = _app()
    estado = _estado(repo, run_id="run-f12-rechazo")
    cfg = _hasta_la_puerta_de_aprobacion(app, estado)

    app.invoke(Command(resume="rejected"), cfg)
    final = _estado_de(app, cfg)

    assert final.status is RunStatus.CANCELLED
    assert final.status.is_terminal
    assert final.next_step is None
    assert final.approvals[-1].decision.value == "rejected"
    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == CONTENIDO_ORIGINAL
    assert _git(repo, "status", "--porcelain").strip() == "", "el arbol del usuario quedo sucio"


def test_pedir_cambios_no_toca_el_repositorio_y_gasta_un_ciclo(repo: Path) -> None:
    """`REQUEST_CHANGES` reencamina al Coder y cuenta el ciclo, sin escribir nada.

    El comentario del humano tiene que llegar al estado: es la unica via por la que
    la siguiente iteracion sabe que corregir.
    """
    _con_modelo_falso()
    app = _app()
    estado = _estado(repo, run_id="run-f12-cambios")
    cfg = _hasta_la_puerta_de_aprobacion(app, estado)

    app.invoke(
        Command(resume={"decision": "modified", "comments": "anade una prueba del caso 42"}),
        cfg,
    )
    final = _estado_de(app, cfg)

    # El ciclo vuelve a pausarse en la puerta de aprobacion: no se promovio nada.
    assert final.status is RunStatus.AWAITING_APPROVAL
    assert final.budget.review_cycles_used == 1
    assert "anade una prueba del caso 42" in " ".join(final.human_feedback)
    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == CONTENIDO_ORIGINAL
    assert _git(repo, "status", "--porcelain").strip() == ""


# ===================================================== c) el Policy Engine


def test_promover_sobre_un_repositorio_no_autorizado_se_deniega(
    repo: Path, otro_repo: Path, tmp_path: Path
) -> None:
    """El destino tiene que ser el repositorio autorizado. Otro se rechaza."""
    sandbox = crear(repo, "run-f12-ajeno", workspace_root=tmp_path / "ws")
    try:
        aplicar(sandbox, _cambio(), allowed_paths=(), protected_paths=())

        with pytest.raises(PromotionDenied):
            promover(sandbox, repo_autorizado=otro_repo)

        # Ni el repositorio autorizado ni el ajeno se tocaron.
        assert (repo / "src" / "app.py").read_text(encoding="utf-8") == CONTENIDO_ORIGINAL
        assert _git(repo, "status", "--porcelain").strip() == ""
        assert _git(otro_repo, "status", "--porcelain").strip() == ""
    finally:
        destruir(sandbox)


def test_una_ruta_fuera_de_alcance_bloquea_la_promocion(repo: Path, tmp_path: Path) -> None:
    """Una ruta que no esta en `allowed_paths` deniega la promocion entera."""
    sandbox = crear(repo, "run-f12-alcance", workspace_root=tmp_path / "ws")
    try:
        aplicar(sandbox, _cambio(), allowed_paths=(), protected_paths=())

        with pytest.raises(PromotionDenied):
            promover(sandbox, repo_autorizado=repo, allowed_paths=("docs",))

        assert (repo / "src" / "app.py").read_text(encoding="utf-8") == CONTENIDO_ORIGINAL
        assert _git(repo, "status", "--porcelain").strip() == ""
    finally:
        destruir(sandbox)


def test_una_ruta_protegida_bloquea_la_promocion(repo: Path, tmp_path: Path) -> None:
    """Una ruta declarada como protegida no se promueve sin permiso explicito."""
    sandbox = crear(repo, "run-f12-protegida", workspace_root=tmp_path / "ws")
    try:
        aplicar(sandbox, _cambio(), allowed_paths=(), protected_paths=())

        with pytest.raises(PromotionDenied):
            promover(sandbox, repo_autorizado=repo, protected_paths=("src",))

        assert (repo / "src" / "app.py").read_text(encoding="utf-8") == CONTENIDO_ORIGINAL
    finally:
        destruir(sandbox)


def test_un_worktree_cambiado_tras_la_revision_no_se_promueve(
    repo: Path, tmp_path: Path
) -> None:
    """Se promueve **lo aprobado**: si el worktree cambio despues, se deniega.

    Es la comprobacion de integridad. Sin ella, una aprobacion sobre un parche
    revisado promoveria un parche distinto, que es peor que no promover.
    """
    sandbox = crear(repo, "run-f12-integridad", workspace_root=tmp_path / "ws")
    try:
        aplicar(sandbox, _cambio(), allowed_paths=(), protected_paths=())
        diff_aprobado = sandbox.diff()

        # Algo cambia el worktree **despues** de la revision y la aprobacion.
        (sandbox.raiz / "src" / "app.py").write_text("def f():\n    return 999\n", encoding="utf-8")

        with pytest.raises(PromotionDenied):
            promover(sandbox, repo_autorizado=repo, expected_diff=diff_aprobado)

        assert (repo / "src" / "app.py").read_text(encoding="utf-8") == CONTENIDO_ORIGINAL
        assert _git(repo, "status", "--porcelain").strip() == ""
    finally:
        destruir(sandbox)
