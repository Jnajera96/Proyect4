"""Proyecto 4 - AI Software Engineering System.

Sistema multiagente para tareas de ingenieria de software sobre un repositorio
autorizado. Documentacion en `docs/`; indice unico en `docs/README.md`.

Estado de la implementacion: **fases M0, M1 y F1-F14 completadas y verificadas**.
La cadena funcional esta cerrada de extremo a extremo: interpretacion, planificacion,
investigacion, codificacion, sandbox aislado, ejecucion de pruebas reales, revision
con guardas deterministas, dos puertas humanas, promocion al repositorio del usuario,
frontend, STT local y evaluacion experimental.

**Alcance declarado**: prototipo local, un solo usuario, `127.0.0.1`, sin
autenticacion. El sandbox confina la **escritura** del Coder, pero **no aisla el
proceso** de ejecucion. Estado verificado, riesgos abiertos y plan de evolucion:
`docs/audit/00-EXECUTIVE-AUDIT.md`.
"""

__version__ = "0.1.0"
