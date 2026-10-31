"""Punto compartido de formato de todas las respuestas del servicio."""
from collections.abc import Mapping

def response_ok(payload, *, request_id=None):
    if isinstance(payload, Mapping):
        data = dict(payload)
    elif isinstance(payload, (list, tuple)):
        data = list(payload)
    elif payload is None:
        data = {}
    else:
        data = {"value": payload}
    meta = {"request_id": request_id, "schema": "workspace.v1"}
    return {"ok": True, "data": data, "meta": meta}

def response_error(message, *, code="invalid_input", request_id=None):
    return {
        "ok": False,
        "data": None,
        "error": {"code": code, "message": str(message)},
        "meta": {"request_id": request_id, "schema": "workspace.v1"},
    }
