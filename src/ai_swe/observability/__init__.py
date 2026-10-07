"""Observabilidad: trazas, metricas y redaccion de secretos.

Pendiente: fase M6.

Decision de diseno: la observabilidad **no** depende de un servicio externo para
ser correcta. Los registros JSON estructurados son la fuente primaria; Langfuse
es la capa de visualizacion. Si Langfuse cae, la trazabilidad no se pierde.

Se registra: llamadas al modelo (con prompt y respuesta redactados, tokens,
latencia y costo), pasos de agente, llamadas a herramienta (con la decision de
politica aplicada), llamadas MCP, transiciones de estado, aprobaciones humanas y
errores por clase. Todo correlacionado por un unico identificador de traza.
"""
