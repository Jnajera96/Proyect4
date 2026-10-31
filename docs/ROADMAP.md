# Roadmap vigente de cierre y experimentación

## Plan maestro hasta la entrega funcional — actualización del 30 de octubre de 2026

Meta inmediata: entrega Windows local que una persona no técnica pueda configurar,
usar para construir una aplicación, revisar y abrir, con recuperación comprobada.
La producción pública requiere además el último control de seguridad de esta lista.
La validación fuente no equivale a actualizar el portable instalado.
El estado ponderado actual (77/100) y la adopción real de patrones están en
`PROJECT-STATUS-2026-10-30.md`. La generalización del Analyst se verifica en
`UNIVERSAL-REQUIREMENTS-VALIDATION.md`; mantiene las mismas puertas humanas.
La preparación integral, recuperación SSE y cancelación cooperativa adaptadas de
Nova se incorporan en fuente: `NOVA-OPERATIONAL-VALIDATION.md`. Se incluyen en el
pendiente de empaquetado y piloto en otra PC, sin declarar producción aprobada.

| Orden | Trabajo y estado | Criterio para avanzar |
| --- | --- | --- |
| 1 | **Completado y validado en fuente:** Analyst como Product Manager, síntesis por familias/núcleo nominal para productos nuevos, revisión editable y chips de inicio rápido. | Confirmación humana obligatoria, confianza de intención clara >=0,85 y exclusiones preservadas; backend962 PASS/4 SKIP, frontend32 PASS y build aprobado. Actas: `PRODUCT-REQUIREMENTS-VALIDATION.md` y `UNIVERSAL-REQUIREMENTS-VALIDATION.md`. |
| 2 | **Empaquetado rc3:** UX, memoria, requisitos y mejoras operativas sobre CPython firmado. | Acta `OPERATIONAL-STATUS-2026-10-30.md`: ZIP, manifiesto, perfiles y SQLite. La promoción remota histórica de rc2 no se repitió en rc3; piloto independiente en fila 3. |
| 3 | **Uso en otra PC confirmado por el usuario; matriz detallada pendiente.** | Falta identificar versión/hash, Windows y recorrido: protecciones activas, reinicio, voz y promoción. No se infiere recuperación entre equipos. Cualquier inferencia pagada exige presupuesto explícito. |
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
- [x] Incluir estos cambios en el portable rc3 y verificar perfiles/SQLite.
- [ ] Validar en otra PC; guía: `PORTABLE-SECOND-PC-PILOT.md`.

### Seguimiento de continuidad

- [x] Mostrar decisiones humanas en Flujo, enfocar progreso tras Ejecutar y ofrecer continuar desde las demás vistas.

Acta UX: `HUMAN-GATES-INTUITIVE-UX-VALIDATION.md`.

- [x] Prueba local para bibliotecas Python y ficha de decisión postgeneración.
- [x] Incluir la mejora de lanzador en rc5; 14 controles portable aprobados (rc4 se conserva).

Acta de esta mejora: `UNIVERSAL-LOCAL-LAUNCH-VALIDATION.md`.

- [x] Revalidar 17 pruebas de memoria/recuperación en desarrollo y con módulos del portable.
- [x] Reproducir y corregir Base64 incompatible al subir respaldos desde la UI.
- [x] Verificar carga binaria en navegador: 4 controles offline aprobados.
- [ ] Validar de extremo a extremo la recuperación desde la UI en una PC independiente.
- [x] Exponer restauración de perfil desde la pantalla de acceso y validar API/ UI offline.
- [x] Añadir lectura previa y asignación guiada de múltiples repositorios al restaurar un perfil.

Acta: `MULTI-REPOSITORY-RESTORE-VALIDATION.md`. La lectura no crea perfiles ni repositorios.

Evidencia y límites: `CONTINUITY-FOLLOWUP-2026-10-30.md`.
Recuperación desde acceso y reporte de otra PC: `PROFILE-IMPORT-UI-VALIDATION.md`.

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
