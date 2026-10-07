"""Integracion de la redaccion con `logging` (`RNF-S3`).

**Por que un filtro y no pedir a cada llamante que redacte.** Una garantia que
depende de que todos los autores de log se acuerden no es una garantia. El filtro
se instala una vez en el logger raiz y actua sobre **cada** registro, lo escriba
quien lo escriba, incluso codigo de terceros (uvicorn, httpx, langgraph).

**Como redacta.** Actua sobre el mensaje ya formateado (`record.getMessage()`) y,
si es distinto, sobre el `repr` de los argumentos sueltos. Se reescribe el campo
`msg` y se vacian `args`, de modo que cualquier `Formatter` posterior -incluido un
`format` personalizado- trabaje ya sobre el texto limpio. Los datos de excepcion
se redactan aparte, porque un traceback puede arrastrar el valor de una variable
local hasta el log.

**Que no toca.** Rutas de fichero, identificadores de ejecucion y mensajes
normales no se alteran: el filtro solo sustituye lo que reconoce como secreto. Un
sistema que enmascara de mas deja de servir para diagnosticar.
"""

from __future__ import annotations

import logging
from typing import Any

from ai_swe.security.redaction import redact

_FILTRO_MARCA = "_ai_swe_redactor_instalado"


class RedactingFilter(logging.Filter):
    """Filtro de logging que elimina secretos conocidos de cada registro.

    Es idempotente en su efecto: aplicar `redact` dos veces da el mismo resultado.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 - firma de la stdlib
        try:
            self._limpiar(record)
        except Exception:  # noqa: BLE001 - un filtro nunca debe romper el logging
            # Ante cualquier fallo, se sustituye el mensaje entero por un aviso.
            # Es preferible perder un mensaje de log que arriesgar una fuga.
            record.msg = f"<registro de log suprimido por el redactor: {type(record).__name__}>"
            record.args = ()
        return True

    @staticmethod
    def _limpiar(record: logging.LogRecord) -> None:
        # 1. Mensaje formateado con sus argumentos. Redactar el mensaje ya
        #    construido es lo que cubre `log.info("clave=%s", api_key)`.
        try:
            mensaje = record.getMessage()
        except Exception:  # noqa: BLE001 - formato roto: no hay nada que redactar
            mensaje = None
        if mensaje is not None:
            limpio = redact(mensaje)
            if limpio != mensaje:
                record.msg = limpio
                record.args = ()

        # 2. Argumentos sueltos, por si un manejador los usa directamente.
        if record.args:
            try:
                record.args = tuple(redact(_repr_arg(a)) for a in _como_tupla(record.args))
            except Exception:  # noqa: BLE001
                record.args = ()

        # 3. Texto de excepcion. `exc_text` puede haberse cacheado; se regenera.
        if record.exc_info and not record.exc_text:
            try:
                record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            except Exception:  # noqa: BLE001
                record.exc_text = "[REDACTED]"
        elif record.exc_text:
            record.exc_text = redact(record.exc_text)

        # 4. `stack_info` (la pila capturada manualmente) tambien es texto libre.
        if record.stack_info:
            record.stack_info = redact(record.stack_info)


def _como_tupla(args: Any) -> tuple[Any, ...]:
    if isinstance(args, tuple):
        return args
    if isinstance(args, dict):
        return tuple(args.values())
    return (args,)


def _repr_arg(valor: Any) -> str:
    if isinstance(valor, str):
        return valor
    try:
        return repr(valor)
    except Exception:  # noqa: BLE001
        return "[REDACTED]"


def install_redacting_filter(
    logger: logging.Logger | None = None,
    *,
    level: int | None = None,
) -> RedactingFilter:
    """Instala el filtro en `logger` (por defecto, el logger raiz).

    Idempotente: instalar dos veces no anade el filtro dos veces. Devuelve el
    filtro, para poder quitarlo en una prueba.
    """
    destino = logger if logger is not None else logging.getLogger()
    for existente in destino.filters:
        if isinstance(existente, RedactingFilter):
            if level is not None:
                destino.setLevel(level)
            return existente
    filtro = RedactingFilter()
    destino.addFilter(filtro)
    setattr(filtro, _FILTRO_MARCA, True)
    if level is not None:
        destino.setLevel(level)
    return filtro
