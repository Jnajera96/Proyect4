# Memoria asociativa: medición offline y límites

Fecha: 30 de octubre de 2026. Base: `e299ed6`.

## Método reproducible

`tools/benchmark_context_memory.py` genera cuatro repositorios sintéticos con
24 archivos cada uno. Ejecuta Researcher y construye la solicitud real del Coder
con FakeModelAdapter: tres brazos por tarea, doce solicitudes locales en total.
No ejecuta el código de los fixtures, no escribe propuestas en repositorios
reales, no publica y no consulta proveedores externos.

Los brazos son: control con inventario ordenado y límite normal de 20 archivos,
selección léxica de ocho archivos y selección asociativa de ocho con historial de
coedición sintético. Cada brazo tiene SQLite independiente. El control es una
ablación acotada del benchmark, no una nueva opción de producción.

La cobertura se mide contra dos archivos requeridos por cada fixture. No mide
calidad del código generado: las respuestas del modelo son falsas a propósito.
Se capturan bytes UTF-8 de mensajes, bytes del ModelRequest y su hash. Las unidades
conservadoras son bytes del request más 1024, siguiendo la reserva local del
gateway; no son tokens del modelo ni cargos.

Comando (elegir una ruta de informe nueva):

```powershell
.venv/Scripts/python.exe tools/benchmark_context_memory.py --output _tmp/context-memory-nuevo/report.json
```

Evidencia de esta ejecución: `_tmp/context-memory-benchmark/report.json`.

## Resultados

| Petición del fixture | Control: archivos / cobertura | Asociativo: archivos / cobertura | Bytes de mensajes antes → después | Reducción |
| --- | --- | --- | --- | --- |
| calculator.py explícito | 20 / 0 % | 8 / 100 % | 9658 → 8081 | 16,33 % |
| calendar.py explícito | 20 / 0 % | 8 / 100 % | 9654 → 8073 | 16,38 % |
| calories.py explícito | 20 / 0 % | 8 / 100 % | 9654 → 8073 | 16,38 % |
| Petición sin coincidencias de rutas | 20 / 0 % | 20 / 0 % | 9664 → 9664 | 0 % |

La selección léxica conserva solo uno de los dos archivos requeridos (50 %) en
los tres casos con ancla; la asociación recupera también su archivo de pruebas.
La cobertura mejora aunque sus mensajes sean unos bytes mayores que los del
brazo léxico. Los archivos relevantes se colocan deliberadamente después del
ruido al ordenar: es una prueba controlada, no una muestra de proyectos reales.

Pasar de 20 a 8 archivos reduce ese conteo un 60 %, pero el prompt completo solo
baja alrededor de un 16 % por su contenido fijo. No hay tokenizer verificado del
modelo remoto en esta medición. **No se demuestra un ahorro del 50–70 % de tokens
facturados**, ni una mejora general de calidad, coste final o latencia.

## Defectos reproducidos y corregidos

1. Sin coincidencias, select devolvía ocho archivos por orden alfabético como si
   fueran relevantes. Ahora no poda sin anclas; Researcher conserva el límite
   normal de 20 y sus avisos. La petición ambigua sigue sin recuperar los dos
   archivos del fixture: no se oculta esa limitación.
2. select conservaba todos los archivos explícitos, pero Researcher y el contexto
   del Coder estaban limitados a 20. Pedir 24 perdía archivos silenciosamente.
   Ahora Researcher termina en needs_human con CONTEXT_SCOPE_TOO_LARGE e indica
   dividir la tarea antes de gastar en el Coder. Aplica a archivos del inventario
   autorizado; no elimina los límites de tamaño, extensiones e inventario.
3. El benchmark reprodujo WinError 32 al limpiar SQLite. El contexto sqlite3
   confirmaba transacciones pero no cerraba las conexiones. Se usa cierre
   determinista manteniendo commit/rollback. Una regresión retiene referencias a
   las conexiones y verifica que todas están realmente cerradas.

## Verificación y continuidad

48 pruebas focalizadas PASS: benchmark, memoria, planificación, constructor y
continuidad. Informe `_tmp/context-memory-regression.xml`. Ruff de memoria,
benchmark y pruebas aprobado. Regresión completa: **986 PASS, 4 SKIP, 0 fallos**,
353,91 s, `_tmp/context-memory-full.xml`.
No cambian API, interfaz, dependencias ni esquemas SQLite.

Pendiente detectado en esta medición original: FTS5 llenaba RunState.historical_context,
pero este campo no se incorporaba al prompt del Coder. La medición anterior
solo acredita coocurrencia de archivos, no consumo de historial por el modelo.
Actualización posterior: integración cerrada con redacción y bloque total de
800 caracteres / tres entradas; `RC8-SHUTDOWN-FTS-CLOSURE.md`. La medición de bytes
anterior no acredita ahorro al añadir ese historial.
Después se deben evaluar consultas sin rutas, más repositorios, tokenizer del
modelo correcto y calidad de propuestas. La publicación real sigue pendiente.

## Estado de distribución

Los cinco casos de memoria pasan con CPython y módulos de rc8, pero **rc8 no se
aprueba**: el smoke estándar agotó dos veces el plazo de cierre. Las repeticiones
con instrumentación pasaron, incluida una con temporizador de 90 s, sin identificar
la causa de la diferencia. Informes y trazas en el acta operativa. Se mantiene rc7
como entrega verificada; no se presenta el timeout como corregido por cerrar SQLite.

## Punto 2 — Búsqueda por contenido y código existente (2026-10-30)

`select()` suma coincidencias de contenido a las de ruta y usa ambas como semillas
para las asociaciones del mismo usuario/repositorio. Normaliza acentos y separa
identificadores; no usa un diccionario cerrado de productos. Lee hasta 32 KiB por
archivo y hasta 2.000 candidatos, rechazando rutas externas, traversal, archivos
ignorados y contenido con NUL. Conserva la selección explícita y el fallback
conservador cuando no encuentra anclas. No cambia esquemas ni dependencias.

Researcher ordena también los repositorios pequeños y entrega bloques de los cinco
primeros archivos: ventana de hasta 100 líneas alrededor de la coincidencia más
fuerte y hasta 1.800 caracteres incluyendo delimitadores. Esta cota respeta el
contrato Finding.evidence (2.000). Coder recibe hasta cinco bloques únicos bajo
«Código y estructura actual de los archivos relevantes en el repositorio:», con
cota agregada de 10.000 caracteres. Los fragmentos se redactan antes de persistir y
se envuelven como datos no confiables; no amplían permisos ni autorizan ejecución.

### Medición offline actual

Comando: `python tools/benchmark_context_memory.py --output _tmp/content-context-benchmark/report.json`
con `src` y raíz del proyecto en sys.path. FakeModelAdapter, cero llamadas pagadas.
Cada fixture tiene 24 archivos. El baseline conserva las primeras 20 rutas; el
brazo `content_only` usa rutas/contenido sin asociaciones previas; `associative`
añade una observación sintética de coedición entre implementación y prueba.

| Caso | Cobertura sin asociaciones | Cobertura con asociaciones | Bytes de mensajes con asociaciones | Código recibido |
| --- | ---: | ---: | ---: | --- |
| Calculadora | 100% | 100% | 9.187 | Sí |
| Calendario | 100% | 100% | 9.171 | Sí |
| Calorías | 100% | 100% | 9.171 | Sí |
| Citas, sin ruta | 50% | 100% | 9.193 | Sí |
| Tangente, sin ruta | 50% | 100% | 9.206 | Sí |
| Guardar, sin ruta | 50% | 100% | 9.187 | Sí |

La reducción de bytes frente al baseline actual ronda 15,0–15,2%. No equivale a
tokens facturados ni acredita el objetivo de 50–70%. Los mensajes contienen ahora
más código útil; no son comparables directamente con el antiguo extracto de 120
caracteres. La prueba comprueba el cuerpo de función en la solicitud capturada,
no solo presencia de nombres de archivo.

El fixture ambiguo anterior contenía únicamente `value = 1` en todos sus archivos:
no tenía señal semántica recuperable. Se sustituye por funciones sintéticas de
registro de citas, tangente y guardado. Por eso el paso histórico de 0% a 100% no
es una comparación sobre archivos idénticos. La cobertura actual es verificable
sobre este nuevo fixture; falta medir calidad en repositorios reales diversos.
La búsqueda sigue siendo léxica: no infiere sinónimos y no ve coincidencias después
de los primeros 32 KiB. Los bloques son parciales y no garantizan reunir todas las
dependencias necesarias para cualquier tarea.

Distribución: esta mejora corresponde al código fuente; no modifica el ZIP rc8
verificado. La aprobación posterior de rc8 corregido está en
`RC8-SHUTDOWN-FTS-CLOSURE.md`; el apartado histórico anterior describe el rc8 original.

### Cierre de verificación

Regresión final: **993 PASS, 4 SKIP, 0 fallos y 0 errores**, 350,797 s;
informe `_tmp/content-context-project-confirmed.xml` (997 casos). Entorno del
proyecto con CPython oficial 3.13.14; firma del intérprete base verificada como
`Valid`. Frontend: **34 PASS**, `npm run build` aprobado. Ruff focalizado y
`git diff --check` aprobados. Sin llamadas pagadas ni nuevas dependencias.

Se adaptó una aserción antigua que exigía evidencia sin delimitadores para exigir
que el contenido de cada archivo siga presente en los nuevos bloques. Una corrida
intermedia tuvo un fallo de creación de worktree Git en aislamiento de perfiles:
no se reprodujo en el reintento de 18 pruebas ni en la regresión final completa.
No se cambió el sandbox ni se atribuye una causa no demostrada a esa incidencia.
El intento inicial con el runtime portable invocado sin inicializador no encontraba
Ruff; el resultado final corresponde al entorno reproducible del proyecto.


## Tokenización exacta de referencia — 31 de octubre

Nuevo benchmark de 15 archivos: cl100k_base 28,293361% y o200k_base 30,075671%
de reducción de mensajes; solo código 66,208948% y 66,428003%. Se conserva el
código crítico de las tres tareas. Es un fixture nuevo, no una conversión de
las mediciones históricas de bytes a tokens. 1.030 backend PASS/4 SKIP y 34 frontend
PASS/build. Acta y JSON: `MEMORY-TOKEN-SAVINGS-EVIDENCE.md`. Cero llamadas pagadas.
La meta 40–70% global y la facturación de modelos reales continúan sin acreditarse.
