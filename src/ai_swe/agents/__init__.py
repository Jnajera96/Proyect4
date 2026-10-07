"""Agentes especializados: Researcher, Coder y Reviewer.

Pendiente: fase M2.

Cada agente escribe **solo** su propio campo de salida en el estado y no se
comunica con los demas por conversacion: la comunicacion es exclusivamente a
traves de campos tipados del Shared State.

Conjuntos de herramientas (matriz completa en docs/01-arquitectura.md, 10.4):
  - Researcher: solo lectura.
  - Coder: lectura + escritura confinada al worktree + run_tests.
  - Reviewer: solo lectura + run_tests. Nunca escribe.
"""
