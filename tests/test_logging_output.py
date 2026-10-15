"""Regresiones del borde de logging; ejecutable con unittest, sin FastAPI.

Se cargan los dos modulos reales directamente para que estas pruebas de logging
no necesiten importar la API HTTP desde security.__init__. No se sustituye la
redaccion ni el sistema de logging. Todo se captura en memoria.
"""

from __future__ import annotations

import importlib.util
import io
import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


def _cargar(nombre: str, ruta: Path):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_SEGURIDAD = Path(__file__).resolve().parents[1] / "src" / "ai_swe" / "security"
_redaccion = _cargar("_redaccion_salida", _SEGURIDAD / "redaction.py")
with patch.dict(sys.modules, {"ai_swe.security.redaction": _redaccion}):
    _logging = _cargar("_logging_salida", _SEGURIDAD / "logging.py")


class LoggingOutputTests(unittest.TestCase):
    def setUp(self):
        self.secreto = "credencial-sintetica-regresion-2026"
        _redaccion.register_secret(self.secreto)
        self.salida = io.StringIO()
        self.handler = logging.StreamHandler(self.salida)
        self.root = logging.getLogger()
        self.root_handlers = self.root.handlers[:]
        self.root_filters = self.root.filters[:]
        self.root_level = self.root.level
        existentes = [self.root, *(v for v in logging.root.manager.loggerDict.copy().values()
                                    if isinstance(v, logging.Logger))]
        handlers = {h for logger in existentes for h in logger.handlers}
        if logging.lastResort is not None:
            handlers.add(logging.lastResort)
        self.filtros_handlers = [(h, h.filters[:]) for h in handlers]
        self.root.handlers = [self.handler]
        self.root.filters = []
        self.root.setLevel(logging.INFO)
        self.registrados = []

    def tearDown(self):
        self.root.handlers = self.root_handlers
        self.root.filters = self.root_filters
        self.root.setLevel(self.root_level)
        for handler, filters in self.filtros_handlers:
            handler.filters = filters
        for logger, handlers, filters, propagate, level, disabled in self.registrados:
            logger.handlers = handlers
            logger.filters = filters
            logger.propagate = propagate
            logger.setLevel(level)
            logger.disabled = disabled
        _redaccion.clear_registered_secrets()

    def logger(self, nombre, *, propio=False):
        logger = logging.getLogger(nombre)
        self.registrados.append((logger, logger.handlers[:], logger.filters[:],
                                 logger.propagate, logger.level, logger.disabled))
        logger.handlers = [logging.StreamHandler(self.salida)] if propio else []
        logger.filters = []
        logger.propagate = not propio
        logger.disabled = False
        logger.setLevel(logging.INFO)
        return logger

    def comprobar_redaccion(self):
        texto = self.salida.getvalue()
        self.assertTrue(self.secreto not in texto, "la salida contiene el secreto sintetico")
        self.assertTrue("[REDACTED]" in texto, "la salida no contiene redaccion")

    def test_root_redactado(self):
        _logging.install_redacting_filter()
        self.root.info("credencial %s", self.secreto)
        self.comprobar_redaccion()

    def test_hijo_propagado_redactado(self):
        logger = self.logger("regresion.salida.hijo")
        _logging.install_redacting_filter()
        logger.info("credencial %s", self.secreto)
        self.comprobar_redaccion()

    def test_auditoria_propagada_redactada(self):
        logger = self.logger("ai_swe.audit")
        _logging.install_redacting_filter()
        logger.info("credencial %s", self.secreto)
        self.comprobar_redaccion()

    def test_handler_propio_sin_propagacion_redactado(self):
        logger = self.logger("regresion.salida.access", propio=True)
        _logging.install_redacting_filter()
        logger.info("credencial %s", self.secreto)
        self.comprobar_redaccion()

    def test_excepcion_de_hijo_redactada(self):
        logger = self.logger("regresion.salida.excepcion")
        _logging.install_redacting_filter()
        try:
            raise ValueError(self.secreto)
        except ValueError:
            logger.exception("fallo %s", self.secreto)
        self.comprobar_redaccion()
        self.assertIn("ValueError", self.salida.getvalue())

    def test_formato_numerico_y_mapping_sobreviven(self):
        _logging.install_redacting_filter()
        self.root.info("objetivos %d", 3)
        self.root.info("objetivos %(n)d", {"n": 4})
        self.assertEqual(self.salida.getvalue(), "objetivos 3\nobjetivos 4\n")

    def test_reinstalacion_cubre_handler_nuevo_sin_duplicados(self):
        primero = _logging.install_redacting_filter()
        otro = logging.StreamHandler(self.salida)
        self.root.handlers = [otro]
        segundo = _logging.install_redacting_filter()
        self.assertIs(primero, segundo)
        _logging.install_redacting_filter()
        self.assertEqual(sum(isinstance(f, _logging.RedactingFilter) for f in otro.filters), 1)
        self.root.info("credencial %s", self.secreto)
        self.comprobar_redaccion()

    def test_redaccion_repetida_conserva_mensaje(self):
        _logging.install_redacting_filter()
        _logging.install_redacting_filter()
        self.root.info("run-123: %s", self.secreto)
        self.comprobar_redaccion()
        self.assertEqual(self.salida.getvalue(), "run-123: [REDACTED]\n")

    def test_formato_invalido_no_filtra_excepcion(self):
        _logging.install_redacting_filter()
        try:
            raise ValueError(self.secreto)
        except ValueError:
            self.root.error("numero %d", "no-es-numero", exc_info=True)
        self.assertTrue(self.secreto not in self.salida.getvalue(),
                        "el fallback de formato filtro el secreto sintetico")

    def test_handler_de_ultimo_recurso_redactado(self):
        logger = self.logger("regresion.salida.sin_handler", propio=True)
        logger.handlers = []
        with patch.object(logging, "lastResort", self.handler):
            _logging.install_redacting_filter()
            logger.warning("credencial %s", self.secreto)
        self.comprobar_redaccion()

    def test_formato_invalido_en_hijo_no_filtra_traceback(self):
        logger = self.logger("regresion.salida.formato", propio=True)
        _logging.install_redacting_filter()
        try:
            raise ValueError(self.secreto)
        except ValueError:
            logger.error("numero %d", "no-es-numero", exc_info=True)
        self.assertTrue(self.secreto not in self.salida.getvalue(),
                        "el fallback del handler filtro el secreto sintetico")


if __name__ == "__main__":
    unittest.main()
