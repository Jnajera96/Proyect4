import json

import httpx
import pytest

from tools.model_lab_cases import CASES
from tools.model_lab_local import benchmark_local


@pytest.mark.parametrize("url", [
    "https://remote.example/v1", "http://localhost.example/v1",
    "http://127.0.0.1@remote.example/v1", "http://127.0.0.1/v1?redirect=remote",
])
def test_local_benchmark_rejects_non_loopback_destinations(url):
    with pytest.raises(ValueError):
        benchmark_local(base_url=url, model_id="synthetic")


def test_local_benchmark_has_no_paid_fallback_on_unavailable_engine():
    calls = []

    def server(request):
        calls.append(request)
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        rows = benchmark_local(
            base_url="http://127.0.0.1:8089/v1", model_id="synthetic",
            client=client, cases=CASES[:1], repeats=1,
        )
    assert len(calls) == 1
    assert calls[0].url.host == "127.0.0.1"
    assert rows[0]["error_class"] == "PROVIDER_UNAVAILABLE"
    assert not rows[0]["task_success"]
    assert rows[0]["cost_usd"] is None


def test_runtime_prompt_experiment_reuses_product_prompt():
    from ai_swe.graph.nodes import PROMPT_INTERPRETACION

    payloads = []

    def server(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        rows = benchmark_local(
            base_url="http://127.0.0.1:8089/v1", model_id="synthetic",
            client=client, cases=CASES[:1], repeats=1, use_runtime_prompts=True,
        )
    assert payloads[0]["messages"][0] == {"role": "system", "content": PROMPT_INTERPRETACION}
    assert rows[0]["prompt_source"] == "runtime"
