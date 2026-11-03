"""Trazas locales SQLite, tokenizer offline y exportación OTLP voluntaria.

La traza primaria sobrevive a fallos de Langfuse. Las exportaciones contienen
metadatos, tokens y costes disponibles; excluyen prompts, respuestas y código.
"""
