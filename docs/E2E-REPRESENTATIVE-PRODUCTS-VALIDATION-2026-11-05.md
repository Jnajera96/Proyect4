# Acta conjunta E2E de productos representativos — Día 3

**Ejecución real: 3 de noviembre de 2026, America/Mexico_City.** El nombre `2026-11-05` conserva la fecha planificada solicitada, no una fecha futura de ejecución. Base: `1aebc015dff3028001821696bec6650a886df921`. Worktree: `provider-preflight`, rama `codex/day3-e2e-products`.

## Dictamen

**Aprobado el recorrido E2E local de los dos productos con modelos simulados.** Se demostraron interpretación, confirmación humana, planificación, propuesta, aplicación en worktree, pruebas reales, revisión, aprobación final, promoción y pruebas sobre el repositorio de destino. No se certifica calidad de generación de un LLM real ni preparación global 100/100 de v0.2.0.

Gasto de API **$0.00**: las únicas respuestas de modelos proceden de FakeModelAdapter; no se invocaron servicios remotos, instaladores, descargas ni GitHub. No se hizo push ni se modificaron core, frontend o portables históricos.

**Límite importante del requisito de egress:** el Producto 2 bloquea conexiones/DNS externos de Python dentro de sus procesos pytest, con sonda negativa antes del syscall de conexión; TestClient intercambia HTTP en memoria. No existe firewall de proceso ni captura de toda la red del host. El Producto 1 usa el runner nativo con opt-in, sin instrumentación de red equivalente. Por tanto, el gasto cero y el carácter hermético de los fixtures están acreditados, pero **no se emite una certificación de ausencia absoluta de egress a nivel de sistema durante ambas pruebas**. El worktree confina los cambios de archivos; no es Docker ni una VM.

## Resumen de resultados

| Comprobación | Resultado |
| --- | --- |
| E2E independientes de calculadora y REST (`pytest`) | 2 PASS / 0 FAIL |
| Producto 1, pytest en sandbox | 3 PASS |
| Producto 1, Ruff en sandbox y oráculo matemático | PASS |
| Producto 1, pytest sobre destino promovido | 3 PASS |
| Producto 2, pytest en sandbox | 9 PASS |
| Producto 2, Ruff en sandbox | PASS |
| Producto 2, pytest sobre destino promovido | 9 PASS |
| Producto 2, Ruff sobre destino promovido | PASS |
| Frontend: estados + workspace_diff_scale | 47 PASS / 0 FAIL |
| Interacciones reales Split Diff en Chrome | 5 controles PASS |
| Ruff del nuevo CLI y test E2E | PASS |

Los conteos de tests internos de cada producto están contenidos en los E2E; no se suman como si fueran casos independientes de la suite del motor. No se ejecutó la regresión backend completa ni se reconstruyó el frontend o el portable.

## Producto 1 — Calculadora científica

Se conservó la evidencia original de Antigravity en [E2E-PRODUCT1-CALCULATOR-EVIDENCE.json](E2E-PRODUCT1-CALCULATOR-EVIDENCE.json), y Codex repitió el CLI existente sin editarlo, exportando el recheck a `_tmp/day3-product1-independent/`. Oráculo de seno/coseno/tangente en grados y pytest sobre destino: PASS. El E2E independiente existente también pasó y contrasta los bytes esperados con los SHA-256 promovidos.

- `calculator.py`: `3a47d1e60f0690c3e1a0447123b178a3c5bbce74b92c5d177c861e79c2142d21`.
- `test_calculator.py`: `f860701b9b896ee7572447704b2a39c686b815521c3e6367c5f76e6f39ceed6f`.

Ambos hashes coinciden con la evidencia original y con los archivos del nuevo destino sintético. La evidencia original declaró egress false; ese campo por sí solo no demuestra aislamiento de red del host.

## Producto 2 — Microservicio REST de tareas

Fixture fijo: FastAPI, modelos Pydantic con validación de títulos/campos extra, SQLite parametrizado, CRUD `/tasks` y persistencia local. Puede ejecutarse manualmente con `python task_api.py` en loopback:8080; Uvicorn y las dependencias están declarados y fijados a las versiones ya disponibles. No se ejecutó ese servidor TCP durante la verificación: se usó ASGI TestClient en memoria. No hubo pip/npm install.

Analyst y Supervisor son deterministas. Coder y Reviewer usan un adaptador derivado de FakeModelAdapter que responde con propuesta y ReviewVerdict estructurados, respectivamente: **2 llamadas simuladas**, sin llamadas de facturación. El Reviewer simulado no es una evaluación independiente de calidad; el oráculo funcional son las pruebas HTTP reales y los checks de integridad. No se sustituyeron pytest/Ruff por TestRun fabricados.

Antes de la aprobación final, los cuatro archivos estaban únicamente en el worktree, el repositorio destino conservaba su commit base y no contenía ninguno de ellos. Tras aprobar, RunEngine declaró `completed`, sin errores y con recibo de promoción. Se verificaron bytes y SHA-256 contra CodeChange/propuesta; se volvieron a ejecutar los dos targets sobre el directorio de usuario promovido y se comprobaron de nuevo los hashes.

| Archivo promovido | SHA-256 |
| --- | --- |
| `task_api.py` | `3a585ecd3e4429a930e1185622eba8dcfbb56837e775e45a59aef8803484582e` |
| `test_task_api.py` | `3b697d6d0b098447c79ecd408d5dea3f9dbe93b9fb8e183063dc9ac0f875b526` |
| `conftest.py` | `8b3fb5c7d4c1a7970c8fe7ac4db6d77267fc02d96432f3778426127df6a32a16` |
| `requirements.txt` | `d6125dafe4cc2de85e3497b394893e4f8bf2a2e9b94d03554a37b5702494e375` |

Los 9 casos del producto cubren CRUD, códigos **200/201/404/422**, rechazo de títulos vacíos/espacios/exceso de longitud/campos extra, IDs inválidos, independencia de bases en memoria, persistencia tras reapertura, datos con texto parecido a SQL y bloqueo explícito de una conexión externa de prueba. La sonda usa una dirección TEST-NET y el guard la rechaza antes de conectar. Se permiten sockets loopback de control del event loop.

Duración del CLI definitivo: **12.148 s**. Evidencia completa: [E2E-PRODUCT2-REST-API-EVIDENCE.json](E2E-PRODUCT2-REST-API-EVIDENCE.json), incluidos argv, stdout, dependencias, hashes y límites de aislamiento.

## Auditoría de Split Diff — 25 archivos

Se ejecutaron expresamente `frontend/tests/estados.test.mjs` y `frontend/tests/workspace_diff_scale.test.mjs`: **47 PASS**. El script `npm test` actual solo incluye el primero; no se atribuyen los 47 a ese comando. El ensayo SSR de 25 archivos tardó aproximadamente 27,8 ms (<200 ms), pero su caso llamado “Split Diff” no activa el selector: comprueba conteos del renderizado inicial.

Para cubrir esa brecha se añadió `tools/verify_split_diff_scale.cjs`: monta VisorDiff real con CSS del proyecto, pulsa “Dividido” en Chrome y verifica 25 archivos, 50 filas emparejadas, navegación mediante scroll al último archivo y plegado/expansión. Cero errores de página y cero solicitudes de página externas; las rutas ajenas al servidor loopback se abortan. No se modifica el frontend.

Cinco cambios a modo dividido: **107.8, 18.7, 16.9, 21.8, 13.9 ms**, máximo **107.8 ms**, umbral del ensayo **1000 ms**. Son medidas locales del fixture con doble requestAnimationFrame; no acreditan una comparación de degradación entre tamaños, equipos lentos, FPS sostenidos ni UI empaquetada. [Evidencia del navegador](E2E-SPLIT-DIFF-SCALE-EVIDENCE.json).

## Reproducción

```powershell
.venv\Scripts\python.exe tools/verify_product2_rest_api_e2e.py --output docs
.venv\Scripts\python.exe -m pytest tests/test_calculator_full_e2e.py tests/test_product2_rest_api_e2e.py
node --test frontend/tests/estados.test.mjs frontend/tests/workspace_diff_scale.test.mjs
node tools/verify_split_diff_scale.cjs _tmp/nuevo-directorio-diff
```

El CLI REST exige aserciones habilitadas, utiliza un repositorio Git descartable y temporales cortos independientes, y rechaza una base que cambie durante la ejecución. El test no escribe informes en docs; solo el CLI lo hace. Los repositorios sintéticos quedan en TEMP para inspección; no contienen credenciales reales.

## Pendientes de certificación global

No se probó el arranque real por socket del servicio, Docker/red a nivel OS, modelos reales, despliegue público, autenticación del producto generado ni segunda PC. No se puede extrapolar la prueba a cualquier aplicación o salida de modelo. Para acreditar aislamiento absoluto de Internet, ambos productos deben repetirse bajo una imagen offline que incluya sus dependencias o una barrera de red de proceso verificable, sin rebajar el contrato estricto del runner de producción.
