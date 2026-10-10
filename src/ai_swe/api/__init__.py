"""Capa HTTP: rutas, validacion de entrada y publicacion de progreso.

Rutas (M1 + F10):

    GET  /health
    POST /transcriptions                  -> Transcript (NO crea ejecucion)
    POST /projects                        -> Project (valida el repositorio en el alta)
    GET  /projects                        -> listado de proyectos
    GET  /projects/{id}                   -> Project
    POST /runs                            -> RunState (202; encola, no bloquea)
    GET  /runs                            -> listado de ejecuciones
    GET  /runs/{id}                       -> RunState
    GET  /runs/{id}/events                -> SSE con las transiciones y los hitos
    POST /runs/{id}/confirm-requirements  -> reanuda la puerta de requisitos (M2)
    POST /runs/{id}/approve               -> reanuda la puerta de aprobacion
    POST /runs/{id}/cancel                -> 501 (ver `app.cancelar_run`)

`GET /runs/{id}/trace` llega con la observabilidad (fase M6).

**El servidor solo escucha en 127.0.0.1.** No hay capa de autenticacion
(`AUD-06`), asi que exponerlo en una interfaz de red publicaria la capacidad de
ejecutar codigo en la maquina. El binding lo fija `ai_swe.__main__`.
"""

from ai_swe.api.app import (
    ApproveRequest,
    ConfirmRequirementsRequest,
    ProjectRequest,
    RunRequest,
    crear_app,
)

__all__ = [
    "ApproveRequest",
    "ConfirmRequirementsRequest",
    "ProjectRequest",
    "RunRequest",
    "crear_app",
]
