"""Capa HTTP: rutas, validacion de entrada y publicacion de progreso.

Rutas de la fase M1:

    GET  /health
    POST /transcriptions        -> Transcript (NO crea ejecucion)
    POST /runs                  -> RunState
    GET  /runs                  -> listado de ejecuciones
    GET  /runs/{id}             -> RunState
    GET  /runs/{id}/events      -> SSE con las transiciones de estado
    POST /runs/{id}/approve     -> reanuda el grafo tras una aprobacion
    POST /runs/{id}/cancel      -> 501 en M1 (ver `app.cancelar_run`)

`GET /runs/{id}/trace` llega con la observabilidad (fase M6).
"""

from ai_swe.api.app import ApproveRequest, RunRequest, crear_app

__all__ = ["ApproveRequest", "RunRequest", "crear_app"]
