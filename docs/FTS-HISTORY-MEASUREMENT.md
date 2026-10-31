# Historial FTS5: entrega y coste de contexto

Fecha: 30 de octubre de 2026. Base: `3100e3c`.

## Alcance

Se amplía `tools/benchmark_context_memory.py` con cuatro repositorios sintéticos
independientes: Python, JavaScript, TypeScript y SQL. Se usan MemoryStore.project,
la búsqueda real del Researcher y el prompt real del Coder. Solo el proveedor se
sustituye por FakeModelAdapter: no hay inferencia ni ejecución de código generado.

Cada caso contiene una lección concreta de una tarea anterior: precisión decimal,
conservación del borrador, cierre del intervalo anterior o transacción de inventario.
Los brazos comparan el mismo estado y código actual, con y sin historical_context.
La ablación sin historial vacía ese campo; no es una opción nueva de producción.

Se añaden documentos señuelo de otro usuario, otro repositorio y la ejecución
actual, además de un token ficticio y un falso delimitador de cierre. La medición
comprueba la solicitud que recibe el adapter, no solo el resultado de la búsqueda.

## Resultados reproducibles

Con el entorno del proyecto, desde su raíz:

```powershell
.venv/Scripts/python.exe -c "import sys;sys.path.insert(0,'.');from tools.benchmark_context_memory import main;main()" --output _tmp/history-context-benchmark-final/report.json
```

Usar una ruta nueva para cada informe; la herramienta no sobrescribe evidencia.
El mismo comando también conserva los seis casos de selección por contenido.

| Lenguaje | Bytes sin historial | Bytes con historial | Aumento | Caracteres del bloque histórico |
| --- | ---: | ---: | ---: | ---: |
| Python | 7.453 | 8.189 | 9,88% | 734 |
| JavaScript | 7.470 | 8.208 | 9,88% | 737 |
| TypeScript | 7.454 | 8.202 | 10,03% | 747 |
| SQL | 7.462 | 8.194 | 9,81% | 730 |

En los cuatro casos:

- La lección completa y el código actual llegan juntos al Coder con historial.
- La lección no aparece en el brazo sin historial.
- No aparecen secretos ficticios ni las marcas privadas de los documentos señuelo.
- El bloque histórico no supera 800 caracteres y el falso cierre queda neutralizado.
- Una búsqueda sin coincidencias devuelve cero documentos.

Las cifras de bytes dependen también de la longitud de las rutas temporales.
El informe conserva los tamaños de mensajes y de solicitud JSON por separado.
No contiene mensajes completos ni datos de perfiles reales.

## Verificación

**30 pruebas PASS, 0 omisiones, 0 fallos**, 37,676 s:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_context_memory_benchmark.py tests/test_memory_graph.py tests/test_coder_historical_context.py tests/test_continuity_l.py tests/test_continuity_m.py --junitxml=_tmp/history-context-regression-final.xml -q
```

Ruff focalizado y diff sin errores. Se usa el entorno reproducible del proyecto,
con CPython oficial 3.13.14 cuya firma base ya se verificó en el cierre anterior.
No cambian runtime, frontend, contratos, dependencias ni esquemas SQLite. Por ello
no se repite la regresión completa ni el build frontend: sus últimos resultados
siguen siendo 993 PASS/4 SKIP y 34 PASS/build, respectivamente, sobre `3100e3c`.
No se actualiza el portable rc8.

## Qué queda pendiente

Esta prueba acredita recuperación, transporte y controles estructurales; no prueba
que un modelo razone mejor, obedezca la lección o resista una inyección semántica.
FakeModelAdapter no puede demostrar calidad de generación.

El historial añade contexto y bytes en estos fixtures. No acredita ahorro de tokens,
coste facturado ni reducción de retrabajo. Siguen pendientes el tokenizer y revisión
exactos del modelo servido, oráculos funcionales en repositorios reales y la
comparación de calidad con/sin historial bajo un presupuesto explícito. No se
descargaron tokenizers, modelos ni dependencias para aparentar ese cierre.
