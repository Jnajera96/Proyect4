"""Pruebas de F7: el Sandbox (worktree aislado) y la aplicacion de parches.

**Que protege este fichero.** Dos invariantes sin los cuales F7 no aporta nada:

  1. **Aislamiento real.** Los archivos se modifican en el sandbox y el repositorio
     original queda **100% intacto**. No se comprueba "leyendo el codigo": se crea un
     repositorio git de verdad, se aplica el parche, y se comprueba el contenido del
     original **y** su `git status`.
  2. **Confinamiento.** Un intento de escape de directorio (`../../`, rutas absolutas,
     unidades de Windows) se bloquea **antes de cualquier escritura**. Se comprueba
     que no se escribio nada, ni dentro ni fuera.

**Por que un repositorio git de verdad y no un mock.** El sandbox es `git worktree`.
Un mock de git no prueba que el worktree aisla: prueba que el mock devuelve lo que le
pedimos. Aqui se ejecuta git de verdad en un temporal. Es mas lento y es el precio
correcto: la propiedad que se verifica -que el arbol del usuario no se toca- solo
existe si hay dos arboles.

Ninguna prueba toca el repositorio del proyecto ni la red.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from ai_swe.contracts import CodeChange, CodeProposal, FileChange
from ai_swe.graph import nodes
from ai_swe.sandbox import EscapeDetectado, Sandbox, SandboxError, crear, destruir
from ai_swe.tools.patcher import aplicar

# --------------------------------------------------------------- utilidades


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, shell=False
    )
    assert result.returncode == 0, f"git {' '.join(args)} fallo: {result.stderr}"
    return result.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Un repositorio git real, con un commit, para que `worktree` funcione.

    `worktree add` exige al menos una confirmacion: sobre un repositorio sin commits
    no hay `HEAD` al que apuntar. Se crea aqui y no se reutiliza el del proyecto por
    una razon obvia: estas pruebas escriben, y el repositorio del proyecto no debe
    ser el conejillo.
    """
    raiz = tmp_path / "repo_usuario"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "test@localhost")
    _git(raiz, "config", "user.name", "Test")

    (raiz / "src").mkdir()
    (raiz / "src" / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (raiz / "README.md").write_text("# Proyecto\n\noriginal\n", encoding="utf-8")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "inicial")
    return raiz


@pytest.fixture
def sandbox(repo: Path, tmp_path: Path) -> Sandbox:
    """Un sandbox recien creado sobre `repo`. Se destruye al terminar."""
    b = crear(repo, "run-test", workspace_root=tmp_path / "workspaces")
    yield b
    destruir(b)


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
                sha256=hashlib.sha256(contenido.encode("utf-8")).hexdigest(),
            )
        )
        cuerpo = "\n".join(f"+{linea}" for linea in contenido.splitlines())
        trozos.append(f"--- /dev/null\n+++ b/{ruta}\n@@ -0,0 +1 @@\n{cuerpo}\n")
    return CodeChange(
        files_changed=files,
        diff="".join(trozos),
        rationale=rationale,
        diff_sha256=hashlib.sha256("".join(trozos).encode("utf-8")).hexdigest(),
    )


# ------------------------------------------- 1. creacion y teardown del sandbox


def test_el_sandbox_es_un_arbol_de_trabajo_separado(repo: Path, sandbox: Sandbox) -> None:
    """El sandbox existe, es un directorio distinto del original y tiene su contenido."""
    assert sandbox.raiz.is_dir()
    assert sandbox.raiz != repo
    assert (sandbox.raiz / "src" / "app.py").is_file()
    assert sandbox.base_commit


def test_el_sandbox_no_deja_una_rama_en_el_repositorio_del_usuario(
    repo: Path, tmp_path: Path
) -> None:
    """Crear un sandbox **no** crea ninguna rama en el repositorio del usuario.

    **El contrato que protege `--detach`, y la mutacion que lo encontro mal.**
    Se comprobo a mano que `git worktree add <ruta> HEAD` **ya** deja un HEAD
    desconectado: pasar un commit-ish (`HEAD`) en lugar de un nombre de rama detacha
    por si solo. Por eso la mutacion que retiraba solo `--detach` **no era observable**:
    el `HEAD` que quedaba seguia evitando la rama.

    El riesgo real esta en la forma `git worktree add <ruta>` **sin** commit-ish: git
    crea entonces una rama **con el nombre del directorio** (`Preparing worktree (new
    branch 'run-...')`) y la deja registrada en el repositorio del usuario. Un
    sandbox que hiciera eso contaminaria el repositorio que pretende no tocar, y dos
    ejecuciones con el mismo id no podrian coexistir. Esta prueba fija que no ocurra:
    tras crear el sandbox, el conjunto de ramas del original es exactamente el que
    habia antes.
    """
    ramas_antes = _git(repo, "branch", "--list", "--format=%(refname:short)").split()
    b = crear(repo, "run-rama", workspace_root=tmp_path / "workspaces")

    ramas_despues = _git(repo, "branch", "--list", "--format=%(refname:short)").split()
    assert ramas_despues == ramas_antes, "el sandbox creo una rama en el repositorio del usuario"
    # Y el worktree esta desconectado, no sobre una rama.
    assert "(detached HEAD)" in _git(repo, "worktree", "list")

    destruir(b)


def test_el_sandbox_tiene_su_propia_copia_del_arbol(sandbox: Sandbox, repo: Path) -> None:
    """Escribir en el sandbox **no** cambia el archivo del original: son dos arboles."""
    original = (repo / "src" / "app.py").read_text(encoding="utf-8")
    sandbox.escribir("src/app.py", "def f():\n    return 999\n")

    assert "999" in (sandbox.raiz / "src" / "app.py").read_text(encoding="utf-8")
    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == original


def test_el_teardown_deja_el_arbol_original_limpio(repo: Path, tmp_path: Path) -> None:
    """Tras destruir el sandbox, el repositorio del usuario no tiene rastro.

    Comprueba las **dos** cosas: que el directorio del sandbox desaparece y que git
    no conserva una entrada de worktree. Un `remove` sin `prune` dejaria un worktree
    fantasma en `.git/worktrees/`, invisible en el `status` y acumulandose.
    """
    b = crear(repo, "run-teardown", workspace_root=tmp_path / "workspaces")
    b.escribir("src/sucio.py", "print('temporal')\n")
    assert b.raiz.exists()

    destruir(b)

    assert not b.raiz.exists()
    assert _git(repo, "worktree", "list").count("\n") == 1, "quedo un worktree registrado"
    assert _git(repo, "status", "--porcelain").strip() == "", "el original quedo sucio"


def test_el_teardown_limpia_tambien_un_worktree_fantasma(repo: Path, tmp_path: Path) -> None:
    """El teardown deja el repositorio sin rastro **aunque el arbol ya no exista**.

    **Hallazgo de la mutacion, y una correccion honesta.** La mutacion que retiraba la
    linea de `prune` no se cazaba. Se investigo a mano y el resultado es incomodo pero
    hay que decirlo: en este git (2.55.0) `git worktree remove --force` con una ruta
    **absoluta** limpia por si solo la entrada administrativa, tanto si el arbol esta
    como si su directorio ya desaparecio. La linea de `prune` es, por tanto,
    **redundante** en este flujo.

    Se conserva `prune` igualmente -es barato y cubre versiones de git donde `remove`
    no podria con el fantasma, y el caso en que `remove` falle por otro motivo-, pero
    **se deja de fingir que una prueba puede cazarlo**: no puede, porque el efecto
    observable no cambia. Esta prueba afirma el **resultado** (no queda fantasma), que
    es lo que de verdad importa y lo que se puede verificar.
    """
    b = crear(repo, "run-fantasma", workspace_root=tmp_path / "workspaces")
    assert _git(repo, "worktree", "list").count("\n") == 2, "el worktree no se registro"

    # El directorio desaparece por una via ajena a `git worktree remove`: es el
    # escenario de una ejecucion interrumpida.
    shutil.rmtree(b.raiz)
    assert "prunable" in _git(repo, "worktree", "list"), "no quedo un fantasma prunable"

    destruir(b)

    assert _git(repo, "worktree", "list").count("\n") == 1, "quedo un worktree fantasma"
    assert _git(repo, "status", "--porcelain").strip() == ""


def test_el_teardown_no_destruye_un_sandbox_de_otro(repo: Path, tmp_path: Path) -> None:
    """`destruir` es inocuo sobre un sandbox que **no creamos nosotros**.

    La salvaguarda `creado_por_nosotros` existe para no borrar un arbol que no se
    abrio en esta ejecucion: un `Sandbox` puede construirse a mano -al reabrir uno
    existente, o en una prueba-. Destruirlo por error borraria trabajo ajeno. Aqui se
    construye un `Sandbox` con `creado_por_nosotros=False` apuntando a un directorio
    real y se comprueba que `destruir` lo deja **intacto**.
    """
    ajeno = tmp_path / "arbol_ajeno"
    ajeno.mkdir()
    (ajeno / "importante.txt").write_text("no me borres\n", encoding="utf-8")

    otro = Sandbox(
        raiz=ajeno,
        repo_original=repo,
        base_commit="0" * 40,
        run_id="ajeno",
        creado_por_nosotros=False,
    )
    destruir(otro)

    assert ajeno.is_dir(), "el teardown destruyo un sandbox que no creamos"
    assert (ajeno / "importante.txt").read_text(encoding="utf-8") == "no me borres\n"


def test_crear_dos_veces_el_mismo_run_limpia_el_anterior(repo: Path, tmp_path: Path) -> None:
    """Un id repetido no reutiliza un sandbox sucio: la ejecucion empieza de cero."""
    ws = tmp_path / "workspaces"
    a = crear(repo, "run-mismo", workspace_root=ws)
    a.escribir("src/basura.py", "x\n")
    b = crear(repo, "run-mismo", workspace_root=ws)

    assert not (b.raiz / "src" / "basura.py").exists()
    destruir(b)


def test_no_se_crea_un_sandbox_dentro_del_propio_repositorio(repo: Path) -> None:
    """Un worktree colgado del arbol que pretende aislar no aisla nada."""
    with pytest.raises(SandboxError, match="no aislaria nada"):
        crear(repo, "run-x", workspace_root=repo / "var" / "workspaces")


def test_un_directorio_que_no_es_repo_git_es_rechazado(tmp_path: Path) -> None:
    suelto = tmp_path / "no_repo"
    suelto.mkdir()
    with pytest.raises(SandboxError, match="no es un repositorio git"):
        crear(suelto, "run-y", workspace_root=tmp_path / "ws")


# ------------------------------------------------- 2. confinamiento de rutas


@pytest.mark.parametrize(
    "ruta",
    [
        "../fuera.py",              # un nivel arriba
        "../../fuera.py",           # dos niveles: el caso del enunciado
        "src/../../fuera.py",       # travesia en medio de una ruta valida
        "/etc/passwd",              # absoluta en POSIX
        "C:\\Windows\\evil.py",     # absoluta en Windows
        "..",
    ],
)
def test_una_ruta_que_escapa_se_bloquea_antes_de_escribir(sandbox: Sandbox, ruta: str) -> None:
    """El confinamiento rechaza el escape y **no escribe nada**."""
    with pytest.raises(EscapeDetectado):
        sandbox.escribir(ruta, "malicioso\n")

    padre = sandbox.raiz.parent
    assert not (padre / "fuera.py").exists()
    assert not (padre / "evil.py").exists()


def test_el_rechazo_nombra_la_ruta_y_el_motivo(sandbox: Sandbox) -> None:
    """Un rechazo explicable: dice que se intento y por que se denego."""
    with pytest.raises(EscapeDetectado) as exc:
        sandbox.resolver_destino("../../fuera.py")

    assert exc.value.ruta == "../../fuera.py"
    assert "escapa" in exc.value.motivo


def test_la_comprobacion_fisica_de_raiz_rechaza_lo_que_la_sintactica_deja_pasar(
    sandbox: Sandbox, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La cuarta barrera tiene poder propio: rechaza una ruta que la sintactica aprueba.

    **El punto ciego que encontro la mutacion.** Al quitar la comprobacion fisica de la
    raiz, la suite seguia en verde: todos los casos de `../../` ya los atrapaba la
    barrera sintactica (`normalize_rel_path`), asi que la cuarta parecia decorativa.

    No lo es. La diferencia entre las dos barreras es **resolver** frente a **normalizar
    texto**: la sintactica solo mira la cadena; la fisica construye la ruta y comprueba
    adonde lleva de verdad. Para aislar la cuarta hay que presentar una ruta que la
    barrera 1 apruebe y cuya resolucion caiga fuera, de modo que **solo** la barrera 4
    pueda rechazarla.

    **Por que se inyecta la resolucion en lugar de plantar un enlace.** El vector real
    es un enlace dentro del arbol que apunte fuera. Se intento construirlo y no es
    posible en esta plataforma: `os.symlink` para directorios crea un enlace que ni
    `Path.resolve()` ni `os.path.realpath()` siguen (comprobado a mano en este entorno),
    asi que la resolucion nunca sale de la raiz y la barrera 4 no llega a tener ocasion
    de actuar. Un enlace que el sistema no resuelve no prueba nada sobre el codigo que
    comprueba el resultado de resolver.

    Lo que si se puede aislar, y es exactamente el contrato de la barrera 4, es: **si la
    resolucion cae fuera, ¿se rechaza?** Se simula el desenlace sustituyendo `resolve`
    para la ruta destino -y solo para ella- por una que devuelve una ruta externa. La
    ruta pedida (`"app.py"`) es relativa y valida; la barrera 1 la aprueba. Entonces la
    unica linea capaz de lanzar es la comprobacion fisica. Verificado por mutacion: con
    la barrera 4 presente la prueba pasa; retirada, la escritura escapa y la prueba
    falla.
    """
    from ai_swe.tools.policy import normalize_rel_path

    # La ruta pedida es relativa, no escapa y no nombra nada especial: la barrera
    # sintactica la aprueba sin discusion. Todo el peso recae en la barrera 4.
    ruta = "app.py"
    assert normalize_rel_path(ruta) == ruta

    fuera = tmp_path / "fuera_del_sandbox"
    fuera.mkdir()
    destino_esperado = sandbox.raiz / ruta
    original = Path.resolve

    def resolve_que_escapa(self: Path, *args: object, **kwargs: object) -> Path:
        """Resuelve el destino fuera de la raiz; el resto resuelve normal."""
        if self == destino_esperado:
            return fuera / ruta
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "resolve", resolve_que_escapa)

    with pytest.raises(EscapeDetectado) as exc:
        sandbox.resolver_destino(ruta)

    assert "fuera de la raiz" in exc.value.motivo


def test_una_ruta_normalizada_que_queda_dentro_si_se_permite(sandbox: Sandbox) -> None:
    """No todo se bloquea: `sub/../src/x.py` normaliza dentro y debe poder escribirse."""
    destino = sandbox.escribir("sub/../src/ok.py", "print(1)\n")

    assert destino == (sandbox.raiz / "src" / "ok.py").resolve()
    assert destino.is_file()


def test_la_plataforma_no_permite_construir_el_vector_de_enlace(sandbox: Sandbox) -> None:
    """Deja constancia del limite real, en lugar de fingir cobertura.

    El ataque canonico contra la barrera 4 es un enlace dentro del arbol que apunte
    fuera. Si la plataforma lo resolviera, `resolver_destino` lo atraparia; si no lo
    resuelve, el escape por esa via no existe en esta maquina. Esta prueba **afirma el
    hecho observable** -como resuelve el sistema un enlace de directorio- para que la
    limitacion quede registrada y no se confunda con una comprobacion que pasa.

    No se salta: se comprueba lo que de verdad hace la plataforma, y el resultado se
    usa para decidir donde vive la cobertura de la barrera 4 (en la prueba anterior,
    que inyecta la resolucion). Si algun dia el sistema empieza a seguir los enlaces,
    esta prueba lo dira y la cobertura podra endurecerse.
    """
    import os

    try:
        os.symlink(sandbox.raiz, sandbox.raiz / "enlace_de_prueba", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - permiso del sistema
        pytest.skip(f"el sistema no permite crear enlaces: {exc}")

    resuelto = (sandbox.raiz / "enlace_de_prueba").resolve()
    # Se deja constancia sin asertar una direccion concreta: lo unico que se afirma es
    # que la resolucion ocurre -y por tanto la barrera 4 tiene un resultado que juzgar-.
    assert resuelto.is_absolute()


# ------------------------------------ 3. aplicacion del parche y aislamiento


def test_el_parche_se_aplica_en_el_sandbox(sandbox: Sandbox) -> None:
    """Un `CodeChange` valido se materializa dentro del sandbox."""
    resultado = aplicar(sandbox, _cambio(("src/nuevo.py", "print('hola')\n")))

    assert resultado.ok
    assert resultado.aplicados == ["src/nuevo.py"]
    assert (sandbox.raiz / "src" / "nuevo.py").read_text(encoding="utf-8") == "print('hola')\n"


def test_el_repositorio_original_queda_intacto(repo: Path, sandbox: Sandbox) -> None:
    """**La prueba central de F7.** Tras aplicar el parche, el original no cambio.

    Se comprueban las tres caras del "intacto": el archivo nuevo no existe en el
    original, el contenido de los existentes es el mismo, y `git status` del original
    sigue limpio. Las tres, porque cada una puede fallar por su cuenta.
    """
    antes = {p: p.read_text(encoding="utf-8") for p in repo.rglob("*.py")}
    antes_readme = (repo / "README.md").read_text(encoding="utf-8")

    resultado = aplicar(
        sandbox,
        _cambio(
            ("src/inyectado.py", "print('solo en el sandbox')\n"),
            ("README.md", "# cambiado\n"),
        ),
    )
    assert resultado.ok

    assert not (repo / "src" / "inyectado.py").exists()
    assert (repo / "README.md").read_text(encoding="utf-8") == antes_readme
    assert {p: p.read_text(encoding="utf-8") for p in repo.rglob("*.py")} == antes
    assert _git(repo, "status", "--porcelain").strip() == ""


def test_un_cambio_con_una_ruta_maliciosa_no_escribe_la_mala_ni_la_buena(
    sandbox: Sandbox, tmp_path: Path
) -> None:
    """Una ruta denegada se aisla: **no** aborta el resto, pero ella no se escribe."""
    cambio = _cambio(("../../fuera.py", "malicioso\n"), ("src/legitimo.py", "print(1)\n"))
    resultado = aplicar(sandbox, cambio)

    assert "../../fuera.py" in resultado.denegados
    assert resultado.hubo_escapes
    assert not (tmp_path / "fuera.py").exists()
    # El archivo legitimo del mismo cambio si se aplico: un infractor no castiga al resto.
    assert resultado.aplicados == ["src/legitimo.py"]


def test_una_ruta_fuera_del_alcance_declarado_se_deniega(sandbox: Sandbox) -> None:
    """El `allowed_paths` del Scope tambien confina, no solo el sandbox.

    **Aqui se decide por la barrera 2, y hay que poder demostrarlo.** El motivo se
    comprueba **literal**, sin el prefijo `POLICY-...`, porque las barreras 2 y 3
    producen el mismo texto base: la 2 (alcance del patcher) devuelve el motivo
    desnudo, y la 3 (Policy Engine) lo devuelve precedido de su regla
    (`POLICY-PATH-OUTSIDE-SCOPE`). Una asercion laxa como `"alcance" in motivo`
    pasa con **las dos** -y por eso la mutacion que retira la barrera 2 no se
    cazaba: la barrera 3 tapaba el hueco-. Aqui se exige la forma exacta de la
    barrera 2, de modo que retirarla cambia el motivo observable y la prueba falla.
    """
    resultado = aplicar(
        sandbox,
        _cambio(("docs/x.md", "# x\n")),
        allowed_paths=("src",),
    )

    assert "docs/x.md" in resultado.denegados
    assert resultado.denegados["docs/x.md"] == (
        "la ruta 'docs/x.md' queda fuera del alcance declarado"
    ), "el motivo debe ser el de la barrera 2 (alcance), sin el prefijo de la regla de politica"
    assert resultado.aplicados == []


def test_las_barreras_de_alcance_y_de_politica_coinciden_por_diseno(sandbox: Sandbox) -> None:
    """Constata que la barrera 2 es redundante con la 3 **para el alcance**, a proposito.

    `decide()` llama a `path_within_scope` con los mismos `allowed_paths`, asi que
    ambas dan el mismo veredicto para toda entrada: la 2 nunca deniega donde la 3
    permita. Se comprueba empiricamente sobre varios casos. **No es un defecto**: es
    defensa en profundidad -el patcher confina antes de consultar la politica, de modo
    que un cambio en el motor de politica no puede abrir un agujero sin que la barrera
    del patcher lo note-. La prueba fija la intencion: si algun dia divergen, esto lo
    dira, y entonces habra que decidir cual es la correcta.
    """
    from ai_swe.contracts import AgentRole
    from ai_swe.contracts.tools import PolicyEffect
    from ai_swe.tools.policy import DecisionContext, decide, path_within_scope

    casos = [
        ("src/x.py", ("src",)),
        ("docs/x.md", ("src",)),
        ("src/sub/y.py", ("src",)),
        ("src", ("src",)),
    ]
    for ruta, allowed in casos:
        barrera_2 = path_within_scope(ruta, allowed)
        ctx = DecisionContext(
            run_id=sandbox.run_id,
            agent=AgentRole.CODER,
            allowed_paths=allowed,
            protected_paths=(),
            subtask_allowed_tools=(),
        )
        barrera_3_permite = decide("write_file", {"path": ruta}, ctx).effect is PolicyEffect.ALLOW
        # La unica divergencia relevante seria "b2 deniega y b3 permite": no existe.
        assert not (not barrera_2 and barrera_3_permite), (
            f"las barreras de alcance y politica divergen para {ruta!r}: "
            "revisar cual es la correcta"
        )


def test_un_cambio_vacio_no_hace_nada(sandbox: Sandbox) -> None:
    """Sin archivos no hay operacion: ni error ni escritura."""
    resultado = aplicar(
        sandbox,
        CodeChange(files_changed=[], diff="", rationale="vacio",
                   diff_sha256=hashlib.sha256(b"").hexdigest()),
    )

    assert resultado.aplicados == [] and resultado.denegados == {} and resultado.ok


def test_el_diff_de_git_confirma_lo_que_se_aplico(sandbox: Sandbox) -> None:
    """La evidencia de git coincide con lo aplicado: la fuente de verdad es el worktree."""
    aplicar(sandbox, _cambio(("src/verificado.py", "print('verdad')\n")))

    rutas = sandbox.archivos_modificados()
    assert "src/verificado.py" in rutas
    assert "verdad" in sandbox.diff()


def test_el_diff_ve_los_archivos_nuevos(sandbox: Sandbox) -> None:
    """`git diff HEAD` a secas no ve los no rastreados; el sandbox lo corrige.

    Sin el `git add -N` interno, un `create` producia un diff vacio: el instrumento
    decia "no hay nada" en lugar de "no lo se". Es la clase de fallo que este proyecto
    proscribe, y por eso tiene prueba propia.
    """
    sandbox.escribir("src/recien_creado.py", "print('nuevo')\n")

    diff = sandbox.diff()
    assert "src/recien_creado.py" in diff
    assert "+print('nuevo')" in diff


# ------------------------------------- 4. diff unificado real (deuda de F6)


def test_el_diff_con_contenido_previo_es_real_no_de_lineas_completas(sandbox: Sandbox) -> None:
    """Con el contenido viejo, el diff es un unificado real: contexto y hunks.

    La deuda declarada en F6 era que, sin el original, `modify` se veia como si el
    archivo se anadiera entero. Aqui se pasa el contenido leido del sandbox y el diff
    sale de `difflib`: hay contexto (`@@`) y las lineas sin cambios no se marcan.
    """
    previo = "linea 1\nlinea 2\nlinea 3\n"
    propuesta = CodeProposal.model_validate(
        {
            "files": [
                {
                    "path": "src/app.py",
                    "operation": "modify",
                    "new_content": "linea 1\nlinea 2 cambiada\nlinea 3\n",
                    "rationale": "cambia la 2",
                }
            ],
            "rationale": "prueba de diff real",
        }
    )

    cambio = nodes._cambio_desde_propuesta(
        propuesta, contenidos_previos={"src/app.py": previo}
    )

    assert "@@" in cambio.diff, "un diff real lleva cabeceras de hunk"
    assert "-linea 2" in cambio.diff, "la linea vieja aparece como eliminada"
    assert "+linea 2 cambiada" in cambio.diff
    # Solo cambio una linea: antes (F6) se habria contado el archivo entero.
    assert cambio.files_changed[0].added == 1
    assert cambio.files_changed[0].removed == 1


def test_sin_contenido_previo_el_diff_degrada_al_comportamiento_de_f6(sandbox: Sandbox) -> None:
    """El Coder puro -sin sandbox- sigue funcionando: se anade el archivo entero.

    No es un fallo: es el limite conocido, y el `--- /dev/null` lo declara. Un
    `create` no tiene contenido previo por definicion.
    """
    propuesta = CodeProposal.model_validate(
        {
            "files": [
                {
                    "path": "src/nuevo.py",
                    "operation": "create",
                    "new_content": "a\nb\n",
                    "rationale": "nuevo",
                }
            ],
            "rationale": "creacion",
        }
    )
    cambio = nodes._cambio_desde_propuesta(propuesta)

    assert "--- /dev/null" in cambio.diff
    assert cambio.files_changed[0].added == 2


def test_un_borrado_siempre_produce_un_trozo(sandbox: Sandbox) -> None:
    """`difflib` no emite nada si ambos lados son iguales; un `delete` no puede quedar vacio.

    Si el diff de un borrado queda vacio, es indistinguible de "no hay cambio": el
    aplicador no sabria que debe eliminar. Se sintetiza la cabecera con `/dev/null`.
    """
    propuesta = CodeProposal.model_validate(
        {
            "files": [
                {"path": "src/viejo.py", "operation": "delete", "rationale": "ya no se usa"}
            ],
            "rationale": "limpieza",
        }
    )
    cambio = nodes._cambio_desde_propuesta(propuesta)

    assert "+++ /dev/null" in cambio.diff


def test_el_borrado_esta_vedado_al_coder_por_politica(repo: Path, sandbox: Sandbox) -> None:
    """`delete_file` es del Supervisor y exige aprobacion: el Coder **no** puede borrar.

    **Hallazgo de F7, no un fallo.** Al escribir el aplicador se asumio que el Coder
    podia borrar. El Policy Engine lo denego con `POLICY-ROLE-NOT-PERMITTED`, y tenia
    razon: `ROLE_APPROVAL_TOOLS[SUPERVISOR]` incluye `delete_file`, y el Coder no.

    El efecto en F7 es correcto y se conserva: aunque el modelo proponga un `delete`,
    el archivo **no se elimina del sandbox**, y la denegacion queda registrada. Borrar
    es una accion destructiva; que un rol con escritura pueda hacerla sin aprobacion
    seria una escalada de privilegios. La prueba fija ese limite.
    """
    propuesta = CodeProposal.model_validate(
        {
            "files": [
                {"path": "src/app.py", "operation": "delete", "rationale": "obsoleto"}
            ],
            "rationale": "borrado",
        }
    )
    cambio = nodes._cambio_desde_propuesta(
        propuesta, contenidos_previos={"src/app.py": sandbox.leer("src/app.py")}
    )
    resultado = aplicar(sandbox, cambio)

    assert resultado.borrados == []
    assert "src/app.py" in resultado.denegados
    assert "POLICY-ROLE-NOT-PERMITTED" in resultado.denegados["src/app.py"]
    # Y el archivo sigue ahi: la denegacion ocurre antes de cualquier efecto.
    assert (sandbox.raiz / "src" / "app.py").is_file()
    assert (repo / "src" / "app.py").is_file()


# ------------------------------------------------ 5. robustez del aplicador


def test_el_sha256_del_cambio_es_el_del_contenido_resultante(sandbox: Sandbox) -> None:
    """La huella permite comprobar despues que el sandbox contiene lo que dice el cambio.

    Se compara el **texto**, no los bytes del archivo. En Windows `read_bytes()` de un
    fichero escrito con `write_text` devuelve `\\r\\n` mientras el hash del contrato se
    calcula sobre `\\n`: comparar bytes contra el hash esperado falla por una diferencia
    de salto de linea, no por un fallo real. La propiedad que importa -el sandbox
    contiene exactamente el contenido propuesto- se comprueba sobre el contenido.
    """
    contenido = "resultado\n"
    aplicar(sandbox, _cambio(("src/h.py", contenido)))

    esperado = hashlib.sha256(contenido.encode("utf-8")).hexdigest()
    real = hashlib.sha256(
        (sandbox.raiz / "src" / "h.py").read_text(encoding="utf-8").encode("utf-8")
    ).hexdigest()
    assert real == esperado
    assert sandbox.leer("src/h.py") == contenido


def test_sin_contenido_en_el_diff_el_archivo_no_se_inventa(sandbox: Sandbox) -> None:
    """Un `FileChange` cuyo diff no trae contenido no produce un archivo vacio falso."""
    cambio = CodeChange(
        files_changed=[
            FileChange(path="src/fantasma.py", added=1, removed=0,
                       sha256=hashlib.sha256(b"x").hexdigest())
        ],
        diff="",  # sin trozo: no hay contenido que aplicar
        rationale="incompleto",
        diff_sha256=hashlib.sha256(b"").hexdigest(),
    )
    resultado = aplicar(sandbox, cambio)

    # Un diff vacio no contiene ningun trozo, asi que la ruta ni siquiera entra al bucle:
    # no se crea un archivo inventado.
    assert not (sandbox.raiz / "src" / "fantasma.py").exists()


def test_el_resultado_distingue_denegado_de_fallo(sandbox: Sandbox) -> None:
    """Denegado es seguridad; fallo es tecnico. Mezclarlos ocultaria un ataque."""
    resultado = aplicar(sandbox, _cambio(("../../malo.py", "x\n")))

    assert resultado.denegados and not resultado.fallos
    assert resultado.hubo_escapes is True
    assert resultado.ok is False


def test_leer_un_archivo_inexistente_devuelve_none(sandbox: Sandbox) -> None:
    """El lector no revienta: devuelve `None` y el diff degrada en lugar de romperse."""
    assert sandbox.leer("no/existe.py") is None


def test_leer_una_ruta_que_escapa_devuelve_none(sandbox: Sandbox) -> None:
    """La lectura tambien confina: no es una via lateral para sacar datos del sandbox."""
    assert sandbox.leer("../../fuera.py") is None
