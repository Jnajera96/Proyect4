# Estado hacia la entrega funcional y adopción de patrones

Fecha: 30 de octubre de 2026. Evaluación del código fuente de
`feature/v0.2.0-madre-continuity`, conservando la distribución anterior.
Última validación fuente: backend990 PASS/4 SKIP, frontend34 PASS y compilación
TypeScript/Vite aprobada; sin nuevas inferencias pagadas.

## Avance estimado

**81/100 hacia v0.2.0 Windows local, confiable y recuperable.** Es una estimación
técnica ponderada (80,90 redondeado), no una métrica derivada del número de pruebas.
No significa que una plataforma pública de producción esté aprobada al 81 %.

Se conserva el método del acta `OPERATIONAL-STATUS-2026-10-29.md` (74,75, redondeado
a 75), y la evaluación anterior de 76,65 (77/100). Se actualizan memoria 85→90
por FTS5 efectivamente incluido en Coder y verificación de contexto/cierre SQLite;
continuidad 45→55 por importación desde acceso, múltiples rutas y reintentos
verificados por API; distribución 45→60 por paquete actual y dos smokes estándar
limpios, además del uso en otra PC reportado por el usuario. Siguen pendientes
el piloto integral entre equipos y operación de producción; voz en destino no sube.

| Objetivo | Peso | Estimación actual | Cierre pendiente |
| --- | ---: | ---: | --- |
| Perfiles y bóveda | 15 % | 95 | Recuperación/actualización en otro equipo. |
| Agentes y promoción | 30 % | 88 | Otros productos con modelos reales y revisión independiente de calidad. |
| UI, actividad y proyectos | 10 % | 95 | UX y puertas accionables incluidas en rc8 corregido; validar recorrido en destino. |
| Voz | 5 % | 90 | Micrófono/audio en el equipo de destino. |
| Memoria, modos y rollback | 10 % | 90 | Calidad del historial, consultas sin anclas y tokens reales; no hay ahorro facturado certificado. |
| Continuidad y respaldo | 15 % | 55 | Recuperación por UI entre dos equipos, auto-backup, conflictos y pérdida de equipo. |
| Distribución y operación segura | 15 % | 60 | Matriz independiente Windows/SAC, actualización/migración e aislamiento fuerte. |

## Qué se adoptó de MADRE

Conceptos adaptados a nuestra arquitectura, no sustitución de LangGraph:

- Preflight de configuración/proveedores sin inferencia: `preflight.py` y
  `models/providers/diagnostics.py`. Acta: `PREFLIGHT-PROVIDERS.md`.
- Modos `INSPECT_ONLY`, `PLAN_ONLY` y `FULL_PROPOSAL` impuestos en el grafo.
- Memoria contextual SQLite FTS5 por usuario/repositorio (`state/memory.py`) y
  consulta histórica en el contexto de trabajo.
  Ya llega al prompt del Coder: máximo tres entradas, 800 caracteres totales,
  redacción de secretos y bloque no confiable. Aislamiento comprobado con FTS5
  real y solicitud capturada por FakeModelAdapter; calidad con modelo real pendiente.
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

Actualización operativa: ya se implementan preparación integral, reconciliación de
huecos SSE por snapshot y cancelación cooperativa con recibo de parada, según
`NOVA-OPERATIONAL-VALIDATION.md`. No se copian módulos de Nova ni se fuerza el corte
de un HTTP activo. El paquete actualizado rc3 ya se verificó; la validación en
destino sigue pendiente. El seguimiento de continuidad y el arreglo de carga de
respaldos constan en `CONTINUITY-FOLLOWUP-2026-10-30.md`.

## Neuromapa se registra por separado

La co-ocurrencia de archivos (`state/memory_graph.py`), selección de contexto y
`max_cost_per_hour` se inspiran en Neuromapa. No se atribuyen a MADRE ni a Nova.
No se ha demostrado ahorro de 50–70 % de tokens facturados.
La medición `CONTEXT-MEMORY-MEASUREMENT.md` obtiene ~16 % menos bytes de mensajes
en tres fixtures con anclas y 0 % sin ellas, sin tokenizer ni cargos reales.

## Ruta restante

1. Paquete rc3 construido y verificado; rc4 incorpora el arreglo de carga de respaldos.
2. Completar la matriz de otra PC tras la confirmación de funcionamiento del usuario: versión, reinicio, voz y promoción.
3. Cerrar recuperación y respaldo de principio a fin entre equipos; acceso de restauración y múltiples rutas implementados, falta piloto integral por UI.
4. Evaluar más productos/modelos y publicación voluntaria con presupuesto explícito.
5. Resolver aislamiento de procesos/red y controles operativos antes de producción pública.

Plan maestro y cola de pendientes: `ROADMAP.md`. Actas fuente:
`INTUITIVE-UX-NEUROMAPA-VALIDATION.md`, `PRODUCT-REQUIREMENTS-VALIDATION.md` y
`UNIVERSAL-REQUIREMENTS-VALIDATION.md`. Los resultados offline no actualizan por sí
solos el ZIP ni el servidor que el usuario tenga abierto.
