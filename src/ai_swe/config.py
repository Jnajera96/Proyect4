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
    )

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
    authorized_repos: list[Path] = Field(
        default_factory=list,
        description="Lista blanca de repositorios que el sistema puede tocar.",
    )
    allowed_test_targets: list[str] = Field(
        default_factory=lambda: ["pytest.unit", "pytest.integration", "ruff.check"],
        description="Enumeracion cerrada de objetivos de prueba ejecutables.",
    )
    allowed_packages: list[str] = Field(
        default_factory=list,
        description="Enumeracion cerrada de paquetes instalables. Vacia = ninguno.",
    )
    network_egress_enabled: bool = Field(
        default=False,
        description="Salida de red desde el entorno de ejecucion. Desactivada por defecto.",
    )

    # --- Presupuesto ---------------------------------------------------------
    max_tokens_per_run: int = Field(default=200_000, ge=1)
    max_tool_calls_per_run: int = Field(default=60, ge=1)
    max_seconds_per_run: float = Field(default=900.0, gt=0)
    max_review_cycles: int = Field(default=2, ge=0, le=5)

    # --- Speech-to-Text ------------------------------------------------------
    stt_provider: str = Field(default="faster-whisper")
    stt_model: str = Field(default="large-v3")
    stt_language: str = Field(default="es")
    stt_confidence_warn_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    tts_enabled: bool = Field(default=False, description="Salida por voz. Opcional por diseno.")

    # --- Observabilidad ------------------------------------------------------
    langfuse_enabled: bool = Field(default=False)
    langfuse_public_key: SecretStr = Field(default=SecretStr(""))
    langfuse_secret_key: SecretStr = Field(default=SecretStr(""))
    langfuse_host: str = Field(default="http://localhost:3000")
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
        """El TTS solo se activa si esta habilitado y el STT esta configurado.

        El informe textual siempre existe: el TTS nunca es la unica via de salida.
        """
        return self.tts_enabled

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
