"""Profile-owned SQLite events are the primary trace; exports contain metadata only."""

import hashlib
import json
from datetime import timedelta
from urllib.parse import urlsplit

from ai_swe.security import redact_deep

_FIELDS = {
    "node",
    "role",
    "mode",
    "model",
    "provider",
    "attempt",
    "target",
    "exit_code",
    "duration_ms",
    "input_tokens",
    "output_tokens",
    "cost",
}


def describe_trace(state, events, *, limit=2000):
    selected = events[:limit]
    entries = [
        {
            "seq": e.seq,
            "at": e.at.isoformat(),
            "kind": e.kind.value,
            "data": {
                k: v
                for k, v in e.data.items()
                if k in _FIELDS and isinstance(v, (str, int, float, bool, type(None)))
            },
        }
        for e in selected
    ]
    return redact_deep(
        {
            "run_id": state.run_id,
            "trace_id": state.trace_id,
            "status": state.status.value,
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            "truncated": len(events) > limit,
            "events": entries,
            "usage": {
                "input_tokens": state.budget.used_input_tokens,
                "output_tokens": state.budget.used_output_tokens,
                "model_calls": state.budget.used_model_calls,
                "used_cost": state.budget.used_cost,
                "cost_available": state.budget.used_model_calls == 0
                or (
                    len(events) <= limit
                    and sum(
                        e.kind.value == "model_response_received" and e.data.get("cost") is not None
                        for e in selected
                    )
                    == state.budget.used_model_calls
                ),
            },
            "errors": [e.error_class for e in state.errors],
            "verification_failures": [
                p.target
                for p in {p.target: p for p in state.evidence.test_runs}.values()
                if not p.passed
            ],
        }
    )


def otlp_payload(trace):
    """Stable IDs make explicit retransmission idempotent at the span identity level."""
    from datetime import datetime

    trace_id = hashlib.sha256(trace["trace_id"].encode()).hexdigest()[:32]
    spans = []
    for event in trace["events"]:
        if event["kind"] not in {"node_completed", "model_response_received"}:
            continue
        data = event["data"]
        end = datetime.fromisoformat(event["at"])
        duration = data.get("duration_ms", 0)
        duration = duration if isinstance(duration, (int, float)) and duration >= 0 else 0
        start = end - timedelta(milliseconds=min(duration, 86400000))
        attrs = []
        attrs.append({"key": "langfuse.trace.name", "value": {"stringValue": "AI SWE workflow"}})
        if event["kind"] == "model_response_received":
            attrs.append(
                {"key": "langfuse.observation.type", "value": {"stringValue": "generation"}}
            )
            if data.get("model"):
                attrs.append(
                    {"key": "gen_ai.request.model", "value": {"stringValue": data["model"]}}
                )
            usage = {
                name: data[field]
                for name, field in (("input", "input_tokens"), ("output", "output_tokens"))
                if data.get(field) is not None
            }
            attrs.append(
                {
                    "key": "langfuse.observation.usage_details",
                    "value": {"stringValue": json.dumps(usage)},
                }
            )
            if data.get("cost") is not None:
                attrs.append(
                    {
                        "key": "langfuse.observation.cost_details",
                        "value": {"stringValue": json.dumps({"total": data["cost"]})},
                    }
                )
        for key, value in data.items():
            if value is not None:
                attrs.append({"key": "ai_swe." + key, "value": {"stringValue": str(value)}})
        spans.append(
            {
                "traceId": trace_id,
                "spanId": hashlib.sha256(f"{trace_id}:{event['seq']}".encode()).hexdigest()[:16],
                "name": str(data.get("node") or event["kind"]),
                "kind": 1,
                "startTimeUnixNano": str(int(start.timestamp() * 1_000_000_000)),
                "endTimeUnixNano": str(int(end.timestamp() * 1_000_000_000)),
                "attributes": attrs,
            }
        )
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [{"key": "service.name", "value": {"stringValue": "ai-swe"}}]
                },
                "scopeSpans": [{"scope": {"name": "ai_swe.local_trace"}, "spans": spans}],
            }
        ]
    }


def export_langfuse(trace, settings):
    """Explicit administrator action; never run on the critical agent path."""
    if not settings.langfuse_enabled:
        raise ValueError("Langfuse está desactivado. La traza local sigue disponible.")
    host = urlsplit(settings.langfuse_host)
    if (
        host.scheme not in {"http", "https"}
        or not host.hostname
        or host.username
        or host.password
        or host.query
        or host.fragment
        or host.path not in {"", "/"}
        or (host.scheme == "http" and host.hostname not in {"localhost", "127.0.0.1", "::1"})
    ):
        raise ValueError("Configura HTTPS para Langfuse remoto o HTTP solo en bucle local.")
    public = settings.langfuse_public_key.get_secret_value()
    secret = settings.langfuse_secret_key.get_secret_value()
    if not public or not secret:
        raise ValueError("Faltan las claves de Langfuse; no se realizó la exportación.")
    payload = otlp_payload(
        {**trace, "trace_id": (settings.profile_id or "legacy") + ":" + trace["trace_id"]}
    )
    count = len(payload["resourceSpans"][0]["scopeSpans"][0]["spans"])
    if not count:
        raise ValueError("Todavía no hay etapas completadas para exportar.")
    from ai_swe.models.providers.langfuse import send_trace

    send_trace(settings.langfuse_host, public, secret, payload)
    return {"exported": True, "spans": count, "truncated": trace["truncated"]}
