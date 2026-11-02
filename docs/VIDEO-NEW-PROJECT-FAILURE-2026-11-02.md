# Diagnóstico de fallo al generar un proyecto nuevo

Fecha: 2 de noviembre de 2026. Base analizada: `25a8d50`.
Video: captura local de Chrome de las 16:09:49, duración 272,73 segundos.
Corrida correlacionada por hora y eventos: `run-7d570f7bf382`, creada a las
16:10:43 y terminada a las 16:14:15 (America/Mexico_City).

## Resultado

**Defecto P0 reproducido en el motor de parches.** El Coder sí respondió;
la credencial, el presupuesto y la selección de repositorio no son el bloqueo
observado en esta corrida. Esto no acredita calidad general del modelo.

Se generan tres archivos y se ejecutan tres rondas de Coder/pruebas/Reviewer.
Hay seis solicitudes y seis respuestas de modelo registradas. Pytest falla con
salida 2 y Ruff con salida 1 en las tres rondas. El Reviewer pide correcciones y
finalmente escala; aprobación y promoción no se completan.

## Evidencia observada

| Momento aproximado del video | Observación |
| --- | --- |
| 00:48–01:12 | Petición de calculadora científica, propuesta de requisitos y confirmación humana. |
| 01:24–01:48 | Coder activo; los objetivos de pruebas todavía no terminan. |
| 02:12 | Tres archivos en sandbox; pruebas 0/2 y Reviewer activo. |
| 02:48 | Seguridad muestra «Sin errores registrados» durante el ciclo correctivo. |
| 04:12 | Inspector muestra propuesta y diff de calculator.py/index.html. |
| 04:30 | Estado requiere intervención; Reviewer declara escalate y no se promociona. |

Las capturas posteriores aportadas por el usuario muestran los eventos
49/51 y 68/70, que coinciden exactamente con la evidencia SQLite leída en modo
inmutable de sólo lectura. No se abrió ninguna bóveda ni se usaron credenciales.

La primera ronda registra:

```text
calculator.py:46
return math.tan(a)--- /dev/null
SyntaxError: invalid syntax
```

Ruff también detecta `math` no definido en los tests de la primera propuesta.
Ese error desaparece en rondas posteriores, pero queda el encabezado de diff
pegado al código. En la segunda ronda ocurre además en test_calculator.py:88;
en la tercera, en test_calculator.py:90. No es una conjetura sobre red o permisos:
son las salidas literales de las herramientas guardadas por el servidor.

## Causa raíz verificada

1. `graph/nodes.py::_diff_unificado` usa `difflib.unified_diff` sobre líneas con
   `keepends=True`. Si el contenido no termina en salto de línea, el diff tampoco.
2. `_cambio_desde_propuesta` concatena los bloques con `"".join(trozos_dif)`.
   El encabezado del archivo siguiente queda pegado a la última línea de código.
3. `tools/patcher.py::_contenido_de` reconstruye archivos a partir de líneas `+`.
   Trata el encabezado pegado como contenido y añade un salto final por su cuenta.
4. Se pierde la igualdad entre `FileProposal.new_content`, los archivos escritos
   y sus hashes declarados. El defecto se repite aunque el modelo repare su propuesta.

La reproducción sintética offline usa tres archivos sin salto final. Los dos
archivos Python son válidos antes de la transformación; después, calculator.py
contiene `return math.tan(a)--- /dev/null` y falla `ast.parse`. Los tres archivos
reconstruidos difieren de los bytes originales. No se ejecutó código generado.

El SHA-256 de nodes.py instalado coincide con el del repositorio:
`8a079f20b6524ab4a26ee974cb2625d11e0a3795d924f53b0772ea31f159572a`.
La evidencia técnica local conserva el hash y la reproducción en
`_tmp/video-review-20261102/reproduction.json` y el resultado de la consulta.

## Corrección necesaria

- Separar correctamente bloques y representar explícitamente fin de archivo sin
  salto en el diff; no basta con pedir al modelo «añade una línea vacía».
- Preservar exactamente el contenido de la propuesta al aplicar y verificar su
  SHA-256 antes de ejecutar pruebas. No normalizar bytes silenciosamente.
- Probar creación/modificación/borrado, archivos vacíos, varios archivos,
  contenido con/sin salto final y parches con contexto. El parser actual sólo
  reconstruye líneas añadidas: no debe confundirse con un aplicador general.
- Añadir un E2E offline de propuesta multiarchivo válida hasta sandbox/pruebas,
  con comparación de bytes/hashes, sin gastar tokens para reparar corrupción local.

## Diagnóstico en la interfaz

`VistaSeguridad` pasa únicamente `estado.errors` a PanelErrores. Los resultados
no verdes viven en `evidence.test_runs`; un fallo de pruebas no se registra siempre
como error del motor. Por eso «Sin errores registrados» puede aparecer durante
un ciclo correctivo, aun con pytest/Ruff fallidos. Se necesita aclarar esa separación
y enlazar a las pruebas vigentes, sin declarar exitosos los objetivos fallidos.

## Alcance de esta intervención

Sólo análisis, consultas de lectura y reproducción sintética. No se cambiaron
la calculadora, el repositorio del usuario, la base de datos, la configuración,
los agentes ni el portable rc24. No se lanzó ninguna inferencia ni publicación.
La corrección de producto y su nuevo candidato de entrega siguen pendientes.
El smoke de rc24 no cubría esta combinación de contenido sin salto y multiarchivo;
no constituye evidencia de que toda aplicación generada por un modelo funcione.
