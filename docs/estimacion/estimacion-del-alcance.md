# Estimación cualitativa del alcance pendiente

## Criterio

La estimación clasifica incertidumbre técnica y dependencias del alcance aprobado.
No es un cronograma, una cotización ni una garantía de coste. No se inventan horas,
presupuestos, velocidad del equipo o fechas. Los datos económicos de un proveedor
solo podrán convertirse en una estimación de consumo con catálogo vigente y límite
autorizado expresamente por el usuario.

| Paquete | Complejidad relativa | Dependencia que condiciona el cierre |
| --- | --- | --- |
| Completar Model Lab | Media | Credencial, autorización de consumo y compatibilidad real |
| Integrar routing por rol | Alta | Modelos seleccionados, esquemas y manejo de fallos |
| Validar STT real | Media | Hardware, modelo, permiso y acceso a micrófono |
| Separar configuración y datos | Media | Decisiones de instalación y rutas Windows |
| Launcher y paquete onedir | Alta | Assets, dependencias nativas y ciclo de vida |
| Instalador y entorno limpio | Alta | Herramienta de instalación y Windows Sandbox o VM |
| Documentación final | Media | Comportamiento y artefactos realmente disponibles |

La clasificación es un juicio técnico preliminar, no una medición cuantitativa.
Debe revisarse al cerrar cada dependencia. Las funcionalidades excluidas de v0.1.0
no se incluyen en este alcance: MCP, Graphify, Knowledge Graph, TTS, multiusuario,
hardening de producción y ticket SSE de un solo uso.
