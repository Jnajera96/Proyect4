# 08 — Auditoría de LangGraph y workflow

> `src/ai_swe/graph/` (workflow, nodes, engine, worker). Commit `065db452`.

## 1. Topología real (leída de `workflow.py`, no del diagrama)

```
                              START
                                │
                                ▼
                          ┌───────────┐
                          │ interpret │  (modelo + fallback determinista)
                          └─────┬─────┘
              route_after_interpret
        ┌───────────────┬───────┴────────────────┐
        │               │                        │
  out_of_scope   sin confirmar            confirmada
        │               │                        │
        ▼               ▼                        │
┌───────────────┐ ┌──────────────────────────┐   │
│ explain_limits│ │ mark_awaiting_requirements│  │
└───────┬───────┘ └────────────┬─────────────┘   │
        │                      ▼                 │
        │        ┌──────────────────────────────┐│
        │        │  confirm_requirements_gate   ││  ◄── INTERRUPT (puerta 1)
        │        └──────────────┬───────────────┘│
        │        route_after_requirements_gate   │
        │            ┌──────────┴────────┐        │
        │       rechazado            confirmado  │
        │            │                   └───────┘
        │            │                        │
        │            │                        ▼
        │            │                   ┌────────┐
        │            │                   │  plan  │  (modelo + fallback)
        │            │                   └───┬────┘
        │            │             route_after_plan
        │            │                       ▼
        │            │                 ┌────────────┐
        │            │                 │ researcher │  (DETERMINISTA)
        │            │                 └─────┬──────┘
        │            │          route_after_execution (plan_index)
        │            │            ┌──────────┴──────────┐
        │            │       hay subtarea          plan agotado
        │            │            │                     │
        │            │            ▼                     │
        │            │      ┌──────────┐                │
        │            │      │  coder   │ (modelo)       │
        │            │      └────┬─────┘                │
        │            │   route_after_coder              │
        │            │   ┌───────┴────────┐             │
        │            │  vacío        con cambios        │
        │            │   │                │             │
        │            │   ▼                ▼             │
        │            │ ┌────────────────┐ ┌───────────────┐
        │            │ │escalate_no_    │ │ apply_sandbox │
        │            │ │changes         │ └───────┬───────┘
        │            │ └───────┬────────┘  route_after_apply
        │            │         │        ┌────────┴────────┐
        │            │         │    fallo             aplicado
        │            │         │        │                │
        │            │         │        │                ▼
        │            │         │        │         ┌───────────┐
        │            │         │        │         │ run_tests │
        │            │         │        │         └─────┬─────┘
        │            │         │        │      route_after_tests
        │            │         │        │      ┌────────┴────────┐
        │            │         │        │  terminal          ok
        │            │         │        │      │               │
        │            │         │        │      │               ▼
        │            │         │        │      │        ┌──────────┐
        │            │         │        │      │        │ reviewer │
        │            │         │        │      │        └────┬─────┘
        │            │         │        │      │   route_after_review
        │            │         │        │      │  ┌──────┬──────┴──────┐
        │            │         │        │      │  │      │             │
        │            │         │        │      │ coder  escalate  mark_awaiting
        │            │         │        │      │  │      │             │
        │            │         │        │      │  └──────┤             ▼
        │            │         │        │      │         │   ┌────────────────┐
        │            │         │        │      │         │   │ approval_gate  │◄ INTERRUPT (puerta 2)
        │            │         │        │      │         │   └───────┬────────┘
        │            │         │        │      │         │  route_after_approval
        │            │         │        │      │         │  ┌────────┼─────────┐
        │            │         │        │      │         │ ACCEPT  REQ_CH   REJECT/terminal
        │            │         │        │      │         │  │      │         │
        │            │         │        │      │         │  ▼      │         │
        │            │         │        │      │         │ promote_changes    │
        │            │         │        │      │         │  │  (vuelve a coder)│
        └────────────┴─────────┴────────┴──────┴─────────┴──┴──────┴─────────┘
                                                        │
                                                        ▼
                                                  ┌──────────┐
                                                  │ finalize │
                                                  └────┬─────┘
                                                       ▼
                                                      END
```

## 2. Nodos

| Nodo | Tipo | Modelo | Escribe en el estado | Estado |
|---|---|---|---|---|
| `interpret` | agente | **sí** + fallback | `interpretation`, `budget`, `errors` | IMPLEMENTED_AND_VERIFIED |
| `mark_awaiting_requirements` | marcador | no | `status`, `next_step` | IMPLEMENTED_AND_VERIFIED |
| `confirm_requirements_gate` | **puerta HITL** | no | `interpretation`, `status` | IMPLEMENTED_AND_VERIFIED |
| `plan` | agente | **sí** + fallback | `plan`, `budget` | IMPLEMENTED_AND_VERIFIED |
| `researcher` | agente | **no** (determinista) | `outputs.researcher_output`, `plan_index` | IMPLEMENTED_AND_VERIFIED |
| `coder` | agente | **sí** + fallback vacío | `outputs.coder_output`, `budget`, `plan_index` | IMPLEMENTED_AND_VERIFIED |
| `apply_sandbox` | efecto | no | `artifacts` | IMPLEMENTED_AND_VERIFIED |
| `run_tests` | efecto | no | `evidence`, `budget` | IMPLEMENTED_AND_VERIFIED |
| `reviewer` | agente | **sí** + veredicto determinista + 2 guardas | `outputs.reviewer_output`, `budget` | IMPLEMENTED_AND_VERIFIED |
| `mark_awaiting` | marcador | no | `status`, `next_step` | IMPLEMENTED_AND_VERIFIED |
| `approval_gate` | **puerta HITL** | no | `approvals`, `budget`, `human_feedback`, `status` | IMPLEMENTED_AND_VERIFIED |
| `promote_changes` | **efecto irreversible** | no | `next_step` | IMPLEMENTED_AND_VERIFIED (F12) |
| `escalate` | terminación | no | `errors`, `status` | IMPLEMENTED_AND_VERIFIED |
| `escalate_no_changes` | terminación | no | `errors`, `status` | IMPLEMENTED_AND_VERIFIED |
| `explain_limits` | respuesta | no | `outputs`, `status` | IMPLEMENTED_AND_VERIFIED |
| `answer_direct` | respuesta | no | `outputs`, `status` | **Vivo pero no alcanzable desde `route_after_interpret`** → `REQUIRES_MANUAL_REVIEW` |
| `finalize` | terminación | no | `final_report`, `status`; **destruye el sandbox** | IMPLEMENTED_AND_VERIFIED |

**17 nodos registrados.** 2 son puertas HITL, 1 es el único efecto irreversible
(`promote_changes`), 5 son de terminación.

## 3. Invariantes de topología (verificados)

| Invariante | Cómo se garantiza | Verificación |
|---|---|---|
| Solo el Coder lleva a escritura | No hay arista desde `researcher` ni `reviewer` hacia nodos con efectos | `tests/test_workflow.py` |
| La única arista al repo del usuario pasa por la puerta humana | La única entrada de `promote_changes` es `approval_gate` | F12 + `test_f12_promotion.py` |
| El ciclo de revisión está acotado | `_guarda_ciclos` convierte `REQUEST_CHANGES` en `ESCALATE` al agotar ciclos | `tests/test_f9_reviewer.py` |
| Ninguna ejecución queda colgada (`MET-13 = 0`) | Red de seguridad en `engine._aplicar_red_de_seguridad` | `test_workflow.py` |
| Una instrucción fuera de alcance no se planifica | `route_after_interpret` → `explain_limits` | `test_f4_supervisor_plan.py` |
| El plan es **dato**, no topología | Aristas fijas escritas a mano | Documentado y probado |

## 4. Rutas muertas y nodos no alcanzables

| Elemento | Análisis | Veredicto |
|---|---|---|
| `answer_direct` | **Verificado a mano.** Se registra como nodo y tiene arista de salida (`→ finalize`), pero **ningún router cableado devuelve `"answer_direct"`**. Los dos que sí lo devuelven —`_ruta_estatica_m1` (`nodes.py:2409`) y `route_after_research` (`nodes.py:2418`)— **no están conectados** en `workflow.py`: `researcher` sale por `route_after_execution`, no por `route_after_research` | **NODO NO ALCANZABLE.** Existe y es correcto, pero el grafo nunca lo ejecuta. `REQUIRES_MANUAL_REVIEW` |
| `route_after_research()` | **Ninguna arista lo usa** | **Código huérfano** (vivo solo por herencia de M1) |
| `_ruta_estatica_m1()` | Su comentario dice «la ruta estatica de M1 no aplica porque el plan es la fuente de verdad», pero la función **sigue en el módulo y no se invoca desde ninguna arista** | **Código huérfano** |
| `route_intent()` | Ya no es arista | `REQUIRES_MANUAL_REVIEW` |

> **Fragmento huérfano completo**: `answer_direct` + `route_after_research` +
> `_ruta_estatica_m1` + `route_intent` forman un trozo del grafo de M1 que quedó
> desconectado al introducir el plan (F4/F5). No rompe nada — nada los llama — pero
> son ~60 líneas y un nodo que un lector podría creer vivos.

## 5. Estados terminales y excepciones

| Situación | Estado final | ¿Terminal? | ¿Limpia el sandbox? |
|---|---|---|---|
| Flujo feliz (con aprobación) | `completed` | Sí | Sí (`finalize`) |
| Rechazo en la puerta 2 | `cancelled` | Sí | Sí |
| Rechazo en la puerta 1 | `needs_human` | Sí | Sí (no había sandbox) |
| Fallo de pruebas + ciclos agotados | `needs_human` | Sí | Sí |
| Fallo del sandbox / del patcher | `needs_human` | Sí | Sí |
| Coder sin cambios | `needs_human` | Sí | Sí |
| Excepción no capturada del trabajador | `needs_human` (`abortar`) | Sí | **No** — `abortar` escribe el estado pero no llama a `finalize`; el worktree queda hasta que se recree con el mismo `run_id` |
| Proceso muerto a mitad | recuperación de huérfanas → `run.failed` | Sí | **No** (no hay proceso que limpie) |

> **Hallazgo (MEDIUM).** La ruta de excepción (`abortar`) y la de huérfanas **no
> destruyen el worktree**. El diseño lo asume (`crear()` limpia al recrear con el
> mismo `run_id`), pero si una ejecución muere y nunca se repite, el worktree y su
> entrada administrativa en `.git/worktrees/` del repositorio del usuario quedan
> ahí. Ver `26-…`.

## 6. `max_review_cycles` y bucles

| Bucle | Acotación | Estado |
|---|---|---|
| `reviewer → coder` | `_guarda_ciclos` con `Budget.max_review_cycles` (default 2, máximo 5) | **Acotado** |
| `approval_gate → coder` (pedir cambios) | Comprueba el mismo contador (F12) | **Acotado** |
| `researcher → …` (plan agotado) | `plan_index` avanza siempre | **Acotado** |
| Reintentos de modelo | **No hay política de reintentos** | N/A |
| Llamadas al modelo | `Budget.max_model_calls` (default 120) | **Acotado**, pero **no configurable desde `Settings`** (`25-…`) |

**No se detecta ningún bucle sin límite.**

## 7. Cobertura de pruebas por nodo

| Nodo | ¿Probado? | Fichero |
|---|---|---|
| `interpret` | Sí | `test_f3_interpret_analyst.py` |
| `plan` | Sí | `test_f4_supervisor_plan.py` |
| `researcher` | Sí | `test_f5_plan_driven_execution.py` |
| `coder` | Sí | `test_f6_real_coder.py` |
| `apply_sandbox` | Sí | `test_f7_sandbox.py`, `test_f8_test_runner.py` |
| `run_tests` | Sí | `test_f8_test_runner.py` |
| `reviewer` | Sí | `test_f9_reviewer.py` |
| Ambas puertas | Sí | `test_m2_e2e.py`, `test_f10_api.py` |
| `promote_changes` | Sí | `test_f12_promotion.py` |
| `finalize` / `escalate*` | Sí (indirecto) | `test_workflow.py` |
| `answer_direct` | **No** (inalcanzable) | — |
| `explain_limits` | Sí | `test_f4_supervisor_plan.py` |

## 8. Conclusión

El workflow está **IMPLEMENTED_AND_VERIFIED**: topología fija y explícita, dos
puertas humanas, un único punto de escritura irreversible protegido, bucles
acotados y una red de seguridad que garantiza terminación.

**Dos cosas que conviene resolver antes de producción:**
1. `answer_direct` es un nodo **inalcanzable** en el grafo actual.
2. Las rutas de excepción y de huérfanas **no limpian el worktree**.
