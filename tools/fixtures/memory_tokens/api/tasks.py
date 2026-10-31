"""Respuestas del gestor de tareas usando el mismo contrato JSON."""
from fastapi import APIRouter
from api.responses import response_ok, response_error
from models.events import Task

router = APIRouter()
tasks = {}

@router.get("")
def list_tasks(completed=None):
    selected = [task.to_dict() for task in tasks.values()
                if completed is None or task.completed == completed]
    return response_ok(sorted(selected, key=lambda row: row["title"]))

@router.post("")
def add_task(identifier: str, title: str):
    if identifier in tasks:
        return response_error("Task already exists", code="duplicate")
    task = Task(identifier=identifier, title=title)
    tasks[identifier] = task
    return response_ok(task.to_dict())

@router.post("/{identifier}/toggle")
def toggle_task(identifier: str):
    if identifier not in tasks:
        return response_error("Task not found", code="not_found")
    task = tasks[identifier]
    task.completed = not task.completed
    return response_ok(task.to_dict())
