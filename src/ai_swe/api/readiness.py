"""Authenticated project readiness and explicit empty base-commit creation."""

import subprocess
from threading import Lock

from fastapi import Depends, HTTPException

from ai_swe.config import repositorio_autorizado
from ai_swe.contracts.state import ExecutionMode
from ai_swe.github_publish import git_environment
from ai_swe.graph.model_routing import _authorized_git_root
from ai_swe.readiness import ReadinessReport, check_readiness


def register_readiness_routes(app, *, store, settings, worker, read, admin, identity, audit):
    lock = Lock()
    actor_dependency = Depends(identity)

    def project_for(project_id):
        project = store.proyecto(project_id)
        if project is None:
            raise HTTPException(404, "No existe ese proyecto.")
        if not repositorio_autorizado(settings, project.repo_path):
            raise HTTPException(403, "La carpeta está fuera de tu espacio autorizado.")
        return project

    @app.get(
        "/projects/{project_id}/readiness", response_model=ReadinessReport, dependencies=[read]
    )
    def readiness(project_id: str, mode: ExecutionMode = ExecutionMode.FULL_PROPOSAL):
        return check_readiness(settings, project_for(project_id).repo_path, mode)

    @app.post(
        "/projects/{project_id}/initialize-head",
        response_model=ReadinessReport,
        dependencies=[admin],
    )
    def initialize_head(project_id: str, actor=actor_dependency):
        project = project_for(project_id)
        with lock:
            if worker.active:
                raise HTTPException(
                    409, "Espera a que terminen las ejecuciones antes de crear la base."
                )
            if not _authorized_git_root(project.repo_path, project.repo_path, require_head=False):
                raise HTTPException(409, "La carpeta no es una raíz Git válida.")
            if not _authorized_git_root(project.repo_path, project.repo_path):
                try:
                    result = subprocess.run(
                        [
                            "git",
                            "-C",
                            project.repo_path,
                            "-c",
                            "user.name=AI SWE",
                            "-c",
                            "user.email=local@ai-swe.invalid",
                            "commit",
                            "--allow-empty",
                            "--only",
                            "--quiet",
                            "-m",
                            "Initial base for AI SWE worktrees",
                        ],
                        env=git_environment(),
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        timeout=30,
                        shell=False,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    raise HTTPException(
                        409, "No se pudo crear la base; revisa Git y la carpeta."
                    ) from None
                if result.returncode:
                    raise HTTPException(
                        409, "Git no pudo crear la base; tus archivos se conservaron."
                    )
            audit("proyecto.base_inicializada", actor, {"project_id": project_id})
            return check_readiness(settings, project.repo_path)
