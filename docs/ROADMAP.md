# Roadmap vigente de cierre y experimentación

## Plan maestro hasta la entrega funcional — actualización del 30 de octubre de 2026

Meta inmediata: entrega Windows local que una persona no técnica pueda configurar,
usar para construir una aplicación, revisar y abrir, con recuperación comprobada.
La producción pública requiere además el último control de seguridad de esta lista.
La validación fuente no equivale a actualizar el portable instalado.

| Orden | Trabajo y estado | Criterio para avanzar |
| --- | --- | --- |
| 1 | **Completado y validado en fuente:** Analyst como Product Manager, especificación base para peticiones breves, revisión editable y chips de inicio rápido. | Confirmación humana obligatoria, confianza de intención clara >=0,85, exclusiones preservadas; backend940 PASS/4 SKIP, frontend32 PASS, build y navegador aprobados. Acta: `PRODUCT-REQUIREMENTS-VALIDATION.md`. |
| 2 | **Pendiente:** empaquetar las mejoras de UX/memoria/requisitos sobre la distribución Python firmada. | ZIP reproducible sin secretos; hashes, smoke, guía de inicio, SQLite, perfiles y promoción comprobados desde el paquete. |
| 3 | **Pendiente:** piloto de instalación/portable en otra PC. | PATH limpio, política Windows activa, configuración de credenciales por el usuario, persistencia/reinicio y recorrido funcional con aprobaciones. Cualquier inferencia pagada exige presupuesto explícito; la entrega actual solo valida offline. |
| 4 | **Pendiente:** cierre de continuidad K/L/M y recuperación. | Exportación/importación cifrada, contraseña/clave de rescate, separación entre usuarios y reconstrucción del trabajo pausado en otro equipo sin pérdida de datos. |
| 5 | **Pendiente:** certificar publicación y medir contexto. | Publicación voluntaria en cuenta de prueba; permisos/errores reales. Comparación reproducible de contexto con/sin memoria, sin presentar reducción de archivos como ahorro de tokens facturados. |
| 6 | **Pendiente antes de producción pública:** aislamiento y operación. | Aislamiento de ejecución/red/recursos, secretos, TLS, límites operativos, auditoría, copias/restauración y política de datos; matriz de release aprobada y límites documentados. |

### Flujo de pendientes de la mejora de requisitos

- [x] Reproducir offline las peticiones concisas que se clasificaban como inspección.
- [x] Proponer bases editables para calculadora, calendario y contador de calorías en la ruta local.
- [x] Actualizar el prompt remoto, sin sustituir permisos ni confirmación humana por confianza.
- [x] Mostrar funciones con viñetas y enviar ajustes al contexto confirmado que recibe Coder.
- [x] Añadir sugerencias que rellenan el compositor sin ejecutar automáticamente.
- [x] Registrar cierre de la regresión completa en el acta y el progreso.
- [ ] Incluir estos cambios en el siguiente paquete y validar en otra PC (filas 2 y 3).

## Antecedentes y líneas posteriores

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
