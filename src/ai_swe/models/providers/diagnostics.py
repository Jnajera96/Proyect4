"""Deterministic provider diagnostics. No inference, downloads or agent CLIs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field

from ai_swe.config import Settings

HF_ROUTER = "https://router.huggingface.co/v1"
HF_IDENTITY = "https://huggingface.co/api/whoami-v2"


class DiagnosticCheck(BaseModel):
    name: str
    status: Literal["ok", "warning", "error", "not_required", "not_checked"]
    code: str
    message: str


class PreflightReport(BaseModel):
    profile: Literal["offline", "hybrid", "unknown"]
    checks: list[DiagnosticCheck] = Field(default_factory=list)
    remote_configuration_ready: bool = False
    credential_validated: bool | None = None
    inference_calls: Literal[0] = 0
    inference_verified: Literal[False] = False
    billing_verified: Literal[False] = False


def user_config_path() -> Path:
    """Expected installed-user location; this diagnostic never creates files."""
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return base / "AISWESystem" / "config" / ".env"


def _health_url(base_url: str) -> str | None:
    try:
        url = urlsplit(base_url)
        if (
            url.scheme != "http"
            or url.hostname != "127.0.0.1"
            or url.username is not None
            or url.password is not None
            or url.path != "/v1"
            or url.query
            or url.fragment
        ):
            return None
        port = 80 if url.port is None else url.port
        if port < 1:
            return None
        return f"http://127.0.0.1:{port}/health"
    except ValueError:
        return None


def diagnose(
    settings: Settings,
    *,
    config_path: Path | None = None,
    local_base_url: str | None = None,
    check_remote: bool = False,
    client: httpx.Client | None = None,
) -> PreflightReport:
    """Inspect setup; optional GET probes never imply working paid inference.

    HF credentials are sent only to the fixed HF identity URL. Local probes use
    literal loopback, no credentials and no redirects. Network errors and bodies
    are not included in the report. A valid token does not prove provider scope,
    credit balance, model availability or successful generation.
    """
    if client is None:
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as owned:
            return diagnose(
                settings,
                config_path=config_path,
                local_base_url=local_base_url,
                check_remote=check_remote,
                client=owned,
            )
    report = PreflightReport(profile="hybrid" if settings.remote_model_roles else "offline")

    def add(name, status, code, message):
        report.checks.append(
            DiagnosticCheck(
                name=name,
                status=status,
                code=code,
                message=message,
            )
        )

    try:
        exists = (config_path or user_config_path()).is_file()
        add(
            "user_config",
            "ok" if exists else "warning",
            "present" if exists else "missing",
            "Configuracion de usuario presente."
            if exists
            else "No hay configuracion instalada; las funciones locales siguen disponibles.",
        )
    except OSError:
        add("user_config", "warning", "inaccessible", "No se pudo consultar la configuracion.")

    if local_base_url is None:
        add(
            "local_model",
            "not_required",
            "deterministic_roles",
            "Analyst y Supervisor son deterministas; no requieren un servidor GGUF.",
        )
    else:
        health_url = _health_url(local_base_url)
        if health_url is None:
            add(
                "local_model",
                "error",
                "invalid_loopback_url",
                "El servidor local debe usar http://127.0.0.1:PUERTO/v1.",
            )
        else:
            try:
                response = client.get(health_url, follow_redirects=False)
                data = response.json() if response.status_code == 200 else None
                healthy = isinstance(data, dict) and data.get("status") == "ok"
                add(
                    "local_model",
                    "ok" if healthy else "error",
                    "reachable" if healthy else "unavailable",
                    "Motor local accesible; inferencia no comprobada."
                    if healthy
                    else "El motor local no confirmo su estado de salud.",
                )
            except (httpx.HTTPError, ValueError):
                add("local_model", "error", "unavailable", "No se pudo consultar el motor local.")

    if not settings.remote_model_roles:
        add("remote_provider", "not_required", "disabled", "Los roles remotos estan desactivados.")
        return report
    if not settings.model_name.strip():
        add("remote_provider", "error", "missing_model", "Falta configurar el modelo remoto.")
        return report
    if settings.model_base_url != HF_ROUTER:
        add(
            "remote_provider",
            "error",
            "unsupported_diagnostic_endpoint",
            "Este diagnostico remoto solo valida el Router de Hugging Face.",
        )
        return report
    if settings.model_provider not in {"openai", "openai_compatible"}:
        add(
            "remote_provider",
            "error",
            "unsupported_provider",
            "El perfil HF requiere el adapter OpenAI-compatible.",
        )
        return report
    secret = settings.model_api_key.get_secret_value().strip()
    if not secret:
        add(
            "remote_provider",
            "error",
            "missing_runtime_key",
            "Falta AI_SWE_MODEL_API_KEY; HF_TOKEN aislado no configura el gateway.",
        )
        return report
    report.remote_configuration_ready = True
    if not check_remote:
        add(
            "remote_provider",
            "not_checked",
            "credential_present_unverified",
            "Configuracion presente; credencial, permisos y facturacion no comprobados.",
        )
        return report
    try:
        response = client.get(
            HF_IDENTITY,
            headers={"Authorization": "Bearer " + secret},
            follow_redirects=False,
        )
        if response.status_code in {401, 403}:
            report.credential_validated = False
            add(
                "remote_provider",
                "error",
                "authentication_rejected",
                "Hugging Face rechazo la autenticacion o autorizacion.",
            )
        elif response.status_code == 200:
            data = response.json()
            auth = data.get("auth") if isinstance(data, dict) else None
            if isinstance(auth, dict) and auth.get("type") == "access_token":
                report.credential_validated = True
                add(
                    "remote_provider",
                    "ok",
                    "identity_validated",
                    "Token aceptado por el Hub; inferencia, permisos y saldo no verificados.",
                )
            else:
                add(
                    "remote_provider",
                    "warning",
                    "unexpected_response",
                    "No se pudo validar el contrato de identidad del Hub.",
                )
        else:
            add(
                "remote_provider",
                "warning",
                "unavailable",
                "El servicio de identidad no esta disponible; validacion pendiente.",
            )
    except (httpx.HTTPError, ValueError):
        add(
            "remote_provider",
            "warning",
            "unavailable",
            "No se pudo consultar la identidad; validacion pendiente.",
        )
    return report
