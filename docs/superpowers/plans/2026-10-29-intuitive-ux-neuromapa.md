# UX intuitiva y memoria asociativa: plan de implementación

**Objetivo:** ejecutar los cinco puntos autorizados sobre `ab079d3`, sin inferencias pagadas.
**Arquitectura:** conservar grafo, perfiles y puertas humanas. Añadir servicios pequeños
para inicio/publicación y un grafo de archivos por propietario/repositorio. El modo
local oculta Git en la experiencia, pero conserva su protección interna.
**Tecnologías:** FastAPI/Pydantic, SQLite, Python estándar, React/TypeScript.

## Restricciones globales

- No modificar ni reducir las suites existentes: 909 backend y 32 frontend deben pasar.
- Cero llamadas de pago; proveedores y GitHub se sustituyen en pruebas offline.
- PAT únicamente en memoria, nunca URL, argumentos de procesos, Git config o logs.
- Sin push sobre el proyecto de desarrollo. Publicación solo por petición del usuario en su proyecto.
- La reducción 50–70% es una meta experimental; informar mediciones, no garantizarla.
- GET de guía será de lectura. Preparar `iniciar.bat` se hará con POST protegido,
  automáticamente desde la ficha completada; nunca sobrescribir un archivo ajeno.
- No afirmar que una biblioteca Python sin punto de entrada es una aplicación ejecutable.

## 1. Memoria y límite horario

- [x] Crear `state/memory_graph.py`: `FileMemoryGraph(database, owner)`, observación
  idempotente por ejecución/repositorio, pesos y selección top-k determinista.
- [x] Integrar selección en Researcher y sus hallazgos para Coder; conservar petición,
  alcance y evidencia de seguridad. Excluir cachés, binarios, locks y rutas externas.
- [x] Añadir `max_cost_per_hour` a configuración/perfil. Comprobar ventana móvil de
  3600 segundos y reservas desconocidas atómicamente en `BudgetLedger.reserve_call`.
- [x] Probar pesos, aislamiento, arranque sin historial, poda, concurrencia y borde horario.

## 2. Guía y publicación

- [x] Crear servicios y rutas de guía: GET consulta; POST prepare idempotente;
  POST launch explícito. Detectar HTML, CLI y FastAPI, sin ejecutar para detectar.
- [x] Restringir a ejecuciones promovidas, rutas registradas, hashes y enlaces seguros;
  preservar `iniciar.bat` existente si no coincide. Usar intérprete incluido cuando exista.
- [x] Crear publicación GitHub aislada: API/repositorio privado por defecto, commit
  de archivos aprobados y push sin fuerza; rechazar origin distinto, secretos y cambios
  ajenos. Credencial temporal por entorno del proceso, sin persistencia ni hooks.
- [x] Probar todas las rutas con repositorios temporales, transporte HTTP y Git simulados.

## 3. Interfaz

- [x] Homologar títulos/etiquetas en sentence case y retirar uppercase visual forzado,
  preservando siglas y marcas. Cambios técnicos quedan en apartados desplegables.
- [x] Añadir selector local/GitHub con creación local sencilla y explicación cotidiana.
- [x] Crear `GuiaEjecucion` y `PublicarGitHubModal`: solo aplicaciones promovidas,
  acciones explícitas y estados de carga/error; PAT olvidado al cerrar/terminar.
- [x] Probar en navegador con fixtures, sin abrir procesos o publicar repositorios reales.

## 4. Integración y entrega

- [x] Regenerar contratos exportados cuando cambien.
- [x] Ejecutar pruebas nuevas focalizadas, suite completa, 32 frontend y `npm run build`.
- [x] Revisar diff de seguridad/compatibilidad; documentar métricas y límites reales.
- [x] Crear commit local de entrega, sin push, indicando qué queda validado offline.

Comandos: `.venv/Scripts/python.exe -m pytest -q`, `npm.cmd test` y
`npm.cmd run build` desde frontend. En este host Python/Chromium requieren ejecución
fuera del sandbox restringido; eso no autoriza inferencia real ni publicación real.
