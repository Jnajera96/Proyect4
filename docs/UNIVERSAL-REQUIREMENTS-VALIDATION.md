# Síntesis generalizada de requisitos

Fecha: 30 de octubre de 2026. Rama: `feature/v0.2.0-madre-continuity`.
Base de trabajo: `d3b144c`, descendiente de `4b4c242` y `ab079d3`.

## Cambio

El prompt de Analyst establece síntesis universal para creación o modificación de
software, sin limitarse a tres productos. Solicita cuatro viñetas en `rationale`:
funcionalidades (3–5 capacidades), validaciones y errores, interfaz y pruebas pytest.
Las reparaciones se describen dentro del cambio solicitado, sin ampliar su alcance.
Se conserva la confianza mínima 0,85 cuando el propósito de modificar es claro,
la revalidación del contrato, el alcance del usuario y la confirmación humana.

La ruta local sustituye `_PRODUCTOS_BASE` por extracción del núcleo nominal y reglas
de familias: gestores/CRUD, conversores/cálculo, temporizadores/planificación y
juegos/interacción. Para nombres no clasificados genera una propuesta paramétrica:
datos y opciones, acción principal, resultado y reinicio. No requiere nuevas
dependencias, embeddings, modelos locales ni peticiones de red.

Las especializaciones existentes de matemáticas, eventos y alimentos se conservan
dentro de sus familias; ya no constituyen la lista de productos admitidos.
El núcleo se extrae de peticiones como «un…», «una…», «quiero un…» o «crea…», y de
vocabulario habitual de herramientas. Se recortan cláusulas accesorias y se limita
el nombre a 160 caracteres. La propuesta se mantiene dentro del contrato de 2000.

Preguntas informativas como «cómo crear…» se clasifican antes de buscar verbos de
modificación. Inspecciones explícitas se conservan, distinguiendo una acción
coordinada como «analiza… y corrige…». Los nombres como «un gestor de listas» no
se interpretan como inspección por coincidencias parciales de vocabulario.
La plantilla local no amplía reparaciones puntuales ni peticiones con exclusiones
explícitas. Estas últimas conservan el texto original y la edición humana.

No cambia el contrato ni hace falta modificar el frontend: la puerta existente
renderiza las cuatro viñetas, permite editarlas y exige confirmación. Ninguna
propuesta, puntuación o sugerencia autoriza por sí sola generar o promover código.

## Evidencia offline

- Pruebas focalizadas de producto y compatibilidad F3: **62 PASS**.
- `tests/test_product_requirements.py`: 34 casos, manteniendo los anteriores y
  añadiendo productos nuevos, familias, núcleo nominal y protección de intención.
- Nueve peticiones adicionales recorren el grafo hasta
  `awaiting_human_requirements_confirmation`, con intención `modify`, confianza
  >=0,85, cuatro viñetas y ninguna llamada al adaptador del Coder.
- Casos: conversor de monedas, temporizador pomodoro, tablero de notas, tres en
  raya, generador de contraseñas, reloj pomodoro, herramienta de clasificación,
  simulador de órbitas y gestor de listas.
- FakeModelAdapter comprueba el prompt y contrato; el E2E previo sigue demostrando
  que las correcciones humanas llegan al Coder y la promoción requiere otra aprobación.
- Frontend: **32 PASS**, build TypeScript/Vite aprobado.
- Suite backend completa: **962 PASS, 4 SKIP, 0 fallos y 0 errores** (966 casos).

Informe de regresión local: `_tmp/universal-requirements-full.xml`.

## Límites

«Universal» describe la regla de síntesis, no una garantía de entender perfectamente
cualquier frase o dominio. La heurística local es conservadora, en español y de
alcance limitado; una familia desconocida recibe una propuesta genérica editable.
No supone conocimiento especializado, tasas de cambio en vivo ni servicios externos.
La puntuación es heurística, no una probabilidad calibrada de calidad del software.

No se hicieron inferencias de pago ni se certificó el comportamiento de un modelo
remoto real. No se generó nuevo ZIP ni se reemplazó la aplicación instalada.
