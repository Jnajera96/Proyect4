"""Opt-in role probes against an existing, screenshot-reconciled session grant.

Default: no inference. The historical ledger is never reset or modified.
"""

from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from pathlib import Path

from dotenv import dotenv_values

from ai_swe.models.errors import ModelAuthenticationError, ModelBillingError
from ai_swe.security import redact_deep
from tools.model_lab import Candidate, GateRequired, SpendGuard, benchmark
from tools.model_lab_cases import CASES
from tools.verify_calculator_e2e import exclusive_lock

ROLE_CASES = tuple(c for c in CASES if c.role in {"coder", "reviewer"})


def reserve_session(ledger: dict, candidates: list[Candidate], cases=ROLE_CASES) -> Decimal:
    """Keep old reservations; the new grant is bounded by the account snapshot."""
    ceiling = Decimal(str(ledger["total_ceiling_usd"]))
    spent = Decimal(str(ledger["account_usage_usd"]))
    credit = Decimal(str(ledger["account_credit_usd"]))
    grant = Decimal(str(ledger["authorized_usd"]))
    used = Decimal(str(ledger["reserved_usd"]))
    if any(not v.is_finite() for v in (ceiling, spent, credit, grant, used)) or not (
        0 < ceiling <= 5
        and 0 <= spent <= ceiling
        and credit >= 0
        and 0 < grant <= min(Decimal("2"), ceiling - spent, credit)
        and used >= 0
    ):
        raise GateRequired("Invalid reconciliation or spending grant")
    if not ledger.get("billing_evidence"):
        raise GateRequired("Account evidence is required; never discard unknown old reservations")
    guard = SpendGuard(grant)
    for candidate in candidates:
        for _ in cases:
            guard.reserve(candidate, 1024)
    if used + guard.reserved_usd > grant:
        raise GateRequired("Session would exceed its existing grant")
    return guard.reserved_usd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-real", action="store_true")
    parser.add_argument(
        "--metadata-probe",
        action="store_true",
        help="Two JSON-mode compatibility probes for routes without native schema metadata",
    )
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.run_real:
        print("Inference calls: 0. Real probes require --run-real and an existing session grant.")
        return 0
    if not all((args.catalog, args.ledger, args.output)):
        parser.error("Supply catalog, existing ledger and a new output file")
    if args.output.exists():
        raise GateRequired("Preserve previous evidence; choose a new output")
    root = Path(__file__).resolve().parents[1]
    selector = json.loads((root / "frontend/src/lib/modelCatalog.json").read_text())
    ids = {m["id"] for m in selector["models"]}
    snapshot = json.loads(args.catalog.read_text())
    cases = (
        tuple(c for c in ROLE_CASES if c.case_id in {"code-return", "review-bad"})
        if args.metadata_probe
        else ROLE_CASES
    )
    candidates = sorted(
        [
            Candidate(**c)
            for c in snapshot["candidates"]
            if f"{c['model_id']}:{c['provider']}" in ids
            and c["status"] == "live"
            and c["supports_structured_output"] is (not args.metadata_probe)
        ],
        key=lambda c: (c.output_usd_per_million or 0, c.routing_id),
    )
    if not candidates:
        raise GateRequired("No eligible selector routes")
    dotenv = dotenv_values(root / ".env")
    token = (
        os.getenv("HF_TOKEN")
        or os.getenv("AI_SWE_HF_TOKEN")
        or dotenv.get("HF_TOKEN")
        or dotenv.get("AI_SWE_HF_TOKEN")
        or ""
    )
    if not token:
        raise GateRequired("Configure a credential privately before running probes")
    with exclusive_lock(args.ledger.with_suffix(".routes.lock")):
        ledger = json.loads(args.ledger.read_text())
        amount = reserve_session(ledger, candidates, cases)
        ledger["reserved_usd"] = str(Decimal(str(ledger["reserved_usd"])) + amount)
        ledger.setdefault("batches", []).append(
            {
                "output": str(args.output),
                "reserved_usd": str(amount),
                "routes": [c.routing_id for c in candidates],
                "max_http_calls": len(candidates) * len(cases),
            }
        )
        args.ledger.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        report = {
            "status": "in_progress",
            "reserved_usd": str(amount),
            "catalog_generated_at": snapshot["generated_at"],
            "scope": "role contract probes, not application E2E",
            "metadata_probe": args.metadata_probe,
            "tested_cases": [c.case_id for c in cases],
            "measurements": [],
        }

        def save():
            args.output.write_text(
                json.dumps(redact_deep(report), ensure_ascii=False, indent=2), encoding="utf-8"
            )

        save()
        for candidate in candidates:
            rows = benchmark(
                [candidate],
                token=token,
                max_usd=amount,
                cases=cases,
                repeats=1,
                max_retries=0,
                max_output_tokens=1024,
                timeout_s=30,
            )
            report["measurements"].extend(rows)
            save()
            print(
                candidate.routing_id,
                "attempts",
                len(rows),
                "passed",
                sum(r["schema_valid"] and r["task_success"] for r in rows),
                flush=True,
            )
            if any(
                r["error_class"]
                in {ModelAuthenticationError.error_class, ModelBillingError.error_class}
                for r in rows
            ):
                report["status"] = "account_gate"
                save()
                return 3
        report["status"] = "completed"
        save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
