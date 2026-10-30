# Adaptación operativa de patrones Nova

Base: `9fe10cb`, rama `feature/v0.2.0-madre-continuity`.
Alcance autorizado: preparación integral, recuperación SSE y cancelación verificable.
Se conservan LangGraph, contratos, worktrees y ambas puertas humanas.

- [x] Preparación: GET autenticado por proyecto, Git/raíz/HEAD, configuración por rol
  y saldo local; sin red. Inicialización explícita de commit vacío sin stage de archivos.
- [x] UI: impedir ejecutar mientras la comprobación falla y ofrecer acciones guiadas;
  volver a comprobar justo antes de crear la ejecución.
- [x] SSE: detectar huecos y duplicados, consultar snapshot autoritativo sin acciones,
  controlar carreras al cambiar de ejecución y mostrar errores de recuperación.
- [x] Cancelación: señal por ejecución, frontera de nodo/antes del despacho HTTP, respuesta solicitada
  distinta de terminada; impedir promoción posterior, preservar archivos promovidos.
- [x] Limpiar solo el worktree propio no promovido y comprobar el resultado.
- [x] Ledger: marcar despacho y liberar solo reservas demostrablemente no enviadas;
  conservar consumo declarado y reservas de resultado incierto.
- [x] Pruebas offline de concurrencia/cancelación, Git descartable, perfiles, SSE,
  regresión completa y frontend/build. Sin inferencia ni red real.

La prueba de API que exige `501` se actualizará al contrato de cancelación real;
no se eliminarán garantías previas ni se relajarán controles para lograr pruebas verdes.
Una cancelación no garantiza que el proveedor remoto haya dejado de facturar.
