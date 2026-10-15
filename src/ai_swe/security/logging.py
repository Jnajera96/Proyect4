"""Integracion de la redaccion con `logging` (`RNF-S3`).

**Por que un filtro y no pedir a cada llamante que redacte.** Una garantia que
depende de que todos los autores de log se acuerden no es una garantia. El filtro
se instala en los handlers de salida: los filtros del logger raiz NO se ejecutan
para registros propagados desde hijos. Se cubren tambien los handlers propios de
loggers como uvicorn y el handler de ultimo recurso de Python. Si se reconfiguran
los handlers despues del arranque, se debe repetir la instalacion (idempotente).

**Como redacta.** Actua sobre el mensaje ya formateado (`record.getMessage()`).
Se reescribe el campo `msg` y se vacian `args`, de modo que cualquier `Formatter` posterior -incluido un
`format` personalizado- trabaje ya sobre el texto limpio. Los datos de excepcion
se redactan aparte, porque un traceback puede arrastrar el valor de una variable
local hasta el log.

**Que no toca.** Rutas de fichero, identificadores de ejecucion y mensajes
normales no se alteran: el filtro solo sustituye lo que reconoce como secreto. Un
sistema que enmascara de mas deja de servir para diagnosticar.
"""

from __future__ import annotations

import logging

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
            # Un fallo de formato no debe dejar que Formatter emita despues el
            # traceback original sin sanear. Este registro ya fue suprimido.
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        return True

    @staticmethod
    def _limpiar(record: logging.LogRecord) -> None:
        # 1. Mensaje formateado con sus argumentos. Redactar el mensaje ya
        #    construido es lo que cubre `log.info("clave=%s", api_key)`.
        # Resolver el formato antes de eliminar args conserva %d, %f y mappings.
        # Convertir los argumentos a strings rompia esos formatos, incluso cuando
        # no habia secretos. Si el formato falla, filter suprime el registro.
        record.msg = redact(record.getMessage())
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


def install_redacting_filter(
    logger: logging.Logger | None = None,
    *,
    level: int | None = None,
) -> RedactingFilter:
    """Protege los handlers existentes de `logger` y sus descendientes.

    Por defecto cubre todos los loggers, incluidos los que no propagan al root.
    Tambien cubre los handlers de ancestros a los que propaga un logger concreto.
    No crea handlers ni cambia destinos, niveles o propagacion. Repetir despues
    de cambiar la configuracion conecta los handlers nuevos sin duplicar filtros.
    Se conserva el filtro del logger para compatibilidad con llamadas directas.
    """
    destino = logger if logger is not None else logging.getLogger()
    filtro = next((f for f in destino.filters if isinstance(f, RedactingFilter)), None)
    if filtro is None:
        filtro = RedactingFilter()
        destino.addFilter(filtro)

    manejadores = set(destino.handlers)
    for candidato in logging.root.manager.loggerDict.copy().values():
        if isinstance(candidato, logging.Logger) and (
            destino is logging.root or candidato.name.startswith(destino.name + ".")
        ):
            manejadores.update(candidato.handlers)
    ancestro = destino
    while ancestro.propagate and ancestro.parent is not None:
        ancestro = ancestro.parent
        manejadores.update(ancestro.handlers)
    if logging.lastResort is not None:
        manejadores.add(logging.lastResort)
    for manejador in manejadores:
        if not any(isinstance(f, RedactingFilter) for f in manejador.filters):
            manejador.addFilter(filtro)

    setattr(filtro, _FILTRO_MARCA, True)
    if level is not None:
        destino.setLevel(level)
    return filtro
