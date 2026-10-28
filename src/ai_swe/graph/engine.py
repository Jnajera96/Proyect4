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
from functools import partial
from datetime import UTC, datetime

from langgraph.types import Command

from ai_swe.config import Settings
from ai_swe.contracts import (
    EVENTO_POR_NODO,
    ApprovalDecision,
    Budget,
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
from ai_swe.sandbox import limpiar_worktree
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


def _repositorio_de(estado: RunState) -> str | None:
    """Repositorio efectivo de una ejecucion.

    Misma precedencia que `nodes._alcance`: si `interpret` ya corrio, el alcance con
    la ruta resuelta esta en la interpretacion; antes de eso, lo unico que hay son las
    opciones de la peticion. Se replica aqui -en lugar de importar el ayudante del
    grafo- para no acoplar el motor a los nodos, y porque es una precedencia de dos
    lineas cuyo contrato es el mismo.
    """
    if estado.interpretation is not None:
        return estado.interpretation.scope.repo_path
    return estado.options.repo_path


class RunEngine:
    """Orquesta el grafo y mantiene el indice y el registro de eventos."""

    def __init__(
        self, store: RunStore, *, constructor_grafo=None, settings: Settings | None = None
    ) -> None:
        self._store = store
        # F2: el presupuesto efectivo sale de la configuracion. Sin `settings` se
        # usan los valores por defecto del contrato, que son **los mismos** que los
        # de `Settings`; pasarlos explicitamente es lo que hace que
        # `AI_SWE_MAX_TOKENS_PER_RUN` y compania dejen de ser decorativos. Se deja
        # opcional para no obligar a cargar `.env` en las pruebas que construyen el
        # motor directamente.
        self._settings = settings
        from ai_swe.state.memory import MemoryStore
        from ai_swe.state.continuity import ContinuityStore
        from ai_swe.tools.rollback import RollbackStore
        owner = (settings.profile_id or "legacy") if settings else "legacy"
        wt_root = settings.workspace_root if settings else None
        self.memory = MemoryStore(store._db_path, owner)
        self.rollbacks = RollbackStore(store._db_path, owner)
        self.continuity = ContinuityStore(store._db_path, owner, worktrees_root=wt_root)
        self._pause_requested: set[str] = set()
        # El grafo se compila **por hilo**, no una sola vez. El checkpointer lleva
        # una conexion SQLite, y compartir una conexion entre el hilo de la
        # peticion y los trabajadores producia fallos intermitentes en el `commit`.
        # Compilar por hilo da a cada uno su propia conexion al mismo fichero.
        self._local = threading.local()
        # F14: el constructor del grafo se puede sustituir para ejecutar **otra**
        # topologia sobre la misma maquinaria (eventos, persistencia, reanudacion).
        # Lo usa el arnes de evaluacion para comparar el flujo multiagente de
        # produccion contra un flujo directo de un solo agente. Por defecto es el
        # grafo de produccion, asi que la API no cambia de comportamiento.
        self._constructor = constructor_grafo or partial(compilar, settings=settings)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        # Reanudaciones ya reclamadas y todavia no terminadas. Ver `reclamar_reanudacion`.
        self._reclamadas: set[str] = set()

    @property
    def _app(self):
        app = getattr(self._local, "app", None)
        if app is None:
            app = self._constructor(self._store)
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

    def reclamar_reanudacion(self, run_id: str, *, puerta_esperada: str | None = None) -> None:
        """Reserva el derecho a reanudar, o lanza `NothingToResume` si no lo hay.

        **Por que existe.** Comprobar `pendiente_de_aprobacion` y luego encolar la
        reanudacion son dos pasos, y la reanudacion se ejecuta despues, en el hilo
        del trabajador. Dos peticiones concurrentes -dos pestanas, un doble clic, un
        reintento del navegador- pasaban ambas la comprobacion antes de que ninguna
        hubiera reanudado, y las dos devolvian 200. La segunda pisaba a la primera:
        el contrato dice que una ejecucion que no espera da 409, y no lo hacia.

        `puerta_esperada` distingue las dos rutas HITL: `confirm-requirements` no
        puede consumir una espera en `approval_gate`, ni `approve` una espera en
        `confirm_requirements_gate`. Un interrupt pendiente no basta; tiene que ser
        el correcto para el endpoint que lo reanuda.

        La reclamacion se toma bajo el **mismo cerrojo por ejecucion** que usa
        `resume`, y se libera cuando la reanudacion termina (`olvidar_reclamacion`).
        La segunda peticion encuentra el derecho tomado y recibe el `NothingToResume`
        que corresponde.
        """
        with self._lock_de(run_id):
            if self._store.summary(run_id) is None:
                raise RunNotFound(run_id)
            with self._locks_guard:
                reclamada = run_id in self._reclamadas
            if reclamada:
                raise NothingToResume(
                    f"la ejecucion {run_id} ya tiene una reanudacion en curso"
                )
            if not self.pendiente_de_aprobacion(run_id):
                raise NothingToResume(
                    f"la ejecucion {run_id} no esta esperando aprobacion: "
                    "no hay punto de control que reanudar"
                )
            if puerta_esperada is not None:
                puerta_actual = _puerta_pendiente(self._app, self._config(run_id))
                if puerta_actual != puerta_esperada:
                    raise NothingToResume(
                        f"la ejecucion {run_id} espera en '{puerta_actual}', "
                        f"no en '{puerta_esperada}'"
                    )
            with self._locks_guard:
                self._reclamadas.add(run_id)

    def olvidar_reclamacion(self, run_id: str) -> None:
        """Libera la reclamacion. Se llama siempre al terminar la reanudacion."""
        with self._locks_guard:
            self._reclamadas.discard(run_id)

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
            budget=self._presupuesto(),
        )

    def _presupuesto(self) -> Budget:
        """Presupuesto con el que nace la ejecucion.

        Con configuracion cargada, la copia de `Settings`; sin ella, los valores por
        defecto del contrato. En ambos casos el presupuesto queda **dentro del
        estado persistido**, que es lo que hace que un reinicio a mitad de ejecucion
        no devuelva los contadores a cero.
        """
        if self._settings is None:
            return Budget()
        return self._settings.presupuesto()

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

    def resume(self, run_id: str, decision: ApprovalDecision | str | dict) -> RunState:
        """Reanuda una ejecucion detenida en una puerta humana.

        Es la via **directa**: comprueba el derecho, lo toma y reanuda en el hilo que
        llama. La usan las pruebas, los scripts y el camino sincrono. La API usa
        `reclamar_reanudacion` + `reanudar_reclamada`, porque entre la comprobacion y
        la ejecucion hay un trabajador de por medio y el derecho tiene que quedar
        reservado en el hueco.
        """
        self.reclamar_reanudacion(run_id)
        return self.reanudar_reclamada(run_id, decision)

    def reanudar_reclamada(
        self, run_id: str, decision: ApprovalDecision | str | dict
    ) -> RunState:
        """Reanuda una ejecucion cuyo derecho **ya** se reclamo con `reclamar_reanudacion`.

        No vuelve a comprobar nada: la comprobacion y la reclamacion fueron atomicas
        en `reclamar_reanudacion`, y repetirla aqui -cuando la reanudacion puede
        llegar con retraso por el trabajador- reabriria justo la ventana que se
        quiere cerrar. Libera la reclamacion al terminar, salga bien o mal.
        """
        try:
            valor = decision.value if isinstance(decision, ApprovalDecision) else decision
            # **No se convierte a texto lo que no sea una `ApprovalDecision`.** La
            # version anterior hacia `str(decision)` para cualquier otra cosa, y eso
            # convertia un diccionario de correcciones en la cadena
            # `"{'decision': 'modified', ...}"`. La puerta de requisitos recibia una
            # cadena irreconocible y la trataba -correctamente- como un rechazo: la
            # via de corregir los requisitos **no funcionaba** a traves del motor.
            # La conversion solo tiene sentido para el enum, que es lo que el grafo
            # espera como texto.
            with self._lock_de(run_id):
                return self._ejecutar(Command(resume=valor), run_id)
        finally:
            self.olvidar_reclamacion(run_id)

    def rollback(self, run_id: str) -> RunState:
        """Revierte en 1 clic los archivos promovidos por esta ejecucion."""
        from ai_swe.tools.rollback import RollbackError

        with self._lock_de(run_id):
            estado = self.get(run_id)
            receipt = estado.promotion_receipt or self.rollbacks.for_run(run_id)
            if receipt is None:
                raise RollbackError("La ejecucion no tiene recibo de promocion")
            alcance = (
                estado.interpretation.scope
                if estado.interpretation is not None
                else estado.options
            )
            repo = alcance.repo_path or estado.options.repo_path
            if not repo:
                raise RollbackError("La ejecucion no tiene repositorio asociado")
            self.rollbacks.rollback(
                receipt.receipt_id,
                repo,
                allowed_paths=tuple(alcance.allowed_paths),
                protected_paths=tuple(alcance.protected_paths),
            )
            actualizado = self.rollbacks.for_run(run_id)
            datos = estado.model_dump()
            datos["promotion_receipt"] = (
                actualizado.model_dump() if actualizado is not None else None
            )
            datos["updated_at"] = _ahora()
            nuevo = RunState.model_validate(datos)
            config = self._config(run_id)
            if self._app.get_state(config).values:
                self._app.update_state(config, nuevo.model_dump())
            self._store.sync(nuevo)
            return nuevo

    def request_pause(self, run_id: str) -> RunState:
        """Solicita una pausa manual cooperativa en frontera de nodo."""
        estado = self.get(run_id)
        if estado.status.is_terminal:
            raise NothingToResume(
                f"la ejecucion {run_id} ya esta en estado terminal ({estado.status.value})"
            )
        if estado.status.is_awaiting_human or estado.status is RunStatus.PAUSED:
            self.continuity.capture_run(estado)
            return estado
        lock = self._lock_de(run_id)
        if lock.acquire(blocking=False):
            try:
                actual = self.get(run_id)
                if not actual.status.is_terminal and not actual.status.is_awaiting_human:
                    self.continuity.set_checkpoint_status(run_id, RunStatus.PAUSED)
                    actual = self.get(run_id)
                    self.continuity.capture_run(actual)
                return actual
            finally:
                lock.release()
        with self._locks_guard:
            self._pause_requested.add(run_id)
        return estado

    def resume_paused(self, run_id: str) -> RunState:
        """Reanuda explicitamente una ejecucion en estado `paused`."""
        with self._lock_de(run_id):
            estado = self.get(run_id)
            if estado.status is not RunStatus.PAUSED:
                raise NothingToResume(
                    f"la ejecucion {run_id} no esta en pausa manual (estado: {estado.status.value})"
                )
            with self._locks_guard:
                self._pause_requested.discard(run_id)
            self.continuity.set_checkpoint_status(run_id, RunStatus.RUNNING)
            config = self._config(run_id)
            if self._app.get_state(config).values:
                return self._ejecutar(None, run_id)
            return self._ejecutar(self._store.initial_state(run_id), run_id)

    # ---------------------------------------------------------------- interno
    @staticmethod
    def _config(run_id: str) -> dict:
        return {"configurable": {"thread_id": run_id}}

    def _ejecutar(self, entrada, run_id: str) -> RunState:
        from ai_swe.graph.activity import activity_sink

        with activity_sink(lambda kind, data: self._store.append_event(run_id, EventKind(kind), data)):
            return self._ejecutar_con_actividad(entrada, run_id)

    def _ejecutar_con_actividad(self, entrada, run_id: str) -> RunState:
        config = self._config(run_id)
        self._store.append_event(run_id, EventKind.RUN_STARTED, {})

        for trozo in self._app.stream(entrada, config, stream_mode="updates"):
            for nodo, salida in trozo.items():
                if nodo == "__interrupt__":
                    carga = _carga_interrupcion(salida)
                    # `run.awaiting_human` es el evento general de cualquier puerta.
                    # Hasta M2 solo habia una y el nombre bastaba; con dos (requisitos
                    # y aprobacion) decir "awaiting_approval" al parar en la de
                    # requisitos seria falso. **Que** puerta espera se lee del estado
                    # (`RunStatus`) o de `next_step`, no del nombre del evento.
                    self._store.append_event(run_id, EventKind.RUN_AWAITING_HUMAN, carga)
                    continue
                # F11 (AUD-11): `run.step` **se retiro**. El nombre del nodo deja de
                # viajar como dato dentro de `run.step` y pasa a ser un **tipo** de
                # evento (`requirements.completed`, `plan.completed`, ...), que es lo
                # que permite al cliente un `switch` exhaustivo. Un nodo sin hito
                # nombrado (p. ej. `research`) no emite nada: su avance queda
                # registrado en el punto de control y en `GET /runs/{id}`, que es
                # donde el cliente lee el estado.
                hito = EVENTO_POR_NODO.get(nodo)
                if hito is not None:
                    self._store.append_event(run_id, hito, {"node": nodo})
                # Se sincroniza el indice en cada paso para que `GET /runs/{id}`
                # refleje el avance mientras la ejecucion sigue en curso.
                current = self._estado_actual(config, run_id)
                self._store.sync(current)
                self.memory.project(current)
                self.continuity.capture_run(current)
                with self._locks_guard:
                    pausar = run_id in self._pause_requested
                    if pausar:
                        self._pause_requested.discard(run_id)
                if pausar and not current.status.is_terminal and not current.status.is_awaiting_human:
                    self.continuity.set_checkpoint_status(run_id, RunStatus.PAUSED)
                    break

        return self._persistir(run_id, self._estado_actual(config, run_id))

    def _estado_actual(self, config: dict, run_id: str) -> RunState:
        instantanea = self._app.get_state(config)
        if not instantanea.values:
            raise RunNotFound(run_id)
        return RunState.model_validate(instantanea.values)

    def _persistir(self, run_id: str, estado: RunState) -> RunState:
        estado = self._aplicar_red_de_seguridad(estado)

        self._store.sync(estado)
        self.memory.project(estado)
        self.continuity.capture_run(estado)
        # F11 (AUD-11): `run.status`, `run.report` y `run.error` **se retiraron**.
        #
        # Que los sustituye:
        #   - `run.status` -> el estado se lee de `GET /runs/{id}`, que es la fuente
        #     autoritativa y no se pierde en el hueco entre lotes del flujo.
        #   - `run.report` -> `final_report` viaja en el estado; el cliente lo lee al
        #     llegar `run.completed`, sin un evento aparte que pueda desincronizarse.
        #   - `run.error`  -> los errores viajan en `estado.errors` y el desenlace
        #     terminal se anuncia con `run.failed`, que lleva el recuento.
        #
        # Se mantienen `run.created` y `run.started` (marcas de arranque sin
        # sustituto canonico) y `run.done` (la senal de cierre del flujo, que no es
        # un alias de nada).
        #
        # F10: resultado explicito. Se emite **antes** de `run.done` a proposito:
        # `run.done` es el evento con el que el flujo SSE cierra, asi que cualquier
        # cosa que se escriba despues puede perderse si cae en el lote siguiente.
        #
        # **Una espera humana no es un resultado.** `_persistir` se ejecuta tambien
        # cuando el grafo se detiene en una puerta, y marcar eso como `run.failed`
        # seria decirle al cliente que algo salio mal justo cuando el sistema esta
        # haciendo lo que debe: pedir una decision. Solo los estados terminales
        # tienen resultado.
        if estado.status is RunStatus.COMPLETED:
            resultado: EventKind | None = EventKind.RUN_COMPLETED
        elif estado.status.is_terminal:
            resultado = EventKind.RUN_FAILED
        else:
            resultado = None
        if resultado is not None:
            self._store.append_event(
                run_id,
                resultado,
                {"status": estado.status.value, "error_count": len(estado.errors)},
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
        # F11 (AUD-11): se retiro `run.error`. El desenlace ya se anuncia con
        # `run.failed` (que lleva el recuento de errores) y el error concreto viaja
        # en `estado.errors`, que el cliente lee de `GET /runs/{id}`. Un evento de
        # error aparte era una tercera copia de lo mismo.
        self._store.append_event(
            run_id,
            EventKind.RUN_FAILED,
            {"status": RunStatus.NEEDS_HUMAN.value, "error_count": len(nuevo.errors)},
        )
        self._store.append_event(run_id, EventKind.RUN_DONE, {"status": RunStatus.NEEDS_HUMAN.value})
        # **El worktree tambien se limpia por aqui.** `finalize` es el unico punto por
        # el que pasan las rutas terminales del grafo, pero un fallo del trabajador
        # **no llega a `finalize`**: sin esto, una excepcion sin capturar dejaba el
        # worktree vivo en `var/workspaces` para siempre, y el repositorio del usuario
        # acumulaba referencias fantasma. Es el mismo teardown, desde la otra puerta.
        limpiar_worktree(
            nuevo.artifacts.worktree_path,
            repo_original=_repositorio_de(nuevo),
            run_id=run_id,
            base_commit=nuevo.artifacts.base_commit or "",
        )
        return nuevo

    @staticmethod
    def _aplicar_red_de_seguridad(estado: RunState) -> RunState:
        """Garantiza que ninguna ejecucion queda colgada (`MET-13`).

        Una espera humana no es anomalia: es una ejecucion detenida a proposito, y
        las dos puertas del flujo -confirmacion de requisitos y aprobacion de
        cambios- cuentan. Cualquier otro estado no terminal al volver del grafo si
        lo es, y significa que la topologia tiene un camino sin salida.
        """
        if (
            estado.status.is_terminal
            or estado.status.is_awaiting_human
            or estado.status is RunStatus.PAUSED
        ):
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


def _puerta_pendiente(app, config) -> str | None:
    """Nombre del nodo que tiene la ejecucion detenida, o `None` si no espera.

    `Snapshot.next` es la tupla de nodos que LangGraph ejecutara a continuacion;
    con la ejecucion interrumpida es el nodo que interrumpio, que es lo que permite
    distinguir **que** puerta humana esta esperando.

    Se captura cualquier excepcion porque esto es **diagnostico**: se usa para
    decidir que evento emitir, y un fallo al leerlo no puede tumbar una ejecucion
    que por lo demas va bien. Si no se puede saber, se devuelve `None` y el evento
    general `run.awaiting_human` ya se ha emitido de todos modos.
    """
    try:
        siguiente = app.get_state(config).next
    except Exception:  # noqa: BLE001 - diagnostico, nunca debe propagar
        return None
    return siguiente[0] if siguiente else None


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
