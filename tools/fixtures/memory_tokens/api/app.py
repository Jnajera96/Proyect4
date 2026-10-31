"""Rutas HTTP con respuestas compartidas para el servicio local."""
from fastapi import FastAPI
from api.inventory import router as inventory_router
from api.tasks import router as tasks_router
from api.responses import response_ok

app = FastAPI(title="Workspace service", version="1.0")
app.include_router(inventory_router, prefix="/inventory")
app.include_router(tasks_router, prefix="/tasks")

@app.get("/healthcheck")
def healthcheck():
    return response_ok({"status": "ok", "service": "workspace"})

@app.get("/about")
def about():
    return response_ok({"version": "1.0", "storage": "local"})

@app.get("/capabilities")
def capabilities():
    return response_ok({"inventory": True, "tasks": True, "authentication": False})
