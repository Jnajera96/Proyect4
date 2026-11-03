# Capacidades locales y conexiones opcionales

Ruta aprobada por el usuario el 2 de noviembre de 2026. Base limpia `86ce801`.
Se pausa el nuevo portable y los pilotos; se conservan LangGraph, contratos,
perfiles, puertas humanas, presupuestos y controles de aislamiento existentes.

1. Conciliar el README: autenticación y cancelación ya existen; Windows Job y
   Docker tienen garantías distintas. No describirlos como pendientes genéricos.
2. Observabilidad: reutilizar los eventos SQLite por perfil. Resumen consultable,
   descarga JSON y exportación manual OTLP/HTTP JSON a Langfuse si el administrador
   configura explícitamente destino y claves. Sin prompts, código ni credenciales
   en la exportación. Un error externo no altera ni elimina la traza local.
3. MCP: cliente/servidor propio stdio JSON-RPC, versión acotada 2025-06-18,
   herramientas de lectura de archivos y estado Git. Nada de servidores arbitrarios,
   escritura, shell o instalación. Proceso separado, sin credenciales heredadas,
   plazos y tamaños máximos. Activación explícita para el Researcher.
4. Grafo: proyección local de archivos, símbolos e importaciones Python, con
   procedencia EXTRACTED. Reutilizar selección de memoria asociativa y exponer
   relaciones al usuario; datos del repositorio siempre no confiables. Graphify
   no se instala ni se afirma implementado: se conserva como alternativa evaluada.
5. TTS: lectura voluntaria del resultado en el navegador usando exclusivamente
   voces con localService=true. Sin voz local, se explica indisponibilidad; nunca
   se elige una voz remota en silencio. Reproducir y detener, sin crear ejecuciones.

Validación: pruebas offline de fronteras, aislamiento por perfil, errores,
protocolos y UI, regresión completa y build. Integraciones externas mediante
dobles HTTP; sin gasto de modelos, push, instalaciones ni cambios al ZIP rc25.
La adopción de Graphify, la recepción real en Langfuse y la audición física se
declaran por separado: implementación probada con dobles no equivale a certificación
del servicio ni de todos los equipos Windows.
