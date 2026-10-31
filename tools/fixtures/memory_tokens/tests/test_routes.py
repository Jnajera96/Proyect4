"""Healthcheck y rutas registradas en el servicio."""
from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)

def test_healthcheck():
    response = client.get("/healthcheck")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"

def test_about():
    result = client.get("/about").json()
    assert result["ok"] is True
    assert result["data"]["storage"] == "local"

def test_inventory_list():
    result = client.get("/inventory").json()
    assert result["ok"] is True and isinstance(result["data"], list)

def test_capabilities():
    result = client.get("/capabilities").json()
    assert result["data"]["inventory"] and result["data"]["tasks"]
