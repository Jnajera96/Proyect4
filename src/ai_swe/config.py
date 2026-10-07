"""Configuracion del sistema.

Validada al arrancar. Los secretos se leen del entorno y **nunca** se escriben
en el repositorio; `.env.example` documenta nombres, no valores.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
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
    model_api_key: str = Field(default="", description="Secreto: solo desde el entorno.")
    model_base_url: str | None = Field(default=None, description="Para proveedores locales.")

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
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
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


def load_settings() -> Settings:
    return Settings()
