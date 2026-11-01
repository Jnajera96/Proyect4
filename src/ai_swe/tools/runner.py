"""Ejecutor de pruebas: corre *targets* de la lista permitida dentro del sandbox (F8).

**La regla que justifica el modulo.** Un identificador de una lista permitida **no
es un comando**. El *target* (`pytest.unit`) se resuelve con una **tabla cerrada
en codigo** (`TARGET_COMMANDS`) y el resultado se pasa a `subprocess` como **lista
de argumentos** con `shell=False`. No existe ninguna via por la que una cadena
llegue a una shell: ni del modelo, ni de la configuracion, ni del estado, ni del
usuario. `run_shell` no esta en el catalogo de herramientas y no se anade aqui.

**Por que se ejecuta dentro del sandbox.** `DEC-07`: los cambios viven en un
`git worktree` aislado hasta que un humano los aprueba. Ejecutar las pruebas en el
repositorio del usuario significaria probar un arbol distinto del que se va a
aprobar, y ademas dejaria artefactos (`.pytest_cache`, `__pycache__`) en el arbol
real. El sandbox es el unico sitio donde el parche existe.

El hijo sigue siendo un proceso local con permisos del usuario. El entorno mínimo
no aísla archivos, red ni procesos; un worktree no es una barrera de ejecución.

**Por que la evidencia es un `TestRun` y no un booleano.** Un sistema cuyo valor es
la evidencia no puede reducir "se probo" a `True`. Se registra el *target*, el
codigo de salida real, la salida capturada, la duracion y **el comando exacto**
(`argv`). Si no hay ejecutor, no hay `TestRun`: se registra un error tipado. Nunca
un exito inventado.
"""

from __future__ import annotations

import logging
import math
import os
import subprocess
import sys
import time
from pathlib import Path

from ai_swe.contracts import TestRun
from ai_swe.sandbox import Sandbox
from ai_swe.tools.windows_job import CREATE_SUSPENDED, JobError, JobLimits, WindowsJob

log = logging.getLogger(__name__)

# Limite por defecto. La suite completa del proyecto tarda minutos; un objetivo
# colgado no debe colgar la ejecucion entera.
DEFAULT_TIMEOUT_S = 600.0

# Convencion de `timeout(1)`: el proceso no termino. Se distingue de un fallo de
# las pruebas (codigo != 0) porque la causa es otra y la accion a tomar tambien.
EXIT_TIMEOUT = 124
EXIT_ORPHANS = 125

# Limite de los campos de salida del contrato `TestRun`.
_MAX_SALIDA = 200_000

# The test child needs the runtime environment, never the server's credentials/configuration.
_ENV_PERMITIDAS = frozenset({
    "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "SYSTEMDRIVE", "PATHEXT",
    "TEMP", "TMP", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
})

# ------------------------------------------------------------------- catalogo
#
# **Tabla CERRADA: la unica fuente de comandos.** Anadir una entrada es una
# decision de codigo revisable, no un valor de configuracion. La configuracion
# (`AI_SWE_ALLOWED_TEST_TARGETS`) decide **que** targets se permiten; esta tabla
# decide **como** se ejecuta cada uno. Las dos cosas son necesarias y ninguna
# sustituye a la otra: un target permitido sin comando definido se rechaza, y un
# comando definido para un target no permitido no se ejecuta nunca.
#
# `sys.executable` y no `"python"`: el interprete del sistema puede no ser el mismo
# que ejecuta el proyecto, y probar con otro Python produce fallos que no tienen
# nada que ver con el cambio.
TARGET_COMMANDS: dict[str, tuple[str, ...]] = {
    "pytest.unit": (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
        # Se excluye la integracion real: exige credenciales y red. Una API
        # externa no puede ser dependencia de una ejecucion offline.
        "-m",
        "not real_provider",
        ".",
    ),
    "pytest.integration": (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
        "-m",
        "integration",
        ".",
    ),
    "ruff.check": (
        sys.executable,
        "-m",
        "ruff",
        "check",
        ".",
    ),
}


class RunnerError(RuntimeError):
    """Fallo al preparar o lanzar una ejecucion de pruebas.

    Es **tipada y accionable**: nombra la operacion que fallo y por que. No se
    lanza cuando las pruebas fallan -eso es un `TestRun` con codigo distinto de
    cero, que es un resultado, no una averia-. Se lanza cuando el ejecutor **no
    pudo correr**: target desconocido, interprete ausente.
    """

    def __init__(self, operacion: str, detalle: str) -> None:
        self.operacion = operacion
        super().__init__(f"runner: fallo en '{operacion}' ({detalle})")


class TargetNoPermitido(RunnerError):
    """El target no esta en la lista permitida. **Se rechaza antes de ejecutar.**

    Es una negativa de seguridad, no una averia: se separa para que quien la
    capture la registre como tal. La comprobacion existe aqui ademas de en el
    Policy Engine a proposito: es la misma clase de redundancia deliberada que las
    barreras del patcher (F7). El ejecutor no depende de que su llamante haya
    consultado la politica.
    """

    def __init__(self, target: str, permitidos: tuple[str, ...]) -> None:
        self.target = target
        super().__init__(
            "target",
            f"'{target}' no esta en la lista permitida {sorted(permitidos)}",
        )


def targets_disponibles() -> tuple[str, ...]:
    """Targets que el ejecutor sabe correr. Ordenado, para que sea comparable."""
    return tuple(sorted(TARGET_COMMANDS))


def comando_de(target: str) -> tuple[str, ...] | None:
    """Argumentos exactos de un target, o `None` si no esta definido.

    Se expone para que una prueba pueda afirmar el comando **sin ejecutarlo**, y
    para que el registro de evidencia sea inspeccionable.
    """
    signed_bundle = getattr(sys, "_ai_swe_bundle", None)
    if signed_bundle and target in TARGET_COMMANDS:
        return (sys.executable, str(Path(signed_bundle) / "start.py"), "--run-test-target", target)
    if getattr(sys, "frozen", False) and target in TARGET_COMMANDS:
        return (sys.executable, "--run-test-target", target)
    return TARGET_COMMANDS.get(target)


def _entorno(sandbox: Sandbox) -> dict[str, str]:
    """Entorno del hijo, con el `src` del **sandbox** al frente del `PYTHONPATH`.

    **Por que se toca el `PYTHONPATH`.** Si el proceso padre tiene
    `PYTHONPATH=<repo original>/src` -y lo tiene, porque asi se ejecuta la suite-,
    el hijo lo hereda y las pruebas importarian el paquete **del repositorio
    original**, no el del sandbox. El resultado seria una evidencia que dice
    "pasa" sobre un codigo que no es el que se va a aprobar: la peor clase de
    fallo, porque el instrumento miente sin avisar.

    Se fija al `src` del sandbox cuando existe. Es determinista y no depende de
    como este configurado el entorno de quien lanza.
    """
    entorno = {k: v for k, v in os.environ.items() if k.upper() in _ENV_PERMITIDAS}
    # pytest's assertion rewriting otherwise writes new .pyc files into a
    # repository without ignore rules, invalidating the already reviewed diff.
    entorno["PYTHONDONTWRITEBYTECODE"] = "1"
    entorno["PYTHONIOENCODING"] = "utf-8"
    raiz_src = sandbox.raiz / "src"
    if raiz_src.is_dir():
        entorno["PYTHONPATH"] = str(raiz_src)
    return entorno


def _recortar(texto: str) -> str:
    """Recorta al limite del contrato conservando el final, que es donde esta el fallo."""
    if len(texto) <= _MAX_SALIDA:
        return texto
    return "...[recortado]...\n" + texto[-(_MAX_SALIDA - 20) :]


def _capturar(
    orden: list[str], sandbox: Sandbox, timeout: float, limits: JobLimits | None = None,
) -> subprocess.CompletedProcess:
    """Drain both pipes fairly with a bounded byte tail and a deadline, without threads/files."""
    deadline = time.monotonic() + timeout
    try:
        if os.name != "nt" and limits is not None:
            raise RunnerError("limites", "Las cuotas del Job Object requieren Windows")
        job = WindowsJob(limits) if os.name == "nt" else None
    except JobError as exc:
        raise RunnerError("grupo", str(exc)) from exc
    except ValueError as exc:
        raise RunnerError("limites", "Configuracion de cuotas no valida") from exc
    try:
        process = subprocess.Popen(
            orden,
            cwd=str(sandbox.raiz),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=CREATE_SUSPENDED if job else 0,
            bufsize=0,
            shell=False,
            env=_entorno(sandbox),
        )
    except BaseException:
        if job:
            job.close()
        raise
    pipes = {"stdout": process.stdout, "stderr": process.stderr}
    active = dict(pipes)
    tails = {name: bytearray() for name in pipes}
    truncated = set()
    timed_out = False
    orphaned = False
    try:
        if job:
            timed_out = not job.assign_and_resume(process, deadline)
        for pipe in pipes.values():
            os.set_blocking(pipe.fileno(), False)
        while not timed_out and (active or process.poll() is None):
            if time.monotonic() >= deadline:
                timed_out = True
                break
            received = False
            for name, pipe in list(active.items()):
                try:
                    data = os.read(pipe.fileno(), 65536)
                except BlockingIOError:
                    continue
                except BrokenPipeError:
                    data = b""
                if not data:
                    del active[name]
                    continue
                received = True
                tail = tails[name]
                tail.extend(data)
                if len(tail) > _MAX_SALIDA:
                    del tail[:-_MAX_SALIDA]
                    truncated.add(name)
            if not received:
                time.sleep(0.01)
    except OSError as exc:
        raise RunnerError("capturar", "no se pudo leer la salida de forma acotada") from exc
    except JobError as exc:
        raise RunnerError("grupo", str(exc)) from exc
    finally:
        try:
            try:
                if job:
                    if not timed_out and process.poll() is not None:
                        orphaned = not job.wait_empty(.1)
                    job.terminate_and_wait()
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
        except (JobError, OSError, subprocess.TimeoutExpired) as exc:
            raise RunnerError("cerrar", "no se confirmó el cierre del grupo/proceso") from exc
        finally:
            try:
                if job:
                    job.close()
            except JobError as exc:
                raise RunnerError("cerrar", str(exc)) from exc
            finally:
                for pipe in pipes.values():
                    pipe.close()
    output = {}
    for name, tail in tails.items():
        text = tail.decode("utf-8", errors="replace")
        if name in truncated:
            text = "...[recortado]...\n" + text
        output[name] = _recortar(text)
    if timed_out:
        raise subprocess.TimeoutExpired(
            orden, timeout, output=output["stdout"], stderr=output["stderr"]
        )
    if orphaned:
        output["stderr"] = _recortar(
            output["stderr"]
            + "\nQuedaron procesos descendientes; el grupo fue terminado y verificado."
        )
        return subprocess.CompletedProcess(orden, EXIT_ORPHANS, **output)
    if process.returncode in (1816, 0xC0000044):  # ERROR_NOT_ENOUGH_QUOTA / STATUS_QUOTA_EXCEEDED.
        output["stderr"] = _recortar(
            output["stderr"]
            + "\nWindows informó cuota insuficiente; revisa los límites de recursos."
        )
    return subprocess.CompletedProcess(orden, process.returncode, **output)


def ejecutar(
    sandbox: Sandbox,
    target: str,
    *,
    permitidos: tuple[str, ...],
    timeout: float = DEFAULT_TIMEOUT_S,
    limits: JobLimits | None = None,
) -> TestRun:
    """Ejecuta `target` dentro del sandbox y devuelve la evidencia.

    Devuelve un `TestRun` **siempre que el ejecutor haya podido correr**, incluso
    si las pruebas fallan: un fallo de pruebas es un resultado con codigo de salida
    distinto de cero, no una excepcion. Lanza `RunnerError` solo cuando el
    ejecutor no pudo lanzarse o el target no es valido.

    Un **timeout** no es una excepcion que escape: se convierte en un `TestRun` con
    `EXIT_TIMEOUT` y el motivo en `stderr`. Un objetivo colgado debe producir
    evidencia de que se colgo, no tumbar el grafo.
    """
    if target not in permitidos:
        raise TargetNoPermitido(target, permitidos)

    argv = comando_de(target)
    if argv is None:
        # Permitido por configuracion pero sin comando definido: no se inventa uno.
        raise RunnerError(
            "target",
            f"'{target}' esta permitido pero no tiene comando definido en TARGET_COMMANDS",
        )

    if not math.isfinite(timeout) or timeout <= 0:
        raise RunnerError("timeout", "el plazo debe ser positivo y finito")

    orden = list(argv)  # lista, nunca una cadena; `shell=False` siempre
    log.info("runner: ejecutando %s en %s", target, sandbox.raiz)

    inicio = time.perf_counter()
    try:
        resultado = _capturar(orden, sandbox, timeout, limits)
    except subprocess.TimeoutExpired as exc:
        duracion = time.perf_counter() - inicio
        salida = (
            exc.stdout.decode(errors="replace")
            if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        )
        error = (
            exc.stderr.decode(errors="replace")
            if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        )
        log.warning("runner: '%s' supero %ss", target, timeout)
        return TestRun(
            target=target,
            exit_code=EXIT_TIMEOUT,
            stdout=_recortar(salida),
            stderr=_recortar(f"{error}\nla ejecucion supero {timeout}s y se interrumpio"),
            duration_s=duracion,
            argv=orden,
        )
    except FileNotFoundError as exc:
        raise RunnerError("lanzar", f"no se encontro el ejecutable '{orden[0]}'") from exc

    duracion = time.perf_counter() - inicio
    return TestRun(
        target=target,
        exit_code=resultado.returncode,
        stdout=_recortar(resultado.stdout or ""),
        stderr=_recortar(resultado.stderr or ""),
        duration_s=duracion,
        argv=orden,
    )
