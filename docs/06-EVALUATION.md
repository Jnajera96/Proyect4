# 06 — Evaluation

> **Documento GENERADO** por `src/ai_swe/evaluation/runner.py` a partir de
> `var/evaluation_results.json`. **No editar a mano**: cualquier cambio se pierde en
> la siguiente ejecucion. Generado el 2026-10-12T19:15:31+00:00.

## La pregunta central

> ¿Cuándo se justifica usar varios agentes y cuándo un único agente o un flujo
> determinista es más simple, barato y fiable?

## Como se responde

La **misma** bateria de 13 tareas controladas (`EXP-01`..`EXP-13`,
en `src/ai_swe/evaluation/tasks.py`) se ejecuta bajo dos configuraciones:

- **`SINGLE_AGENT`** — flujo directo: `interpret → coder → apply_sandbox →
  run_tests → finalize`. Sin plan, sin investigacion, **sin Reviewer** y sin puertas
  humanas.
- **`MULTI_AGENT`** — el grafo de produccion completo, con planificacion,
  investigacion, ciclo de revision y **las dos puertas HITL**.

Cada tarea tiene un criterio de exito **objetivo**: su suite de validacion falla
antes del cambio y pasa despues. El exito exige que la ejecucion termine en
`completed` **y** que la evidencia de pruebas lo respalde.

**Cuatro tareas exigen dos intentos** (`EXP-02`, `EXP-05`, `EXP-09`, `EXP-11`): el
primer parche que produce el modelo guionizado falla las pruebas. Son las que
separan las dos configuraciones, porque solo el ciclo de revision vuelve a intentarlo.

**Una tarea no converge** (`EXP-13`): sus dos propuestas fallan. Sirve de control
negativo — el multiagente **no** es magia: agota el ciclo de revision y escala.

## Resultados

| Metrica | SINGLE_AGENT | MULTI_AGENT | Diferencia |
|---|---|---|---|
| Tasa de exito (MET-01) | 62% | 92% | +31% |
| Tareas resueltas | 8/13 | 12/13 | +4 |
| Tokens de entrada | 23,087 | 40,834 | +17,747 |
| Tokens de salida | 1,734 | 3,930 | +2,196 |
| Tokens totales | 24,821 | 44,764 | +19,943 |
| Latencia media (ms) | 12304.7 | 19055.2 | +6750.5 |
| Llamadas al modelo | 26 | 44 | +18 |
| Llamadas a herramientas | 13 | 18 | +5 |
| Ciclos de revision | 0 | 6 | +6 |
| Intervenciones humanas (MET-12) | 0 | 25 | +25 |
| Escalamientos | 0 | 1 | +1 |
| Terminacion correcta (MET-13) | 13/13 | 13/13 | +0 |
| Pruebas aprobadas / fallidas | 8/5 | 12/1 | - |
| Violaciones de politica (MET-14) | 0 | 0 | +0 |

### Por tarea

| Tarea | Categoria | Correccion | Single | Multi | Ciclos (M) | Interv. (M) |
|---|---|---|---|---|---|---|
| `EXP-01` Corregir el desfase de una paginacion 1-based | bugfix | no | OK | OK | 0 | 2 |
| `EXP-02` Corregir el comparador que confunde mayor con mayor o igual | bugfix | si | fallo | OK | 1 | 2 |
| `EXP-03` Anadir una ruta al enrutador | endpoint | no | OK | OK | 0 | 2 |
| `EXP-04` Endurecer la validacion de correo | validacion | no | OK | OK | 0 | 2 |
| `EXP-05` Corregir el contador de numeros pares | prueba | si | fallo | OK | 1 | 2 |
| `EXP-06` Normalizar guiones repetidos en un identificador | refactor | no | OK | OK | 0 | 2 |
| `EXP-07` Documentar la funcion publica del modulo | documentacion | no | OK | OK | 0 | 2 |
| `EXP-08` Leer el tiempo de espera de la configuracion con valor por defecto | configuracion | no | OK | OK | 0 | 2 |
| `EXP-09` Impedir que una ruta relativa escape del directorio base | revision de seguridad | si | fallo | OK | 1 | 2 |
| `EXP-10` Convertir a numero antes de sumar | bugfix | no | OK | OK | 0 | 2 |
| `EXP-11` Rechazar un limite no positivo | endpoint | si | fallo | OK | 1 | 2 |
| `EXP-12` Rechazar un nombre vacio | validacion | no | OK | OK | 0 | 2 |
| `EXP-13` Devolver `None` en lugar de fallar al dividir entre cero | bugfix | si | fallo | fallo | 2 | 1 |

### Por categoria

| Categoria | Single (exitos/total) | Multi (exitos/total) |
|---|---|---|
| bugfix | 2/4 | 3/4 |
| configuracion | 1/1 | 1/1 |
| documentacion | 1/1 | 1/1 |
| endpoint | 1/2 | 2/2 |
| prueba | 0/1 | 1/1 |
| refactor | 1/1 | 1/1 |
| revision de seguridad | 0/1 | 1/1 |
| validacion | 2/2 | 2/2 |

## Respuesta a la pregunta central

- **Tasa de exito:** 62% (`SINGLE_AGENT`) frente a
  92% (`MULTI_AGENT`). La diferencia se concentra en las
  tareas que exigen correccion: **EXP-02, EXP-05, EXP-09, EXP-11** las
  resuelve solo el flujo multiagente.
- **Coste:** el multiagente gasta **+19,943 tokens** y
  **+6750.5 ms** de media por
  tarea. El sobrecoste es el precio de planificar, investigar y revisar.
- **Intervenciones humanas:** 0 frente a
  25. El flujo directo no tiene puertas; el
  multiagente pide confirmar requisitos y aprobar el cambio.
- **Terminacion correcta (`MET-13`):** 13/13
  y 13/13. Ninguna ejecucion quedo colgada.

**Conclusion.** El multiagente **se justifica cuando el primer intento puede estar
mal**: su valor medible es convertir un fallo silencioso en un ciclo de correccion.
Cuando la tarea es directa y el primer parche es correcto, el flujo directo la
resuelve con menos tokens, menos latencia y sin pedir nada a una persona. La
arquitectura no se defiende por ser mas compleja, sino por **cuando** esa complejidad
paga.

## Limitaciones declaradas

1. **Modelo guionizado.** El arnes es offline y determinista (sin credenciales ni
   red), asi que el modelo es un guion por tarea. Esta comparacion mide el **coste y
   el beneficio de la orquestacion**, no la calidad de un modelo concreto. Es la
   misma limitacion que declara `TD-01`.
2. **Los tokens son una estimacion del proveedor guionizado** (~4 caracteres por
   token), no una medicion de facturacion. Sirven para comparar las dos
   configuraciones entre si.
3. **Doce tareas es una muestra pequena.** Las cifras son indicativas; el valor del
   arnes es que es **reproducible** y que cualquier conclusion se puede volver a
   medir.

## Metricas y experimentos

Definiciones canonicas: [`01-arquitectura.md`](01-arquitectura.md) §18
(`MET-01`..`MET-14`, `EXP-01`..`EXP-08`) y
[`auditoria-2026-10-06/10_EVALUACION_METRICAS.md`](auditoria-2026-10-06/10_EVALUACION_METRICAS.md).

## Como se reproduce

```bash
PYTHONPATH=src python -m ai_swe.evaluation.runner
```

Escribe `var/evaluation_results.json` y **regenera este documento**. La suite
`tests/test_f14_evaluation.py` ejecuta el arnes en miniatura (offline) en cada
corrida de pytest.

## Verificacion del propio sistema

- **Suite offline** — 26 corridas de
  evaluacion en el informe, sin red ni credenciales.
- **Mutacion** — `tools/mutation_check.py`: se introduce cada fallo a proposito y se
  comprueba que alguna prueba falla. Un corte por tiempo **no** cuenta como cazada.
- **Frontend** — `tools/verify_frontend.py` (arnes aparte, no incluido en pytest).
