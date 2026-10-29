# Validación real del Coder — 29 de octubre de 2026

## Resultado comprobado

El token actualizado por el usuario permitió llamar a Hugging Face. La ejecución
`run-8d9a765d748c` utilizó Qwen/Qwen2.5-Coder-32B-Instruct por nscale, desde la UI
del portable basado en `06a40bb`. Hubo tres llamadas Coder y tres Reviewer,
nueve ejecuciones de objetivos de pruebas y dos ciclos de corrección.

El Coder generó archivos, las pruebas se ejecutaron y el Reviewer pidió cambios.
La ejecución terminó en `needs_human`, con `REVIEW_CYCLES_EXHAUSTED`, sin aprobación
ni promoción. Esto valida conexión y actividad del flujo, **no un E2E exitoso**
ni disponibilidad para producción. No se forzó un veredicto favorable.

Repositorio descartable creado desde la aplicación:
`_tmp/ui-calculator-e2e-20261029-01`. El repositorio real del usuario no recibió
esta propuesta. Captura local: `_tmp/coder-real-20261029.png`.

## Fallos observados

1. Primera propuesta: faltaba importar `math` en las pruebas; pytest dio cinco
   fallos y cinco éxitos. Ruff detectó imports desordenados y nombres no definidos.
2. Segunda propuesta: devolvió solo el archivo de pruebas. Al reemplazar la
   propuesta anterior desde el commit base desapareció `calculator.py`; pytest
   informó error de colección. La reparación debe devolver la propuesta completa.
3. Tercera propuesta: recuperó ambos archivos, pero persistieron errores en
   pruebas de trigonometría y Ruff. Se agotaron los dos ciclos de revisión.
4. `pytest.integration` devolvió 5 al no existir pruebas seleccionadas por ese
   marcador. No equivale a una prueba aprobada: queda pendiente resolver la
   selección explícita de objetivos según el proyecto, sin fabricar éxitos.
5. Guardar la bóveda desmonta la pantalla principal y pierde selección de
   proyecto/borrador. Se volvió a seleccionar expresamente el repositorio de prueba.
6. El encabezado heredado muestra «sin autenticación» mientras el perfil figura
   autenticado. Pendiente corregir esa inconsistencia visual.

## Cambios realizados en el código fuente

- Clasificación: una restricción negada como «sin dependencias de producción»
  deja de interpretarse automáticamente como una solicitud de despliegue.
  Las acciones afirmativas fuera de alcance siguen rechazándose.
- Instrucciones de reparación: exigir todos los archivos de la propuesta acumulada
  con operaciones relativas al commit base; se explica el efecto de omitirlos.
- Instrucciones Python: separar imports estándar, terceros y locales, y solicitar
  tolerancias relativas y absolutas explícitas para cálculos aproximados.

Verificación focalizada: **54 PASS**, cero fallos/errores/omitidas, en
`test_intent_negations.py`, `test_f3_interpret_analyst.py`,
`test_calculator_pipeline.py` y `test_project_builder_pipeline.py`.
XML local: `_tmp/nova-review-intent-suite.xml`. `git diff --check` correcto.
Son pruebas del motor/contrato; no demuestran que el modelo vaya a obedecer el
prompt. Estos cambios **aún no están incluidos en el portable que está abierto**.

## Presupuesto y antecedentes de la conexión

El usuario autorizó un máximo acumulado de **5 USD**, no cinco adicionales.
Se preservó la reserva anterior de 2.99999104 USD y se reservaron dos bloques de
1 USD, con total conservador reservado 4.99999104 USD. No se liberaron reservas
de consumo incierto ni se abrió un tercer bloque.

- `run-5cef2fa1ff97`: HTTP 401 con el token anterior. Su reserva se conserva;
  no se presume gratuidad por carecer de información de uso.
- `run-7d167f3dd4b9`: presupuesto de perfil insuficiente antes de llamar al modelo.
- Tras la actualización del token y del límite acumulado del perfil a 2 USD
  (máximo por ejecución conservado en 1 USD), se ejecutó `run-8d9a765d748c`.
- Uso reportado de esta última: 18 868 tokens de entrada y 3 925 de salida.
  Con las tarifas declaradas en el perfil: **0.00191708 USD**; la UI muestra
  0.0019. Es un registro calculado con tarifas configuradas, no una factura
  conciliada con Hugging Face. Reservado no significa facturado.

No se inspeccionaron ni incluyeron tokens, contraseñas o bóvedas en este informe.

## Pendiente para cerrar el problema

Empaquetar los cambios, conservar/restaurar correctamente el proyecto al guardar
la bóveda, definir los objetivos aplicables sin tratar ausencia de pruebas como
éxito y repetir una corrida real dentro del saldo verificado del bloque ya
autorizado. Exigir pruebas verdes, revisión favorable y promoción comprobada
solo en el repositorio descartable antes de declarar el cierre funcional.

La comparación con Nova está en `NOVA-COMPARATIVE-REVIEW.md`; su código se revisó
estáticamente, sin instalarlo ni ejecutarlo.
