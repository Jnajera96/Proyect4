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
import re
import sqlite3
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from ai_swe.config import load_settings, repositorio_autorizado
from ai_swe.contracts import (
    ApprovalDecision,
    EventKind,
    InstructionSource,
    Intent,
    Project,
    ProjectRequest,
    RunOptions,
    RunState,
    RunStatus,
    RunSummary,
    TranscriptMeta,
)
from ai_swe.graph.engine import NothingToResume, RunEngine, RunNotFound
from ai_swe.graph.worker import RunWorker
from ai_swe.models import BudgetExceededError
from ai_swe.sandbox import SandboxError, validar_repositorio
from ai_swe.security import install_redacting_filter
from ai_swe.state import RunStore
from ai_swe.stt.base import STTAdapter, STTError, STTNotAvailable, Transcript, crear_adaptador_stt

log = logging.getLogger(__name__)

TERMINALES = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.NEEDS_HUMAN, RunStatus.CANCELLED}


def _configurar_nivel_de_log(nivel: str) -> None:
    """Fija el nivel del logger raiz a partir de la configuracion validada.

    `log_level` ya paso por el validador de `Settings`, asi que aqui llega en
    mayusculas y dentro del conjunto permitido. Se envuelve igualmente en un
    `try` porque configurar el logging nunca debe impedir que el servicio arranque.
    """
    try:
        logging.getLogger().setLevel(nivel)
    except (ValueError, TypeError):  # pragma: no cover - defensivo
        log.warning("nivel de log invalido en configuracion: %r", nivel)
FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"

#: Directorio **construido** que se sirve en `/app`. Ver el montaje al final de
#: `crear_app`: se sirve lo compilado, no el fuente.
FRONTEND_DIST = FRONTEND_DIR / "dist"


class RunRequest(BaseModel):
    """Peticion de creacion de una ejecucion. Solo texto confirmado."""

    instruction: str = Field(min_length=1, max_length=20_000)
    source: InstructionSource = InstructionSource.TEXT
    transcript_meta: TranscriptMeta | None = None
    options: RunOptions = Field(default_factory=RunOptions)
    project_id: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Proyecto registrado contra el que ejecutar. Si se indica, su "
            "`repo_path` manda sobre el de `options`: el proyecto es la ruta "
            "**validada** en el alta, y dejar que una peticion la sustituya "
            "esquivaria esa validacion."
        ),
    )


class ApproveRequest(BaseModel):
    """Decision sobre la puerta de aprobacion (F12).

    `comments` solo tiene sentido al **pedir cambios**: son las instrucciones que el
    humano deja al Coder para la siguiente iteracion. En una aprobacion o un rechazo
    se ignoran, pero no se prohiben: un cliente no deberia tener que ramificar el
    cuerpo de la peticion segun la decision.

    **`decision` es obligatoria, y no por descuido.** Aprobar esta ruta **escribe en
    el repositorio del usuario**: promueve el parche aprobado desde el worktree. Un
    valor por defecto afirmativo convertia un cuerpo mal formado -un `{}`, un campo
    con el nombre mal escrito, un cliente que olvido el campo- en una promocion
    silenciosa. La decision la toma una persona: el sistema no puede suponerla.
    """

    decision: ApprovalDecision = Field(
        description="Decision humana. Sin valor por defecto: un cuerpo vacio es un 422."
    )
    comments: str | None = Field(
        default=None,
        max_length=2000,
        description="Comentarios del humano al pedir cambios. Viajan al RunState.",
    )


class ConfirmRequirementsRequest(BaseModel):
    """Respuesta a la puerta de requisitos (M2, item 3 del DoD).

    Ademas de confirmar o rechazar, permite **corregir** lo que el sistema
    entendio. Los campos de correccion son opcionales: sin ellos la peticion es una
    confirmacion limpia.

    **`decision` es obligatoria** por la misma razon que en `ApproveRequest`: es una
    decision humana y el sistema no puede suponerla. Un `{}` confirmaria la
    interpretacion sin que nadie lo haya pedido, y esa confirmacion es la que
    autoriza a planificar.
    """

    decision: ApprovalDecision = Field(
        description="Decision humana. Sin valor por defecto: un cuerpo vacio es un 422."
    )
    intent: Intent | None = None
    constraints: list[str] | None = None
    rationale: str | None = Field(default=None, max_length=2000)


def _valor_de_confirmacion(peticion: ConfirmRequirementsRequest) -> str | dict:
    """Traduce la peticion a lo que espera la puerta de requisitos.

    Sin correcciones se manda la decision como texto, que es la forma simple. Con
    correcciones se manda un objeto, porque es la unica forma de que viajen. La
    puerta acepta las dos (ver `nodes._confirmacion_del_humano`).
    """
    correcciones: dict = {}
    if peticion.intent is not None:
        correcciones["intent"] = peticion.intent.value
    if peticion.constraints is not None:
        correcciones["constraints"] = peticion.constraints
    if peticion.rationale is not None:
        correcciones["rationale"] = peticion.rationale
    if not correcciones:
        return peticion.decision.value
    return {"decision": peticion.decision.value, **correcciones}


def _valor_de_aprobacion(peticion: ApproveRequest) -> str | dict:
    """Traduce la peticion de aprobacion a lo que espera la puerta (F12).

    Sin comentarios se manda la decision como texto, que es la forma simple. Con
    comentarios se manda un objeto, porque es la unica forma de que viajen al
    `RunState`. La puerta acepta las dos (ver `nodes._decision_de_aprobacion`).
    """
    if peticion.comments:
        return {"decision": peticion.decision.value, "comments": peticion.comments}
    return peticion.decision.value


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


def _nuevo_project_id(nombre: str) -> str:
    """Identificador legible y unico para un proyecto.

    Legible porque aparece en las rutas y en los registros; unico por el sufijo
    aleatorio, porque dos proyectos pueden llamarse igual y el id es la clave
    primaria. Se normaliza al patron del contrato (`[a-z0-9][a-z0-9_-]*`).
    """
    base = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")[:40] or "proyecto"
    return f"{base}-{uuid.uuid4().hex[:8]}"


def registrar_manejadores_de_error(app: FastAPI) -> None:
    """Mapea las excepciones tipadas de dominio a respuestas HTTP estructuradas.

    **Por que centralizado y no un `try` por ruta.** Una excepcion de dominio que
    escape sin mapear llega al cliente como un 500 con una traza, que no dice que
    paso ni de quien es la culpa. Con un manejador por tipo, la respuesta es
    **accionable** y el mismo mapeo vale para toda ruta presente y futura.

    Se devuelve siempre un cuerpo con `error_class`, para que un cliente pueda
    ramificar por tipo sin leer el texto del mensaje.

    Nota sobre `PolicyViolationError`: **no existe en este repositorio**. El Policy
    Engine no lanza: devuelve `PolicyEffect.DENY` (`contracts/tools.py`), y una
    denegacion viaja como `RunError` tipado **dentro** de la ejecucion, no como una
    excepcion que cruce la frontera HTTP. Se mapea lo que de verdad puede escapar,
    no lo que una lista de deseos menciona.
    """

    def _cuerpo(exc: BaseException, error_class: str) -> dict:
        return {"detail": str(exc), "error_class": error_class}

    @app.exception_handler(RunNotFound)
    async def _no_encontrado(_peticion: Request, exc: RunNotFound):
        return JSONResponse(status_code=404, content=_cuerpo(exc, "RUN_NOT_FOUND"))

    @app.exception_handler(NothingToResume)
    async def _nada_que_reanudar(_peticion: Request, exc: NothingToResume):
        return JSONResponse(status_code=409, content=_cuerpo(exc, "NOTHING_TO_RESUME"))

    @app.exception_handler(SandboxError)
    async def _sandbox(_peticion: Request, exc: SandboxError):
        # 422 y no 500: el sandbox falla por algo del **entorno o de la peticion**
        # (una ruta que no es un repositorio, un worktree que no se puede crear),
        # no por un defecto del servidor.
        return JSONResponse(status_code=422, content=_cuerpo(exc, "SANDBOX_ERROR"))

    @app.exception_handler(BudgetExceededError)
    async def _presupuesto(_peticion: Request, exc: BudgetExceededError):
        # 429: el recurso que se agoto es el presupuesto, y el cliente puede
        # reintentar mas tarde con uno mayor. No es un fallo del servidor.
        return JSONResponse(status_code=429, content=_cuerpo(exc, "BUDGET_EXCEEDED"))

    @app.exception_handler(STTNotAvailable)
    async def _stt_no_disponible(_peticion: Request, exc: STTNotAvailable):
        # 503 y no 500: la **capacidad** no esta instalada (falta el extra `voice`),
        # no hay un defecto del servidor. El cliente puede seguir por texto, que es
        # como el sistema funciona sin STT.
        return JSONResponse(status_code=503, content=_cuerpo(exc, "STT_NOT_AVAILABLE"))

    @app.exception_handler(STTError)
    async def _stt(_peticion: Request, exc: STTError):
        # 422: el audio no se pudo transcribir por algo de la peticion (vacio, sin
        # voz reconocible) o del motor, no por un fallo del servidor.
        return JSONResponse(status_code=422, content=_cuerpo(exc, "STT_ERROR"))


def crear_app(
    store: RunStore | None = None,
    stt: STTAdapter | None = None,
    worker: RunWorker | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    # La configuracion se carga **una vez**, al construir la aplicacion. Los
    # manejadores la necesitan -la ruta del almacen y el alcance de repositorios- y
    # leerla dos veces, aqui y en el arranque, dejaba dos copias que podian
    # discrepar. El ciclo de vida se queda con lo que si es de arranque: la
    # redaccion de secretos y el nivel de log.
    #
    # La ruta del almacen sale de `Settings`, no de un `os.environ.get` aparte: asi
    # `AI_SWE_STATE_DB_PATH` en el entorno **o** en `.env` funcionan igual, y hay una
    # sola fuente tipada. Sigue permitiendo que una verificacion arranque con una
    # base limpia y sea reproducible.
    ajustes = load_settings()
    almacen = store or RunStore(ajustes.state_db_path)
    # F13: el adaptador se elige por configuracion (`AI_SWE_STT_PROVIDER`). El
    # defecto es el adaptador local real; `fake` queda para pruebas y para entornos
    # sin la dependencia `voice`. Antes el defecto era `FakeAdapter`, que devolvia un
    # texto fijo con independencia del audio: una transcripcion fabricada.
    adaptador_stt = stt or crear_adaptador_stt()
    motor = RunEngine(almacen, settings=ajustes)
    trabajador = worker or RunWorker(motor)
    origenes = cors_origins if cors_origins is not None else []

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        # La redaccion de secretos se instala ANTES de cualquier otra cosa: si un
        # arranque posterior falla y registra su error, ese error ya pasa por el
        # filtro. Hacerlo al final dejaria una ventana sin proteccion justo en el
        # momento en que la configuracion (con sus claves) esta en la mano.
        install_redacting_filter()
        _configurar_nivel_de_log(ajustes.log_level)

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

    registrar_manejadores_de_error(app)

    # ------------------------------------------------------------------ salud
    @app.get("/health")
    def salud() -> dict:
        return {
            "status": "ok",
            "fase": "M3",
            "stt": adaptador_stt.health(),
            "ejecuciones": len(almacen.list_summaries(limit=1000)),
            "proyectos": len(almacen.listar_proyectos(limit=1000)),
        }

    # ------------------------------------------------------------- proyectos
    @app.post("/projects", response_model=Project, status_code=201)
    def crear_proyecto(peticion: ProjectRequest) -> Project:
        """Registra un repositorio para poder ejecutar contra el.

        La ruta se **valida aqui**, en el alta, y no al lanzar una ejecucion: un
        repositorio inexistente o que no sea git se rechaza en el momento en que
        alguien lo declara, con un 422 que dice que pasa, en lugar de dentro de una
        ejecucion ya en marcha. Es la razon de que el proyecto exista como concepto
        en vez de llevar la ruta suelta en cada peticion.
        """
        ruta = validar_repositorio(peticion.repo_path)
        if not repositorio_autorizado(ajustes, ruta):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"el repositorio '{ruta}' queda fuera del alcance autorizado en "
                    "AI_SWE_AUTHORIZED_REPOS"
                ),
            )
        proyecto = Project(
            project_id=_nuevo_project_id(peticion.name),
            name=peticion.name,
            repo_path=str(ruta),
            created_at=datetime.now(UTC),
        )
        try:
            return almacen.crear_proyecto(proyecto)
        except sqlite3.IntegrityError as exc:  # pragma: no cover - colision de id
            raise HTTPException(
                status_code=409, detail=f"ya existe un proyecto con id {proyecto.project_id}"
            ) from exc

    @app.get("/projects", response_model=list[Project])
    def listar_proyectos(limit: int = 50) -> list[Project]:
        return almacen.listar_proyectos(limit)

    @app.get("/projects/{project_id}", response_model=Project)
    def obtener_proyecto(project_id: str) -> Project:
        proyecto = almacen.proyecto(project_id)
        if proyecto is None:
            raise HTTPException(status_code=404, detail=f"no existe el proyecto {project_id}")
        return proyecto

    # ----------------------------------------------------------- transcripcion
    @app.post("/transcriptions", response_model=Transcript)
    async def transcribir(
        audio: UploadFile = File(...),
        vocabulary: str | None = Form(default=None),
    ) -> Transcript:
        """Convierte audio en texto. **No crea ninguna ejecucion** (`RF-02`).

        La transcripcion corre en un **hilo aparte**. Es trabajo intensivo de CPU
        -segundos por minuto de audio en el adaptador local-, y hacerlo dentro del
        bucle de eventos bloquearia todas las demas peticiones mientras dura,
        incluido el flujo SSE de una ejecucion en curso.
        """
        datos = await audio.read()
        if not datos:
            raise HTTPException(status_code=422, detail="el audio esta vacio")
        vocabulario = [v for v in (vocabulary or "").split(",") if v.strip()]
        return await run_in_threadpool(
            adaptador_stt.transcribe, datos, vocabulary=vocabulario or None
        )

    # ------------------------------------------------------------ ejecuciones
    @app.post("/runs", response_model=RunState, status_code=202)
    def crear_run(peticion: RunRequest) -> RunState:
        """Crea la ejecucion y la encola. **No espera a que termine.**

        Responde 202 con el `run_id` para que el cliente pueda suscribirse al
        progreso de inmediato.
        """
        opciones = peticion.options
        if peticion.project_id is not None:
            proyecto = almacen.proyecto(peticion.project_id)
            if proyecto is None:
                raise HTTPException(
                    status_code=404, detail=f"no existe el proyecto {peticion.project_id}"
                )
            # `model_validate` y no `model_copy`: una copia no ejecuta los
            # validadores de `RunOptions`, y el alcance es una restriccion de
            # seguridad que no debe poder quedar sin comprobar.
            opciones = RunOptions.model_validate(
                {**opciones.model_dump(), "repo_path": proyecto.repo_path}
            )

        # El alcance se comprueba **aqui**, sobre la ruta efectiva, y no solo al dar
        # de alta el proyecto. Una ejecucion tambien puede declarar `repo_path`
        # directamente, sin proyecto; y un proyecto registrado antes de cambiar
        # `AI_SWE_AUTHORIZED_REPOS` no deberia seguir siendo utilizable.
        if opciones.repo_path and not repositorio_autorizado(ajustes, opciones.repo_path):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"el repositorio '{opciones.repo_path}' queda fuera del alcance "
                    "autorizado en AI_SWE_AUTHORIZED_REPOS"
                ),
            )

        try:
            estado = motor.crear_estado(
                peticion.instruction,
                options=opciones,
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
        # `RunNotFound` la mapea el manejador central a un 404 estructurado.
        return motor.get(run_id)

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

    # ------------------------------------------------------- puertas humanas
    #
    # **Dos puertas, dos rutas.** No se unifican en una sola con un parametro
    # "que puerta": responden a momentos distintos del flujo y a decisiones
    # distintas (confirmar lo que se entendio / aprobar lo que se hizo). Una ruta
    # unica obligaria al cliente a saber cual esta pendiente para elegir el cuerpo,
    # que es justo lo que el estado ya le dice.

    @app.post("/runs/{run_id}/confirm-requirements", response_model=RunState)
    def confirmar_requisitos(
        run_id: str, peticion: ConfirmRequirementsRequest
    ) -> RunState:
        """Reanuda la puerta `confirm_requirements_gate` (M2, item 3 del DoD).

        Acepta confirmar, rechazar o **corregir** lo que el sistema entendio. La
        reanudacion vuelve al trabajador: el cliente recibe el estado en cuanto el
        grafo arranca de nuevo, no cuando termina.

        La comprobacion y la reserva del derecho a reanudar son **una sola
        operacion** (`reclamar_reanudacion`), no dos. Comprobar aqui y encolar
        despues dejaba una ventana en la que dos peticiones concurrentes -dos
        pestanas, un doble clic, un reintento- pasaban ambas y devolvian 200.
        """
        motor.reclamar_reanudacion(
            run_id, puerta_esperada="confirm_requirements_gate"
        )
        try:
            trabajador.submit_resume(run_id, _valor_de_confirmacion(peticion))
        except Exception:
            motor.olvidar_reclamacion(run_id)
            raise
        return motor.get(run_id)

    @app.post("/runs/{run_id}/approve", response_model=RunState)
    def aprobar_run(run_id: str, peticion: ApproveRequest) -> RunState:
        """Aprueba o rechaza el cambio pendiente y reanuda la puerta `approval_gate`.

        La reanudacion vuelve al trabajador: el cliente recibe el estado en cuanto el
        grafo arranca de nuevo, no cuando termina. Misma reserva atomica que la puerta
        de requisitos.
        """
        motor.reclamar_reanudacion(run_id, puerta_esperada="approval_gate")
        try:
            trabajador.submit_resume(run_id, _valor_de_aprobacion(peticion))
        except Exception:
            motor.olvidar_reclamacion(run_id)
            raise
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

    # ------------------------------------------------------------------ frontend
    #
    # **Se sirve el resultado de la construccion, no el codigo fuente.** Hasta F10
    # el frontend era un `index.html` con un `<script>` en linea y se servia tal
    # cual. Desde F11 es una aplicacion React que se compila con Vite: el
    # `index.html` de la raiz es el punto de entrada del **fuente** (apunta a
    # `/src/main.tsx`, que solo existe en el servidor de desarrollo) y no se puede
    # servir. Lo que se sirve es `frontend/dist`, que produce `npm run build`.
    #
    # Si `dist/` no existe se avisa y **no se monta**: montar el directorio raiz
    # serviria un `index.html` que el navegador no puede ejecutar, y el fallo
    # apareceria como una pagina en blanco sin explicacion. Es mejor no montar nada
    # y que el 404 diga que falta la construccion.
    if FRONTEND_DIST.is_dir():
        app.mount("/app", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
    else:
        log.warning(
            "no se encontro la construccion del frontend en %s; "
            "ejecuta `npm install && npm run build` en frontend/",
            FRONTEND_DIST,
        )

    return app
