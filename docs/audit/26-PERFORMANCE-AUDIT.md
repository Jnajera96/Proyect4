# 26 — Auditoría de rendimiento y escalabilidad

> Análisis **estático** (no se hicieron pruebas de carga). Commit `065db452`.
> **No se optimiza nada aquí.**

## 1. Puntos calientes identificados

| # | Área | Problema | Impacto | Severidad |
|---|---|---|---|---|
| 1 | **SSE + sondeo** | El frontend abre un `EventSource` **y** sondea `GET /runs/{id}` cada 900 ms mientras la ejecución no es terminal | Dos fuentes de carga por cliente; el sondeo sigue vivo todo el tiempo que dure la ejecución (minutos) | MEDIA |
| 2 | **SQLite: un solo escritor** | Cada evento se escribe con un `INSERT`; un run emite ~10-20 eventos, pero el checkpoint se sincroniza **en cada nodo** | Con varias ejecuciones concurrentes, contención de escritura. Documentado como límite conocido (`docs/02-tecnologias.md` §8) | MEDIA |
| 3 | **Cerrojo por ejecución** | `_locks: dict[str, threading.Lock]` **nunca se limpia**: crece con cada `run_id` visto | Fuga de memoria lenta en procesos de larga vida | BAJA |
| 4 | **`GET /health`** | Llama a `list_summaries(limit=1000)` y `listar_proyectos(limit=1000)` en **cada** sonda | Una sonda barata que hace dos consultas con `ORDER BY` y hasta 2.000 filas | **MEDIA** |
| 5 | **Paginación sin tope** | `limit` sin máximo ⇒ `LIMIT 1000000` | Consulta costosa por petición | MEDIA |
| 6 | **Eventos sin purga** | La tabla `events` crece indefinidamente; `store.events(run_id)` lee **todos** los de una ejecución | Una ejecución con muchos ciclos acumula eventos; la lectura del histórico es O(n) | MEDIA |
| 7 | **Contexto del modelo** | El Coder recibe hallazgos + diff + petición; el Reviewer recibe plan completo + diff + evidencia | El contexto crece con el número de ciclos. **No hay recorte** salvo `_MAX_ARCHIVOS=20` en el Researcher | MEDIA |
| 8 | **`researcher` recorre el repositorio** | Hasta 20 ficheros × 4.000 líneas | En un repo grande, la primera pasada puede ser lenta | BAJA |
| 9 | **Ejecución de pruebas** | `pytest` completo en el worktree, con `timeout` pero sin paralelismo | Es el cuello de botella dominante (segundos a minutos) | **ALTA** (por diseño) |
| 10 | **Transcripción** | Segundos por minuto de audio en CPU | Ya mitigado con `run_in_threadpool` | BAJA |
| 11 | **`App.tsx` monolítico** | 476 líneas, 16 `useState`; cada evento SSE provoca un re-render de toda la pantalla | Con muchos eventos, *jank* perceptible | BAJA |
| 12 | **Sin caché** | `contracts.json` se importa en build (bien); la API no cachea nada | Aceptable en local | INFO |

## 2. Lo que **no** es un problema

| Aspecto | Valoración |
|---|---|
| Bloqueo del bucle de eventos | **Mitigado**: la transcripción va a `run_in_threadpool`; los endpoints síncronos los lleva FastAPI a su threadpool |
| `async` mal usado | Correcto: solo son `async` las dos rutas que lo necesitan |
| Crecimiento del contexto por el histórico de pruebas | **Resuelto en F14** (`evidencia_vigente`): el juicio no crece con el número de ciclos |
| Reintentos en tormenta | No hay política de reintentos ⇒ no hay tormenta |
| Bucles del agente | Todos acotados (`max_review_cycles`, `plan_index`, `max_model_calls`) |

## 3. Escalabilidad: dónde se rompe primero

```
1 usuario, 1 ejecución        → sin problema
1 usuario, 5 ejecuciones      → contención de escritura en SQLite (se serializan)
10 usuarios, 10 ejecuciones   → SQLite es el límite duro (un escritor)
N usuarios                   → hace falta Postgres y separar el trabajador a otro proceso
```

**El diseño ya lo prevé**: el trabajador es un hilo separado (`RunWorker`) y
`docs/02-tecnologias.md` §8 documenta el límite de SQLite. La migración a un
trabajador en proceso aparte con cola es el camino natural, y **no** requiere
reescribir el grafo.

## 4. Medición disponible

| Dato real medido en esta auditoría | Valor |
|---|---|
| Suite completa (601 tests) | **969,85 s** (~16 min) |
| Suite F14 (43 tests, con sandboxes reales) | 209-244 s |
| Evaluación completa (13 tareas × 2 modos) | ~7 min |
| `git apply` de un parche | < 1 s |
| Arranque de la app | No medido |

> **La suite de 16 minutos es un dato de rendimiento en sí mismo.** La mayor parte
> del tiempo la consumen las pruebas con **sandbox real y pytest anidado**
> (`test_m2_e2e`, `test_f8`, `test_f10_api`, `test_f14`). Es el precio de verificar
> de verdad, y está asumido.

## 5. Recomendaciones (no implementadas)

| Prioridad | Acción | Beneficio |
|---|---|---|
| P1 | Aligerar `GET /health`: contadores por `COUNT(*)` o cacheados | Una sonda de monitorización no debe recorrer 2.000 filas |
| P1 | Tope superior en `limit` | Corta el DoS trivial |
| P2 | Purgar `_locks` de ejecuciones terminadas | Evita la fuga lenta |
| P2 | Retención/purga de `events` | Evita el crecimiento indefinido |
| P2 | Sustituir el sondeo de 900 ms por un latido SSE | Elimina la mitad de la carga del cliente |
| P3 | Recortar el contexto del modelo por presupuesto de tokens | Controla el coste (`MET-06`) |
| P3 | Dividir `App.tsx` y memorizar componentes | Fluidez |
| P4 | Mover el trabajador a otro proceso + Postgres | Escala real |

## 6. Conclusión

El rendimiento es **adecuado para el caso de uso previsto** (un usuario local, una
ejecución a la vez). No hay bloqueos del bucle de eventos, no hay bucles sin límite y
los peores costes están identificados y documentados.

**Los dos puntos que conviene arreglar antes de exponer el sistema** son baratos:
`GET /health` y el tope de `limit`. **El límite estructural** (SQLite) está declarado
y no es un defecto, es una frontera conocida.
