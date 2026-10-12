# Baseline de F3 — Requirements Analyst

**Fecha:** 2026-10-07
**Fase:** `F3` — Requirements Analyst (primer nodo conectado al modelo).
**Estado de partida:** `M1`/`F1`/`F2` cerradas. `MODEL_GATEWAY_READY = YES`.
**Estado de llegada:** el `ModelGateway` está conectado a **un solo nodo**,
`interpret`, con el clasificador determinista conservado como *fallback* permanente.

> **Qué es este documento.** El acta de cierre de `F3`. Registra qué se cambió, qué
> se verificó y con qué evidencia, y qué **no** se pudo verificar. No es un plan.
>
> **Regla de evidencia.** Un componente no cuenta por existir. Cada afirmación va
> con la prueba que la sostiene, y lo que no se pudo comprobar se dice con esas
> palabras.

---

## 1. Entregable en una frase

`interpret` pasa a pedirle la clasificación al modelo **cuando hay uno disponible**,
valida la respuesta contra el contrato `TaskInterpretation`, contabiliza el gasto, y
**si no hay modelo, falla o responde algo que no cumple el contrato, cae de forma
transparente y declarada** al clasificador por vocabulario que ya existía.

```
                    ┌─ hay gateway y responde válido ──> interpretación del modelo
interpret ──────────┤                                    + gasto contabilizado
                    └─ no hay / falla / no valida ─────> clasificador determinista
                                                         + RunError recuperable
```

---

## 2. La regla crítica: el fallback no se borró

Era la condición explícita del encargo: *«No borres el clasificador por vocabulario
determinista actual»*. No se borró, y no es código muerto:

| Situación | Qué ocurre |
|---|---|
| Sin credenciales (el caso de la demo) | Clasificación determinista, sin error, sin gasto |
| Sin red | Igual: el fallo del adapter cae al fallback |
| Proveedor caído (timeout/429/503) | Igual, con un `RunError` recuperable que lo declara |
| Credencial inválida | Igual, declarado |
| Respuesta que no cumple el contrato | Igual, declarado |

En **todos** los casos el sistema termina en `completed` con un informe. La ejecución
no se cae por no tener modelo, que es lo que permitía ejecutar la demo sin proveedor.

**La degradación no es silenciosa.** Deja un `RunError` con `error_class =
"MODEL_FALLBACK"`, `recoverable = True`, el **tipo** del fallo y su motivo. Un
fallback que no se declara es indistinguible de un acierto: una demo que funcionara
«por el fallback» parecería funcionar por el modelo.

---

## 3. El contrato Pydantic sigue siendo la puerta absoluta

El modelo **propone**; el contrato **valida**. En `interpret` hay dos capas:

1. `gateway.generate_structured(..., response_model=TaskInterpretation)` deriva el
   JSON Schema del contrato con `model_json_schema()` y lanza `StructuredOutputError`
   si la respuesta no valida.
2. El nodo **revalida** con `TaskInterpretation.model_validate(datos)`.

La segunda capa es defensa en profundidad, y **la verificación por mutación demostró
que era necesaria**: al sustituir `model_validate` por `model_construct` (que se salta
toda la validación) no se rompía ninguna prueba, porque el gateway validaba antes y el
dato corrupto no llegaba hasta ahí. Es decir: la línea estaba sin proteger.

Al escribir la prueba que **sí** la alcanza apareció un **defecto real**: un
`pydantic.ValidationError` en el nodo **no** es un `ModelGatewayError`, así que
atravesaba la frontera y **abortaba la ejecución** en lugar de degradar al fallback.
Se corrigió envolviendo la revalidación y convirtiéndola en `StructuredOutputError`.
Sin la mutación, ese camino se habría quedado ahí.

---

## 4. El modelo no puede ampliar el alcance

`Scope` (repositorio y rutas autorizadas) llega en la respuesta del modelo, pero el
nodo **lo sobrescribe** con el que declaró el usuario:

```python
interpretacion = interpretacion.model_copy(update={"scope": _alcance(state)})
```

El alcance es una **restricción de seguridad**, no una interpretación. Un modelo al
que se le pregunta por su alcance puede devolver el que quiera; si ese valor llegara
al estado, un prompt malicioso ampliaría las rutas que el sistema considera
autorizadas. Hay una prueba que hace que el modelo devuelva `/otro/repo` y comprueba
que el alcance que queda es el del usuario. Y hay una mutación que quita esa línea:
está cazada.

---

## 5. Contabilidad del gasto

El nodo aplica `gateway.consume(state.budget, respuesta)`, que devuelve un `Budget`
**nuevo**:

- `used_model_calls` se incrementa **siempre** (es lo que evita un bucle infinito);
- `used_tokens` solo se suma si el proveedor los reportó (`None` ≠ `0`);
- `used_cost` solo se suma si el coste se conoce.

El presupuesto de entrada **no se muta**: es la misma disciplina que ya usaban los
nodos, y lo que hace que dos ejecuciones concurrentes queden aisladas por
construcción en lugar de por cerrojo.

---

## 6. Precios: mecanismo sí, tarifas inventadas no

`pricing.py` gana un mecanismo de carga real (`AI_SWE_MODEL_PRICING`, una lista JSON
en el entorno) y **sigue vacío en el repositorio**. Es deliberado y está documentado
en el propio módulo:

> Un precio ausente obliga a mirar; un precio inventado se cree.

No se ha escrito **ninguna tarifa** en el código. El proyecto no afirma conocer un
precio que solo el proveedor publica y que cambia sin avisar, así que cada llamada
registra `cost = None` («no se sabe») hasta que quien despliega declare los suyos.

**Un defecto encontrado aquí:** la primera prueba de precio afirmaba
`used_cost == 0.0` sin tarifa, y eso era cierto **tanto si el coste era `None` como
si era `0.0`** (porque `consume` no suma ninguno de los dos). Pasaba con el defecto
dentro. Se reescribió para comprobar `PricingTable.cost(...) is None`, que sí
distingue «no se sabe» de «fue gratis».

---

## 7. Prueba real de proveedor: **NO EJECUTADA**

`REAL_PROVIDER_TEST = NOT_EXECUTED_NO_CREDENTIALS`.

Se comprobó que en el entorno **no hay** `AI_SWE_MODEL_API_KEY`, `AI_SWE_MODEL_NAME`,
`AI_SWE_MODEL_PROVIDER` ni `AI_SWE_RUN_REAL_PROVIDER_TESTS`, y que no existe `.env`.
La prueba está en su fichero, marcada `real_provider`, y **se salta** en lugar de
pasar en falso (verificado con `-v`: `1 skipped`).

No se pidió la clave por el chat, no se escribió en el código y no se inventó: la
regla del encargo. **La ejecución real contra un proveedor queda pendiente** y es el
único punto de este baseline sin evidencia empírica. Cómo completarlo:

```
AI_SWE_RUN_REAL_PROVIDER_TESTS=1 AI_SWE_MODEL_API_KEY=<clave> \
  AI_SWE_MODEL_NAME=<modelo> AI_SWE_MODEL_PROVIDER=openai \
  python -m pytest tests/test_model_gateway_real.py -m real_provider
```

---

## 8. Archivos

**Modificados**

| Fichero | Cambio |
|---|---|
| `src/ai_swe/graph/nodes.py` | `interpret` conectado al gateway; `usar_gateway()`; prompt; revalidación; fallback declarado; `_es_fallo_esperado` |
| `src/ai_swe/models/pricing.py` | `from_mapping`, `from_entries`, `from_json`, `__len__`; tabla **sigue vacía** |
| `src/ai_swe/models/gateway.py` | `gateway_from_settings` carga los precios de la configuración y falla si están mal escritos |
| `src/ai_swe/models/__init__.py` | exporta las funciones nuevas de precios |
| `src/ai_swe/config.py` | campo `model_pricing` |
| `.env.example` | documenta `AI_SWE_MODEL_PRICING` (nombre, nunca valor) |
| `tests/test_model_gateway.py` | la prueba estructural de F2 se sustituye por dos que sí comprueban la invariante de F3 |
| `tools/mutation_check.py` | **8 mutaciones** de F3 + filtro opcional por nombre |

**Creados**

| Fichero | Qué contiene |
|---|---|
| `tests/test_f3_interpret_analyst.py` | 28 pruebas de F3, sin red ni credenciales |
| `docs/BASELINE-F3-REQUIREMENTS-ANALYST.md` | este documento |

**No se tocó** ningún otro nodo, ni el almacén, ni la API, ni el frontend, ni el
motor de ejecución. Solo `interpret` habla con el modelo, y hay una prueba
estructural que lo hace cumplir.

---

## 9. La prueba estructural que hubo que reescribir

La de `F2` afirmaba: «ningún fichero del grafo contiene la cadena `ai_swe.models`».
Al conectar el gateway falló —**por una mención en un comentario**—, lo que reveló que
era frágil en los dos sentidos:

- **falso positivo**: cualquier comentario que nombrara el módulo la rompía;
- **falso negativo**: no habría detectado `importlib.import_module("ai_swe.models")`.

Se reescribió con `ast`, y la primera versión **también tenía un punto ciego**: un
`import` dentro de `researcher` (el segundo nodo) seguía dejando el conjunto de
ficheros en `{nodes.py}`. La mutación correspondiente **no se cazó**. La versión
correcta compara **nombres de función**, no ficheros, y comprueba además que el
import sea perezoso.

---

## 10. Verificación

| Comprobación | Resultado |
|---|---|
| Suite completa (`pytest`) | **312 passed, 1 skipped** |
| — de los cuales, nuevos de F3 | 28 |
| Pruebas que exigen red | **0** |
| Pruebas que exigen credenciales | **0** |
| Mutaciones de F3 | **8/8 cazadas** (verificado por separado, ver §11) |
| Mutaciones de F1/F2 | 35/35 + 8/8 (verificadas en su momento) |
| Ejecución E2E del grafo **sin** modelo | `completed`, sin errores, con informe |
| Ejecución E2E del grafo **con** modelo | `completed`, clasificación del modelo, 1 llamada contabilizada |
| `.gitignore` no excluye nada nuevo | verificado con `git check-ignore` |
| Árbol limpio tras las mutaciones | `git diff` sin cambios ajenos; diario `{}` |

---

## 11. Las tres mutaciones que **no** se cazaron (y qué se hizo)

La primera pasada dio **5/8**. Las tres no cazadas eran puntos ciegos reales, y se
documentan porque el valor está en el proceso, no en el 8/8 final:

1. **«el segundo nodo también habla con el gateway»** — la prueba estructural
   comparaba ficheros, no funciones. → se reescribió (§9).
2. **«la tabla de precios acepta un modelo sin tarifa como 0.0»** — la aserción
   `used_cost == 0.0` era cierta en ambos casos. → se reescribió para mirar el valor
   en el punto de cálculo (§6).
3. **«la interpretación estructurada se salta la validación Pydantic»** — nadie
   alcanzaba la línea con un dato inválido. → se añadió una prueba con un gateway que
   **no** valida, y apareció un **defecto real** de degradación (§3).

Las tres se cerraron; la segunda pasada dio **8/8**.

---

## 12. Riesgos abiertos y reservas

- **`REAL_PROVIDER_TEST` sin ejecutar** (§7). Es la única afirmación de este
  documento sin evidencia empírica.
- **Sin autenticación.** Hallazgo abierto de la auditoría externa, ajeno a `F3`.
- **La tabla de precios está vacía**, así que el presupuesto de **coste** no actúa
  hasta que se declaren tarifas. El de tokens y llamadas sí.
- **Solo `interpret` está conectado.** Los demás agentes siguen siendo deterministas.
  Es deliberado: una fase, un nodo.
- **`test_workflow.py` tarda ~24 s** en esta máquina. Se comprobó que **también tarda
  ~24 s en el commit de `F2` sin tocar**, así que no es una regresión de `F3`.

---

## 13. Veredicto

**REQUIREMENTS_ANALYST_READY = YES** (con una reserva: la prueba real contra un
proveedor no se ha ejecutado por no haber credenciales en el entorno).

El nodo usa el modelo cuando puede, valida su salida contra el contrato, contabiliza
el gasto, no permite que el modelo amplíe el alcance, y sin modelo sigue funcionando
exactamente como antes. La suite offline está en verde y las mutaciones de la fase
están cazadas.
