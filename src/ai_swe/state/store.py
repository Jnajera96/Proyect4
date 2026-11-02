"""Almacen de estado de las ejecuciones.

Cuatro responsabilidades:

  1. El **checkpointer** de LangGraph: el estado completo por punto de control. Es
     lo que permite reanudar (`RF-12`, `RNF-D1`).
  2. El **estado inicial** de cada ejecucion, persistido aparte del checkpoint. Hace
     falta porque la ejecucion ya no ocurre dentro de la peticion: el trabajador
     recibe un `run_id` y debe poder reconstruir con que empezar. Ademas separa
     "lo que se pidio" de "lo que ocurrio", que es lo que hace auditable una
     ejecucion.
  3. Un **indice de ejecuciones** para listados y paneles.
  4. Un **registro de eventos** persistente. No es una cola en memoria a proposito:
     es lo que permite que un navegador que se reconecta pida solo lo que se
     perdio, y lo que hace que la trazabilidad sobreviva a una recarga.

Nota sobre `SQLite`: un solo escritor a la vez y fichero local. Es suficiente para
el prototipo y es el primer componente que se sustituye al escalar
(`docs/02-tecnologias.md`, seccion 8).
"""

from __future__ import annotations

import importlib
import inspect
import json
import pkgutil
import sqlite3
import threading
from datetime import UTC, datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from ai_swe.contracts import Project, RunEvent, RunState, RunStatus, RunSummary
from ai_swe.contracts.api import EventKind
from ai_swe.security import redact_deep
from ai_swe.state.migrations import LATEST_VERSION, SchemaMigrator

ESQUEMA_VERSION = LATEST_VERSION


@lru_cache(maxsize=1)
def msgpack_allowlist() -> tuple[tuple[str, str], ...]:
    """Tipos de contrato que el checkpointer puede deserializar.

    Se recorre el paquete `ai_swe.contracts` en lugar de usar `__all__`: la
    primera version lo hacia con `__all__` y **dejaba fuera** `Outputs`,
    `Artifacts` y `Evidence`, que no estaban exportados. El resultado no era un
    error, era peor: el checkpoint los descartaba en silencio y el estado
    recuperado perdia datos sin avisar.

    Recorrer los modulos no depende de que alguien recuerde exportar un tipo nuevo.
    """
    import ai_swe.contracts as paquete

    pares: set[tuple[str, str]] = set()
    for info in pkgutil.iter_modules(paquete.__path__, paquete.__name__ + "."):
        modulo = importlib.import_module(info.name)
        for _, obj in inspect.getmembers(modulo, inspect.isclass):
            if obj.__module__ != info.name:
                continue  # importado, no definido aqui
            if issubclass(obj, (BaseModel, Enum)):
                pares.add((obj.__module__, obj.__name__))
    return tuple(sorted(pares))



def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).isoformat()


def _fecha(texto: str) -> datetime:
    return datetime.fromisoformat(texto)


def _aplicar_pragmas(con: sqlite3.Connection, *, fijar_modo: bool = False) -> None:
    """Ajustes para que la base soporte accesos concurrentes.

    `WAL` permite que las lecturas del hilo que atiende HTTP no bloqueen la
    escritura del hilo que ejecuta. `busy_timeout` hace que una escritura que
    coincide con otra **espere** en lugar de fallar con `database is locked`.

    `fijar_modo` solo se activa al crear la base. **`PRAGMA journal_mode=WAL`
    necesita un bloqueo exclusivo momentaneo**, asi que aplicarlo en cada conexion
    nueva chocaba con las escrituras en curso y producia `database is locked` bajo
    concurrencia. El modo es persistente en el fichero: se fija una vez.
    """
    if fijar_modo:
        con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=15000")
    con.execute("PRAGMA synchronous=NORMAL")


class RunStore:
    """Almacen SQLite: checkpointer, estado inicial, indice y eventos.

    Cada hilo que ejecuta el grafo recibe **su propia conexion** para el
    checkpointer. Compartir una sola conexion entre el hilo de la peticion y los
    trabajadores no es seguro, aunque se pase `check_same_thread=False`: SQLite
    serializa las sentencias, pero no la transaccion completa.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        SchemaMigrator().migrate_database(self._db_path)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        _aplicar_pragmas(self._conn, fijar_modo=True)
        self._lock = threading.RLock()
        self._conexiones_extra: list[sqlite3.Connection] = []

    # ------------------------------------------------------------ ciclo de vida
    def close(self) -> None:
        """Cerrar es obligatorio en Windows: un descriptor abierto impide borrar
        el fichero y `TemporaryDirectory` falla al limpiar con WinError 32."""
        with self._lock:
            for con in self._conexiones_extra:
                try:
                    con.close()
                except sqlite3.Error:
                    pass
            self._conexiones_extra.clear()
            self._conn.close()

    def __enter__(self) -> RunStore:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------- checkpointer
    def checkpointer(self):
        """Devuelve un checkpointer de LangGraph con **su propia conexion**.

        Una conexion nueva por llamada, no la compartida. El motor compila el
        grafo una vez por hilo, asi que cada hilo de ejecucion acaba con su propia
        conexion al mismo fichero, y `WAL` permite que las lecturas del hilo de la
        peticion no se bloqueen entre si.
        """
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
        from langgraph.checkpoint.sqlite import SqliteSaver

        conexion = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conexion.row_factory = sqlite3.Row
        _aplicar_pragmas(conexion)
        with self._lock:
            self._conexiones_extra.append(conexion)

        serde = JsonPlusSerializer(allowed_msgpack_modules=list(msgpack_allowlist()))
        return SqliteSaver(conexion, serde=serde)

    # ----------------------------------------------------------- estado inicial
    def create(self, state: RunState) -> RunSummary:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO runs (run_id, trace_id, status, intent,"
                " created_at, updated_at, error_count, state_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    state.run_id,
                    state.trace_id,
                    state.status.value,
                    state.interpretation.intent.value if state.interpretation else None,
                    _iso(state.created_at),
                    _iso(state.updated_at),
                    len(state.errors),
                    state.model_dump_json(),
                ),
            )
            self._conn.commit()
        resumen = self.summary(state.run_id)
        assert resumen is not None
        return resumen

    def initial_state(self, run_id: str) -> RunState:
        """Reconstruye el estado con el que se creo la ejecucion.

        Es lo que permite que el trabajador ejecute a partir de un `run_id` en
        lugar de recibir un objeto en memoria. Sin esto, una ejecucion aceptada
        pero no iniciada se perderia al reiniciar el proceso.
        """
        with self._lock:
            fila = self._conn.execute(
                "SELECT state_json FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if fila is None:
            raise KeyError(run_id)
        return RunState.model_validate_json(fila["state_json"])

    def sync(self, state: RunState) -> None:
        """Refleja el estado actual en el indice. No toca `state_json`."""
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET status = ?, intent = ?, updated_at = ?, error_count = ?"
                " WHERE run_id = ?",
                (
                    state.status.value,
                    state.interpretation.intent.value if state.interpretation else None,
                    _iso(state.updated_at),
                    len(state.errors),
                    state.run_id,
                ),
            )
            self._conn.commit()

    def summary(self, run_id: str) -> RunSummary | None:
        with self._lock:
            fila = self._conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _a_resumen(fila) if fila else None

    def list_summaries(self, limit: int = 50) -> list[RunSummary]:
        with self._lock:
            filas = self._conn.execute(
                "SELECT * FROM runs ORDER BY updated_at DESC LIMIT ?", (max(1, limit),)
            ).fetchall()
        return [_a_resumen(f) for f in filas]

    # ------------------------------------------------------------- proyectos
    def crear_proyecto(self, proyecto: Project) -> Project:
        """Registra un proyecto. El `project_id` lo decide quien llama.

        `INSERT OR REPLACE` no: registrar dos veces el mismo id pisaria en silencio
        la ruta del anterior, y una ejecucion lanzada contra el proyecto acabaria
        trabajando sobre otro repositorio sin que nadie lo hubiera pedido. La
        violacion de clave primaria es la respuesta correcta.
        """
        with self._lock:
            self._conn.execute(
                ("INSERT INTO projects (project_id, name, repo_path, created_at) "
                 "VALUES (?, ?, ?, ?)"),
                (
                    proyecto.project_id,
                    proyecto.name,
                    proyecto.repo_path,
                    _iso(proyecto.created_at),
                ),
            )
            self._conn.commit()
        return proyecto

    def proyecto(self, project_id: str) -> Project | None:
        with self._lock:
            fila = self._conn.execute(
                "SELECT * FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
        if fila is None:
            return None
        return Project(
            project_id=fila["project_id"],
            name=fila["name"],
            repo_path=fila["repo_path"],
            created_at=_fecha(fila["created_at"]),
        )

    def eliminar_proyecto(self, project_id: str) -> bool:
        """Da de baja un proyecto del almacen.

        No toca los archivos del disco ni el repositorio Git. Devuelve True si
        existia y se elimino, False si no existia.
        """
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM projects WHERE project_id = ?", (project_id,)
            )
            self._conn.commit()
            return cur.rowcount > 0

    def listar_proyectos(self, limit: int = 50) -> list[Project]:
        with self._lock:
            filas = self._conn.execute(
                "SELECT * FROM projects ORDER BY created_at DESC LIMIT ?", (max(1, limit),)
            ).fetchall()
        return [
            Project(
                project_id=f["project_id"],
                name=f["name"],
                repo_path=f["repo_path"],
                created_at=_fecha(f["created_at"]),
            )
            for f in filas
        ]

    def orphan_open_runs(self) -> list[str]:
        """Marca como escaladas las ejecuciones que quedaron a medias.

        Al arrancar, cualquier ejecucion en `planned` o `running` pertenece a un
        proceso que ya no existe: nadie la va a continuar. Dejarlas asi seria
        exactamente la terminacion anomala que `MET-13` prohibe, y ademas el
        navegador se quedaria esperando para siempre.
        """
        abiertas = [
            fila["run_id"]
            for fila in self._conn.execute(
                "SELECT run_id FROM runs WHERE status IN (?, ?)",
                (RunStatus.PLANNED.value, RunStatus.RUNNING.value),
            ).fetchall()
        ]
        for run_id in abiertas:
            with self._lock:
                self._conn.execute(
                    "UPDATE runs SET status = ?, updated_at = ? WHERE run_id = ?",
                    (RunStatus.NEEDS_HUMAN.value, _iso(datetime.now(UTC)), run_id),
                )
                self._conn.commit()
            self.append_event(
                run_id,
                EventKind.RUN_FAILED,
                {
                    "status": RunStatus.NEEDS_HUMAN.value,
                    "error_class": "ORPHANED_RUN",
                    "message": "el proceso que ejecutaba esta ejecucion ya no existe",
                },
            )
            # Tambien se emite `run.done`: es la senal de fin del flujo de eventos.
            # Sin ella, un navegador que se reconecte a una ejecucion huerfana se
            # quedaria esperando un evento que no va a llegar.
            self.append_event(run_id, EventKind.RUN_DONE, {"status": RunStatus.NEEDS_HUMAN.value})
        return abiertas

    def recover_from_crash(self) -> dict:
        """Verifica la integridad de la base y consolida diarios WAL pendientes tras un corte."""
        with self._lock:
            integrity = self._conn.execute("PRAGMA integrity_check").fetchone()
            is_ok = bool(integrity and integrity[0] == "ok")
            if not is_ok:
                raise sqlite3.DatabaseError("Fallo de integridad: restaura un respaldo verificado")
            checkpoint = self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            self._conn.commit()
            return {
                "integrity_ok": is_ok,
                "wal_checkpoint": list(checkpoint) if checkpoint else None,
            }

    # ------------------------------------------------------------------ eventos
    def append_event(self, run_id: str, kind: EventKind, data: dict | None = None) -> RunEvent:
        """Anade un evento en una sola sentencia.

        El numero de secuencia se calcula dentro del propio `INSERT` en lugar de
        con un `SELECT MAX(seq)` previo. No es microoptimizacion: cada sentencia
        adicional es una transaccion mas compitiendo por el unico escritor de
        SQLite, y con varias ejecuciones a la vez esa contencion se nota.

        **La carga pasa por el redactor (`RNF-S3`, F10).** Este es el unico punto
        por el que un evento llega al registro y al flujo SSE, asi que redactar aqui
        cubre **todos** los eventos, presentes y futuros, sin depender de que cada
        emisor se acuerde. Un evento que llevara una clave en claro -por ejemplo una
        instruccion del usuario que la incluya, o el mensaje de un error del
        proveedor- la publicaria al navegador tal cual; el filtro de logging no la
        veria, porque esto no pasa por el logging.
        """
        momento = datetime.now(UTC)
        redactado = redact_deep(data or {})
        carga = json.dumps(redactado, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            fila = self._conn.execute(
                "INSERT INTO run_events (run_id, seq, at, kind, data)"
                " SELECT ?, COALESCE(MAX(seq), 0) + 1, ?, ?, ? FROM run_events WHERE run_id = ?"
                " RETURNING seq",
                (run_id, _iso(momento), kind.value, carga, run_id),
            ).fetchone()
            self._conn.commit()
        return RunEvent(seq=int(fila["seq"]), at=momento, kind=kind, data=json.loads(carga))

    def events(self, run_id: str, after_seq: int = 0) -> list[RunEvent]:
        """Eventos de una ejecucion posteriores a `after_seq`.

        La lectura tambien toma el cerrojo. **No es exceso de celo:** la primera
        version dejaba leer sin cerrojo mientras un trabajador escribia sobre la
        **misma conexion**, y bajo concurrencia eso producia
        `database is locked`. Una conexion de SQLite se usa desde un hilo a la vez,
        y eso incluye las lecturas.
        """
        with self._lock:
            filas = self._conn.execute(
                "SELECT seq, at, kind, data FROM run_events"
                " WHERE run_id = ? AND seq > ? ORDER BY seq",
                (run_id, max(0, after_seq)),
            ).fetchall()
        return [
            RunEvent(
                seq=f["seq"],
                at=_fecha(f["at"]),
                kind=EventKind(f["kind"]),
                data=json.loads(f["data"]),
            )
            for f in filas
        ]


def _a_resumen(fila: sqlite3.Row) -> RunSummary:
    estado = RunStatus(fila["status"])
    return RunSummary(
        run_id=fila["run_id"],
        trace_id=fila["trace_id"],
        status=estado,
        intent=fila["intent"],
        created_at=_fecha(fila["created_at"]),
        updated_at=_fecha(fila["updated_at"]),
        error_count=int(fila["error_count"]),
        awaiting_approval=estado is RunStatus.AWAITING_APPROVAL,
    )
