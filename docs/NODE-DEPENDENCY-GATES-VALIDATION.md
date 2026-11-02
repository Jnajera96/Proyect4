# Bloqueo de dependencias npm en Coder y pruebas

Fecha: 2 de noviembre de 2026. Base: `a5e7e7e`.

La base ya integra `detect_node_dependencies` y `node_dependency_issues` en
`coder` y `run_tests` (el ejecutor de pruebas de este repositorio). Ambos usan
el inventario del repositorio y, en Coder, la propuesta superpuesta.

Se reprodujeron tres fallos antes de corregir: la política aceptaba una lista
permitida vacía, Coder dejaba pasar el paquete y el runner llegaba a intentar
ejecutar herramientas. La condición `if allowed` omitía la autorización.
Además, la política sólo recorría imports, excluyendo paquetes declarados sin
un import visible.

## Corrección

- Una lista `allowed_packages` vacía autoriza cero paquetes npm externos.
- Se comprueba la unión de paquetes importados y declarados en package.json.
- Los imports externos deben estar declarados; la declaración no concede permiso.
- Ante incumplimiento, los dos nodos escalan a `needs_human` con
  `DEPENDENCY_UNAVAILABLE`, no recuperable y `next_step=None`.
- Coder conserva propuesta y presupuesto; el ejecutor no inicia targets.
- No se añaden reintentos, instalaciones, llamadas remotas ni ejecución Node.

La corrección se hace una vez en la política compartida, sin duplicar lógica
ni renombrar nodos. La autorización no sustituye comprobación de runtime,
versiones ni disponibilidad real de dependencias offline.

## Verificación offline

- Detección, política, dependencias Python, Coder, runner y construcción:
  **150 PASS / 2 SKIP**. Las omisiones son las dos pruebas Docker opt-in de
  dependencias: no se configuró imagen para esta ejecución focalizada.
- Detección e integración Node: **17 PASS** (incluye pruebas compartidas con
  el conjunto anterior; no sumar como casos distintos).
- Se cubren, para cada nodo: lista vacía, lista que excluye el paquete y
  paquete autorizado sin declaración. La llamada a herramientas falla la prueba
  si llega a ocurrir. La propuesta del Coder se obtiene una sola vez.
- La integración existente usa FakeModelAdapter; no hay llamadas pagadas.
- Ruff de la política aprobado; no se introduce deuda nueva en las pruebas.

Resultados de ejecución: `_tmp/node-gate-repro.xml`,
`_tmp/node-gate-fixed.xml` y `_tmp/node-gate-integration.xml`.
No se ejecutó nuevamente la suite completa ni se recompiló el portable:
rc23 conserva las fuentes de su acta y no incluye esta corrección.
