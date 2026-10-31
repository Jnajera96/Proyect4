"""Contrato de formato de respuestas compartidas entre los endpoints."""
from api.responses import response_ok, response_error

def test_respuestas_success():
    result = response_ok({"id": "1"}, request_id="r1")
    assert result["ok"] is True and result["data"] == {"id": "1"}
    assert result["meta"]["request_id"] == "r1"

def test_respuestas_copy_lists():
    original = [1, 2]
    result = response_ok(original)
    original.append(3)
    assert result["data"] == [1, 2]

def test_respuestas_error():
    result = response_error("Missing item", code="not_found")
    assert result["ok"] is False and result["data"] is None
    assert result["error"]["code"] == "not_found"

def test_respuestas_empty_payload():
    assert response_ok(None)["data"] == {}
