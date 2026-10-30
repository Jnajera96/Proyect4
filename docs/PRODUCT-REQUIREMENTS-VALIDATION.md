# Requisitos base para peticiones breves

Fecha: 30 de octubre de 2026. Rama: `feature/v0.2.0-madre-continuity`.
Base solicitada `ab079d3`; se continúa desde su descendiente `4b4c242` para conservar
las mejoras de UX, guía y memoria ya integradas. Sin llamadas de pago ni publicación.

## Problema y corrección

La reproducción inicial encontró cinco fallos nuevos: los nombres breves de productos
y «hazme una calculadora científica» acababan como inspección; además, una respuesta
remota válida con confianza 0,5 la conservaba aunque la creación fuera inequívoca.
Cambiar solo el prompt no bastaba: Analyst y Supervisor usan normalmente la ruta
determinista local.

`PROMPT_INTERPRETACION` ahora define Product Manager y Analista de Requisitos, pide
identificar el arquetipo y redactar en `rationale` una propuesta base con funciones,
validaciones/errores, interfaz y pruebas. Distingue propuestas de hechos del usuario
y prohíbe inventar permisos, credenciales o rutas. Mantiene el límite de 2000 caracteres.

La ruta local reconoce peticiones nominales acotadas de calculadora, calendario y
contador de calorías, además de «hazme». Para creaciones sin exclusiones propone:

- Calculadora: operaciones, potencias, raíces, logaritmos y trigonometría con grados/radianes.
- Calendario: vista mensual y gestión/persistencia local de eventos.
- Calorías: registro de alimentos/porciones con calorías aportadas por la persona y totales diarios.

Cada base incluye sus validaciones, una interfaz accesible y pruebas. Las propuestas
son texto revisable, no código preconstruido. Preguntas e inspecciones no se convierten
en creación. Reparaciones puntuales y peticiones con exclusiones explícitas no reciben
una plantilla genérica que amplíe su alcance.

El fallback mantiene 0,9 para modificación. La ruta de modelo aplica mínimo 0,85
cuando coinciden su intención de modificar y la clasificación local de propósito
claro. Esta puntuación sigue siendo una heurística de intención, no una probabilidad
calibrada ni una garantía del programa. No reemplaza las dos aprobaciones humanas,
las rutas autorizadas, el presupuesto ni las pruebas.

## Interfaz y continuidad del requisito

`PuertaRequisitos` presenta viñetas bajo «Características planificadas para tu aplicación».
«Confirmar y construir» envía una aprobación; «Ajustar propuesta» abre el área editable
y conserva las correcciones mediante el contrato existente de confirmación. El texto
corregido pasa a planificación y al contexto de Coder, verificado con FakeModelAdapter.
La aprobación del código y su promoción siguen siendo una decisión posterior.

Los tres chips solicitados rellenan el campo controlado del compositor. No crean
ejecuciones, no llaman a modelos y no sustituyen la selección de carpeta/proyecto.
Los verificadores que usaban etiquetas antiguas se actualizaron; la suite existente
de pruebas frontend se conserva intacta.

## Verificación

- Analyst y compatibilidad F3: 39 PASS antes de añadir el E2E nuevo.
- Pruebas nuevas finales: 12 PASS; incluyen clasificación, no expansión de exclusiones,
  prompt remoto con FakeModelAdapter y recorrido real de grafo hasta aprobación de código.
- Frontend existente: 32 PASS; build TypeScript/Vite aprobado.
- Navegador offline: 12 controles de pipeline dinámico y 11 de entrega/chips aprobados.
  El modo solo planificar no promete construir código en su confirmación.
- Ruff de pruebas nuevas y `git diff --check` aprobados.
- Suite backend completa: **940 PASS, 4 SKIP, 0 fallos y 0 errores** (944 casos).

Evidencia local: `_tmp/product-requirements-full.xml`,
`_tmp/dynamic-pipeline-browser/report.json` y `_tmp/intuitive-browser/report.json`.
Comandos: `.venv/Scripts/python.exe -m pytest -q`, `npm.cmd test`,
`npm.cmd run build`, `node tools/verify_dynamic_pipeline.cjs` y
`node tools/verify_intuitive_delivery.cjs`.

## Límites y siguientes pasos

No se ejecutó inferencia remota real: un adaptador simulado comprueba contratos,
prompts y flujo, no la calidad semántica futura de un proveedor.
La ruta determinista solo incorpora los tres arquetipos indicados; otros productos
conservan su clasificación anterior y el prompt remoto puede proponer su base.
Con exclusiones explícitas se conserva el alcance sin añadir plantilla local;
la persona puede detallar su propuesta en la confirmación.

No se generó ZIP ni se actualizó el servidor abierto. Integrar en el portable,
validar en otra PC, cerrar continuidad y los controles previos a producción forman
parte del plan maestro y la cola de pendientes de `ROADMAP.md`.
