"""Local GGUF evaluation through the existing gateway; not a runtime dependency."""

from __future__ import annotations

import time
from collections.abc import Sequence
from urllib.parse import urlsplit

import httpx

from ai_swe.contracts import Budget
from ai_swe.models import ModelGateway, ModelMessage, ModelRequest
from ai_swe.models.errors import ModelGatewayError
from ai_swe.models.providers.openai_compatible import OpenAICompatibleAdapter
from tools.model_lab_cases import CASES, LabCase, task_success


def benchmark_local(
    *,
    base_url: str,
    model_id: str,
    api_key: str = "",
    client: httpx.Client | None = None,
    cases: Sequence[LabCase] = tuple(
        case for case in CASES if case.role in {"requirements_analyst", "supervisor"}
    ),
    repeats: int = 2,
    timeout_s: float = 120,
    use_runtime_prompts: bool = False,
) -> list[dict]:
    """Evaluate a caller-managed loopback server, without downloads or paid fallback.

    Caller owns engine startup, memory checks, asset checksums and cleanup.
    A dedicated client ignores proxy environment variables and rejects redirects.
    No raw generated content is retained or executed.
    """
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
        raise ValueError("local laboratory requires http://127.0.0.1:PORT/v1")
    if not 1 <= repeats <= 5 or not 0 < timeout_s <= 120 or not cases:
        raise ValueError("invalid repeats, timeout or empty cases")
    if client is None:
        with httpx.Client(timeout=timeout_s, trust_env=False, follow_redirects=False) as owned:
            return benchmark_local(
                base_url=base_url, model_id=model_id, api_key=api_key,
                client=owned, cases=cases, repeats=repeats, timeout_s=timeout_s,
                use_runtime_prompts=use_runtime_prompts,
            )
    rows = []
    with OpenAICompatibleAdapter(
        name="local_gguf", model=model_id, base_url=base_url, api_key=api_key,
        client=client, timeout_s=timeout_s,
    ) as adapter:
        gateway = ModelGateway([adapter], max_retries=0, timeout_s=timeout_s)
        for case in cases:
            messages = [ModelMessage(role="user", content=case.prompt)]
            if use_runtime_prompts:
                from ai_swe.graph.nodes import PROMPT_INTERPRETACION, PROMPT_PLANIFICACION

                prompts = {
                    "requirements_analyst": PROMPT_INTERPRETACION,
                    "supervisor": PROMPT_PLANIFICACION,
                }
                if case.role not in prompts:
                    raise ValueError("runtime prompt not available for this local role")
                messages.insert(0, ModelMessage(role="system", content=prompts[case.role]))
            for repeat in range(repeats):
                started = time.perf_counter()
                parsed, response, error = None, None, None
                try:
                    response = gateway.generate_structured(
                        ModelRequest(
                            messages=messages,
                            model=model_id, max_output_tokens=512, temperature=0,
                        ),
                        response_model=case.schema,
                        budget=Budget(max_tokens=100_000, max_model_calls=1),
                    )
                    parsed = response.structured_as(case.schema)
                except ModelGatewayError as exc:
                    error = exc.error_class
                rows.append({
                    "model_id": model_id, "provider": "local_gguf",
                    "role": case.role, "case_id": case.case_id, "repeat": repeat,
                    "schema_valid": parsed is not None,
                    "task_success": parsed is not None and task_success(case, parsed),
                    "error_class": error,
                    "latency_ms": (time.perf_counter() - started) * 1000,
                    "input_tokens": response.usage.input_tokens if response else None,
                    "output_tokens": response.usage.output_tokens if response else None,
                    "cost_usd": None,
                    "cost_basis": "local hardware and electricity not measured",
                    "prompt_source": "runtime" if use_runtime_prompts else "lab_case_only",
                })
    return rows
