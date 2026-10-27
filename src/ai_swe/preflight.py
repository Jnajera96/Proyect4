"""CLI for deterministic provider diagnostics; no inference or configuration writes."""

from __future__ import annotations

import argparse

from pydantic import ValidationError

from ai_swe.config import Settings
from ai_swe.models.providers.diagnostics import (
    HF_IDENTITY,
    HF_ROUTER,
    DiagnosticCheck,
    PreflightReport,
    diagnose,
    user_config_path,
)

__all__ = [
    "HF_IDENTITY",
    "HF_ROUTER",
    "DiagnosticCheck",
    "PreflightReport",
    "diagnose",
    "user_config_path",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-remote", action="store_true")
    parser.add_argument("--local-base-url")
    args = parser.parse_args()
    try:
        settings = Settings()
    except ValidationError:
        report = PreflightReport(
            profile="unknown",
            checks=[
                DiagnosticCheck(
                    name="configuration",
                    status="error",
                    code="invalid_configuration",
                    message="Configuracion invalida; revisar ajustes sin compartir secretos.",
                )
            ],
        )
    else:
        report = diagnose(
            settings,
            check_remote=args.check_remote,
            local_base_url=args.local_base_url,
        )
    print(report.model_dump_json(indent=2))
    return 1 if any(check.status == "error" for check in report.checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
