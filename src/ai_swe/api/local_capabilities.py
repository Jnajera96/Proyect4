"""Profile-scoped local inspection; external export is an explicit admin mutation."""

import json

from fastapi import HTTPException
from fastapi.responses import Response

from ai_swe.config import repositorio_autorizado
from ai_swe.observability.traces import describe_trace, export_langfuse
from ai_swe.state.knowledge_graph import build_graph


def register_local_capabilities(app, *, settings, engine, store, read, admin):
    @app.get("/capabilities/local", dependencies=[read])
    def capabilities():
        return {
            "mcp": {
                "enabled": settings.mcp_enabled,
                "transport": "stdio",
                "tools": ["read_file", "git_status"],
            },
            "tts": {"enabled": settings.tts_active, "provider": "browser_local_only"},
            "observability": {
                "local": True,
                "langfuse_enabled": settings.langfuse_enabled,
                "langfuse_configured": bool(
                    settings.langfuse_public_key.get_secret_value()
                    and settings.langfuse_secret_key.get_secret_value()
                ),
            },
            "knowledge_graph": {"provider": "python_ast_local", "graphify_integrated": False},
        }

    def trace(run_id):
        return describe_trace(engine.get(run_id), store.events(run_id, limit=2001))

    @app.get("/runs/{run_id}/observability", dependencies=[read])
    def observability(run_id: str, download: bool = False):
        report = trace(run_id)
        if download:
            return Response(
                json.dumps(report, ensure_ascii=False),
                media_type="application/json",
                headers={"Content-Disposition": 'attachment; filename="traza-local.json"'},
            )
        return report

    @app.post("/runs/{run_id}/observability/langfuse", dependencies=[admin])
    def export_trace(run_id: str):
        try:
            return export_langfuse(trace(run_id), settings)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.get("/runs/{run_id}/context-graph", dependencies=[read])
    def context_graph(run_id: str):
        state = engine.get(run_id)
        repo = state.options.repo_path
        if not repo or not repositorio_autorizado(settings, repo):
            raise HTTPException(403, "La carpeta está fuera de tu espacio autorizado.")
        paths = (
            state.outputs.researcher_output.files_read if state.outputs.researcher_output else []
        )
        scope = state.interpretation.scope.allowed_paths if state.interpretation else []
        graph = build_graph(repo, paths, scope)
        graph["selected_paths"] = paths[:100]  # Already selected by the Researcher's memory.
        return graph
