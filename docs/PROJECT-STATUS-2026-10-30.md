# Estado hacia la entrega funcional y adopción de patrones

Fecha: 30 de octubre de 2026. Evaluación del código fuente de
`feature/v0.2.0-madre-continuity`, conservando la distribución anterior.
Última validación fuente: backend962 PASS/4 SKIP, frontend32 PASS y compilación
TypeScript/Vite aprobada; sin nuevas inferencias pagadas.

## Avance estimado

**77/100 hacia v0.2.0 Windows local, confiable y recuperable.** Es una estimación
técnica ponderada (76,65 redondeado), no una métrica derivada del número de pruebas.
No significa que una plataforma pública de producción esté aprobada al 77 %.

Se conserva el método del acta `OPERATIONAL-STATUS-2026-10-29.md` (74,75, redondeado
a 75). Las mejoras de requisitos, UX y memoria aumentan su estimación; no se otorga
avance adicional a distribución, voz en destino ni continuidad sin nuevas evidencias.

| Objetivo | Peso | Estimación actual | Cierre pendiente |
| --- | ---: | ---: | --- |
| Perfiles y bóveda | 15 % | 95 | Recuperación/actualización en otro equipo. |
| Agentes y promoción | 30 % | 88 | Otros productos con modelos reales y revisión independiente de calidad. |
| UI, actividad y proyectos | 10 % | 95 | Empaquetar la UX actual y cerrar comprobación previa integral. |
| Voz | 5 % | 90 | Micrófono/audio en el equipo de destino. |
| Memoria, modos y rollback | 10 % | 85 | Recuperación integral independiente y medición de contexto. |
| Continuidad y respaldo | 15 % | 45 | Integración/validación completa de importación, auto-backup y recuperación. |
| Distribución y operación segura | 15 % | 45 | Nuevo paquete, otra PC/VM, actualizaciones y aislamiento de ejecución. |

## Qué se adoptó de MADRE

Conceptos adaptados a nuestra arquitectura, no sustitución de LangGraph:

- Preflight de configuración/proveedores sin inferencia: `preflight.py` y
  `models/providers/diagnostics.py`. Acta: `PREFLIGHT-PROVIDERS.md`.
- Modos `INSPECT_ONLY`, `PLAN_ONLY` y `FULL_PROPOSAL` impuestos en el grafo.
- Memoria contextual SQLite FTS5 por usuario/repositorio (`state/memory.py`) y
  consulta histórica en el contexto de trabajo.
- Recibos y reversión de promoción acotada a los archivos aprobados
  (`tools/rollback.py`), con acción en la UI, sin reset destructivo global.
- Auditoría de propuesta de Coder frente a veredicto de Reviewer y pruebas.
- En la evolución asociada K/L/M: perfiles/bóveda aislados y base de pausa,
  checkpoints, archivos `.aiswe-vault` y reconstrucción (`state/continuity.py`).
  **Tener estas piezas no acredita recuperación completa de equipo:** su cierre
  integral sigue pendiente.

## Qué existe respecto a Nova

`NOVA-COMPARATIVE-REVIEW.md` registra una revisión estática del repositorio de referencia.
**No se copiaron módulos de Nova ni se incorporó su motor conversacional.** Ya existen
en AI SWE estos patrones coincidentes, algunos implementados antes de la comparación:

- Diagnóstico de repositorio/Git y comprobación específica de HEAD antes de Coder.
- Releer del servidor con estados visibles de carga, éxito y error.
- SSE con cursor y relectura, y actividad basada en eventos del servidor.
- Distinción entre nodo terminado, propuesta producida, prueba y promoción comprobada.
- Timeout y reintentos acotados del gateway, sin agregar un bucle externo de gasto.

La vista previa integral de preparación, reconciliación certificada de huecos SSE
y cancelación cooperativa con confirmación de terminación continúan pendientes.
No deben contarse como incorporaciones completas de Nova.

## Neuromapa se registra por separado

La co-ocurrencia de archivos (`state/memory_graph.py`), selección de contexto y
`max_cost_per_hour` se inspiran en Neuromapa. No se atribuyen a MADRE ni a Nova.
No se ha demostrado ahorro de 50–70 % de tokens facturados.

## Ruta restante

1. Construir el paquete con los cambios actuales y validar desde su runtime firmado.
2. Probar otra PC, configuración de usuario, reinicio y ejecución/promoción.
3. Cerrar recuperación y respaldo de principio a fin entre equipos.
4. Evaluar más productos/modelos y publicación voluntaria con presupuesto explícito.
5. Resolver aislamiento de procesos/red y controles operativos antes de producción pública.

Plan maestro y cola de pendientes: `ROADMAP.md`. Actas fuente:
`INTUITIVE-UX-NEUROMAPA-VALIDATION.md`, `PRODUCT-REQUIREMENTS-VALIDATION.md` y
`UNIVERSAL-REQUIREMENTS-VALIDATION.md`. Los resultados offline no actualizan por sí
solos el ZIP ni el servidor que el usuario tenga abierto.
