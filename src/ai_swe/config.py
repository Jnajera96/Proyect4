"""Configuracion del sistema.

Validada al arrancar. Los secretos se leen del entorno y **nunca** se escriben
en el repositorio; `.env.example` documenta nombres, no valores.

**Por que `SecretStr` y no `str`.** Un `str` corriente acaba en un `repr`, en un
`model_dump()`, en un mensaje de error de validacion o en un volcado de depuracion
sin que nadie lo escriba a proposito. `SecretStr` no elimina el riesgo, pero lo
reduce a un acto explicito: hay que llamar a `.get_secret_value()` para ver el
valor. La redaccion centralizada (`ai_swe.security`) es la segunda linea, para los
sitios donde un secreto llegue igualmente en texto.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AI_SWE_",
        env_file_encoding="utf-8",
        extra="ignore",
        # Una variable **presente pero vacia** se trata como ausente y se usa el
        # valor por defecto. Sin esto, un `.env` copiado de `.env.example` -donde
        # las lineas van sin valor- rompia el arranque en los campos tipados
        # (`AI_SWE_MAX_COST_PER_RUN=` no es un `float`), que es justo lo contrario
        # de lo que promete una plantilla. Con esto, `.env` funciona de forma
        # consistente: dejar una linea vacia equivale a no declararla.
        env_ignore_empty=True,
    )

    # --- Servidor ------------------------------------------------------------
    # El **puerto** es configurable; la **interfaz** no (ver `ai_swe.__main__`):
    # cambiar el puerto no amplia quien puede llegar, escuchar en la red si.
    port: int = Field(default=8000, ge=1, le=65535)

    # --- Proveedor de modelo -------------------------------------------------
    model_provider: str = Field(default="openai", description="Proveedor del Foundation Model.")
    model_name: str = Field(default="", description="Identificador del modelo a usar.")
    # Modelo especifico del Reviewer (F9). Vacio = usa `model_name`.
    #
    # **Por que un campo aparte y no reutilizar `model_name`.** Criticar no es
    # producir: el rol de revision se beneficia de un modelo distinto (mas capaz de
    # razonar, o al reves, mas barato si el volumen es alto), y R1 en
    # `docs/01-arquitectura.md` lo deja dicho -un mismo prompt no se optimiza a la
    # vez para explorar, producir y criticar-. Vacio por defecto para no obligar a
    # configurar nada: sin valor, el Reviewer usa el modelo general.
    reviewer_model: str = Field(
        default="",
        description="Modelo del Reviewer. Vacio = usar `model_name`.",
    )
    model_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Secreto: solo desde el entorno. Nunca se registra en claro.",
    )
    model_base_url: str | None = Field(default=None, description="Para proveedores locales.")
    # Tarifas publicadas por el proveedor, en la moneda del proveedor. Vacio = no
    # se declara ninguna, y entonces el coste de cada llamada es `None` ("no se
    # sabe"). Se mantiene vacio en el repositorio a proposito: un precio inventado
    # se cree, y una tarifa cambia sin avisar. Ver `models/pricing.py`.
    #
    # Forma: [{"model": "...", "input_per_1k": 0.0, "output_per_1k": 0.0,
    #          "currency": "USD"}]
    model_pricing: str = Field(
        default="",
        description="Lista JSON de tarifas por modelo. Vacia = no se conoce ningun precio.",
    )

    # --- Almacen de estado ---------------------------------------------------
    state_db_path: Path = Field(default=Path("var/state.sqlite3"))

    # --- Alcance y seguridad -------------------------------------------------
    workspace_root: Path = Field(
        default=Path("var/workspaces"),
        description="Raiz donde se crean los worktrees de cada ejecucion.",
    )
    # Lista blanca de repositorios. **Vacia = sin restriccion adicional**: es el
    # modo local mono-usuario, donde el usuario registra a mano los proyectos que
    # quiere tocar y esa accion ya es la autorizacion. **No vacia = se aplica**:
    # solo se aceptan repositorios dentro de esas rutas (ver
    # `repositorio_autorizado`), y registrar o lanzar contra otro devuelve 403.
    #
    # La distincion importa y estaba implicita: el campo se documentaba como un
    # limite y ningun codigo lo leia. Un control declarado que no existe es peor
    # que no tenerlo, porque se cree aplicado.
    authorized_repos: list[Path] = Field(
        default_factory=list,
        description=(
            "Lista blanca de repositorios. Vacia = sin restriccion adicional (modo local). "
            "No vacia = solo se aceptan rutas dentro de esas."
        ),
    )
    allowed_test_targets: list[str] = Field(
        default_factory=lambda: ["pytest.unit", "pytest.integration", "ruff.check"],
        description="Enumeracion cerrada de objetivos de prueba ejecutables.",
    )
    allowed_packages: list[str] = Field(
        default_factory=list,
        description="Enumeracion cerrada de paquetes instalables. Vacia = ninguno.",
    )
    # Salida de red desde el entorno de ejecucion. **Todavia NO se aplica.** El
    # aislamiento real de proceso (contenedor desechable, `network none`) llega en
    # su propia fase; hasta entonces este campo se conserva porque es la
    # configuracion que ese aislamiento consumira, pero **no se declara como si ya
    # bloqueara nada**: hoy, con el valor que sea, la ejecucion de pruebas hereda el
    # entorno del proceso padre. Prometer un bloqueo que no existe es la misma clase
    # de fallo que el resto de esta fase corrige.
    network_egress_enabled: bool = Field(
        default=False,
        description=(
            "Salida de red deseada para el entorno de ejecucion. **No aplicado aun**: "
            "se conectara al aislamiento real de proceso (fase de aislamiento)."
        ),
    )

    # --- Presupuesto ---------------------------------------------------------
    # Estos valores son los que el `Budget` de cada ejecucion copia al crearse
    # (ver `Settings.presupuesto`). Antes existian y no se leian: poner
    # `AI_SWE_MAX_TOKENS_PER_RUN=1000` no cambiaba nada. Ahora el presupuesto
    # efectivo sale de aqui.
    max_tokens_per_run: int = Field(default=200_000, ge=1)
    max_tool_calls_per_run: int = Field(default=60, ge=1)
    max_model_calls_per_run: int = Field(default=120, ge=1)
    max_seconds_per_run: float = Field(default=900.0, gt=0)
    max_review_cycles: int = Field(default=2, ge=0, le=5)
    # Coste maximo en la moneda del proveedor. `None` = sin limite declarado, que
    # es distinto de cero: cero seria "no se permite gastar nada".
    max_cost_per_run: float | None = Field(default=None, ge=0)

    # --- Limites del borde (hardening local) ---------------------------------
    # Todo lo que entra por la API tiene un tope. Sin ellos, una peticion puede
    # pedir un millon de filas o subir un fichero de gigabytes y el coste lo paga el
    # proceso: es denegacion de servicio por la via mas tonta.
    max_page_size: int = Field(
        default=200,
        ge=1,
        le=10_000,
        description="Tamano maximo de pagina en los listados. Pedir mas devuelve 422.",
    )
    max_audio_bytes: int = Field(
        default=25 * 1024 * 1024,
        ge=1024,
        description="Tamano maximo del audio aceptado en /transcriptions. Superarlo es 413.",
    )
    max_sse_connections: int = Field(
        default=16,
        ge=1,
        description=(
            "Conexiones SSE simultaneas. Cada una mantiene un bucle sondeando el "
            "almacen, asi que no son gratis; superarlo es 503."
        ),
    )
    # Limite de peticiones por minuto y por cliente. **Apagado por defecto**: en
    # bucle local mono-usuario no protege de nadie -quien llama es el dueno de la
    # maquina- y encenderlo podria estorbar a una verificacion que dispara cientos
    # de peticiones. Se implementa y se prueba, y se enciende **antes** de exponer
    # el servicio, que es cuando tiene sentido.
    rate_limit_enabled: bool = Field(
        default=False,
        description="Limite de peticiones por minuto. Apagado: encenderlo antes de exponer.",
    )
    rate_limit_per_minute: int = Field(default=120, ge=1)
    # Hosts aceptados en la cabecera `Host`. Un valor que no este aqui es 400: es la
    # defensa contra el envenenamiento de host. `testserver` esta porque es el que
    # usa el cliente de pruebas de FastAPI.
    trusted_hosts: list[str] = Field(
        default_factory=lambda: ["127.0.0.1", "localhost", "testserver"],
        description="Hosts aceptados en la cabecera Host. Cualquier otro es 400.",
    )

    # --- Speech-to-Text ------------------------------------------------------
    stt_provider: str = Field(default="faster-whisper")
    stt_model: str = Field(default="large-v3")
    stt_language: str = Field(default="es")
    stt_confidence_warn_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    # Salida por voz. **NO IMPLEMENTADA.** No existe `TTSAdapter` ni un solo
    # consumidor de este ajuste: se conserva porque `docs/01-arquitectura.md` la
    # declara como **propuesta** (`[PROP]`), no como requisito (`RF-01`..`RF-03` no
    # la incluyen). Se marca aqui y en `.env.example` para que no se lea como una
    # capacidad presente: un flag que aparenta una funcion que no existe es
    # exactamente la configuracion enganosa que esta fase corrige. Cuando exista el
    # adaptador, la marca desaparece.
    tts_enabled: bool = Field(
        default=False,
        description="Salida por voz. **NO IMPLEMENTADO**: ningun codigo lo consume (propuesta).",
    )

    # --- Observabilidad ------------------------------------------------------
    # **NO IMPLEMENTADA.** No hay integracion con Langfuse: `langfuse_enabled` y
    # `langfuse_host` no los lee ningun codigo. Las **claves** si se usan -las
    # registra el redactor en `registrar_secretos`, para que una clave no acabe en
    # un log el dia que la integracion exista-, y ese registro es la unica parte
    # viva de estos cuatro campos. Llega en la fase de observabilidad.
    langfuse_enabled: bool = Field(
        default=False, description="**NO IMPLEMENTADO**: no hay integracion con Langfuse."
    )
    langfuse_public_key: SecretStr = Field(default=SecretStr(""))
    langfuse_secret_key: SecretStr = Field(default=SecretStr(""))
    langfuse_host: str = Field(
        default="http://localhost:3000",
        description="**NO IMPLEMENTADO**: host previsto para Langfuse.",
    )
    log_level: str = Field(default="INFO")

    @field_validator("log_level")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"log_level debe ser uno de {sorted(allowed)}")
        return upper

    @property
    def tts_active(self) -> bool:
        """Refleja `tts_enabled`. **El TTS no esta implementado** (ver el campo).

        La descripcion anterior decia que "el TTS solo se activa si esta habilitado
        y el STT esta configurado", y el cuerpo solo devolvia `tts_enabled`: la
        documentacion prometia una comprobacion que no existia. Se corrige la
        descripcion en lugar de la comprobacion, porque no hay nada que comprobar
        mientras no exista el adaptador. Se conserva el acceso porque es el punto
        por el que la futura implementacion consultara la configuracion.
        """
        return self.tts_enabled

    def presupuesto(self):
        """Presupuesto efectivo de una ejecucion, construido desde la configuracion.

        **Por que aqui y no en el motor.** El presupuesto es la traduccion directa de
        la configuracion al contrato del estado; ponerlo en un metodo de `Settings`
        deja una sola definicion de esa traduccion y la hace comprobable sin arrancar
        nada (ver `tests/test_config_budget.py`). Antes, `Budget` se construia con sus
        propios valores por defecto y los seis ajustes `AI_SWE_MAX_*_PER_RUN` no se
        leian en ningun sitio: existian, se documentaban y no hacian nada.

        Se importa `ai_swe.contracts` de forma diferida para que `config` no dependa
        de los contratos en tiempo de importacion.
        """
        from ai_swe.contracts import Budget

        return Budget(
            max_tokens=self.max_tokens_per_run,
            max_tool_calls=self.max_tool_calls_per_run,
            max_model_calls=self.max_model_calls_per_run,
            max_seconds=self.max_seconds_per_run,
            max_cost=self.max_cost_per_run,
            max_review_cycles=self.max_review_cycles,
        )

    def registrar_secretos(self) -> int:
        """Registra los secretos conocidos en el redactor central (`RNF-S3`).

        Devuelve cuantos valores se registraron, para poder comprobarlo en una
        prueba. Se registra el valor literal porque es la unica forma fiable de
        redactar una clave corta o con formato impredecible que ningun patron
        reconoceria.

        Se importa `ai_swe.security` de forma diferida para que `config` no
        dependa de la capa de seguridad en tiempo de importacion.
        """
        from ai_swe.security import register_secret

        registrados = 0
        for secreto in (self.model_api_key, self.langfuse_secret_key, self.langfuse_public_key):
            if register_secret(secreto.get_secret_value()):
                registrados += 1
        return registrados


def load_settings() -> Settings:
    """Carga la configuracion y deja sus secretos protegidos por el redactor.

    **No exige una clave de API.** M1 debe arrancar sin proveedor: el grafo se
    recorre, la API responde y el frontend funciona sin ninguna credencial. La
    exigencia de clave se evalua cuando se intenta usar un modelo, no al arrancar
    (ver `require_model_credentials`).
    """
    settings = Settings()
    settings.registrar_secretos()
    return settings


# ------------------------------------------------------------------- alcance

def repositorio_autorizado(settings: Settings, ruta: Path | str) -> bool:
    """Comprueba que `ruta` esta dentro del alcance declarado por `authorized_repos`.

    **Semantica, explicita.** Con la lista vacia no hay restriccion adicional: es el
    modo local mono-usuario, donde la autorizacion es que una persona registre a
    mano el proyecto. Con la lista poblada, solo se aceptan rutas **dentro** de
    alguna de las declaradas -la propia ruta o cualquier cosa colgando de ella-, y
    todo lo demas se rechaza.

    La comparacion es sobre rutas **resueltas**, no sobre el texto recibido: sin
    resolver, `repo/../otro` o un enlace simbolico esquivarian la lista. Se resuelve
    primero y se compara despues.
    """
    if not settings.authorized_repos:
        return True
    objetivo = Path(ruta).resolve()
    for permitido in settings.authorized_repos:
        base = Path(permitido).resolve()
        if objetivo == base or base in objetivo.parents:
            return True
    return False


# --------------------------------------------------------------- validacion de uso

# Proveedores que **necesitan** una clave para llamar al modelo. Un proveedor
# local (`ollama`, `vllm`...) expone un endpoint HTTP y no usa clave.
PROVEEDORES_CON_CLAVE = frozenset({"openai", "anthropic", "azure", "openrouter", "mistral"})


class ConfiguracionInsuficiente(RuntimeError):
    """Falta configuracion para realizar una operacion concreta.

    Es una excepcion **tipada y segura**: su mensaje nombra el campo que falta y
    nunca incluye el valor de un secreto. Existe para que el fallo ocurra en el
    borde del sistema -antes de gastar una llamada y antes de que un error opaco
    suba desde dentro del cliente del modelo- y para que sea accionable.

    **No se lanza al arrancar.** Se lanza cuando se va a usar el modelo sin la
    configuracion necesaria, que es el momento en que el problema tiene sentido.
    Arrancar M1 sin clave es valido y deliberado.
    """

    def __init__(self, campo: str, detalle: str) -> None:
        self.campo = campo
        super().__init__(f"configuracion insuficiente: {campo} ({detalle})")


def require_model_credentials(settings: Settings) -> None:
    """Comprueba que hay credenciales antes de llamar al modelo.

    Lanza `ConfiguracionInsuficiente` -con el **nombre** del campo, nunca su
    valor- si el proveedor configurado necesita una clave y no la tiene. Si el
    proveedor no necesita clave (local), no comprueba nada.

    Debe llamarse **justo antes** de la primera llamada real al proveedor, no al
    importar ni al arrancar. Asi M1 sigue funcionando sin proveedor y el error
    llega pronto y con contexto cuando de verdad se necesita.
    """
    if settings.model_provider.lower() not in PROVEEDORES_CON_CLAVE:
        return
    if not settings.model_api_key.get_secret_value().strip():
        raise ConfiguracionInsuficiente(
            campo="model_api_key",
            detalle=f"el proveedor '{settings.model_provider}' exige una clave",
        )
    if not settings.model_name.strip():
        raise ConfiguracionInsuficiente(
            campo="model_name",
            detalle=f"el proveedor '{settings.model_provider}' exige un modelo",
        )
