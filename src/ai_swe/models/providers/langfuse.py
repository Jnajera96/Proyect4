"""Optional OTLP/HTTP adapter; never called automatically by the model gateway."""

import json

import httpx


def send_trace(host, public, secret, payload):
    try:
        with (
            httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client,
            client.stream(
                "POST",
                host.rstrip("/") + "/api/public/otel/v1/traces",
                auth=(public, secret),
                json=payload,
                headers={"x-langfuse-ingestion-version": "4"},
            ) as response,
        ):
            if response.status_code != 200:
                raise ValueError("Respuesta de exportación no aceptada.")
            raw = bytearray()
            for chunk in response.iter_bytes(chunk_size=16384):
                raw.extend(chunk)
                if len(raw) > 65536:
                    raise ValueError("Respuesta de exportación demasiado extensa.")
            receipt = json.loads(raw)
            if (
                not isinstance(receipt, dict)
                or not isinstance(receipt.get("partialSuccess", {}), dict)
                or receipt.get("partialSuccess", {}).get("rejectedSpans", 0) not in (0, "0")
            ):
                raise ValueError("Recepción parcial o no confirmada.")
    except (httpx.HTTPError, ValueError, TypeError):
        raise ValueError(
            "No se confirmó la exportación a Langfuse. La traza local se conserva."
        ) from None
