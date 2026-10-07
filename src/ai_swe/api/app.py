"""Capa HTTP: rutas, validacion de entrada y progreso en vivo.

Cambios respecto de la primera version, motivados por el navegador como interfaz
principal:

  - **`POST /runs` responde 202 y no bloquea.** Devuelve el `run_id` de inmediato
    para que el cliente pueda suscribirse **antes** de que ocurra nada. Con la
    ejecucion dentro de la peticion el identificador llegaba al terminar, asi que
    el progreso en vivo era estructuralmente imposible.
  - **El flujo SSE emite en vivo**, con `id:` por evento para que el navegador se
    reconecte con `Last-Event-ID` y reciba solo lo que se perdio.
  - **El frontend se sirve desde el mismo origen** (`/app`), asi que el prototipo no
    necesita CORS. La lista de origenes permitidos existe para el desarrollo con un
    servidor de frontend aparte.

Decisiones que se mantienen y conviene declarar:

  - **`POST /runs` no acepta audio.** El audio entra por `/transcriptions`, que
    devuelve texto y **no crea ejecucion**. La regla la impone el contrato
    `Instruction`, no un `if` en el manejador.
  - **Cancelar no esta implementado** (501). Ahora que la ejecucion sale de la
    peticion si seria posible, pero exige senalizar al trabajador para que abandone
    la ejecucion en curso; llega cuando haya trabajo lento que interrumpir.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
from sse_starlette.sse import EventSourceResponse

from ai_swe.contracts import (
    ApprovalDecision,
    EventKind,
    InstructionSource,
    RunOptions,
    RunState,
    RunStatus,
    RunSummary,
    TranscriptMeta,
)
from ai_swe.graph.engine import NothingToResume, RunEngine, RunNotFound
from ai_swe.graph.worker import RunWorker
from ai_swe.state import RunStore
from ai_swe.stt.base import FakeAdapter, STTAdapter, Transcript

log = logging.getLogger(__name__)

TERMINALES = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.NEEDS_HUMAN, RunStatus.CANCELLED}
FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"


class RunRequest(BaseModel):
    """Peticion de creacion de una ejecucion. Solo texto confirmado."""

    instruction: str = Field(min_length=1, max_length=20_000)
    source: InstructionSource = InstructionSource.TEXT
    transcript_meta: TranscriptMeta | None = None
    options: RunOptions = Field(default_factory=RunOptions)


class ApproveRequest(BaseModel):
    decision: ApprovalDecision = ApprovalDecision.APPROVED


def _detalle_validacion(exc: ValidationError) -> list[dict]:
    """Convierte los errores de Pydantic en algo serializable.

    Hace falta porque cuando un `model_validator` lanza `ValueError`, Pydantic
    guarda **la instancia de la excepcion** en `ctx`. FastAPI intenta serializarla
    y falla con `TypeError: Object of type ValueError is not JSON serializable`,
    de modo que un 422 limpio se convierte en un 500. Se proyectan solo los campos
    que se pueden enviar.
    """
    return [
        {
            "loc": [str(parte) for parte in error.get("loc", ())],
            "msg": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        for error in exc.errors()
    ]


def crear_app(
    store: RunStore | None = None,
    stt: STTAdapter | None = None,
    worker: RunWorker | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    # La ruta del almacen se puede sobrescribir por entorno. Es lo que permite que
    # una verificacion arranque con una base limpia y sea **reproducible**: sin
    # esto, la comprobacion del navegador medía una base que crecia entre
    # ejecuciones y sus numeros cambiaban sin que cambiara el codigo.
    ruta_estado = os.environ.get("AI_SWE_STATE_DB_PATH", "var/state.sqlite3")
    almacen = store or RunStore(ruta_estado)
    adaptador_stt = stt or FakeAdapter()
    motor = RunEngine(almacen)
    trabajador = worker or RunWorker(motor)
    origenes = cors_origins if cors_origins is not None else []

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        # Recuperacion al arrancar: una ejecucion en `planned` o `running`
        # pertenece a un proceso que ya no existe. Dejarla asi seria la terminacion
        # anomala que MET-13 prohibe, y el navegador esperaria para siempre.
        huerfanas = almacen.orphan_open_runs()
        if huerfanas:
            log.warning("ejecuciones huerfanas marcadas como escaladas: %s", huerfanas)
        try:
            yield
        finally:
            # Se espera a las ejecuciones aceptadas **antes** de cerrar el almacen.
            # Cerrar por debajo de un trabajador activo lo hace fallar con
            # `Cannot operate on a closed database` y deja la ejecucion sin estado
            # terminal. El orden importa.
            trabajador.shutdown(wait=True)
            if store is None:
                almacen.close()

    app = FastAPI(
        title="AI Software Engineering System",
        version="0.2.0",
        description=(
            "Proyecto 4, Equipo 4. Fase M1: esqueleto ejecutable con ejecucion "
            "asincrona y progreso en vivo. Los nodos del grafo son deterministas y "
            "sin modelo."
        ),
        lifespan=ciclo_de_vida,
    )

    if origenes:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origenes,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.state.store = almacen
    app.state.engine = motor
    app.state.worker = trabajador

    # ------------------------------------------------------------------ salud
    @app.get("/health")
    def salud() -> dict:
        return {
            "status": "ok",
            "fase": "M1",
            "stt": adaptador_stt.health(),
            "ejecuciones": len(almacen.list_summaries(limit=1000)),
        }

    # ----------------------------------------------------------- transcripcion
    @app.post("/transcriptions", response_model=Transcript)
    async def transcribir(
        audio: UploadFile = File(...),
        vocabulary: str | None = Form(default=None),
    ) -> Transcript:
        """Convierte audio en texto. **No crea ninguna ejecucion** (`RF-02`)."""
        datos = await audio.read()
        if not datos:
            raise HTTPException(status_code=422, detail="el audio esta vacio")
        vocabulario = [v for v in (vocabulary or "").split(",") if v.strip()]
        return adaptador_stt.transcribe(datos, vocabulary=vocabulario or None)

    # ------------------------------------------------------------ ejecuciones
    @app.post("/runs", response_model=RunState, status_code=202)
    def crear_run(peticion: RunRequest) -> RunState:
        """Crea la ejecucion y la encola. **No espera a que termine.**

        Responde 202 con el `run_id` para que el cliente pueda suscribirse al
        progreso de inmediato.
        """
        try:
            estado = motor.crear_estado(
                peticion.instruction,
                options=peticion.options,
                source=peticion.source.value,
                transcript_meta=peticion.transcript_meta,
            )
        except ValidationError as exc:
            # Aqui es donde se hace cumplir RF-03: una instruccion de origen 'voice'
            # sin confirmacion ni metadatos no supera el contrato.
            raise HTTPException(status_code=422, detail=_detalle_validacion(exc)) from exc

        motor.create(estado)
        trabajador.submit(estado.run_id)
        return estado

    @app.get("/runs", response_model=list[RunSummary])
    def listar_runs(limit: int = 50) -> list[RunSummary]:
        return almacen.list_summaries(limit)

    @app.get("/runs/{run_id}", response_model=RunState)
    def obtener_run(run_id: str) -> RunState:
        try:
            return motor.get(run_id)
        except RunNotFound as exc:
            raise HTTPException(status_code=404, detail=f"no existe la ejecucion {run_id}") from exc

    @app.get("/runs/{run_id}/events")
    async def eventos_run(
        run_id: str,
        after: int = 0,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
        timeout_s: float = 300.0,
    ) -> EventSourceResponse:
        """Progreso en vivo. Emite y cierra cuando la ejecucion llega a un terminal.

        Reanudable: si el navegador se reconecta, manda `Last-Event-ID` y solo
        recibe los eventos que se perdio. Es la razon de que el registro sea
        persistente y no una cola en memoria.
        """
        if almacen.summary(run_id) is None:
            raise HTTPException(status_code=404, detail=f"no existe la ejecucion {run_id}")

        desde = after
        if last_event_id and last_event_id.isdigit():
            desde = max(desde, int(last_event_id))

        async def flujo() -> AsyncIterator[dict]:
            ultimo = desde
            esperado = 0.0
            sin_novedades = 0
            while esperado < timeout_s:
                nuevos = almacen.events(run_id, ultimo)
                for evento in nuevos:
                    ultimo = evento.seq
                    yield {
                        "id": str(evento.seq),
                        "event": evento.kind.value,
                        "data": evento.model_dump_json(),
                    }
                # La senal de fin es el **evento** `run.done`, no el estado del
                # indice. Cerrar cuando el indice dice "terminal" producia una
                # carrera real: el indice se sincroniza antes de escribir los
                # eventos, asi que el flujo se cerraba y el cliente perdia
                # `run.status`, `run.report` y `run.done`.
                if any(e.kind is EventKind.RUN_DONE for e in nuevos):
                    return

                # Red de seguridad por si `run.done` no llega nunca: se espera un
                # margen de 2 s con el indice en terminal antes de cerrar. El
                # margen es muy superior a la ventana de milisegundos de la
                # carrera, de modo que no la reintroduce.
                resumen = almacen.summary(run_id)
                if resumen and resumen.status in TERMINALES and not nuevos:
                    sin_novedades += 1
                    if sin_novedades >= 40:
                        return
                else:
                    sin_novedades = 0

                await asyncio.sleep(0.05)
                esperado += 0.05

        # `ping` mantiene viva la conexion a traves de proxies que cerrarian una
        # conexion inactiva. Sin el, una ejecucion larga se corta en silencio.
        return EventSourceResponse(flujo(), ping=10)

    @app.post("/runs/{run_id}/approve", response_model=RunState)
    def aprobar_run(run_id: str, peticion: ApproveRequest) -> RunState:
        """Aprueba o rechaza la accion pendiente y reanuda el grafo.

        La reanudacion vuelve al trabajador: el cliente recibe el estado en cuanto
        el grafo arranca de nuevo, no cuando termina.
        """
        try:
            if not motor.pendiente_de_aprobacion(run_id):
                # Fuerza el error tipado correcto (404 o 409) sin reanudar nada.
                motor.resume(run_id, peticion.decision)
        except RunNotFound as exc:
            raise HTTPException(status_code=404, detail=f"no existe la ejecucion {run_id}") from exc
        except NothingToResume as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        trabajador.submit_resume(run_id, peticion.decision)
        return motor.get(run_id)

    @app.post("/runs/{run_id}/cancel", status_code=501)
    def cancelar_run(run_id: str) -> dict:
        """Cancelacion de una ejecucion en curso. Requiere senalizar al trabajador."""
        if almacen.summary(run_id) is None:
            raise HTTPException(status_code=404, detail=f"no existe la ejecucion {run_id}")
        raise HTTPException(
            status_code=501,
            detail=(
                "RF-16 no esta implementado: exige senalizar al trabajador para que abandone "
                "la ejecucion en curso, y todavia no hay trabajo lento que interrumpir. "
                "Llega con el modelo conectado (fase M2)."
            ),
        )

    # -------------------------------------------------------------- frontend
    if FRONTEND_DIR.is_dir():
        app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    return app
