"""Motor de ejecucion: crea, ejecuta, reanuda y consulta ejecuciones.

Es la unica puerta de entrada al grafo. Concentra cuatro cosas que no deben quedar
repartidas por el codigo:

  1. **Creacion y ejecucion separadas.** Con la ejecucion dentro de la peticion, el
     cliente recibia el `run_id` cuando la ejecucion ya habia terminado, asi que
     **no podia suscribirse al progreso**: el flujo SSE solo podia reproducir, no
     emitir en vivo. Ahora `create()` persiste y devuelve, y `execute()` corre en
     un trabajador.
  2. **Progreso real por nodo.** Se usa `stream` del grafo, de modo que cada nodo
     terminado emite un evento en el momento en que ocurre. Es lo que alimenta la
     barra de progreso del navegador.
  3. **La red de seguridad de `MET-13`.** Toda ejecucion que devuelve el grafo
     termina en un estado terminal o en `awaiting_approval`. Si no, se fuerza
     `needs_human` y se registra el fallo.
  4. **La comprobacion de punto de control antes de reanudar.** Hallazgo de
     `tools/verify_m1_assumptions.py`: reanudar sobre un hilo sin punto de control
     entrega un estado vacio y hace fallar a los nodos por dentro, en el peor lugar
     posible.

Concurrencia: un cerrojo **por ejecucion**, no global. Dos ejecuciones distintas
avanzan a la vez; la misma ejecucion no se ejecuta dos veces. El limite real sigue
siendo SQLite, que admite un solo escritor (`docs/02-tecnologias.md`, seccion 8).
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime

from langgraph.types import Command

from ai_swe.contracts import (
    ApprovalDecision,
    EventKind,
    Instruction,
    InstructionSource,
    RunError,
    RunOptions,
    RunState,
    RunStatus,
    TranscriptMeta,
)
from ai_swe.graph.workflow import compilar
from ai_swe.state import RunStore


class RunNotFound(LookupError):
    """No existe una ejecucion con ese identificador."""


class NothingToResume(RuntimeError):
    """La ejecucion no esta esperando nada.

    Se lanza en lugar de reanudar a ciegas: reanudar sin punto de control produce
    un estado vacio y los nodos fallan por dentro con un `KeyError` que no dice
    nada util.
    """


def nuevo_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


def _ahora() -> datetime:
    return datetime.now(UTC)


class RunEngine:
    """Orquesta el grafo y mantiene el indice y el registro de eventos."""

    def __init__(self, store: RunStore) -> None:
        self._store = store
        # El grafo se compila **por hilo**, no una sola vez. El checkpointer lleva
        # una conexion SQLite, y compartir una conexion entre el hilo de la
        # peticion y los trabajadores producia fallos intermitentes en el `commit`.
        # Compilar por hilo da a cada uno su propia conexion al mismo fichero.
        self._local = threading.local()
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    @property
    def _app(self):
        app = getattr(self._local, "app", None)
        if app is None:
            app = compilar(self._store)
            self._local.app = app
        return app

    # ------------------------------------------------------------- consultas
    def get(self, run_id: str) -> RunState:
        """Estado actual de una ejecucion.

        Si aun no hay punto de control, devuelve el **estado inicial**. No es un
        detalle: entre que `POST /runs` responde 202 y el trabajador ejecuta el
        primer nodo hay una ventana en la que la ejecucion existe pero no tiene
        punto de control. Sin esta caida hacia atras, el cliente que acababa de
        recibir el `run_id` recibia un 404 al consultarlo.
        """
        instantanea = self._app.get_state(self._config(run_id))
        if instantanea.values:
            return RunState.model_validate(instantanea.values)
        try:
            return self._store.initial_state(run_id)
        except KeyError as exc:
            raise RunNotFound(run_id) from exc

    def pendiente_de_aprobacion(self, run_id: str) -> bool:
        instantanea = self._app.get_state(self._config(run_id))
        return bool(instantanea.values) and bool(instantanea.next)

    def _lock_de(self, run_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(run_id, threading.Lock())

    # --------------------------------------------------------------- creacion
    def crear_estado(
        self,
        instruccion: str,
        *,
        options: RunOptions | None = None,
        source: str = "text",
        transcript_meta: TranscriptMeta | None = None,
    ) -> RunState:
        ahora = _ahora()
        return RunState(
            run_id=nuevo_run_id(),
            trace_id=f"trace-{uuid.uuid4().hex[:12]}",
            created_at=ahora,
            updated_at=ahora,
            instruction=Instruction(
                text=instruccion,
                source=InstructionSource(source),
                transcript_meta=transcript_meta,
                confirmed_by_user=True,
            ),
            options=options or RunOptions(),
        )

    def create(self, estado: RunState) -> RunState:
        """Persiste la ejecucion y la deja lista. **No la ejecuta.**

        Devuelve el estado con el `run_id` ya conocido por el cliente, que es lo
        que le permite suscribirse al progreso antes de que ocurra nada.
        """
        self._store.create(estado)
        self._store.append_event(
            estado.run_id,
            EventKind.RUN_CREATED,
            {
                "instruction": estado.instruction.text[:200],
                "source": estado.instruction.source.value,
                "repo_path": estado.options.repo_path,
            },
        )
        return estado

    def start(self, estado: RunState) -> RunState:
        """Crea y ejecuta en el acto, en el hilo que llama.

        Es la via sin trabajador: util para pruebas, para un uso por linea de
        comandos y para scripts de evaluacion, donde no hay navegador esperando y
        no tiene sentido encolar. La API **no** la usa: usa `create` y delega en el
        trabajador para no bloquear la peticion.
        """
        self.create(estado)
        return self.execute(estado.run_id)

    # ------------------------------------------------------------- ejecucion
    def execute(self, run_id: str) -> RunState:
        """Ejecuta una ejecucion ya creada, emitiendo progreso por nodo."""
        with self._lock_de(run_id):
            entrada = self._store.initial_state(run_id)
            return self._ejecutar(entrada, run_id)

    def resume(self, run_id: str, decision: ApprovalDecision | str) -> RunState:
        with self._lock_de(run_id):
            # El orden importa: comprobar primero que existe. Si no, una ejecucion
            # inexistente respondia 409 ("no esta esperando aprobacion") en lugar
            # de 404, que es lo que corresponde y lo que espera cualquier cliente.
            if self._store.summary(run_id) is None:
                raise RunNotFound(run_id)
            if not self.pendiente_de_aprobacion(run_id):
                raise NothingToResume(
                    f"la ejecucion {run_id} no esta esperando aprobacion: "
                    "no hay punto de control que reanudar"
                )
            valor = decision.value if isinstance(decision, ApprovalDecision) else str(decision)
            return self._ejecutar(Command(resume=valor), run_id)

    # ---------------------------------------------------------------- interno
    @staticmethod
    def _config(run_id: str) -> dict:
        return {"configurable": {"thread_id": run_id}}

    def _ejecutar(self, entrada, run_id: str) -> RunState:
        config = self._config(run_id)
        self._store.append_event(run_id, EventKind.RUN_STARTED, {})

        for trozo in self._app.stream(entrada, config, stream_mode="updates"):
            for nodo, salida in trozo.items():
                if nodo == "__interrupt__":
                    self._store.append_event(
                        run_id, EventKind.RUN_AWAITING_APPROVAL, _carga_interrupcion(salida)
                    )
                    continue
                self._store.append_event(run_id, EventKind.RUN_STEP, {"node": nodo})
                # Se sincroniza el indice en cada paso para que `GET /runs/{id}`
                # refleje el avance mientras la ejecucion sigue en curso.
                self._store.sync(self._estado_actual(config, run_id))

        return self._persistir(run_id, self._estado_actual(config, run_id))

    def _estado_actual(self, config: dict, run_id: str) -> RunState:
        instantanea = self._app.get_state(config)
        if not instantanea.values:
            raise RunNotFound(run_id)
        return RunState.model_validate(instantanea.values)

    def _persistir(self, run_id: str, estado: RunState) -> RunState:
        estado = self._aplicar_red_de_seguridad(estado)

        self._store.sync(estado)
        self._store.append_event(
            run_id,
            EventKind.RUN_STATUS,
            {
                "status": estado.status.value,
                "next_step": estado.next_step,
                "error_count": len(estado.errors),
            },
        )
        if estado.final_report is not None:
            self._store.append_event(
                run_id, EventKind.RUN_REPORT, {"summary": estado.final_report.summary}
            )
        for error in estado.errors:
            self._store.append_event(
                run_id,
                EventKind.RUN_ERROR,
                {"error_class": error.error_class, "agent": error.agent, "message": error.message},
            )
        self._store.append_event(run_id, EventKind.RUN_DONE, {"status": estado.status.value})
        return estado

    def abortar(self, run_id: str, *, error_class: str, message: str) -> RunState | None:
        """Deja una ejecucion en estado terminal tras un fallo del trabajador.

        Escribe en el **checkpoint**, no solo en el indice. La primera version solo
        actualizaba el indice, y entonces `GET /runs/{id}` —que lee el checkpoint—
        seguia devolviendo `running` para una ejecucion ya abortada: dos vistas del
        mismo hecho que no coincidian.

        Sin esto, ademas, una excepcion sin capturar dejaria la ejecucion en
        `running` para siempre y `MET-13` se incumpliria.
        """
        config = self._config(run_id)
        try:
            estado = self._estado_actual(config, run_id)
        except RunNotFound:
            # El fallo ocurrio antes del primer nodo: no hay punto de control.
            try:
                estado = self._store.initial_state(run_id)
            except KeyError:
                return None

        datos = estado.model_dump()
        datos["errors"] = [
            *datos["errors"],
            RunError(
                error_class=error_class,
                agent="supervisor",
                message=message,
                recoverable=False,
                occurred_at=_ahora(),
            ).model_dump(),
        ]
        datos["status"] = RunStatus.NEEDS_HUMAN
        datos["next_step"] = None
        datos["updated_at"] = _ahora()
        nuevo = RunState.model_validate(datos)

        # `update_state` exige el estado **completo** con un esquema Pydantic:
        # valida la entrada contra el esquema en lugar de fusionarla. Pasar un
        # diccionario parcial falla con errores de campos requeridos.
        self._app.update_state(config, nuevo.model_dump())

        self._store.sync(nuevo)
        self._store.append_event(
            run_id, EventKind.RUN_ERROR, {"error_class": error_class, "message": message}
        )
        self._store.append_event(run_id, EventKind.RUN_DONE, {"status": RunStatus.NEEDS_HUMAN.value})
        return nuevo

    @staticmethod
    def _aplicar_red_de_seguridad(estado: RunState) -> RunState:
        """Garantiza que ninguna ejecucion queda colgada (`MET-13`).

        `awaiting_approval` no es anomalia: es una espera legitima. Cualquier otro
        estado no terminal al volver del grafo si lo es, y significa que la
        topologia tiene un camino sin salida.
        """
        if estado.status.is_terminal or estado.status is RunStatus.AWAITING_APPROVAL:
            return estado

        datos = estado.model_dump()
        datos["errors"] = [
            *datos["errors"],
            RunError(
                error_class="UNTERMINATED_RUN",
                agent="supervisor",
                message=(
                    f"el grafo devolvio el estado '{estado.status.value}' sin ser terminal; "
                    "hay un camino sin salida en la topologia"
                ),
                recoverable=False,
                occurred_at=_ahora(),
            ).model_dump(),
        ]
        datos["status"] = RunStatus.NEEDS_HUMAN
        datos["next_step"] = None
        datos["updated_at"] = _ahora()
        return RunState.model_validate(datos)


def _carga_interrupcion(salida) -> dict:
    """Extrae la pregunta de la puerta de aprobacion del trozo de interrupcion."""
    try:
        primera = salida[0]
        valor = getattr(primera, "value", None) or {}
        return {
            "question": valor.get("pregunta", "se requiere aprobacion"),
            "run_id": valor.get("run_id"),
            "review_summary": valor.get("resumen_revision"),
        }
    except (IndexError, TypeError, AttributeError):
        return {"question": "se requiere aprobacion"}
