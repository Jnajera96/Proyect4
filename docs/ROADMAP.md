# Roadmap vigente de cierre y experimentación

Este documento distingue trabajo futuro de capacidades implementadas. Los planes
de `docs/history/` son referencias históricas.

1. **Fase A:** garantías de redacción y estados del frontend. Preservación del
   rediseño en `f095729`; correcciones en `245a4a8`.
2. **Fase B:** experiencia de frontend para entrega sobre endpoints existentes.
   Shell, alcance, errores, voz, evidencia, temas y responsive. Resultado y
   límites de comprobación en `BASELINE-FRONTEND-DELIVERY.md`.
3. **Fase C — ejecutada:** candidato local verificado, tres defectos corregidos,
   690 pruebas Python aprobadas y tres omitidas; navegador y promoción con checkpoint
   real verificados. Alcance, evidencia y límites en `RELEASE-CANDIDATE-PHASE-C.md`.
4. **Jupyter / Hugging Face Agent Model Lab — PLANNED:** laboratorio externo con
   Inference Providers o GPU cloud y modelos del Hub. Descubrimiento de modelos y
   proveedores, pruebas reproducibles de structured output/tool calling/contexto,
   latencia, tokens, coste fiable, errores y fallbacks. Comparación por rol y futura
   exportación JSON de resultados y recomendaciones para ModelGateway. El notebook
   no forma parte del runtime; no hay interfaz ni endpoint de laboratorio todavía.
5. **Posterior a entrega:** evaluar MCP, Graphify/Knowledge Graph y observabilidad
   con criterios de adopción medibles, sin presentar placeholders como funciones.
6. **Antes de producción:** TD-02, TLS, secretos, rate limiting operativo,
   auditoría persistente, aislamiento de ejecución/red/recursos, backups y retención.

El laboratorio no requiere un HuggingFaceAdapter de antemano: primero se comprobará
el adapter OpenAI-compatible existente. No se descargan modelos ni se consume un
proveedor real en la fase de frontend.
