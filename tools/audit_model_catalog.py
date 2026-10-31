"""Audit selector routes and the existing grant without credentials or inference.

Run with python -m tools.audit_model_catalog; a public snapshot is required.
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from tools.model_lab import Candidate, GateRequired, SpendGuard


def assess(models: list[dict], candidates: list[Candidate], ledger: dict) -> dict:
    ceiling = Decimal(str(ledger["authorized_usd"]))
    reserved = Decimal(str(ledger["reserved_usd"]))
    if not ceiling.is_finite() or not reserved.is_finite() or not 0 < ceiling <= 5 or reserved < 0:
        raise ValueError("Invalid historical grant; no spending can be authorized")
    available = min(Decimal("2"), max(Decimal(0), ceiling - reserved))
    lookup = {c.routing_id: c for c in candidates}
    rows = []
    for model in models:
        candidate = lookup.get(model["id"])
        reason = "candidate_unverified"
        if candidate is None:
            reason = "not_in_catalog"
        elif candidate.status != "live":
            reason = "not_live"
        elif candidate.supports_structured_output is not True:
            reason = "structured_output_not_declared"
        elif model["projectValidated"]:
            reason = "historical_e2e_only"
        required = None
        if reason in {"candidate_unverified", "historical_e2e_only"}:
            try:
                guard = SpendGuard(Decimal("1000000"))
                # Two cases per role, two repetitions, no retries, output capped at 1024.
                required = sum(guard.reserve(candidate, 1024) for _ in range(8))
            except GateRequired:
                reason = "missing_cost_or_context_bounds"
        rows.append(
            {
                "id": model["id"],
                "label": model["label"],
                "status": reason,
                "metadata": candidate.model_dump() if candidate else None,
                "new_inference_tested": False,
                "batch_reservation_usd": str(required) if required is not None else None,
                "budget_allows_batch": required is not None and required <= available,
            }
        )
    return {
        "paid_calls": 0,
        "inference_calls": 0,
        "historical_ceiling_usd": str(ceiling),
        "historical_reserved_usd": str(reserved),
        "session_authorized_usd": "2",
        "available_conservative_usd": str(available),
        "reservation_is_not_billed_cost": True,
        "plan": {
            "roles": ["coder", "reviewer"],
            "cases_per_role": 2,
            "repeats": 2,
            "retries": 0,
            "max_output_tokens": 1024,
        },
        "models": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / "frontend/src/lib/modelCatalog.json").read_text())
    snapshot = json.loads(args.snapshot.read_text())
    report = assess(
        catalog["models"],
        [Candidate(**row) for row in snapshot["candidates"]],
        json.loads(args.ledger.read_text()),
    )
    report["catalog_generated_at"] = snapshot["generated_at"]
    report["catalog_source"] = snapshot["catalog_source"]
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    for row in report["models"]:
        print(f"{row['id']} | {row['status']} | reserve={row['batch_reservation_usd']} USD")
    print("Available conservative USD:", report["available_conservative_usd"])
    print("Inference calls: 0; historical ledger unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
