"""Trabajador de ejecucion: saca la ejecucion del hilo de la peticion.

Motivo: un navegador necesita el `run_id` **antes** de que la ejecucion ocurra
para poder suscribirse al progreso. Con la ejecucion dentro de la peticion, el
cliente recibia el identificador cuando ya habia terminado y el flujo de eventos
solo podia reproducir.

Ademas, `RNF-E3` lo exige: el proceso que atiende HTTP no debe ejecutar tareas
largas, porque degrada la atencion de todas las peticiones. En M2, con el modelo
conectado, una ejecucion pasara de milisegundos a decenas de segundos.

Limite conocido: son **hilos**, no procesos. Suficiente porque el trabajo es
espera de red (llamadas al modelo). El aislamiento de procesos llega con el
contenedor por ejecucion, y esta declarado en `docs/02-tecnologias.md`.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

from ai_swe.graph.engine import RunEngine

log = logging.getLogger(__name__)


class RunWorker:
    """Ejecuta ejecuciones fuera del hilo de la peticion."""

    def __init__(self, engine: RunEngine, max_workers: int = 4) -> None:
        self._engine = engine
        self._pool = ThreadPoolExecutor(
            max_workers=max(1, max_workers), thread_name_prefix="ai-swe-run"
        )
        self._cerrado = False
        self._active = 0
        self._active_lock = threading.Lock()

    def submit(self, run_id: str) -> None:
        if self._cerrado:
            raise RuntimeError("el trabajador esta cerrado")
        self._submit(self._ejecutar_seguro, run_id)

    def submit_resume(self, run_id: str, decision) -> None:
        """Reanuda una ejecucion en el trabajador.

        La reanudacion tambien sale del hilo de la peticion: el cliente recibe la
        respuesta en cuanto el grafo arranca de nuevo, no cuando termina.
        """
        if self._cerrado:
            raise RuntimeError("el trabajador esta cerrado")
        self._submit(self._reanudar_seguro, run_id, decision)

    @property
    def active(self):
        with self._active_lock:
            return self._active

    def _submit(self, operation, *args):
        context = copy_context()
        with self._active_lock:
            self._active += 1
        def run():
            try:
                context.run(operation, *args)
            finally:
                with self._active_lock:
                    self._active -= 1
        try:
            self._pool.submit(run)
        except BaseException:
            with self._active_lock:
                self._active -= 1
            raise

    def _ejecutar_seguro(self, run_id: str) -> None:
        """Ejecuta y **siempre** deja la ejecucion en un estado terminal.

        Una excepcion sin capturar dejaria la ejecucion en `running` para siempre:
        el navegador esperaria indefinidamente y `MET-13` se incumpliria. Por eso
        cualquier fallo se convierte en un error tipado y un estado terminal.
        """
        try:
            self._engine.execute(run_id)
        except Exception as exc:  # noqa: BLE001 - la red de seguridad es el proposito
            log.exception("la ejecucion %s fallo", run_id)
            self._engine.abortar(
                run_id,
                error_class="WORKER_EXCEPTION",
                message=f"{type(exc).__name__}: {exc}"[:1000],
            )

    def _reanudar_seguro(self, run_id: str, decision) -> None:
        try:
            # `reanudar_reclamada`, no `resume`: el derecho a reanudar ya se reclamo
            # en el hilo de la peticion, de forma atomica con la comprobacion de que
            # la puerta esperaba. Volver a comprobar aqui reabriria justo la ventana
            # que la reclamacion cierra, porque la ejecucion llega con retraso.
            self._engine.reanudar_reclamada(run_id, decision)
        except Exception as exc:  # noqa: BLE001
            log.exception("la reanudacion de %s fallo", run_id)
            self._engine.abortar(
                run_id,
                error_class="RESUME_EXCEPTION",
                message=f"{type(exc).__name__}: {exc}"[:1000],
            )

    def shutdown(self, wait: bool = True) -> None:
        """Detiene el trabajador.

        Por defecto **espera** a que terminen las ejecuciones aceptadas. No es
        comodidad: si el proceso cierra el almacen mientras un trabajador sigue
        escribiendo, el trabajador falla con `Cannot operate on a closed database`
        y la ejecucion queda sin estado terminal.

        En produccion esto se sustituye por un drenaje con limite de tiempo: se
        deja de aceptar trabajo, se espera un margen y lo que siga en curso se
        marca como huerfano al arrancar (`RunStore.orphan_open_runs`), que ya
        existe y es la red que cubre ese caso.
        """
        self._cerrado = True
        self._pool.shutdown(wait=wait, cancel_futures=not wait)
