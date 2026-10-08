# Acta de cierre — FASE F4 (Supervisor)

Fecha: 2026-10-08
Fase anterior: F3 (Requirements Analyst) — commit `00c52a1`, aprobada por el Arquitecto.
Estado: **implementada, verificada y pendiente de revision del Arquitecto.**

---

## 1. Entregable

El Supervisor pasa de no existir a **planificar**. Se anade el nodo `plan` al grafo,
entre `interpret` y `researcher`, y es el **segundo y ultimo** nodo conectado al
`ModelGateway`.

```
START -> interpret --fuera de alcance?--> explain_limits -> finalize
                 \--si no--> plan --primera subtarea--> researcher
                                                       researcher --intencion--> ...
```

`RunState.plan` recibe el `RunPlan` producido. La topologia es **fija**: no se genera
a partir del plan.

---

## 2. Reglas de la fase

| # | Regla | Donde se cumple |
|---|-------|-----------------|
| F4-1 | El plan se pide con `response_model=RunPlan`; el contrato aplica DFS, unicidad de ids, dependencias existentes y maximo de 32 subtareas | `_plan_del_modelo` -> `gateway.generate_structured(..., response_model=RunPlan)` |
| F4-2 | **Nunca `model_construct`** | `_plan_del_modelo` usa `RunPlan.model_validate(datos)` y envuelve el fallo en `StructuredOutputError` |
| F4-3 | El plan se guarda en `RunState.plan` | `plan(state) -> {"plan": ...}` |
| F4-4 | La planificacion consume presupuesto | `gateway.consume(state.budget, respuesta)`; delta de tokens calculado, no inventado |
| F4-5 | **Fallback determinista inquebrantable**: sin modelo o con modelo roto, siempre hay plan | `_plan_determinista`; `RunError MODEL_FALLBACK recoverable=True` |
| F4-6 | Un plan no puede prometer mas ciclos de revision de los presupuestados | `_acotar_al_presupuesto_plan` |
| F4-7 | Una instruccion fuera de alcance no se planifica | `route_after_interpret` |

---

## 3. Codigo principal del nodo `plan`

```python
def plan(state: RunState) -> dict:
    """Planificacion del Supervisor. **Segundo nodo conectado al modelo (F4).**"""
    try:
        resultado = _plan_del_modelo(state)
    except Exception as exc:  # noqa: BLE001 - la frontera convierte cualquier fallo
        if not _es_fallo_esperado(exc):
            raise
        motivo = f"{type(exc).__name__}: {exc}"[:500]
        log.warning("plan: el modelo no respondio, se usa el fallback (%s)", motivo)
        plan_fallback = _plan_determinista(state, motivo="modelo no disponible")
        return {
            "plan": plan_fallback,
            "errors": _error(state, "MODEL_FALLBACK", AgentRole.SUPERVISOR.value,
                f"plan determinista de respaldo: el modelo no se pudo usar ({motivo})",
                recuperable=True),
            "status": RunStatus.RUNNING,
            "next_step": plan_fallback.subtasks[0].agent.value,
            "updated_at": _ahora(),
        }

    if resultado is None:
        plan_fallback = _plan_determinista(state, motivo="modelo no conectado")
        return {
            "plan": plan_fallback,
            "status": RunStatus.RUNNING,
            "next_step": plan_fallback.subtasks[0].agent.value,
            "updated_at": _ahora(),
        }

    plan_modelo, presupuesto, _tokens = resultado
    return {
        "plan": plan_modelo,
        "budget": presupuesto,
        "status": RunStatus.RUNNING,
        "next_step": plan_modelo.subtasks[0].agent.value,
        "updated_at": _ahora(),
    }
```

**Los tres caminos y por que son tres.** `resultado is None` no es un fallo: es «no hay
modelo conectado», el camino normal de la suite offline, y **no deja error** (no ha
pasado nada malo). El `except` es «habia modelo y fallo», y **si** deja error recuperable.
El camino final es el modelo usado con exito. Mezclar los dos primeros habria hecho que
el desarrollo local sin red acumulara errores falsos.

---

## 4. Codigo del fallback determinista

```python
_HERRAMIENTAS_RESEARCHER = ("list_files", "read_file", "search_text", "git_status", "git_diff")
_HERRAMIENTAS_CODER = ("read_file", "write_file", "apply_patch")


def _plan_determinista(state: RunState, *, motivo: str) -> RunPlan:
    """Plan minimo y seguro: investigar y, si procede, aplicar cambios."""
    intencion = state.interpretation.intent if state.interpretation else Intent.INSPECT

    investigar = Subtask(
        id="investigar",
        description="Investigar el repositorio y reunir la evidencia necesaria.",
        agent=AgentRole.RESEARCHER,
        depends_on=[],
        allowed_tools=list(_HERRAMIENTAS_RESEARCHER),
        done_criteria="Se han enumerado los archivos relevantes y citado rutas reales.",
    )

    subtareas = [investigar]
    if intencion is Intent.MODIFY:
        subtareas.append(
            Subtask(
                id="aplicar_cambios",
                description="Aplicar los cambios propuestos sobre la evidencia reunida.",
                agent=AgentRole.CODER,
                depends_on=["investigar"],
                allowed_tools=list(_HERRAMIENTAS_CODER),
                done_criteria="Los cambios estan aplicados y el diff es revisable.",
            )
        )

    return RunPlan(
        subtasks=subtareas,
        max_review_cycles=state.budget.max_review_cycles,
        rationale=(
            "plan determinista de respaldo: "
            f"{len(subtareas)} subtarea(s) para la intencion '{intencion.value}'"
            f"; motivo del fallback: {motivo}"
        ),
    )
```

**Por que el plan de respaldo es «duro» y no «inteligente».** Dos subtareas fijas, sin
dependencias creativas. Un fallback que intentara adivinar la estructura de la tarea
seria un plan **inventado**, y eso es peor que uno generico: el generico se lee y se ve
que es generico. La intencion decide la forma: para `modify` se encadena investigacion y
cambio; para el resto, solo lectura, porque planificar una escritura cuando el usuario
pregunto algo seria un plan que no corresponde a la peticion.

Las herramientas declaradas son **subconjuntos de las del rol** (`ROLE_TOOLS`). La
asignacion efectiva es la interseccion, asi que declarar una herramienta ajena no
ampliaria permisos: solo daria un plan que promete algo inejecutable.

---

## 5. El hallazgo de F4: el plan no puede pedir mas de lo presupuestado

`RunPlan.max_review_cycles` esta acotado a `[0, 5]` por el contrato, pero el presupuesto
de la ejecucion puede ser **menor**. Un plan que pidiera 5 ciclos cuando
`Budget.max_review_cycles` es 2 prometeria un trabajo que el sistema no va a poder pagar:
el bucle de revision se cortaria antes de cumplir lo planificado, y el plan quedaria
**mintiendo**.

```python
def _acotar_al_presupuesto_plan(plan: RunPlan, state: RunState) -> RunPlan:
    if plan.max_review_cycles <= state.budget.max_review_cycles:
        return plan

    motivo = (f" [acotado: max_review_cycles reducido a {state.budget.max_review_cycles} "
              "por el presupuesto de la ejecucion]")
    return plan.model_copy(update={
        "max_review_cycles": state.budget.max_review_cycles,
        "rationale": (plan.rationale + motivo)[:4000],
    })
```

**La primera version mutaba el plan in situ** (`plan.subtasks = ...`, `-> None`) y se
reescribio. Un modelo Pydantic mutado en su lugar queda en un estado que **no ha pasado
por sus validadores**, y el siguiente que lo lea no puede confiar en el. La firma `-> RunPlan`
que devuelve un objeto nuevo hace imposible olvidarse de recoger el resultado.

---

## 6. La estrategia defensiva: el plan es dato, no topologia

La pregunta del Arquitecto era como evitar un `RunPlan` infinito o con ciclos. La
respuesta tiene **tres capas independientes**, y ninguna depende de que el modelo se porte
bien:

1. **El contrato acota el dato.** `RunPlan` valida `1 <= len(subtasks) <= 32`, ids unicos,
   dependencias existentes (autodependencia incluida) y **ausencia de ciclos por DFS con
   marcas 1/2**. Un plan ciclico o gigantesco no cruza la frontera: el gateway lanza
   `StructuredOutputError` y se cae al fallback.
2. **El alcance del daño esta acotado por el nodo.** Un plan rechazado **no deja el estado
   a medias**: se sustituye por el determinista. La ejecucion nunca se queda sin plan.
3. **El grafo no se genera del plan.** Esta es la capa que hace que el problema sea
   *imposible* en lugar de *improbable*: las aristas estan escritas a mano
   (`interpret -> plan`, `plan -> <primer agente>`), y `route_after_plan` solo lee la
   **primera** subtarea. Aunque un plan circular cruzara todas las validaciones, no crearia
   un bucle en la ejecucion, porque la forma del grafo no depende de el.

La capa 3 es la que convierte la propiedad de «el contrato lo rechaza» (defensa en
profundidad, dependiente de que el contrato siga siendo correcto) en «no hay mecanismo por
el que un plan pueda crear un bucle» (garantia estructural).

---

## 7. Verificacion

### 7.1 Suite completa

```
tests=351  failures=0  errors=0  skipped=1
```

El `skipped` es `tests/test_model_gateway_real.py`, que se salta sin credenciales (ver
`TD-01`). **No se ejecuto ningun test contra red ni credenciales.**

El conteo se lee del **informe XML** (`--junitxml=`), no de la salida estandar: en este
entorno el interceptor de borrado corrompe el resumen de pytest, y `--collect-only -q`
tampoco imprime el total. Cambiar de senal en lugar de rodear la corrompida.

### 7.2 Mutaciones F4: 8/8 cazadas

```
F4: plan ignora el modelo aunque este conectado               -> cazada
F4: un fallo del modelo se traga en vez de caer al fallback   -> cazada
F4-fallback: no hay plan cuando no hay modelo                 -> cazada
F4-fallback: el plan de respaldo no encadena investigacion... -> cazada
F4-presupuesto: la planificacion no se contabiliza            -> cazada
F4-presupuesto: el plan puede pedir mas ciclos de los...      -> cazada
F4: el plan estructurado se salta la validacion Pydantic...   -> cazada
F4: una instruccion fuera de alcance se planifica igualmente  -> cazada

8/8 mutaciones cazadas (de 51 en total; esta ejecucion estaba filtrada)
```

Cubre explicitamente lo que pidio el Arquitecto: **2 de presupuesto** y **2 de fallback**.

**En F3 la primera pasada dio 5/8 y tres eran puntos ciegos reales. En F4, 8/8 a la
primera.** La causa no es suerte: las dos lecciones de F3 se aplicaron desde el diseno de
la suite — (a) cada comprobacion tiene que **alcanzar** la linea que dice proteger, y
(b) hay que comprobar el **valor en el punto donde se calcula**, no un acumulado que puede
ser 0 por dos motivos distintos.

### 7.3 Ejecucion E2E real del grafo (sin modelo)

| Instruccion | status | intent | plan |
|---|---|---|---|
| «Explica el modulo de autenticacion.» | completed | question | `['investigar']` |
| «Corrige el error de parseo del config.» | needs_human | modify | `['investigar', 'aplicar_cambios']` |
| «Sube los cambios a GitHub.» | completed | out_of_scope | `None` (no se planifica) |

### 7.4 Ejecucion E2E real del grafo (con modelo)

Con un `FakeModelAdapter` que devuelve un plan de 2 subtareas pidiendo 5 ciclos:

```
plan guardado:                 [('mapear_http','researcher'), ('refactor','coder')]
max_review_cycles del plan:    2          <- el modelo pidio 5, el presupuesto manda
rationale:                     "... [acotado: max_review_cycles reducido a 2 ...]"
llamadas contabilizadas:       1
tokens contabilizados:         15
```

### 7.5 Arbol limpio

Tras las mutaciones, `grep -rn "mutacion:" src/` no devuelve nada y `git status` solo
muestra los ficheros de F4 legítimamente modificados.

---

## 8. Ficheros

| Fichero | Cambio |
|---|---|
| `src/ai_swe/graph/nodes.py` | `HERRAMIENTAS_*`, `_plan_determinista`, `PROMPT_PLANIFICACION`, `_plan_del_modelo`, `_acotar_al_presupuesto_plan`, `plan`, `route_after_interpret`, `route_after_plan` (+275 lineas) |
| `src/ai_swe/graph/workflow.py` | nodo `plan`; `route_after_interpret` sustituye a `route_intent` como arista; nueva arista condicional desde `plan`; invariante «el plan es dato, no topologia» |
| `tests/test_f4_supervisor_plan.py` | **nuevo**, 38 pruebas |
| `tests/test_model_gateway.py` | la prueba estructural de F2 pasa a `test_solo_interpret_y_plan_hablan_con_el_gateway` |
| `tools/mutation_check.py` | 8 mutaciones F4 |
| `docs/auditoria-2026-10-06/PROJECT_SNAPSHOT.json` | fase F4, contadores, caveats, reglas |

---

## 9. Deuda tecnica

**TD-01 sigue ABIERTA** (decision del Arquitecto, 2026-10-07: aplazada a proposito). Ahora
afecta a **dos** nodos: `interpret` y `plan`. La cadena real completa no se ha ejecutado
contra un proveedor de verdad. El mecanismo esta listo y la prueba existe, pero se **salta**
en lugar de pasar en falso.

**Deuda nueva de F4, declarada honestamente:** el plan se **produce y guarda**, pero la
ejecucion **todavia no se orquesta subtarea a subtarea**. `route_after_plan` lee la primera
subtarea y el resto del grafo sigue conduciendose por la intencion (como en M1). Un plan de
3 subtareas no las recorre todas. Esto es exactamente lo que cubre F5.

---

## 10. Veredicto

```
F4_SUPERVISOR_READY = YES
```

- El Supervisor planifica con el modelo cuando esta disponible, con `response_model=RunPlan`
  como puerta absoluta y **sin `model_construct`**.
- El plan se inyecta en `RunState.plan` y el gasto se contabiliza.
- **Sin modelo o con modelo roto siempre hay plan**: fallback determinista, declarado con
  `MODEL_FALLBACK` recuperable, nunca silencioso.
- **351 pruebas en verde, 1 saltada, 0 fallos. 8/8 mutaciones F4 cazadas.**
- Un plan circular o infinito no puede crear un bucle en la ejecucion: la topologia es fija.

Pendiente de revision del Arquitecto. **No se ha hecho commit.** No se ha hecho push.
