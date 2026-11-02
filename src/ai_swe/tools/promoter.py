"""Promocion de cambios aprobados: del worktree aislado al repositorio del usuario (F12).

**El problema que resuelve.** F7/F8 materializan el cambio del Coder en un `git
worktree` aislado y F9 lo revisa con evidencia real, pero hasta F12 el cambio
**nunca llegaba al repositorio del usuario**: la ejecucion terminaba y el parche se
quedaba en el worktree. Aprobar no promovia nada. Este modulo cierra ese ultimo
tramo, y solo cuando un humano lo ha decidido de forma explicita.

**Invariante central: el repositorio del usuario no se toca sin una aprobacion
explicita.** La funcion de este modulo (`promover`) **solo** la llama el nodo
`promote_changes`, al que el grafo solo llega desde `approval_gate` con una
`ApprovalDecision.APPROVED` registrada. No hay ninguna otra arista que la alcance.

**Determinismo y sin `shell=True`.** La promocion no reimplementa el parche: toma
el diff **real** que el worktree ya contiene (`git diff HEAD`, el mismo que se
reviso y se probo) y lo aplica con `git apply`. Todos los comandos de git se
ejecutan como **lista de argumentos** con `shell=False`; nada se construye por
concatenacion de texto.

**Por que `git apply` y no una copia de archivos.** Un diff unificado describe
creaciones, modificaciones y borrados -y lo hace con la misma forma con la que git
los reproduce-. Copiar archivo a archivo perderia los borrados (un `FileChange` no
lleva la operacion) y tendria que inventar el contenido de un archivo eliminado.
`git apply --check` valida el encaje **antes** de escribir nada.

**Verificacion de integridad (SHA256).** Antes de tocar el repositorio:

  1. el parche tiene que ser **byte a byte** el que se reviso y aprobo
     (`expected_diff`), de modo que un worktree que cambio despues de la revision
     no se promueve;
  2. cada ruta se confina con las mismas funciones del Policy Engine
     (`normalize_rel_path` + `path_within_scope`) y ninguna puede ser protegida;
  3. el repositorio destino tiene que ser **el autorizado** por el usuario, no otro.

Y despues de aplicar, se comprueba que el arbol del usuario reproduce el worktree
**archivo por archivo**. Si no, se revierte: un repositorio a medias es peor que uno
sin tocar.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from ai_swe.sandbox import Sandbox, SandboxError, git
from ai_swe.tools.policy import normalize_rel_path, path_within_scope

log = logging.getLogger(__name__)


class PromotionError(SandboxError):
    """Fallo al promover. Contrato: el repositorio del usuario **no** quedo modificado.

    Se hereda de `SandboxError` a proposito: es el mismo tipo que la API ya mapea a
    un 4xx estructurado, y el nodo que lo capture degrada a un error declarado en
    lugar de tumbar la ejecucion con una traza.
    """

    def __init__(self, operacion: str, detalle: str) -> None:
        self.operacion = operacion
        super().__init__(operacion, detalle)


class PromotionDenied(PromotionError):
    """La promocion se rechaza por **politica**, no por una averia.

    Igual que `EscapeDetectado` en el sandbox: es una negativa de seguridad. Quien
    la capture debe registrarla como tal y **no** haber escrito nada.
    """

    def __init__(self, motivo: str) -> None:
        self.motivo = motivo
        super().__init__("politica", motivo)


@dataclass(frozen=True)
class PromotionResult:
    """Que paso al promover. Todo declarado, nada implicito."""

    applied: bool
    """Si el repositorio del usuario quedo modificado."""

    files: list[str] = field(default_factory=list)
    """Rutas relativas promovidas, tal como las nombra git."""

    patch_sha256: str = ""
    """SHA256 del parche aplicado. Es la huella de lo que se promovio."""

    detail: str = ""
    """Explicacion legible, sobre todo cuando `applied` es falso."""


def sha256_texto(texto: str) -> str:
    """SHA256 de un texto en UTF-8. Un solo sitio para el algoritmo."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _rutas_del_patch(sandbox: Sandbox) -> list[str]:
    """Rutas que toca el diff del worktree, **segun git**, no parseando el texto.

    Se pide `--name-only -z`: separador NUL, de modo que una ruta con espacios o
    acentos no se confunde con dos rutas. Parsear las cabeceras `diff --git` a mano
    fallaria justo en esos casos, y ademas git ya sabe la respuesta.
    """
    resultado = git("diff", "HEAD", "--name-only", "-z", cwd=sandbox.raiz, check=False)
    return [ruta for ruta in (resultado.stdout or "").split("\0") if ruta]


def _aplicar(repo: Path, parche: str, *, check: bool) -> None:
    """Aplica (o valida) el parche en el repositorio. `shell=False` siempre."""
    # Normalize existing CRLF for matching without converting approved output to CRLF.
    args = ["-c", "core.autocrlf=input", "apply"]
    if check:
        args.append("--check")
    args.append("-")
    resultado = git(*args, cwd=repo, check=False, entrada=parche)
    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout or "").strip()[:400]
        verbo = "validar" if check else "aplicar"
        raise PromotionError(
            "apply", f"no se pudo {verbo} el parche en '{repo}': {detalle}"
        )


def _contenido(ruta: Path) -> bytes | None:
    """Bytes de un archivo, o `None` si no existe. Un borrado es `None` en los dos lados."""
    try:
        return ruta.read_bytes() if ruta.is_file() else None
    except OSError:  # pragma: no cover - depende del sistema de archivos
        return None


def _verificar_reproduccion(sandbox: Sandbox, repo: Path, rutas: list[str]) -> list[str]:
    """Comprueba que el arbol del usuario reproduce el worktree, archivo por archivo.

    Devuelve las rutas que **no** coinciden (vacio = todo bien). Comparar archivo a
    archivo -y no el diff completo del repositorio- es lo que hace la comprobacion
    inmune a cambios previos que el usuario tuviera sin confirmar en otras rutas.
    """
    discrepancias: list[str] = []
    for ruta in rutas:
        if _contenido(sandbox.raiz / ruta) != _contenido(repo / ruta):
            discrepancias.append(ruta)
    return discrepancias


def promover(
    sandbox: Sandbox,
    *,
    repo_autorizado: Path | str,
    allowed_paths: tuple[str, ...] = (),
    protected_paths: tuple[str, ...] = (),
    expected_diff: str | None = None,
) -> PromotionResult:
    """Promueve el cambio del worktree al repositorio del usuario. Ver el modulo.

    `repo_autorizado` es la ruta que el **usuario** declaro (`RunOptions.repo_path`),
    no la que el worktree tenga apuntada. Se comprueba que coincidan: promover sobre
    un repositorio distinto del autorizado es exactamente el fallo que la politica
    existe para impedir.

    `expected_diff` es el diff que se reviso y aprobo (`artifacts.diff`). Si se pasa
    y el worktree ya no contiene ese mismo parche, se **deniega**: se promueve lo
    aprobado, no lo que haya en ese momento.

    Lanza `PromotionDenied` si la politica lo impide y `PromotionError` si el
    parche no encaja. En ambos casos, el repositorio del usuario no se ha tocado.
    """
    repo = Path(repo_autorizado).resolve()

    # 1. El destino tiene que ser el repositorio autorizado. Comprobacion de politica
    #    antes de leer nada mas: si no es el correcto, no hay nada que negociar.
    if sandbox.repo_original.resolve() != repo:
        raise PromotionDenied(
            f"el sandbox se creo sobre '{sandbox.repo_original}', no sobre el "
            f"repositorio autorizado '{repo}'"
        )

    parche = sandbox.diff()
    if not parche.strip():
        return PromotionResult(
            applied=False, detail="el worktree no contiene cambios que promover"
        )

    # 2. Integridad: se promueve el parche aprobado, no otro.
    parche_sha = sha256_texto(parche)
    if expected_diff is not None and parche != expected_diff:
        raise PromotionDenied(
            "el contenido del worktree no coincide con el diff revisado y aprobado "
            f"(sha256 {parche_sha[:12]} != {sha256_texto(expected_diff)[:12]})"
        )

    # 3. Confinamiento de rutas con el Policy Engine. Una ruta absoluta, fuera de
    #    alcance o protegida deniega la promocion **entera**: aplicar "el resto"
    #    dejaria un cambio a medias en el repositorio del usuario.
    rutas = _rutas_del_patch(sandbox)
    for ruta in rutas:
        normalizada = normalize_rel_path(ruta)
        if normalizada is None:
            raise PromotionDenied(
                f"la ruta '{ruta}' es absoluta o escapa del area autorizada"
            )
        if not path_within_scope(normalizada, allowed_paths):
            raise PromotionDenied(
                f"la ruta '{normalizada}' queda fuera del alcance declarado"
            )
        for protegida in protected_paths:
            p = normalize_rel_path(protegida)
            if p and (normalizada == p or normalizada.startswith(p + "/")):
                raise PromotionDenied(
                    f"la ruta '{normalizada}' esta declarada como protegida"
                )

    # 4. Validar el encaje **antes** de escribir. Si no encaja, se falla sin tocar nada.
    _aplicar(repo, parche, check=True)

    # 5. Aplicar de verdad.
    _aplicar(repo, parche, check=False)

    # 6. Verificar que el repositorio reproduce el worktree. Si no, revertir: un
    #    repositorio a medias es peor que uno sin tocar.
    discrepancias = _verificar_reproduccion(sandbox, repo, rutas)
    if discrepancias:
        resultado = git("-c", "core.autocrlf=input", "apply", "-R", "-",
                        cwd=repo, check=False, entrada=parche)
        revertido = resultado.returncode == 0
        raise PromotionError(
            "verificacion",
            "el repositorio no reprodujo el cambio promovido en "
            f"{discrepancias}; se {'revirtio' if revertido else 'intento revertir'} "
            "para no dejarlo a medias",
        )

    log.info("promocion aplicada en %s (%d archivo(s))", repo, len(rutas))
    return PromotionResult(
        applied=True,
        files=rutas,
        patch_sha256=parche_sha,
        detail=f"{len(rutas)} archivo(s) promovido(s)",
    )
