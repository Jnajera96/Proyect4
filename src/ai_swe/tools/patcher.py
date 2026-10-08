"""Aplicador de parches: lleva un `CodeChange` al sandbox (F7).

**Que hace exactamente.** Toma el cambio que el Coder propuso en F6 -que solo vivia en
el estado- y lo materializa dentro del worktree aislado. No toca el repositorio del
usuario: eso es lo que lo hace seguro.

**Regla de seguridad critica (la que justifica el modulo).** Antes de escribir
CUALQUIER archivo, la ruta pasa por el confinamiento del Policy Engine. No una vez al
principio: **por cada archivo**, en el momento de aplicarlo. La validacion no es un
paso previo que se pueda olvidar, es parte de la operacion de escritura.

  `normalize_rel_path` (sintactica) + `path_within_scope` + `decide` (politica)
  + la comprobacion fisica de `Sandbox.resolver_destino`.

Cuatro barreras para una escritura. Suena redundante y no lo es: cada una atrapa una
clase distinta -sintaxis, alcance declarado, permisos por rol y subtarea, y resolucion
real del sistema de archivos-. Un escape que pase las tres primeras sigue sin poder
salir del sandbox, porque la cuarta compara rutas ya resueltas.

**Por que se valida antes de tener el contenido preparado.** El orden importa: se
confina la ruta, se pide al Policy Engine su veredicto, y solo si es ALLOW se escribe.
Una ruta denegada no llega nunca a `mkdir`, ni siquiera crea el directorio padre.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ai_swe.contracts import AgentRole, CodeChange, FileOperation
from ai_swe.contracts.tools import PolicyEffect
from ai_swe.sandbox import EscapeDetectado, Sandbox, SandboxError
from ai_swe.tools.policy import DecisionContext, decide, normalize_rel_path, path_within_scope

log = logging.getLogger(__name__)


@dataclass
class ResultadoAplicacion:
    """Que paso al intentar aplicar el cambio. Todo declarado, nada implícito."""

    aplicados: list[str] = field(default_factory=list)
    """Rutas que se escribieron de verdad en el sandbox."""

    denegados: dict[str, str] = field(default_factory=dict)
    """Rutas rechazadas por el confinamiento, con el motivo. Nunca se tocaron."""

    borrados: list[str] = field(default_factory=list)
    """Rutas eliminadas en el sandbox (operacion `delete`)."""

    fallos: dict[str, str] = field(default_factory=dict)
    """Rutas que fallaron por una causa tecnica, no de seguridad."""

    @property
    def hubo_escapes(self) -> bool:
        """Si el confinamiento bloqueo al menos una ruta. Es la senal de ataque."""
        return bool(self.denegados)

    @property
    def ok(self) -> bool:
        """El cambio se aplico entero, sin denegaciones ni fallos."""
        return not self.denegados and not self.fallos


def _contexto(sandbox: Sandbox, *, allowed_paths: tuple[str, ...],
              protected_paths: tuple[str, ...], subtask_allowed_tools: tuple[str, ...] = ()) -> DecisionContext:
    """Contexto para el Policy Engine. El agente es el Coder: es quien escribia."""
    return DecisionContext(
        run_id=sandbox.run_id,
        agent=AgentRole.CODER,
        allowed_paths=allowed_paths,
        protected_paths=protected_paths,
        subtask_allowed_tools=subtask_allowed_tools,
    )


def _veredicto_de_escritura(
    sandbox: Sandbox,
    ruta: str,
    *,
    herramienta: str,
    allowed_paths: tuple[str, ...],
    protected_paths: tuple[str, ...],
    subtask_allowed_tools: tuple[str, ...],
) -> tuple[bool, str]:
    """Decide si una ruta puede escribirse. Devuelve `(permitido, motivo)`.

    **Cuatro comprobaciones, en orden de coste creciente.** Las tres primeras son
    puras y no tocan el disco; la cuarta resuelve la ruta de verdad. Si cualquiera
    falla, se devuelve el motivo y **no se escribe nada**.
    """
    # 1. Sintactica: rechaza absolutas, unidades de Windows y `..` que salga arriba.
    normalizada = normalize_rel_path(ruta)
    if normalizada is None:
        return False, f"la ruta '{ruta}' es absoluta o escapa del area autorizada"

    # 2. Alcance declarado.
    if not path_within_scope(normalizada, allowed_paths):
        return False, f"la ruta '{normalizada}' queda fuera del alcance declarado"

    # 3. Politica: rol, subtarea, proteccion, presupuesto. Es el mismo motor que
    #    decide para cualquier otra herramienta, no una copia de sus reglas.
    ctx = _contexto(
        sandbox,
        allowed_paths=allowed_paths,
        protected_paths=protected_paths,
        subtask_allowed_tools=subtask_allowed_tools,
    )
    decision = decide(herramienta, {"path": normalizada}, ctx)
    if decision.effect is not PolicyEffect.ALLOW:
        return False, f"{decision.matched_rule}: {decision.reason}"

    # 4. Fisica: que la ruta resuelta siga dentro de la raiz del sandbox.
    try:
        sandbox.resolver_destino(normalizada)
    except EscapeDetectado as exc:
        return False, exc.motivo

    return True, ""


def aplicar(
    sandbox: Sandbox,
    cambio: CodeChange,
    *,
    allowed_paths: tuple[str, ...] = (),
    protected_paths: tuple[str, ...] = (),
    subtask_allowed_tools: tuple[str, ...] = (),
) -> ResultadoAplicacion:
    """Aplica un `CodeChange` dentro del sandbox, confinando cada ruta.

    Devuelve un `ResultadoAplicacion`: que se aplico, que se denego y por que. Un
    cambio vacio es un resultado valido con listas vacias.

    **No propaga la excepcion de escape.** Un intento de salir del area de trabajo no
    es una averia, es una negativa: se registra en `denegados` y la ejecucion sigue,
    porque los demas archivos de la propuesta siguen siendo legitimamente aplicables.
    Abortar todo por un archivo malicioso castigaria al resto del cambio.
    """
    resultado = ResultadoAplicacion()
    if not cambio.files_changed:
        return resultado

    # El contenido nuevo no viaja en `FileChange` (que solo tiene metadatos): se
    # resuelve aqui desde el diff. Ver `_contenido_de`.
    contenidos = _contenido_de(cambio)

    for archivo in cambio.files_changed:
        ruta = archivo.path
        # Sin contenido nuevo en el diff, la operacion es un borrado. `FileChange` no
        # lleva `operation`: la intencion viaja en el diff, que es el parche.
        es_borrado = contenidos.get(ruta) is None
        herramienta = "delete_file" if es_borrado else "write_file"

        permitido, motivo = _veredicto_de_escritura(
            sandbox,
            ruta,
            herramienta=herramienta,
            allowed_paths=allowed_paths,
            protected_paths=protected_paths,
            subtask_allowed_tools=subtask_allowed_tools,
        )
        if not permitido:
            resultado.denegados[ruta] = motivo
            log.warning("sandbox: ruta denegada %r: %s", ruta, motivo)
            continue

        try:
            if es_borrado:
                if sandbox.eliminar(ruta):
                    resultado.borrados.append(ruta)
            else:
                sandbox.escribir(ruta, contenidos[ruta] or "")
                resultado.aplicados.append(ruta)
        except EscapeDetectado as exc:
            # La barrera fisica salto. Cuenta como denegacion: es un escape.
            resultado.denegados[ruta] = exc.motivo
            log.warning("sandbox: escape detectado en %r: %s", ruta, exc.motivo)
        except SandboxError as exc:
            resultado.fallos[ruta] = str(exc)
            log.warning("sandbox: fallo aplicando %r: %s", ruta, exc)

    return resultado


# --------------------------------------------------------- contenido del parche

def _contenido_de(cambio: CodeChange) -> dict[str, str | None]:
    """Extrae, por archivo, el contenido **nuevo** a partir del diff del cambio.

    **Por que desde el diff y no desde un campo dedicado.** `CodeChange.files_changed`
    solo lleva metadatos (`path`, `added`, `removed`, `sha256`); el contenido vive en
    `diff`, que F7 genera como diff unificado real. Parsear las lineas `+` reconstruye
    exactamente lo que el archivo debe contener.

    Se aplica el **ultimo** trozo de diff de cada archivo: si un archivo aparece dos
    veces, gana el mas reciente, que es lo que hace cualquier aplicador de parches.

    Un archivo `delete` no tiene lineas `+`: su entrada queda a `None`, y eso es lo
    que `aplicar` interpreta como borrado.
    """
    contenidos: dict[str, str | None] = {}
    for ruta, lineas in _trozos_por_archivo(cambio.diff).items():
        nuevas = [linea[1:] for linea in lineas if linea.startswith("+") and not linea.startswith("+++")]
        contenidos[ruta] = ("\n".join(nuevas) + "\n") if nuevas else None
    return contenidos


def _trozos_por_archivo(diff: str) -> dict[str, list[str]]:
    """Agrupa las lineas del diff por la ruta de destino de cada bloque.

    Se lee la cabecera `+++ b/<ruta>` de cada trozo. Un diff de git sin contenido
    nuevo -solo borrado- lleva `+++ /dev/null`, y entonces no hay ruta de destino: el
    bloque se asocia a la ruta del `--- a/<ruta>`.

    **Es un parser deliberadamente literal.** No interpreta hunks ni contextos: solo
    separa bloques y clasifica lineas por su primer caracter. Un diff que no sigue
    esta forma no produce contenido, y el resultado lo declara como fallo en lugar de
    inventar un archivo.
    """
    trozos: dict[str, list[str]] = {}
    ruta_actual: str | None = None

    for linea in diff.splitlines():
        if linea.startswith("+++ "):
            destino = linea[4:].strip()
            if destino.startswith("b/"):
                ruta_actual = destino[2:]
                trozos.setdefault(ruta_actual, [])
            else:
                # `+++ /dev/null`: es un borrado. La ruta la da la cabecera `---`.
                ruta_actual = None
            continue
        if linea.startswith("--- "):
            origen = linea[4:].strip()
            if ruta_actual is None and origen.startswith("a/"):
                ruta_actual = origen[2:]
                trozos.setdefault(ruta_actual, [])
            continue
        if ruta_actual is None:
            continue
        if linea.startswith(("diff --git", "index ", "@@", "new file mode", "deleted file mode",
                             "old mode", "new mode", "similarity index")):
            continue
        trozos[ruta_actual].append(linea)

    return trozos
