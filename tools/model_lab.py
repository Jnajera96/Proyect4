"""External model laboratory. Default command only discovers public metadata.

Inference requires HF_TOKEN and an explicit positive spending grant. No runtime
dependency on this module, notebooks, transformers or Jupyter is introduced.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai_swe.contracts import Budget
from ai_swe.models import ModelGateway, ModelMessage, ModelRequest
from ai_swe.models.errors import ModelAuthenticationError, ModelBillingError, ModelGatewayError
from ai_swe.models.providers.openai_compatible import OpenAICompatibleAdapter
from ai_swe.security import redact_deep, register_secret
from tools.model_lab_cases import CASES, LabCase, task_success

HF_ROUTER = "https://router.huggingface.co/v1"
CATALOG_URL = HF_ROUTER + "/models"


class GateRequired(RuntimeError):
    """Human credential or spending gate; no secret is part of the message."""


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    model_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", max_length=100)
    provider: str = Field(pattern=r"^[a-z0-9-]+$", max_length=40)
    status: str
    context_length: int | None = Field(default=None, gt=0)
    input_usd_per_million: float | None = Field(default=None, ge=0)
    output_usd_per_million: float | None = Field(default=None, ge=0)
    supports_structured_output: bool | None = None
    supports_tools: bool | None = None
    is_free: bool | None = None

    @property
    def routing_id(self) -> str:
        return f"{self.model_id}:{self.provider}"


def discover(client: httpx.Client | None = None) -> list[Candidate]:
    """GET public catalog, no credentials, no inference and no private account data."""
    if client is None:
        with httpx.Client(timeout=30, follow_redirects=False) as public:
            return discover(public)
    response = client.get(CATALOG_URL)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("catalog schema changed: data must be a list")
    found = {}
    for model in payload["data"]:
        if not isinstance(model, dict):
            continue
        providers = model.get("providers", [])
        if not isinstance(providers, list):
            continue
        for provider in providers:
            if not isinstance(provider, dict):
                continue
            pricing = provider.get("pricing")
            pricing = pricing if isinstance(pricing, dict) else {}
            try:
                candidate = Candidate(
                    model_id=model.get("id"),
                    provider=provider.get("provider"),
                    status=provider.get("status", "unknown"),
                    context_length=provider.get("context_length"),
                    input_usd_per_million=pricing.get("input"),
                    output_usd_per_million=pricing.get("output"),
                    supports_tools=provider.get("supports_tools"),
                    supports_structured_output=provider.get("supports_structured_output"),
                    is_free=provider.get("is_free"),
                )
            except ValidationError:
                continue
            found[candidate.routing_id] = candidate
    return sorted(found.values(), key=lambda c: c.routing_id)


def shortlist(candidates: Sequence[Candidate], limit: int = 3) -> list[Candidate]:
    """Metadata shortlist only; this is not a quality recommendation."""
    if not 1 <= limit <= 10:
        raise ValueError("limit must be 1..10")
    eligible = [
        c
        for c in candidates
        if c.status == "live"
        and c.supports_structured_output is True
        and c.context_length
        and c.context_length >= 4096
        and c.input_usd_per_million is not None
        and c.output_usd_per_million is not None
    ]
    return sorted(
        eligible,
        key=lambda c: (
            c.output_usd_per_million,
            c.input_usd_per_million,
            c.supports_tools is not True,
            c.routing_id,
        ),
    )[:limit]


class SpendGuard:
    """Conservative reservation, never refunded when a call fails or lacks usage.

    Uses full context as input upper bound, requested output cap and published
    USD/Mtoken rates. Provider-side billing controls remain necessary for a hard
    account ceiling; this does not claim to verify account credit availability.
    """

    def __init__(self, max_usd: Decimal):
        if not max_usd.is_finite() or max_usd <= 0:
            raise GateRequired("positive explicit spending authorization required")
        self.limit = max_usd
        self.reserved_usd = Decimal(0)

    def reserve(self, candidate: Candidate, max_output_tokens: int) -> Decimal:
        if (
            candidate.context_length is None
            or candidate.input_usd_per_million is None
            or candidate.output_usd_per_million is None
        ):
            raise GateRequired("trusted token prices and context bound required")
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        amount = (
            Decimal(str(candidate.input_usd_per_million)) * candidate.context_length
            + Decimal(str(candidate.output_usd_per_million)) * max_output_tokens
        ) / Decimal(1_000_000)
        if self.reserved_usd + amount > self.limit:
            raise GateRequired("spending reservation would exceed authorized limit")
        self.reserved_usd += amount
        return amount


class _ObservedAdapter:
    """Retains response in memory to count usage even if local schema validation fails."""

    def __init__(self, adapter):
        self.adapter = adapter
        self.last = None

    @property
    def name(self):
        return self.adapter.name

    def generate(self, request):
        self.last = self.adapter.generate(request)
        return self.last


def benchmark(
    candidates: Sequence[Candidate],
    *,
    token: str,
    max_usd: Decimal | None,
    client: httpx.Client | None = None,
    cases: Sequence[LabCase] = CASES,
    repeats: int = 2,
    max_retries: int = 0,
    timeout_s: float = 30,
    max_output_tokens: int = 512,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    if not token.strip():
        raise GateRequired("HF_TOKEN is not configured")
    if max_usd is None:
        raise GateRequired("explicit economic authorization required; included credit unknown")
    if not 1 <= repeats <= 5 or not 0 <= max_retries <= 2:
        raise ValueError("repeats 1..5 and retries 0..2 required")
    if not math.isfinite(timeout_s) or not 0 < timeout_s <= 120:
        raise ValueError("timeout must be 0..120 seconds")
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 4096:
        raise ValueError("max_output_tokens must be an integer in 1..4096")
    if not candidates or not cases:
        raise ValueError("at least one candidate and case required")
    register_secret(token)
    guard = SpendGuard(max_usd)
    # Preflight complete maximum call count so a gate never loses partial results.
    for candidate in candidates:
        for _ in range(len(cases) * repeats * (max_retries + 1)):
            guard.reserve(candidate, max_output_tokens)
    rows = []
    for candidate in candidates:
        with OpenAICompatibleAdapter(
            name="huggingface",
            model=candidate.routing_id,
            api_key=token,
            base_url=HF_ROUTER,
            client=client,
            timeout_s=timeout_s,
        ) as adapter:
            observed = _ObservedAdapter(adapter)
            gateway = ModelGateway([observed], timeout_s=timeout_s, max_retries=0)
            for case in cases:
                for repeat in range(repeats):
                    for retry in range(max_retries + 1):
                        observed.last = None
                        started = time.perf_counter()
                        error = None
                        parsed = None
                        try:
                            response = gateway.generate_structured(
                                ModelRequest(
                                    messages=[ModelMessage(role="user", content=case.prompt)],
                                    model=candidate.routing_id,
                                    max_output_tokens=max_output_tokens,
                                    timeout_s=timeout_s,
                                    temperature=0,
                                ),
                                response_model=case.schema,
                                budget=Budget(max_tokens=100_000, max_model_calls=100),
                            )
                            parsed = response.structured_as(case.schema)
                        except ModelGatewayError as exc:
                            error = exc
                        raw = observed.last
                        valid_json = False
                        if raw is not None:
                            with suppress(ValueError, TypeError):
                                valid_json = isinstance(json.loads(raw.content), dict)
                        usage = raw.usage if raw is not None else None
                        cost = None
                        if (
                            usage
                            and usage.input_tokens is not None
                            and usage.output_tokens is not None
                        ):
                            cost = float(
                                (
                                    Decimal(usage.input_tokens)
                                    * Decimal(str(candidate.input_usd_per_million))
                                    + Decimal(usage.output_tokens)
                                    * Decimal(str(candidate.output_usd_per_million))
                                )
                                / Decimal(1_000_000)
                            )
                        rows.append(
                            {
                                "model_id": candidate.model_id,
                                "provider": candidate.provider,
                                "role": case.role,
                                "case_id": case.case_id,
                                "repeat": repeat,
                                "retry": retry,
                                "fallbacks": 0,
                                "structured_output_success": valid_json,
                                "schema_valid": parsed is not None,
                                "task_success": parsed is not None and task_success(case, parsed),
                                "latency_ms": (time.perf_counter() - started) * 1000,
                                "input_tokens": usage.input_tokens if usage else None,
                                "output_tokens": usage.output_tokens if usage else None,
                                "total_tokens": usage.total_tokens if usage else None,
                                "cost_usd": cost,
                                "cost_basis": "catalog_estimate" if cost is not None else None,
                                "error_class": error.error_class if error else None,
                                "tool_call_compatibility": "not_probed",
                                "max_output_tokens": max_output_tokens,
                                "finish_reason": raw.finish_reason if raw else None,
                            }
                        )
                        if isinstance(error, (ModelAuthenticationError, ModelBillingError)):
                            return rows  # Account gates never trigger another paid attempt.
                        if error is None or not error.recoverable or retry == max_retries:
                            break
                        sleep(min(2**retry, 8))
    return rows


def recommend(candidates: Sequence[Candidate], rows: list[dict]) -> dict:
    """All cases need >=2 successful repetitions; no extrapolation to unseen roles."""
    recommendation = {}
    for role in sorted({c.role for c in CASES}):
        expected = {c.case_id for c in CASES if c.role == role}
        scored = []
        for candidate in candidates:
            samples = [
                r
                for r in rows
                if r["role"] == role
                and r["model_id"] == candidate.model_id
                and r["provider"] == candidate.provider
            ]
            if (
                candidate.status != "live"
                or not samples
                or {r["case_id"] for r in samples} != expected
                or any(
                    not r["schema_valid"] or not r["task_success"] or r["error_class"]
                    for r in samples
                )
                or any(
                    len({r["repeat"] for r in samples if r["case_id"] == case}) < 2
                    for case in expected
                )
            ):
                continue
            latency = statistics.median(r["latency_ms"] for r in samples)
            costs = [r["cost_usd"] for r in samples]
            cost = sum(costs) if all(c is not None for c in costs) else math.inf
            scored.append(
                (
                    (
                        latency,
                        cost,
                        -(candidate.context_length or 0),
                        candidate.supports_tools is not True,
                        candidate.routing_id,
                    ),
                    candidate,
                )
            )
        if scored:
            _, selected = min(scored, key=lambda item: item[0])
            recommendation[role] = {
                "model_id": selected.model_id,
                "provider": selected.provider,
                "routing_id": selected.routing_id,
                "evidence": "all role cases passed >=2 repetitions",
            }
    return recommendation


def save_results(path: Path, candidates: Sequence[Candidate], rows: list[dict]) -> None:
    selected = recommend(candidates, rows)
    report = {
        "format_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "catalog_source": CATALOG_URL,
        "status": "BENCHMARK_PARTIAL" if rows else "DISCOVERY_ONLY",
        "candidates": [c.model_dump() for c in candidates],
        "measurements": rows,
        "routing_recommendation": selected,
        "researcher": "deterministic",
        "runtime_tool_calling": "not implemented; lab metadata is not runtime support",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(redact_deep(report), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["discover", "benchmark", "check-gate"])
    parser.add_argument("--output", type=Path, default=Path("var/model_lab_results.json"))
    parser.add_argument("--max-usd", type=Decimal)
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    if args.command == "discover":
        candidates = discover()
        save_results(args.output, candidates, [])
        print(f"Public catalog: {len(candidates)} model/provider entries; inference calls: 0")
        return 0
    from dotenv import dotenv_values

    token = os.environ.get("HF_TOKEN") or dotenv_values(".env").get("HF_TOKEN") or ""
    if not token.strip():
        raise GateRequired("HF_TOKEN is not configured")
    register_secret(token)
    if args.max_usd is None:
        raise GateRequired("economic authorization required; included quota cannot be established")
    if args.command == "check-gate":
        SpendGuard(args.max_usd)
        print("Credential present; explicit positive spending limit configured")
        return 0
    candidates = shortlist(discover(), limit=args.limit)
    rows = benchmark(candidates, token=token, max_usd=args.max_usd)
    save_results(args.output, candidates, rows)
    print(f"Saved {len(rows)} attempts, no secrets or raw responses exported")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except GateRequired as exc:
        print(f"GATE_REQUIRED: {exc}")
        sys.exit(3)
