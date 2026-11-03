# Conciliación del README público y pendientes vigentes

Fecha: 2 de noviembre de 2026. Fuente pública revisada por solicitud del usuario:
[README de main](https://github.com/Jnajera96/Proyect4/blob/main/README.md).
Se contrastó con fuente local `f2554d2` y las actas de rc25; no se hizo fetch,
push ni inferencia. La lectura web documental fue autorizada después del encargo
offline de empaquetado y no aportó archivos al build. No se atribuye un hash de
commit remoto que la página consultada no permitió verificar.

## Matriz de conciliación

| Tema del README | Estado contrastado | Acción en el plan |
| --- | --- | --- |
| Autenticación pendiente | Perfiles, bóveda, cookies/CSRF, recuperación y frontera HTTP implementados y probados localmente. | Corregir la documentación histórica; no implementar otro login. Mantener validación física y de seguridad integral pendiente. |
| Cancelación con 501 | La ruta llama request_cancel y devuelve estado/recibo cooperativo; hay pruebas de limpieza y reservas. | Marcar implementada en el alcance documentado; no prometer detención instantánea ni devolución de consumo remoto. |
| Sin límites de proceso | Windows Job impone recursos; Docker opt-in proporciona aislamiento de ejecución/red. | Mantener explícito qué runner está activo y validar destino. Worktree por sí solo no aísla procesos. |
| Cinco ajustes inactivos | Allowlist de repositorios y presupuestos tienen consumidores y pruebas. El campo network_egress_enabled sigue sólo declarado. | Separar variables: no cerrar el grupo por una afirmación genérica. P0: reconciliar el contrato de egreso con el backend real. |
| Modelos nunca probados | Hay actas de modelo real y la captura diagnosticada registra respuestas remotas. | Pendiente calidad/E2E de productos representativos con rc25, presupuesto y aprobación; no repetir la afirmación histórica. |
| Observabilidad ausente | Hay logs, auditoría, presupuesto y medición local de tokens; Langfuse no está integrado. | Separar observabilidad local de integración externa; Langfuse queda posterior y sujeto a alcance. |
| MCP pendiente | No hay integración runtime acreditada. | Línea futura, con casos y aceptación antes de implementar; no bloquea automáticamente el MVP Windows acordado. |
| Graphify/Knowledge Graph propuesto | FTS5 y co-ocurrencia implementan memoria local; no equivalen al producto Graphify ni a una vista Knowledge Graph. | Mantener propuesta posterior, condicionada a beneficio medido; no renombrar la memoria existente como integración terminada. |
| TTS opcional | No hay adaptador TTS; el ajuste está marcado como no implementado. | Funcionalidad futura, no exigir para entrada por voz STT ni tratar el flag como operable. |
| Versiones, cifras y arranque | El texto mezcla varias auditorías previas y la entrega v0.1.0. Rc25 es el candidato local actual. | Añadir estado vigente al README, conservar historia y enlazar actas; revisar índices/snapshot generados por separado. |

## Pendiente de red confirmado en código

`network_egress_enabled` sólo aparece declarado en config.py. El valor falso no
constituye una barrera de red del runner nativo. Docker limita red mediante su
propia política `--network none`, independientemente de ese campo. No se afirma
que falte todo aislamiento ni que el indicador por sí solo lo provea.

Criterio de cierre: configuración y API deben describir fielmente la política del
runner seleccionado; un test negativo debe demostrar rechazo de egreso cuando
se declara bloqueo. Hasta entonces, no inferir aislamiento de red por ese flag.
Esta revisión documenta el defecto de contrato; no cambia su implementación.

## Orden recomendado y autorizaciones

1. Mantener rc25 como candidato local y probar el recorrido completo de creación
   y modificación antes de sumar funciones. La reparación de EOF ya se verifica
   offline en el paquete; faltan calidad e interacción reales con productos distintos.
2. Cerrar contrato de red y disponibilidad Node mediante comprobaciones negativas,
   sin ejecutar npm install ni proyectos evaluados en el host.
3. Revalidar respaldo ante concurrencia/renovación de credenciales y cerrar la
   matriz física Windows, micrófono y recuperación, al reactivar esos pilotos.
4. Reactivar por decisión explícita los pilotos de continuidad y publicación del
   asistente GitHub. El remoto del propio proyecto no los sustituye.
5. Autorizar por separado evaluación real de modelos, con límite de coste,
   tokenizer correcto y medición de calidad/consumo en repositorios reales.
6. Tratar MCP, Langfuse, Graphify/Knowledge Graph y TTS como evolución posterior,
   con decisión de alcance; TLS/retención y operación pública son otro cierre.

Avance informado: 91/100 estimado; no certificado ni recalculado por contar tests.
No hay base para anunciar 100 % mientras falten criterios obligatorios del plan.
El README se actualiza localmente. El público no cambiará sin autorización de push.
