"""Cliente y servidores MCP.

Pendiente: fase M3.

Dos servidores en el prototipo: sistema de archivos y Git. Se justifica en
docs/01-arquitectura.md, seccion 12.3: MCP se usa **solo** donde cruza un limite
de proceso o de confianza.

Notas de implementacion derivadas de la revision 2026-07-28 del protocolo:
  - La restriccion de rutas NO puede depender de `Roots` (deprecado). Se valida
    cada ruta resolviendola y comprobando que queda dentro del area autorizada.
  - El contexto de traza W3C se propaga en `_meta` para no romper la traza.
"""
