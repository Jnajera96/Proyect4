"""Sandbox de ejecucion: un worktree de git aislado por Run (F7).

**El problema que resuelve.** En F6 el Coder propone un `CodeChange` pero no escribe
nada: el parche vive en el estado. F7 lo aplica **en algun sitio**, y ese sitio no
puede ser el repositorio del usuario. Un agente que escribe en el arbol real antes de
que nadie revise convierte cualquier error del modelo en dano irreversible.

**La solucion.** Un `git worktree` por ejecucion, bajo `workspace_root`
(`var/workspaces/<run_id>`), que es una ruta **ignorada por el repositorio**
(`.gitignore` ancla `/var/`). El worktree comparte el historial de git pero tiene su
propio arbol de trabajo: los archivos se modifican ahi, y el repositorio original no
se toca. `git worktree` es preferible a clonar porque no copia el historial entero ni
duplica el `.git`.

**Por que `detached HEAD`.** El worktree se crea con `--detach` en la confirmacion
actual. Una rama con nombre permitiria a una ejecucion dejar una rama suelta en el
repositorio del usuario, y dos ejecuciones simultaneas no pueden tener la misma rama
"cogida" a la vez. Detached no nombra nada y no colisiona.

**Invariante de aislamiento.** Toda ruta bajo la que se escribe pasa por
`resolver_destino`, que confina con `normalize_rel_path` (Policy Engine) **y** comprueba
que el resultado sigue dentro de la raiz del sandbox. Son dos barreras distintas: la
primera rechaza `..` y rutas absolutas tal como vienen; la segunda atrapa cualquier
cosa que se escape por otra via -por ejemplo, un enlace simbolico, o una ruta que la
primera dejo pasar y que el sistema de archivos resolveria fuera-.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ai_swe.tools.policy import normalize_rel_path

log = logging.getLogger(__name__)

# Identidad que se usa para las confirmaciones dentro del worktree. No depende de la
# configuracion global de git del usuario: una ejecucion no debe fallar porque a nadie
# se le ocurrio configurar user.email en la maquina.
_IDENTIDAD = (
    "-c",
    "user.name=AI SWE",
    "-c",
    "user.email=ai-swe@localhost",
)

# Limite de tiempo para las operaciones de git. Un `git worktree` sobre un repositorio
# grande no deberia tardar mas; si lo hace, algo va mal y es mejor fallar que colgarse.
_TIEMPO_GIT_S = 120.0


class SandboxError(RuntimeError):
    """Fallo al crear, usar o destruir el sandbox.

    Es una excepcion **tipada y accionable**: nombra la operacion que fallo y por que.
    El nodo que la capture debe degradar a un error declarado, nunca a un parche
    aplicado a medias.
    """

    def __init__(self, operacion: str, detalle: str) -> None:
        self.operacion = operacion
        super().__init__(f"sandbox: fallo en '{operacion}' ({detalle})")


class EscapeDetectado(SandboxError):
    """La ruta pedida escaparia del sandbox. **Se deniega antes de escribir.**

    Se separa de `SandboxError` a proposito: no es un fallo tecnico, es una negativa
    de seguridad. Quien la capture debe registrarla como tal -un evento de politica-,
    no como una averia.
    """

    def __init__(self, ruta: str, motivo: str) -> None:
        self.ruta = ruta
        self.motivo = motivo
        super().__init__("confinamiento", f"la ruta '{ruta}' {motivo}")


def git(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
    entrada: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Ejecuta git de verdad. `shell=False` siempre: sin comandos construidos por texto.

    `entrada` se entrega por la **entrada estandar** del proceso, que es la forma de
    aplicar un parche (`git apply -`) sin escribir un fichero temporal. Sigue sin
    haber `shell=True`: el parche viaja como **dato**, nunca como parte de la orden.
    """
    orden = ["git", *args]
    try:
        result = subprocess.run(
            orden,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            # Binary pipes preserve patch bytes: text mode translates LF to
            # CRLF on Windows and normalizes CRLF content in git diff output.
            input=(
                entrada.encode("utf-8", errors="surrogateescape") if entrada is not None else None
            ),
            timeout=_TIEMPO_GIT_S,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise SandboxError(
            "git", f"no se encontro el ejecutable 'git' o el directorio '{cwd}' no existe"
        ) from exc
    except OSError as exc:
        # Un `cwd` que no es un directorio (p. ej. el repositorio se borro a mitad de
        # la ejecucion) lanza `NotADirectoryError` en Windows, que **no** es
        # `FileNotFoundError`. Sin esta rama, el teardown de `finalize` propagaba una
        # traza y tumbaba una ejecucion que por lo demas iba bien.
        raise SandboxError(
            "git", f"no se pudo ejecutar git (cwd={cwd}): {type(exc).__name__}: {exc}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SandboxError("git", f"'{' '.join(orden)}' supero {_TIEMPO_GIT_S}s") from exc

    result = subprocess.CompletedProcess(
        result.args,
        result.returncode,
        stdout=result.stdout.decode("utf-8", errors="surrogateescape"),
        stderr=result.stderr.decode("utf-8", errors="surrogateescape"),
    )
    if check and result.returncode != 0:
        detalle = (result.stderr or result.stdout or "").strip()[:300]
        raise SandboxError("git", f"'{' '.join(orden)}' salio {result.returncode}: {detalle}")
    return result


# Alias interno historico. El resto del modulo lo usa; se conserva para no tocar
# cada llamada, pero la funcion publica es `git` (la usa tambien `tools/promoter.py`).
_git = git


@dataclass(frozen=True)
class Sandbox:
    """Un worktree aislado y listo para recibir parches.

    `raiz` es la ruta del arbol de trabajo del worktree. `base_commit` es la
    confirmacion sobre la que se creo, y se guarda para poder decir de donde parte
    el cambio y para poder comparar despues.
    """

    raiz: Path
    repo_original: Path
    base_commit: str
    run_id: str
    creado_por_nosotros: bool

    # ------------------------------------------------------------ confinamiento
    def resolver_destino(self, ruta_relativa: str) -> Path:
        """Ruta absoluta dentro del sandbox, o `EscapeDetectado`.

        **Dos barreras, no una.**

        1. `normalize_rel_path` (la misma funcion del Policy Engine) rechaza rutas
           absolutas, unidades de Windows y cualquier `..` que salga por arriba.
        2. Se comprueba que la ruta resuelta siga **dentro** de `raiz`. Es la
           comprobacion que atrapa lo que la primera no ve: enlaces simbolicos, o
           una ruta que normaliza a algo valido pero que el sistema de archivos
           llevaria fuera.

        La segunda barrera es la que importa de verdad. La primera puede tener un
        punto ciego -toda validacion sintactica lo tiene-; la segunda es fisica:
        compara rutas ya resueltas contra la raiz.
        """
        normalizada = normalize_rel_path(ruta_relativa)
        if normalizada is None:
            raise EscapeDetectado(
                ruta_relativa, "es absoluta o escapa del area de trabajo autorizada"
            )
        if not normalizada:
            raise EscapeDetectado(ruta_relativa, "no nombra ningun archivo")

        destino = (self.raiz / normalizada).resolve()
        # `raiz.resolve()` tambien, porque en Windows la raiz temporal puede pasar por
        # un nombre corto (8.3) y la comparacion de prefijos fallaria por eso.
        raiz_resuelta = self.raiz.resolve()
        if destino != raiz_resuelta and raiz_resuelta not in destino.parents:
            raise EscapeDetectado(
                ruta_relativa, "resuelve fuera de la raiz del sandbox"
            )
        return destino

    def escribir(self, ruta_relativa: str, contenido: str) -> Path:
        """Escribe un archivo dentro del sandbox tras confinar la ruta.

        **El confinamiento ocurre antes de cualquier efecto.** La ruta se valida
        entera -normalizacion y comprobacion fisica- y solo despues se crea el
        directorio padre y se escribe. No hay ninguna ventana en la que una ruta sin
        validar llegue al sistema de archivos.

        **Un fallo del sistema de archivos se envuelve en `SandboxError`.** No
        basta con confinar la ruta: escribir puede fallar por causas que no son de
        seguridad -un directorio padre que es un archivo, disco lleno, permisos-.
        Si ese `OSError` escapara crudo, el llamante (`patcher.aplicar`) no lo
        capturaria -solo captura `SandboxError`- y la excepcion subiria hasta
        LangGraph, tumbando la ejecucion con una traza en lugar de registrarse como
        un `fallo` tipado. Se envuelve **aqui**, en el borde del efecto, que es
        donde se sabe que la operacion era escribir.
        """
        destino = self.resolver_destino(ruta_relativa)
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(contenido, encoding="utf-8", newline="")
        except OSError as exc:
            raise SandboxError(
                "escribir",
                f"no se pudo escribir '{ruta_relativa}' en el sandbox: "
                f"{type(exc).__name__}: {exc}",
            ) from exc
        return destino

    def leer(self, ruta_relativa: str) -> str | None:
        """Contenido actual de un archivo del sandbox. `None` si no existe.

        Es lo que permite que F7 genere un **diff unificado real**: aqui esta el
        contenido viejo que en F6 no se tenia. Un binario o un archivo ilegible se
        trata como ausente en lugar de reventar: el diff degrada, el parche no.
        """
        try:
            destino = self.resolver_destino(ruta_relativa)
        except EscapeDetectado:
            return None
        if not destino.is_file():
            return None
        try:
            return destino.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            return None

    def eliminar(self, ruta_relativa: str) -> bool:
        """Elimina un archivo del sandbox tras confinar la ruta. `False` si no existia."""
        destino = self.resolver_destino(ruta_relativa)
        if not destino.is_file():
            return False
        destino.unlink()
        return True

    # -------------------------------------------------------------- observacion
    def diff(self) -> str:
        """Diff real del worktree contra su base, segun git.

        Es la fuente de verdad de lo que el sandbox contiene, independiente de lo que
        crea el nodo que aplico los cambios. Se usa para verificar, no para informar.

        **`git add -N` antes del diff, y no es opcional.** `git diff HEAD` **no ve los
        archivos nuevos**: un `create` recien escrito aparece como un diff vacio. Se
        comprobo en este entorno y es la peor clase de fallo -el instrumento no dice
        "no lo se", dice "no hay nada"-. `-N` (intent-to-add) registra la intencion
        sin preparar el contenido, y entonces el archivo nuevo si entra al diff. No
        altera lo que se confirma: no hay `git commit` aqui.
        """
        _git("add", "-N", "--", ".", cwd=self.raiz, check=False)
        changed = _git("diff", "HEAD", "--name-only", "-z", cwd=self.raiz, check=False)
        rutas = [ruta for ruta in (changed.stdout or "").split("\0") if ruta]
        if not rutas:
            return ""
        # Ignore untouched checkout CRLF while preserving bytes of the actual changes.
        result = _git("-c", "core.autocrlf=false", "diff", "HEAD", "--no-color", "--", *rutas,
                      cwd=self.raiz, check=False)
        return result.stdout or ""

    def archivos_modificados(self) -> list[str]:
        """Rutas relativas que git ve cambiadas respecto a la base."""
        result = _git(
            "status", "--porcelain", "--untracked-files=all", cwd=self.raiz, check=False
        )
        rutas: list[str] = []
        for linea in (result.stdout or "").splitlines():
            if len(linea) > 3:
                rutas.append(linea[3:].strip().strip('"'))
        return rutas


def validar_repositorio(repo: Path | str) -> Path:
    """Comprueba que la ruta es un repositorio git usable y la devuelve resuelta.

    Se extrae de `crear` para que el alta de un proyecto (F10) y la creacion del
    sandbox usen **la misma** comprobacion. Duplicarla dejaria dos definiciones de
    "repositorio valido" que pueden divergir, y la que se ejecuta antes -la del
    alta- seria la que no se prueba.

    Lanza `SandboxError`, que es el tipo que la API mapea a un 4xx estructurado.
    """
    resuelto = Path(repo).resolve()
    if not (resuelto / ".git").exists():
        raise SandboxError("validar", f"'{resuelto}' no es un repositorio git")
    return resuelto


def crear(repo: Path, run_id: str, *, workspace_root: Path) -> Sandbox:
    """Crea un worktree aislado para `run_id` a partir de `repo`.

    El destino es `workspace_root/<run_id>`. Se rechaza crear dentro del propio
    repositorio fuente: un worktree cuyo directorio cuelga del arbol que pretende
    aislar no aisla nada -el `git status` del original lo veria como sucio-.
    """
    repo = validar_repositorio(repo)

    raiz = (Path(workspace_root) / run_id).resolve()
    if raiz == repo or repo in raiz.parents:
        raise SandboxError(
            "crear",
            f"el sandbox '{raiz}' quedaria dentro del repositorio '{repo}': no aislaria nada",
        )

    # Un worktree de una ejecucion anterior con el mismo id no debe reutilizarse: la
    # ejecucion empieza de cero. Se limpia antes de crear.
    if raiz.exists():
        _quitar_worktree(repo, raiz)

    raiz.parent.mkdir(parents=True, exist_ok=True)
    base = _git("rev-parse", "HEAD", cwd=repo).stdout.strip()

    # `--detach` para no dejar una rama con nombre en el repositorio del usuario.
    _git("worktree", "add", "--detach", str(raiz), "HEAD", cwd=repo)

    log.info("sandbox creado para %s en %s (base %s)", run_id, raiz, base[:12])
    return Sandbox(
        raiz=raiz,
        repo_original=repo,
        base_commit=base,
        run_id=run_id,
        creado_por_nosotros=True,
    )


def destruir(sandbox: Sandbox, *, force: bool = True) -> None:
    """Deshace el worktree y **limpia la entrada de git** en el repositorio original.

    Es el teardown. Importa que sea completo: `git worktree remove` deja el arbol si
    hay cambios sin confirmar, y `git worktree prune` es lo que finalmente borra la
    referencia administrativa en `.git/worktrees/`. Si se olvida el prune, el
    repositorio del usuario acumula worktrees fantasma ejecucion tras ejecucion.

    No propaga errores: el teardown corre en un `finally` y un fallo al limpiar no
    debe tapar el resultado real de la ejecucion. Se registra.
    """
    if not sandbox.creado_por_nosotros:
        return
    orden = ["worktree", "remove"]
    if force:
        orden.append("--force")
    orden.append(str(sandbox.raiz))
    try:
        _git(*orden, cwd=sandbox.repo_original, check=False)
        _git("worktree", "prune", cwd=sandbox.repo_original, check=False)
        if sandbox.raiz.exists():
            shutil.rmtree(sandbox.raiz, ignore_errors=True)
    except SandboxError as exc:  # pragma: no cover - depende del sistema de archivos
        log.warning("no se pudo destruir el sandbox %s: %s", sandbox.raiz, exc)
    else:
        log.info("sandbox destruido: %s", sandbox.raiz)


def limpiar_worktree(
    ruta: str | Path | None,
    *,
    repo_original: str | Path | None,
    run_id: str,
    base_commit: str = "",
) -> bool:
    """Destruye el worktree que declara una ejecucion. `True` si habia uno.

    **Por que esta funcion existe.** Hay **tres** caminos terminales que deben
    limpiar el worktree, y no son el mismo: el cierre normal del grafo (`finalize`),
    el **aborto** por un fallo del trabajador (`RunEngine.abortar`, que no pasa por
    `finalize`) y la **recuperacion de ejecuciones huerfanas** al arrancar. Con la
    construccion del `Sandbox` repetida en los tres sitios, el dia que uno se
    olvidara quedaria un worktree vivo sin que nada lo dijera. Aqui hay una sola.

    Devuelve `False` -sin intentar nada- si no hay ruta de worktree o si no hay
    repositorio con el que operar: `git worktree remove` sin `cwd` valido correria en
    el directorio equivocado, que es peor que no limpiar.
    """
    if not ruta or not repo_original:
        return False
    sandbox = Sandbox(
        raiz=Path(ruta),
        repo_original=Path(repo_original),
        base_commit=base_commit,
        run_id=run_id,
        creado_por_nosotros=True,
    )
    destruir(sandbox)
    return True


def _quitar_worktree(repo: Path, raiz: Path) -> None:
    """Quita un worktree previo antes de recrear. Best-effort y registrado."""
    _git("worktree", "remove", "--force", str(raiz), cwd=repo, check=False)
    _git("worktree", "prune", cwd=repo, check=False)
    if raiz.exists():
        shutil.rmtree(raiz, ignore_errors=True)
