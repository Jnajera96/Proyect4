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
  - Cancelar es cooperativo: 202 significa solicitud pendiente; el recibo y el
    estado autoritativo confirman la parada. No acredita detener facturación remota.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from ai_swe import __version__
from ai_swe.config import Settings, load_settings, provider_configuration, repositorio_autorizado
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
from ai_swe.projects import crear_proyecto_git
from ai_swe.resources import frontend_dist
from ai_swe.runtime_logging import close_installed_log_handler, installed_log_handler
from ai_swe.sandbox import SandboxError, limpiar_worktree, validar_repositorio
from ai_swe.security import (
    Credenciales,
    Identidad,
    Rol,
    credencial_de_peticion,
    credenciales_de,
    install_redacting_filter,
    redact_deep,
)
from ai_swe.state import RunStore
from ai_swe.stt.base import STTAdapter, STTError, STTNotAvailable, Transcript, crear_adaptador_stt

log = logging.getLogger(__name__)

TERMINALES = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.NEEDS_HUMAN, RunStatus.CANCELLED}

#: Formatos de audio aceptados en `/transcriptions`. Es una **lista blanca**: lo que
#: no este aqui se rechaza con 415.
#:
#: **Que garantiza y que no.** El tipo declarado por el cliente es un dato suyo, no
#: una prueba: nada impide anunciar `audio/wav` y enviar otra cosa. Esto filtra lo
#: evidente y, sobre todo, deja el error **cerca del cliente** -un 415 claro- en
#: lugar de dentro del decodificador, donde se convierte en un fallo opaco. Quien
#: valida el contenido de verdad es el motor de transcripcion, que lo decodifica.
FORMATOS_AUDIO = frozenset(
    {
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/x-m4a",
        "audio/m4a",
        "audio/webm",
        "audio/ogg",
        "audio/flac",
        "audio/x-flac",
        "audio/aac",
        "audio/opus",
    }
)

#: Cabeceras de seguridad, aplicadas a **todas** las respuestas.
#:
#: `style-src` necesita `'unsafe-inline'`: el frontend usa atributos `style` de
#: React (`style={{...}}`), que la CSP trata como estilo en linea; sin esa excepcion
#: la interfaz pierde parte de su maquetacion. `script-src` **no** la lleva: el HTML
#: construido no tiene un solo script en linea, solo el modulo externo de Vite.
CABECERAS_SEGURIDAD = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class LimitadorDePeticiones:
    """Limite de peticiones por minuto y por cliente, en memoria.

    **Ventana deslizante por marcas de tiempo**, no un contador que se reinicia al
    cambiar el minuto: ese contador deja pasar el doble de peticiones a caballo del
    cambio de minuto. Se guardan las marcas recientes de cada cliente y se descartan
    las que salen de la ventana.

    **Es por proceso y en memoria**: no sobrevive a un reinicio ni se coordina entre
    varias instancias. Para el bucle local es suficiente y esta declarado; el dia
    que haya varias instancias, el limite tiene que vivir fuera de ellas.
    """

    def __init__(self, por_minuto: int, ventana_s: float = 60.0) -> None:
        self._por_minuto = por_minuto
        self._ventana = ventana_s
        self._marcas: dict[str, list[float]] = {}

    def permitir(self, cliente: str, ahora: float) -> bool:
        """`True` si la peticion cabe en la ventana. Registra la marca si cabe."""
        vigentes = [t for t in self._marcas.get(cliente, ()) if ahora - t < self._ventana]
        if len(vigentes) >= self._por_minuto:
            self._marcas[cliente] = vigentes
            return False
        vigentes.append(ahora)
        self._marcas[cliente] = vigentes
        return True


async def _leer_audio_limitado(audio: UploadFile, limite: int) -> bytes:
    """Lee el audio por trozos y corta en cuanto supera `limite` (413).

    **Por que no `await audio.read()`.** Ese lee el fichero **entero** en memoria
    antes de que nadie pueda medirlo: subir 4 GB deja al proceso sin memoria y el
    limite se comprueba cuando ya no sirve de nada. Leer a trozos permite abortar en
    el momento exacto en que se pasa, con el fichero todavia a medio subir.
    """
    trozo_bytes = 1024 * 1024
    trozos: list[bytes] = []
    total = 0
    while True:
        trozo = await audio.read(trozo_bytes)
        if not trozo:
            break
        total += len(trozo)
        if total > limite:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"el audio supera el limite de {limite} bytes "
                    f"(AI_SWE_MAX_AUDIO_BYTES)"
                ),
            )
        trozos.append(trozo)
    return b"".join(trozos)


def _limpiar_worktree_de_huerfana(motor: RunEngine, run_id: str) -> None:
    """Limpia el worktree de una ejecucion huerfana. **Nunca propaga.**

    Es el tercer camino terminal y el unico que no pasa ni por el grafo ni por el
    motor: una ejecucion huerfana no llegara nunca a `finalize`, asi que si no se
    limpia aqui el worktree se queda para siempre en `var/workspaces` y el
    repositorio del usuario acumula referencias fantasma.

    Se lee el estado del **punto de control** porque la ruta del worktree vive ahi,
    no en el indice. Si no se puede leer -no hay punto de control, o esta corrupto-
    se registra y se sigue: romper el arranque del servicio por un worktree es peor
    que dejar un worktree.
    """
    try:
        estado = motor.get(run_id)
    except Exception as exc:
        log.warning("no se pudo leer el estado huerfano %s: %s", run_id, exc)
        return
    repo = (
        estado.interpretation.scope.repo_path
        if estado.interpretation is not None
        else estado.options.repo_path
    )
    limpiar_worktree(
        estado.artifacts.worktree_path,
        repo_original=repo,
        run_id=run_id,
        base_commit=estado.artifacts.base_commit or "",
    )


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
FRONTEND_DIR = frontend_dist().parent

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


class BackupConfigRequest(BaseModel):
    folder: str | None = Field(default=None, max_length=500)
    enabled: bool = True


class ExportVaultRequest(BaseModel):
    password: str = Field(min_length=12, max_length=1024)


class ImportVaultRequest(BaseModel):
    archive_b64: str = Field(min_length=1)
    password: str = Field(min_length=12, max_length=1024)
    repo_mapping: dict[str, str] = Field(default_factory=dict)


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

    from ai_swe.tools.rollback import RollbackError
    from ai_swe.state.continuity import ContinuityError

    @app.exception_handler(ContinuityError)
    async def _continuity(_peticion: Request, exc: ContinuityError):
        return JSONResponse(status_code=409, content=_cuerpo(exc, "CONTINUITY_ERROR"))

    @app.exception_handler(RollbackError)
    async def _rollback(_peticion: Request, exc: RollbackError):
        return JSONResponse(status_code=409, content=_cuerpo(exc, "ROLLBACK_ERROR"))


def crear_app(
    store: RunStore | None = None,
    stt: STTAdapter | None = None,
    worker: RunWorker | None = None,
    cors_origins: list[str] | None = None,
    settings: Settings | None = None,
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
    ajustes = settings or load_settings()
    if ajustes.profile_mode:
        from ai_swe.api.profiles import create_profile_app
        return create_profile_app(ajustes)
    almacen = store or RunStore(ajustes.state_db_path)
    # F13: el adaptador se elige por configuracion (`AI_SWE_STT_PROVIDER`). El
    # defecto es el adaptador local real; `fake` queda para pruebas y para entornos
    # sin la dependencia `voice`. Antes el defecto era `FakeAdapter`, que devolvia un
    # texto fijo con independencia del audio: una transcripcion fabricada.
    adaptador_stt = stt or crear_adaptador_stt(ajustes)
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
        file_handler = installed_log_handler(ajustes.log_dir, profile_id=ajustes.profile_id)
        if ajustes.runner_docker is not None:
            from ai_swe.tools.docker_runner import recover_stopped_sessions

            _app.state.docker_recovery = await run_in_threadpool(recover_stopped_sessions)

        # Recuperacion al arrancar: una ejecucion en `planned` o `running`
        # pertenece a un proceso que ya no existe. Dejarla asi seria la terminacion
        # anomala que MET-13 prohibe, y el navegador esperaria para siempre.
        huerfanas = almacen.orphan_open_runs()
        if huerfanas:
            log.warning("ejecuciones huerfanas marcadas como escaladas: %s", huerfanas)
            # Y se limpia su worktree. Una ejecucion huerfana no va a llegar nunca a
            # `finalize` ni al aborto del motor: es el tercer camino terminal, y el
            # unico que no pasa ni por el grafo ni por el motor.
            for run_id in huerfanas:
                _limpiar_worktree_de_huerfana(motor, run_id)
        try:
            yield
        finally:
            # Se espera a las ejecuciones aceptadas **antes** de cerrar el almacen.
            # Cerrar por debajo de un trabajador activo lo hace fallar con
            # `Cannot operate on a closed database` y deja la ejecucion sin estado
            # terminal. El orden importa.
            await run_in_threadpool(trabajador.shutdown, wait=True)
            if store is None:
                almacen.close()
            close_installed_log_handler(file_handler)

    app = FastAPI(
        title="AI Software Engineering System",
        version=__version__,
        description=(
            "Producto local mono-usuario con ejecucion asincrona, progreso en vivo "
            "y aprobacion humana. Analyst/Supervisor deterministas; modelos de "
            "Coder/Reviewer opcionales mediante configuracion explicita."
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

    # Hosts aceptados. Con lista explicita, un `Host` que no este en ella es **400**:
    # es la defensa contra el envenenamiento de host, en el que un enlace con un
    # nombre ajeno acaba dentro de una URL que genera el propio servidor. `localhost`
    # y `testserver` estan porque son el bucle local y el cliente de pruebas.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(ajustes.trusted_hosts))

    if ajustes.rate_limit_enabled:
        limitador = LimitadorDePeticiones(ajustes.rate_limit_per_minute)
        app.state.rate_limiter = limitador

        @app.middleware("http")
        async def _limitar_peticiones(request: Request, call_next):
            cliente = request.client.host if request.client else "desconocido"
            if not limitador.permitir(cliente, time.monotonic()):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "demasiadas peticiones; intentalo mas tarde"},
                    headers={"Retry-After": "60"},
                )
            return await call_next(request)

    # Cabeceras de seguridad. Se anade **la ultima** a proposito: en Starlette el
    # ultimo middleware anadido es el mas externo, y eso hace que las cabeceras
    # acompanen tambien a las respuestas de error de los middleware de dentro (un
    # 400 de host o un 429 de limite), no solo a las respuestas correctas.
    @app.middleware("http")
    async def _cabeceras_de_seguridad(request: Request, call_next):
        respuesta = await call_next(request)
        for nombre, valor in CABECERAS_SEGURIDAD.items():
            respuesta.headers.setdefault(nombre, valor)
        return respuesta

    app.state.settings = ajustes
    app.state.store = almacen
    app.state.engine = motor
    app.state.worker = trabajador
    #: Conexiones SSE abiertas ahora mismo. Ver el tope en `eventos_run`.
    app.state.sse_activas = 0

    # ------------------------------------------------------- autenticacion
    # Las credenciales se construyen **una vez** con los ajustes validados: leerlas
    # por peticion revalidaria el mapa de claves en cada llamada. `None` como
    # identidad significa "autenticacion desactivada", y entonces las dependencias
    # de rol dejan pasar sin comprobar nada -que es el comportamiento de siempre.
    credenciales = credenciales_de(ajustes)
    app.state.credenciales = credenciales
    log.info(
        "autenticacion %s (%d claves)",
        "activada" if credenciales.activa else "desactivada",
        credenciales.numero_de_claves,
    )

    def _identidad_de_cabecera(
        x_api_key: str | None, authorization: str | None
    ) -> Identidad | None:
        """Identidad a partir de las dos cabeceras admitidas.

        `None` sin excepcion significa "autenticacion desactivada". Con la
        autenticacion activa, una clave ausente o invalida es **401** aqui, antes de
        llegar al manejador. El mensaje no dice cual era la clave ni cual falta:
        distinguir "no mandaste nada" de "esa no existe" permitiria enumerar que
        claves son validas.
        """
        if not credenciales.activa:
            return None
        identidad = credencial_de_peticion(credenciales, x_api_key, authorization)
        if identidad is None:
            raise HTTPException(
                status_code=401,
                detail=(
                    "se requiere una clave de API valida. Se acepta en la cabecera "
                    "X-API-Key o como Authorization: Bearer."
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )
        return identidad

    def _identidad(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None),
    ) -> Identidad | None:
        """Dependencia de identidad para los manejadores normales."""
        return _identidad_de_cabecera(x_api_key, authorization)

    def _exige(minimo: Rol):
        """Dependencia que exige un rol minimo. Sin autenticacion, no exige nada."""

        def dependencia(identidad: Identidad | None = Depends(_identidad)) -> Identidad | None:
            if identidad is None:
                return None
            if not identidad.puede(minimo):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"esta accion requiere el rol '{minimo.value}'; la clave "
                        f"usada tiene '{identidad.rol.value}'"
                    ),
                )
            return identidad

        return dependencia

    #: Roles por endpoint. Se declaran **aqui**, en un solo sitio, para que la
    #: matriz de permisos sea legible de un vistazo en lugar de repartida entre
    #: diez manejadores.
    #
    #   reader    consultas: nada que escriba ni apruebe.
    #   operator  ciclo de vida de ejecuciones, incluido aprobar (lo mas sensible)
    #             y transcribir.
    #   admin     registrar proyectos: fija el `repo_path` contra el que se
    #             ejecutara, y con alcance amplio eso es elegir sobre que
    #             repositorio se escribe.
    #
    # `/health` queda fuera a proposito: un health check de infraestructura tiene
    # que poder llegar sin credenciales, o el balanceador marca el servicio caido.
    LEER = Depends(_exige(Rol.READER))
    OPERAR = Depends(_exige(Rol.OPERATOR))
    ADMINISTRAR = Depends(_exige(Rol.ADMIN))

    # ---------------------------------------------------------- auditoria
    # Registro de quien hizo que, en las acciones que cambian estado o conceden
    # permisos. Va a un logger **dedicado** (`ai_swe.audit`), no al general: la
    # auditoria se consume de otra forma -se retiene, se busca, se compara- y
    # mezclarla con el log de aplicacion la haria inutilizable.
    #
    # Lo que se registra es el `clave_id` de la identidad (cuatro caracteres y
    # longitud), nunca la clave: basta para saber que clave actuo. Como las claves
    # se registran en el redactor central, si alguna acabara aqui saldria
    # `[REDACTED]` igualmente.
    #
    # **Limitacion declarada:** esto escribe en el flujo de log. Antes de una
    # exposicion real hace falta un sumidero persistente (fichero rotado, o el
    # almacen), porque un log que nadie retiene no es un registro de auditoria. Se
    # deja dicho y no se finge lo contrario.
    auditoria = logging.getLogger("ai_swe.audit")

    def _auditar(accion: str, identidad: Identidad | None, detalle: dict) -> None:
        actor = (
            f"{identidad.rol.value}:{identidad.clave_id}"
            if identidad is not None
            else "sin-autenticar"
        )
        auditoria.info(
            "accion=%s actor=%s %s",
            accion,
            actor,
            json.dumps(redact_deep(detalle), ensure_ascii=False),
        )

    registrar_manejadores_de_error(app)

    # ------------------------------------------------------------------ salud
    @app.get("/auth/status")
    def profile_status():
        return {"profile_mode": False, "authenticated": False}

    @app.get("/health")
    def salud() -> dict:
        return {
            "status": "ok",
            "fase": "M3",
            "stt": adaptador_stt.health(),
            "provider_configuration": provider_configuration(ajustes),
            "ejecuciones": len(almacen.list_summaries(limit=1000)),
            "proyectos": len(almacen.listar_proyectos(limit=1000)),
        }

    # ------------------------------------------------------------- proyectos
    @app.post("/projects", response_model=Project, status_code=201, dependencies=[ADMINISTRAR])
    def crear_proyecto(
        peticion: ProjectRequest, identidad: Identidad | None = Depends(_identidad)
    ) -> Project:
        """Registra un repositorio para poder ejecutar contra el.

        La ruta se **valida aqui**, en el alta, y no al lanzar una ejecucion: un
        repositorio inexistente o que no sea git se rechaza en el momento en que
        alguien lo declara, con un 422 que dice que pasa, en lugar de dentro de una
        ejecucion ya en marcha. Es la razon de que el proyecto exista como concepto
        en vez de llevar la ruta suelta en cada peticion.

        Es la unica accion de `admin`: fija el `repo_path` contra el que se
        ejecutara, y con el alcance amplio eso es elegir sobre que repositorio se
        escribe.
        """
        _auditar("proyecto.registrado", identidad, {"repo_path": peticion.repo_path})
        ruta = (
            crear_proyecto_git(peticion.repo_path, peticion.name, ajustes)
            if peticion.create_if_missing else validar_repositorio(peticion.repo_path)
        )
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

    @app.get("/projects", response_model=list[Project], dependencies=[LEER])
    def listar_proyectos(
        limit: int = Query(default=50, ge=1, le=ajustes.max_page_size),
    ) -> list[Project]:
        """Lista proyectos. El tope de pagina lo impone el contrato de la peticion.

        Antes, `limit` llegaba tal cual a SQL: `?limit=1000000000` era una peticion
        valida y el coste lo pagaba el proceso. Acotarlo con `le` hace que el limite
        sea parte del contrato -y aparezca en OpenAPI-, en lugar de una comprobacion
        a mano que alguien puede olvidar.
        """
        return almacen.listar_proyectos(limit)

    @app.get("/projects/{project_id}", response_model=Project, dependencies=[LEER])
    def obtener_proyecto(project_id: str) -> Project:
        proyecto = almacen.proyecto(project_id)
        if proyecto is None:
            raise HTTPException(status_code=404, detail=f"no existe el proyecto {project_id}")
        return proyecto

    @app.delete("/projects/{project_id}", status_code=204, dependencies=[ADMINISTRAR])
    def eliminar_proyecto(
        project_id: str,
        identidad: Identidad | None = Depends(_identidad),
    ) -> None:
        """Da de baja un proyecto del registro sin borrar archivos del disco.

        Solo retira el proyecto de la lista autorizada en base de datos.
        Los repositorios locales y el historial de ejecuciones se conservan intactos.
        """
        _auditar("proyecto.baja", identidad, {"project_id": project_id})
        borrado = almacen.eliminar_proyecto(project_id)
        if not borrado:
            raise HTTPException(
                status_code=404, detail=f"no existe el proyecto {project_id}"
            )

    # ----------------------------------------------------------- transcripcion
    @app.post("/transcriptions", response_model=Transcript, dependencies=[OPERAR])
    async def transcribir(
        audio: UploadFile = File(...),
        vocabulary: str | None = Form(default=None),
    ) -> Transcript:
        """Convierte audio en texto. **No crea ninguna ejecucion** (`RF-02`).

        La transcripcion corre en un **hilo aparte**. Es trabajo intensivo de CPU
        -segundos por minuto de audio en el adaptador local-, y hacerlo dentro del
        bucle de eventos bloquearia todas las demas peticiones mientras dura,
        incluido el flujo SSE de una ejecucion en curso.

        **El borde esta acotado.** El tipo se comprueba antes de leer un solo byte
        (415 si no es un formato de la lista) y el tamano se corta **mientras se lee**
        (413): `await audio.read()` a secas cargaba el fichero entero en memoria antes
        de que nadie pudiera medirlo, asi que el limite habria llegado tarde.
        """
        tipo = (audio.content_type or "").split(";")[0].strip().lower()
        if tipo not in FORMATOS_AUDIO:
            raise HTTPException(
                status_code=415,
                detail=(
                    f"formato de audio no soportado: {tipo or '(sin tipo declarado)'}. "
                    f"Formatos aceptados: {', '.join(sorted(FORMATOS_AUDIO))}"
                ),
            )
        datos = await _leer_audio_limitado(audio, ajustes.max_audio_bytes)
        if not datos:
            raise HTTPException(status_code=422, detail="el audio esta vacio")
        vocabulario = [v for v in (vocabulary or "").split(",") if v.strip()]
        return await run_in_threadpool(
            adaptador_stt.transcribe, datos, vocabulary=vocabulario or None
        )

    # ------------------------------------------------------------ ejecuciones
    @app.post("/runs", response_model=RunState, status_code=202, dependencies=[OPERAR])
    def crear_run(
        peticion: RunRequest, identidad: Identidad | None = Depends(_identidad)
    ) -> RunState:
        """Crea la ejecucion y la encola. **No espera a que termine.**

        Responde 202 con el `run_id` para que el cliente pueda suscribirse al
        progreso de inmediato.
        """
        configuration = provider_configuration(ajustes)
        if configuration["remote_enabled"] and configuration["status"] == "not_configured":
            raise HTTPException(status_code=503, detail=configuration["message"])
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
        _auditar(
            "ejecucion.creada",
            identidad,
            {"run_id": estado.run_id, "repo_path": str(opciones.repo_path or "")},
        )
        return estado

    @app.get("/runs", response_model=list[RunSummary], dependencies=[LEER])
    def listar_runs(
        limit: int = Query(default=50, ge=1, le=ajustes.max_page_size),
    ) -> list[RunSummary]:
        """Lista ejecuciones. Mismo tope de pagina que `/projects`."""
        return almacen.list_summaries(limit)

    @app.get("/runs/{run_id}", response_model=RunState, dependencies=[LEER])
    def obtener_run(run_id: str) -> RunState:
        # `RunNotFound` la mapea el manejador central a un 404 estructurado.
        return motor.get(run_id)

    @app.get("/runs/{run_id}/events")
    async def eventos_run(
        run_id: str,
        after: int = 0,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
        timeout_s: float = 300.0,
        api_key: str | None = Query(default=None, alias="api_key"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None),
    ) -> EventSourceResponse:
        """Progreso en vivo. Emite y cierra cuando la ejecucion llega a un terminal.

        Reanudable: si el navegador se reconecta, manda `Last-Event-ID` y solo
        recibe los eventos que se perdio. Es la razon de que el registro sea
        persistente y no una cola en memoria.

        **La clave por query, y por que es una excepcion.** `EventSource`, la API
        que usa el dashboard para suscribirse, **no puede enviar cabeceras**: solo
        cookies. Un endpoint de solo cabeceras dejaria el streaming fuera del
        dashboard, que es su unico consumidor real. Se acepta entonces la clave en
        `?api_key=`, **solo en este endpoint y solo como alternativa a la
        cabecera**.

        La comprobacion vive **en el manejador**, no en una dependencia de ruta, y
        es a proposito: la dependencia de rol solo lee cabeceras y se resuelve
        antes que el manejador, asi que con ella puesta la clave por query daba
        siempre 401 -la excepcion era codigo muerto, y asi lo detecto la prueba de
        `tests/test_auth.py`-. La precedencia es: si viene **cualquier** cabecera,
        manda ella -una invalida es 401, no se cae a la query-; si no viene
        ninguna, se admite la query. Sin ninguna de las dos cosas, 401.

        La concesion tiene un precio y se dice: una clave en la URL acaba en los
        registros de acceso, en el historial y en cualquier proxy del medio. Por eso
        esta pensado para una clave de **lectura** (`reader`), y por eso antes de
        una exposicion real hay que sustituirlo por un vale de un solo uso emitido
        por un endpoint autenticado -o por sesion con cookie-. No es la forma
        definitiva, es la que funciona hoy sin romper el dashboard.
        """
        # Autenticacion del flujo. Ver el por que del sitio en el docstring: la
        # dependencia de ruta habria rechazado la clave por query antes de llegar.
        if credenciales.activa:
            identidad = None
            if x_api_key or authorization:
                identidad = credencial_de_peticion(credenciales, x_api_key, authorization)
            elif api_key:
                identidad = credenciales.identificar(api_key.strip())
            if identidad is None:
                raise HTTPException(
                    status_code=401,
                    detail=(
                        "se requiere una clave de API valida. Se acepta en la "
                        "cabecera X-API-Key o como Authorization: Bearer; en este "
                        "flujo tambien en el parametro api_key."
                    ),
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # El minimo del flujo es `reader`. Con la enumeracion de roles cerrada
            # ninguna clave declarada queda por debajo, asi que esta rama es
            # defensiva: si apareciera un rol inferior, el flujo no se abriria por
            # accidente.
            if not identidad.puede(Rol.READER):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"esta accion requiere el rol 'reader'; la clave usada "
                        f"tiene '{identidad.rol.value}'"
                    ),
                )

        if almacen.summary(run_id) is None:
            raise HTTPException(status_code=404, detail=f"no existe la ejecucion {run_id}")

        # Tope de conexiones. Cada flujo abierto mantiene un bucle sondeando el
        # almacen cada 50 ms; no son gratis, y sin tope un cliente puede abrir
        # cientos y dejar al proceso sin aire. El rechazo es **503 y no 429**: el
        # recurso que falta es capacidad del servidor, no una cuota del cliente, y
        # el mensaje dice que el flujo es reanudable para que reintentar sea barato.
        if app.state.sse_activas >= ajustes.max_sse_connections:
            raise HTTPException(
                status_code=503,
                detail=(
                    "demasiadas conexiones de eventos abiertas; cierra alguna y "
                    "reintenta. El flujo es reanudable: al reconectar con "
                    "Last-Event-ID solo se reciben los eventos que faltan."
                ),
                headers={"Retry-After": "5"},
            )

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

        async def flujo_contado() -> AsyncIterator[dict]:
            """Cuenta la conexion **mientras dura**, no mientras se despacha.

            El manejador devuelve la respuesta antes de que el flujo se consuma: si
            se contara ahi, la reserva se liberaria al salir del manejador, cuando la
            conexion sigue abierta. Se cuenta dentro del generador y se libera en su
            `finally`, que corre cuando el cliente se desconecta o el flujo termina.

            Consecuencia declarada: entre la comprobacion del tope y el arranque del
            generador hay una rendija por la que dos peticiones simultaneas podrian
            colarse. Se admite a proposito -preferimos admitir una conexion de mas
            que dejar una reserva sin liberar, que con un tope de 16 acabaria
            bloqueando el servicio entero.
            """
            app.state.sse_activas += 1
            try:
                async for elemento in flujo():
                    yield elemento
            finally:
                app.state.sse_activas -= 1

        # `ping` mantiene viva la conexion a traves de proxies que cerrarian una
        # conexion inactiva. Sin el, una ejecucion larga se corta en silencio.
        return EventSourceResponse(flujo_contado(), ping=10)

    # ------------------------------------------------------- puertas humanas
    #
    # **Dos puertas, dos rutas.** No se unifican en una sola con un parametro
    # "que puerta": responden a momentos distintos del flujo y a decisiones
    # distintas (confirmar lo que se entendio / aprobar lo que se hizo). Una ruta
    # unica obligaria al cliente a saber cual esta pendiente para elegir el cuerpo,
    # que es justo lo que el estado ya le dice.

    @app.post(
        "/runs/{run_id}/confirm-requirements",
        response_model=RunState,
        dependencies=[OPERAR],
    )
    def confirmar_requisitos(
        run_id: str,
        peticion: ConfirmRequirementsRequest,
        identidad: Identidad | None = Depends(_identidad),
    ) -> RunState:
        """Reanuda la puerta `confirm_requirements_gate` (M2, item 3 del DoD).

        Acepta confirmar, rechazar o **corregir** lo que el sistema entendio. La
        reanudacion vuelve al trabajador: el cliente recibe el estado en cuanto el
        grafo arranca de nuevo, no cuando termina.

        La comprobacion y la reserva del derecho a reanudar son **una sola
        operacion** (`reclamar_reanudacion`), no dos. Comprobar aqui y encolar
        despues dejaba una ventana en la que dos peticiones concurrentes -dos
        pestanas, un doble clic, un reintento- pasaban ambas y devolvian 200.

        `operator` y no `reader`: lo que se confirma aqui es la **interpretacion**
        del trabajo, y con ella el alcance sobre el que se va a escribir. Una
        correccion maliciosa de los requisitos desvia la ejecucion hacia otro
        objetivo, asi que no es una consulta.
        """
        _auditar(
            "requisitos.confirmados",
            identidad,
            {"run_id": run_id, "decision": peticion.decision.value},
        )
        motor.reclamar_reanudacion(
            run_id, puerta_esperada="confirm_requirements_gate"
        )
        try:
            trabajador.submit_resume(run_id, _valor_de_confirmacion(peticion))
        except Exception:
            motor.olvidar_reclamacion(run_id)
            raise
        return motor.get(run_id)

    @app.post(
        "/runs/{run_id}/approve", response_model=RunState, dependencies=[OPERAR]
    )
    def aprobar_run(
        run_id: str,
        peticion: ApproveRequest,
        identidad: Identidad | None = Depends(_identidad),
    ) -> RunState:
        """Aprueba o rechaza el cambio pendiente y reanuda la puerta `approval_gate`.

        La reanudacion vuelve al trabajador: el cliente recibe el estado en cuanto el
        grafo arranca de nuevo, no cuando termina. Misma reserva atomica que la puerta
        de requisitos.

        **La accion mas sensible de la API.** Aprobar promueve el parche al
        repositorio del usuario: es el unico punto en el que el sistema escribe
        codigo en un sitio que no es su worktree. Por eso `operator` como minimo, y
        por eso se audita con el `run_id`, el veredicto y los archivos que toca.
        """
        _auditar(
            "ejecucion.aprobada",
            identidad,
            {
                "run_id": run_id,
                "decision": peticion.decision.value,
                "comentarios": peticion.comments or "",
            },
        )
        motor.reclamar_reanudacion(run_id, puerta_esperada="approval_gate")
        try:
            trabajador.submit_resume(run_id, _valor_de_aprobacion(peticion))
        except Exception:
            motor.olvidar_reclamacion(run_id)
            raise
        return motor.get(run_id)

    @app.post(
        "/runs/{run_id}/rollback", response_model=RunState, dependencies=[OPERAR]
    )
    def revertir_run(
        run_id: str,
        identidad: Identidad | None = Depends(_identidad),
    ) -> RunState:
        """Revierte en 1 clic los archivos promovidos por esta ejecucion."""
        estado = motor.rollback(run_id)
        _auditar(
            "ejecucion.revertida",
            identidad,
            {
                "run_id": run_id,
                "receipt_id": (
                    estado.promotion_receipt.receipt_id
                    if estado.promotion_receipt is not None
                    else ""
                ),
            },
        )
        return estado

    @app.post(
        "/runs/{run_id}/pause", response_model=RunState, dependencies=[OPERAR]
    )
    def pausar_run(
        run_id: str,
        identidad: Identidad | None = Depends(_identidad),
    ) -> RunState:
        """Solicita una pausa manual cooperativa en frontera de nodo."""
        estado = motor.request_pause(run_id)
        _auditar("ejecucion.pausada", identidad, {"run_id": run_id})
        return estado

    @app.post(
        "/runs/{run_id}/resume", response_model=RunState, dependencies=[OPERAR]
    )
    def reanudar_pausa_run(
        run_id: str,
        identidad: Identidad | None = Depends(_identidad),
    ) -> RunState:
        """Reanuda una ejecucion en pausa manual (`paused`)."""
        estado = motor.get(run_id)
        if estado.status is not RunStatus.PAUSED:
            raise NothingToResume(
                f"la ejecucion {run_id} no esta en pausa manual (estado: {estado.status.value})"
            )
        _auditar("ejecucion.reanudada", identidad, {"run_id": run_id})
        trabajador.submit_resume_paused(run_id)
        return motor.get(run_id)

    @app.get("/continuity/status", dependencies=[LEER])
    def estado_continuidad() -> dict:
        return motor.continuity.backup_status()

    @app.post("/continuity/backup-config", dependencies=[ADMINISTRAR])
    def configurar_respaldo(
        peticion: BackupConfigRequest,
        identidad: Identidad | None = Depends(_identidad),
    ) -> dict:
        resultado = motor.continuity.configure_backup(
            peticion.folder, enabled=peticion.enabled
        )
        _auditar(
            "continuidad.respaldo_configurado",
            identidad,
            {"enabled": resultado["enabled"], "backup_dir": resultado["backup_dir"] or ""},
        )
        return resultado

    @app.post("/continuity/export", dependencies=[ADMINISTRAR])
    def exportar_boveda(
        peticion: ExportVaultRequest,
        identidad: Identidad | None = Depends(_identidad),
    ) -> dict:
        import base64

        archive = motor.continuity.export_archive(
            peticion.password, active_runs=trabajador.active
        )
        _auditar("continuidad.exportada", identidad, {"bytes": len(archive)})
        return {
            "filename": f"aiswe-{motor.continuity.owner[:8]}.aiswe-vault",
            "archive_b64": base64.b64encode(archive).decode("ascii"),
            "size": len(archive),
        }

    @app.post("/continuity/import", dependencies=[ADMINISTRAR])
    def importar_boveda(
        peticion: ImportVaultRequest,
        identidad: Identidad | None = Depends(_identidad),
    ) -> dict:
        import base64

        try:
            raw = base64.b64decode(peticion.archive_b64, validate=True)
        except Exception as exc:
            raise ContinuityError("El archivo .aiswe-vault en base64 no es valido") from exc
        resultado = motor.continuity.import_archive(
            raw,
            peticion.password,
            repo_mapping=peticion.repo_mapping,
        )
        _auditar(
            "continuidad.importada",
            identidad,
            {"runs": len(resultado["restored_runs"])},
        )
        return resultado

    @app.post("/runs/{run_id}/cancel", response_model=RunState, dependencies=[OPERAR],
              responses={202: {"model": RunState, "description": "Solicitud pendiente de parada"}})
    def cancelar_run(run_id: str, response: Response,
                     identidad: Identidad | None = Depends(_identidad)) -> RunState:
        result = motor.request_cancel(run_id)
        _auditar("ejecucion.cancelacion_solicitada", identidad,
                 {"run_id": run_id, "status": result.cancellation.status if result.cancellation else result.status})
        response.status_code = (202 if result.cancellation and
                                result.cancellation.status == "requested" else 200)
        return result

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

    from ai_swe.api.delivery import register_delivery_routes

    register_delivery_routes(app, engine=motor, store=almacen, settings=ajustes,
                             read=LEER, operate=OPERAR, admin=ADMINISTRAR)
    from ai_swe.api.readiness import register_readiness_routes

    register_readiness_routes(app, store=almacen,
                              settings=ajustes.model_copy(update={"state_db_path": almacen._db_path}), worker=trabajador,
                              read=LEER, admin=ADMINISTRAR, identity=_identidad, audit=_auditar)
    return app
