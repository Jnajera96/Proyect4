"""Authenticated delivery actions; GET is read-only, mutations require operator/admin."""

import json
from pathlib import Path
from threading import Lock

from fastapi import HTTPException
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from ai_swe.config import repositorio_autorizado
from ai_swe.github_publish import GitHubPublishRequest, publication_steps, publish
from ai_swe.launch_guide import LaunchGuide, describe, launch, prepare


def register_delivery_routes(app, *, engine, store, settings, read, operate, admin):
    lock = Lock()
    previous_validation = app.exception_handlers.get(
        RequestValidationError, request_validation_exception_handler
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_publication(request, exc):
        if request.url.path.endswith("/publish-github"):
            return JSONResponse(
                status_code=422,
                content={"detail": "Revisa el nombre del repositorio, la organización y el PAT."},
            )
        return await previous_validation(request, exc)

    def state_for(run_id):
        state = engine.get(run_id)
        if not state.options.repo_path or not repositorio_autorizado(
            settings, state.options.repo_path
        ):
            raise HTTPException(403, "La carpeta está fuera de tu espacio autorizado.")
        return state

    def action(function, run_id):
        try:
            with lock:
                return function(state_for(run_id))
        except (ValueError, OSError) as error:
            raise HTTPException(409, str(error)) from None

    @app.get("/runs/{run_id}/launch-guide", response_model=LaunchGuide, dependencies=[read])
    def guide(run_id: str):
        return action(describe, run_id)

    @app.post(
        "/runs/{run_id}/launch-guide/prepare", response_model=LaunchGuide, dependencies=[operate]
    )
    def prepare_guide(run_id: str):
        return action(prepare, run_id)

    @app.post("/runs/{run_id}/launch", response_model=LaunchGuide, dependencies=[operate])
    def launch_application(run_id: str):
        return action(launch, run_id)

    @app.post("/projects/{project_id}/publish-github", dependencies=[admin])
    def publish_github(project_id: str, request: GitHubPublishRequest, stream: bool = False):
        project = store.proyecto(project_id)
        if project is None:
            raise HTTPException(404, "No existe ese proyecto.")
        with lock:
            for summary in store.list_summaries(limit=1000):
                state = engine.get(summary.run_id)
                if (
                    state.options.repo_path
                    and Path(state.options.repo_path).resolve() == Path(project.repo_path).resolve()
                    and state.status == "completed"
                    and state.promotion_receipt
                ):
                    try:
                        state_for(state.run_id)
                        if stream:

                            def events(state=state):
                                try:
                                    with lock:
                                        for event in publication_steps(state, request):
                                            yield json.dumps(event, ensure_ascii=False) + "\n"
                                except (ValueError, OSError) as error:
                                    from ai_swe.security import redact

                                    yield json.dumps({"error": redact(str(error))}) + "\n"

                            return StreamingResponse(
                                events(),
                                media_type="application/x-ndjson",
                                headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
                            )
                        return publish(state, request)
                    except (ValueError, OSError) as error:
                        raise HTTPException(409, str(error)) from None
            raise HTTPException(409, "Primero genera, revisa y aprueba tu aplicación.")
