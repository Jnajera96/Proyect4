"""Read-only local readiness; never probes credentials or remote billing."""

import shutil

from pydantic import BaseModel, Field

from ai_swe.config import Settings, provider_configuration
from ai_swe.graph.model_routing import _authorized_git_root
from ai_swe.models.contracts import ModelUsage
from ai_swe.models.pricing import pricing_from_json
from ai_swe.models.registry import registered_providers
from ai_swe.state.budget_ledger import BudgetLedger


class ReadinessCheck(BaseModel):
    code: str
    ready: bool
    message: str
    action: str | None = None


class ReadinessReport(BaseModel):
    ready: bool = False
    checks: list[ReadinessCheck] = Field(default_factory=list)
    inference_verified: bool = False
    remote_billing_verified: bool = False


def check_readiness(settings: Settings, repo: str, mode: str = "FULL_PROPOSAL") -> ReadinessReport:
    checks = []

    def add(code, ready, message, action=None):
        checks.append(
            ReadinessCheck(
                code=code, ready=ready, message=message, action=None if ready else action
            )
        )

    available = shutil.which("git") is not None
    add(
        "GIT",
        available,
        "Git disponible." if available else "Instala Git para Windows.",
        "install_git",
    )
    valid = available and _authorized_git_root(repo, repo, require_head=False)
    add(
        "REPOSITORY",
        valid,
        "Carpeta Git válida." if valid else "Selecciona una carpeta Git válida.",
        "register_project",
    )
    head = valid and _authorized_git_root(repo, repo)
    add(
        "HEAD",
        head,
        "Commit base disponible." if head else "Falta un commit base para proteger los cambios.",
        "initialize_head" if valid else "register_project",
    )
    if mode == "FULL_PROPOSAL":
        if settings.runner_docker is not None:
            from ai_swe.tools.docker_runner import DockerError, check_ready

            try:
                check_ready(settings.runner_docker)
                add("DOCKER", True, "Pruebas aisladas con Docker listas.")
            except (DockerError, OSError) as exc:
                add("DOCKER", False, str(exc), "configure_runner")
        config = provider_configuration(settings)
        roles = {"coder", "reviewer"}.issubset(settings.remote_model_roles)
        configured = (
            roles
            and not config["missing_fields"]
            and settings.model_provider in registered_providers()
        )
        add(
            "PROVIDER",
            configured,
            "Configuración presente; permisos y saldo remoto sin verificar."
            if configured
            else "Configura proveedor, modelos, credencial y roles Coder/Reviewer en la bóveda.",
            "configure_vault",
        )
        try:
            pricing = pricing_from_json(settings.model_pricing)
            names = (settings.model_name, settings.reviewer_model or settings.model_name)
            priced = all(
                pricing.cost(name, ModelUsage(input_tokens=1, output_tokens=1)) is not None
                for name in names
            )
        except ValueError:
            priced = False
        add(
            "PRICING",
            priced,
            "Tarifas declaradas."
            if priced
            else "Declara las tarifas de ambos modelos en la bóveda.",
            "configure_vault",
        )
        budget = BudgetLedger.read_status(settings.state_db_path)
        allowance = settings.max_cost_per_run
        enough = (
            bool(settings.profile_id)
            and allowance is not None
            and allowance > 0
            and budget["available"] >= allowance
            and (
                settings.max_cost_per_hour is None
                or budget["hourly_used"] + allowance <= settings.max_cost_per_hour
            )
        )
        add(
            "BUDGET",
            enough,
            "Ledger local con saldo para reservar la ejecución."
            if enough
            else (
                "El ledger local no cubre el límite por ejecución. "
                "Revisa límites y reservas en la bóveda."
            ),
            "configure_vault",
        )
    return ReadinessReport(ready=all(c.ready for c in checks), checks=checks)
