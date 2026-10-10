"""Arranque del servidor HTTP: `python -m ai_swe`.

**El binding esta fijado a 127.0.0.1 en una constante, no en un argumento.** La
razon es `AUD-06`: no hay capa de autenticacion, asi que cualquiera que alcance el
puerto puede lanzar una ejecucion, y una ejecucion **escribe codigo y ejecuta
pruebas** en un worktree. En `0.0.0.0` eso queda al alcance de toda la red local.

Dejar el host como parametro de linea de comandos seria una invitacion a abrirlo
"un momento para probar" y olvidarlo. Si algun dia hace falta exponerlo, tendra que
ser un cambio de codigo con su revision, y acompanado de la autenticacion que hoy
no existe.

El puerto si es configurable por entorno: cambiarlo no amplia quien puede llegar,
solo donde escucha el bucle local.
"""

from __future__ import annotations

import os
import sys

#: Interfaz de red. **Solo bucle local.** Ver el docstring del modulo.
HOST = "127.0.0.1"

#: Puerto por defecto del bucle local.
PUERTO_POR_DEFECTO = 8000


def puerto() -> int:
    """Puerto de escucha, de `AI_SWE_PORT` o el de por defecto.

    Un valor invalido **no** se ignora en silencio: arrancar en el puerto por
    defecto cuando alguien pidio otro deja al cliente llamando a donde no hay nada,
    y el error aparece lejos de su causa.
    """
    crudo = os.environ.get("AI_SWE_PORT")
    if crudo is None or not crudo.strip():
        return PUERTO_POR_DEFECTO
    try:
        valor = int(crudo)
    except ValueError as exc:
        raise SystemExit(f"AI_SWE_PORT no es un numero: {crudo!r}") from exc
    if not (1 <= valor <= 65535):
        raise SystemExit(f"AI_SWE_PORT fuera de rango: {valor}")
    return valor


def main() -> int:
    import uvicorn

    from ai_swe.api import crear_app

    uvicorn.run(crear_app(), host=HOST, port=puerto(), log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
