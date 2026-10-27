"""Offline tests of the laboratory; no HF account, notebook, GPU or network."""

import json
from decimal import Decimal

import httpx
import pytest

from tools.model_lab import (
    Candidate,
    GateRequired,
    SpendGuard,
    benchmark,
    discover,
    recommend,
    save_results,
    shortlist,
)
from tools.model_lab_cases import CASES, task_success


def candidate(**changes):
    return Candidate(
        model_id="example/current-model",
        provider="test-provider",
        status="live",
        context_length=4096,
        input_usd_per_million=0.1,
        output_usd_per_million=0.2,
        supports_structured_output=True,
        supports_tools=True,
        **changes,
    )


def test_discovery_is_public_and_missing_metadata_stays_unknown():
    def server(request):
        assert request.url == "https://router.huggingface.co/v1/models"
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "example/current", "providers": [{"provider": "test", "status": "live"}]}
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        found = discover(client)
    assert len(found) == 1
    assert found[0].input_usd_per_million is None
    assert found[0].supports_tools is None
    assert found[0].context_length is None


def test_shortlist_does_not_select_error_unknown_prices_or_incapable():
    good = candidate()
    found = [
        good.model_copy(update={"status": "error"}),
        good.model_copy(update={"supports_structured_output": False}),
        good.model_copy(update={"input_usd_per_million": None}),
        good,
    ]
    assert shortlist(found, limit=2) == [good]


def test_spend_guard_is_conservative_and_does_not_refund_failed_attempts():
    guard = SpendGuard(Decimal("0.001"))
    first = guard.reserve(candidate(), max_output_tokens=512)
    assert first == Decimal("0.000512")
    with pytest.raises(GateRequired):
        guard.reserve(candidate(), max_output_tokens=512)
    assert guard.reserved_usd == first


def test_unknown_prices_do_not_authorize_a_paid_call():
    guard = SpendGuard(Decimal("2"))
    with pytest.raises(GateRequired):
        guard.reserve(candidate().model_copy(update={"input_usd_per_million": None}), 512)


def test_benchmark_requires_token_and_grant_without_contacting_server():
    def server(_):
        pytest.fail("inference before gate")

    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        with pytest.raises(GateRequired):
            benchmark([candidate()], token="", max_usd=Decimal("1"), client=client)
        with pytest.raises(GateRequired):
            benchmark([candidate()], token="synthetic-test-secret", max_usd=None, client=client)


def valid_requirements():
    return {
        "intent": "modify",
        "scope": {"repo_path": ".", "protected_paths": [".env"]},
        "constraints": ["No modificar .env"],
        "confidence": 0.9,
        "rationale": "crear /hello con tests",
    }


def test_existing_adapter_hf_wire_usage_schema_and_secret_free_export(tmp_path):
    secret = "synthetic-lab-credential-do-not-export"

    def server(request):
        assert request.url == "https://router.huggingface.co/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer " + secret
        data = json.loads(request.content)
        assert data["model"] == "example/current-model:test-provider"
        assert data["response_format"]["type"] == "json_object"
        assert data["max_tokens"] == 512
        assert request.extensions["timeout"]["read"] == 15
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": json.dumps(valid_requirements())},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 20, "total_tokens": 32},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        rows = benchmark(
            [candidate()],
            token=secret,
            max_usd=Decimal("1"),
            client=client,
            cases=CASES[:1],
            repeats=1,
            timeout_s=15,
        )
    assert len(rows) == 1
    assert rows[0]["schema_valid"] and rows[0]["task_success"]
    assert rows[0]["total_tokens"] == 32
    assert rows[0]["cost_usd"] == pytest.approx(0.0000052)
    assert rows[0]["tool_call_compatibility"] == "not_probed"
    path = tmp_path / "results.json"
    save_results(path, [candidate()], rows)
    assert secret not in path.read_text()
    assert "Authorization" not in path.read_text()


@pytest.mark.parametrize(
    "status,retryable", [(401, False), (403, False), (429, True), (500, True), (400, False)]
)
def test_provider_errors_retry_only_transient(status, retryable):
    calls = []

    def server(request):
        calls.append(request)
        return httpx.Response(status, json={"error": "synthetic-test-secret"})

    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        rows = benchmark(
            [candidate()],
            token="synthetic-test-secret",
            max_usd=Decimal("1"),
            client=client,
            cases=CASES[:1],
            repeats=1,
            max_retries=1,
            sleep=lambda _: None,
        )
    assert len(calls) == (2 if retryable else 1)
    assert all(not row["schema_valid"] for row in rows)
    assert "synthetic-test-secret" not in json.dumps(rows)


@pytest.mark.parametrize("content", ["not json", '{"broken":true}', '{"intent":'])
def test_invalid_and_truncated_outputs_are_not_success(content):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
            )
        )
    ) as client:
        rows = benchmark(
            [candidate()],
            token="synthetic-test-secret",
            max_usd=Decimal("1"),
            client=client,
            cases=CASES[:1],
            repeats=1,
        )
    assert not rows[0]["schema_valid"]
    assert not rows[0]["task_success"]
    assert rows[0]["input_tokens"] is None
    assert rows[0]["cost_usd"] is None


def test_timeout_is_recorded_without_secret_or_fake_usage():
    def server(request):
        raise httpx.ReadTimeout("synthetic-test-secret", request=request)

    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        rows = benchmark(
            [candidate()],
            token="synthetic-test-secret",
            max_usd=Decimal("1"),
            client=client,
            cases=CASES[:1],
            repeats=1,
        )
    assert rows[0]["error_class"] == "MODEL_TIMEOUT"
    assert rows[0]["total_tokens"] is None


def test_schema_valid_but_wrong_requirements_fail_quality_gate():
    parsed = CASES[0].schema.model_validate(valid_requirements())
    assert task_success(CASES[0], parsed)
    parsed = CASES[0].schema.model_validate({**valid_requirements(), "intent": "question"})
    assert not task_success(CASES[0], parsed)


def test_coder_quality_check_never_executes_generated_code(tmp_path):
    case = next(c for c in CASES if c.role == "coder")
    malicious = {
        "files": [
            {
                "path": "src/app.py",
                "operation": "modify",
                "new_content": "raise RuntimeError('never execute')",
                "rationale": "invalid",
            }
        ],
        "rationale": "invalid",
    }
    assert not task_success(case, case.schema.model_validate(malicious))


def test_recommendation_requires_repeated_complete_semantic_evidence():
    assert recommend([candidate()], []) == {}
    rows = [
        {
            "model_id": "example/current-model",
            "provider": "test-provider",
            "role": case.role,
            "case_id": case.case_id,
            "repeat": repeat,
            "schema_valid": True,
            "task_success": True,
            "error_class": None,
            "latency_ms": 1,
            "cost_usd": None,
            "retry": 0,
        }
        for case in CASES
        for repeat in range(2)
    ]
    selected = recommend([candidate()], rows)
    assert set(selected) == {case.role for case in CASES}
    assert all(v["model_id"] == "example/current-model" for v in selected.values())
    rows[0]["task_success"] = False
    assert "requirements_analyst" not in recommend([candidate()], rows)


def test_notebook_does_not_store_outputs_or_tokens():
    from pathlib import Path

    notebook = json.loads(Path("notebooks/01_HF_AGENT_MODEL_LAB.ipynb").read_text())
    assert notebook["nbformat"] == 4
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None


def test_billing_error_aborts_entire_benchmark_without_retry_or_secret():
    calls = []

    def server(request):
        calls.append(request)
        return httpx.Response(402, json={"error": "Insufficient credits synthetic-billing-secret"})

    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        rows = benchmark(
            [candidate(), candidate().model_copy(update={"provider": "other"})],
            token="synthetic-billing-secret",
            max_usd=Decimal("1"),
            client=client,
            repeats=2,
            max_retries=2,
        )
    assert len(calls) == 1
    assert len(rows) == 1
    assert rows[0]["error_class"] == "MODEL_BILLING_ERROR"
    assert rows[0]["cost_usd"] is None
    assert "synthetic-billing-secret" not in json.dumps(rows)
