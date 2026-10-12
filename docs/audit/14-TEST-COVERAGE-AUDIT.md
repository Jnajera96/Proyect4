# 14 — Auditoría de testing

> Ejecución real de la suite completa el 2026-10-12 sobre el commit `065db452`.
> **Comando**: `python -m pytest tests/ -q --junitxml=_audit_final.xml`
> (sin red, sin credenciales).

## 1. Resultado medido

| Métrica | Valor |
|---|---|
| **Recogidos** | **601** |
| **Pasados** | **599** |
| **Fallidos** | **0** |
| **Errores** | **0** |
| **Saltados** | **2** |
| **Duración** | 969,85 s (~16 min) |
| **Veredicto (JUnit XML)** | **GREEN** |
| `EXIT` del proceso | `1` — **artefacto del entorno**, no un fallo (ver §5) |

## 2. Inventario por fichero

| Fichero | Casos | Tipo | Funcionalidad protegida |
|---|---|---|---|
| `test_model_gateway.py` | 73 | unit + contract | Gateway, proveedores, structured output, budget, pricing |
| `test_policy.py` | 46 | unit | Catálogo, matriz de permisos, Policy Engine |
| `test_f14_evaluation.py` | 43 | integration | Arnés de evaluación (F14) |
| `test_redaction.py` | 40 | unit + security | Redacción de secretos y filtro de logging |
| `test_workflow.py` | 39 | integration | Topología, routers, red de seguridad |
| `test_f4_supervisor_plan.py` | 38 | integration | Nodo `plan` |
| `test_f7_sandbox.py` | 36 | integration + security | Sandbox, confinamiento (4 barreras) |
| `test_f6_real_coder.py` | 33 | integration | Nodo `coder` |
| `test_f8_test_runner.py` | 30 | integration | Runner real, targets cerrados |
| `test_f3_interpret_analyst.py` | 28 | integration | Nodo `interpret` |
| `test_f9_reviewer.py` | 26 | integration | Reviewer + guardas |
| `test_api.py` | 26 | API + E2E | Capa HTTP, asincronía, `RF-03` |
| `test_f13_stt.py` | 24 | unit + API | STT (23 herméticas + 1 opt-in saltada) |
| `test_f10_api.py` | 23 | API + E2E | REST + SSE + hitos |
| `test_contracts.py` | 22 | contract | Invariantes de los contratos |
| `test_config_budget.py` | 18 | unit | Configuración y presupuesto |
| `test_f5_plan_driven_execution.py` | 15 | integration | Ejecución por `plan_index` |
| `test_diagram_layout.py` | 13 | unit | Geometría del diagrama (validación antes de dibujar) |
| `test_f12_promotion.py` | 11 | integration + security | Promoción al repo del usuario |
| `test_m2_e2e.py` | 9 | **E2E** | Cadena completa M2 con sandbox real |
| `test_store.py` | 7 | unit | Persistencia y eventos |
| `test_model_gateway_real.py` | 1 | **provider integration (opt-in)** | Llamada real — **SALTADA por diseño** |

## 3. Clasificación por tipo

| Tipo | Dónde |
|---|---|
| **Unit** | `test_policy`, `test_redaction`, `test_config_budget`, `test_store`, `test_diagram_layout`, parte de `test_contracts` |
| **Contract** | `test_contracts` (incluye serializabilidad y el contrato exportado) |
| **Integration** | `test_f3`..`test_f9`, `test_f10_api`, `test_f12`, `test_f13`, `test_f14`, `test_workflow` |
| **API / E2E** | `test_api`, `test_f10_api`, `test_m2_e2e` (sandbox real + pytest anidado) |
| **Security** | `test_redaction`, `test_f7_sandbox`, `test_f12_promotion`, `test_policy` |
| **Browser** | **Fuera de pytest**: `tools/verify_frontend.py` (15/15) — deuda `AUD-07` |
| **Mutation** | **Fuera de pytest**: `tools/mutation_check.py` (137 mutaciones definidas) |
| **Provider integration** | `test_model_gateway_real` (marcador `real_provider`, opt-in) |

## 4. Cobertura funcional: qué está protegido y qué no

### Protegido con evidencia fuerte

| Funcionalidad | Prueba |
|---|---|
| Contratos e invariantes cruzados | `test_contracts.py` |
| Policy Engine y matriz de permisos | `test_policy.py` (afirma conjuntos **exactos**) |
| Confinamiento del sandbox | `test_f7_sandbox.py` |
| Redacción de secretos | `test_redaction.py` + 8 mutaciones propias |
| Puertas HITL | `test_m2_e2e.py`, `test_f10_api.py` |
| Promoción con integridad | `test_f12_promotion.py` |
| Invariante `RF-03` (audio) | `test_api.py`, `test_f13_stt.py` |
| Terminación `MET-13` | `test_workflow.py` |
| Reglas del Reviewer (orden de guardas) | `test_f9_reviewer.py` |

### **Sin pruebas**

| Funcionalidad sin cobertura | Riesgo |
|---|---|
| `nodes.answer_direct` | Bajo (nodo inalcanzable) |
| `route_after_research`, `_ruta_estatica_m1`, `route_intent` | Bajo (huérfanos) |
| `src/ai_swe/agents/`, `mcp/`, `observability/` | N/A (vacías) |
| Rutas de excepción del motor (`abortar`) y recuperación de huérfanas | **MEDIO** — hay tests de `store`, pero no de que el worktree se limpie |
| `__main__.py` (arranque, `puerto()`) | BAJO-MEDIO — sin prueba directa |
| **El frontend dentro de pytest** | **MEDIO** — `AUD-07`: es un arnés aparte |
| Cabeceras de seguridad HTTP / CORS activo | BAJO (no existen) |
| STT con audio real | Declarado opt-in |

## 5. Sobre el `EXIT=1`

El proceso de pytest terminó con código 1 **y el resumen final truncado**, pero:

- El **JUnit XML** (escrito por pytest) dice `tests=601 failures=0 errors=0 skipped=2`.
- La **salida de progreso completa** (8 líneas, todas visibles) contiene solo `.` y
  una `s`: **ni una `F` ni una `E`**.

**Causa**: el guardia `safe-delete` del entorno aborta la limpieza masiva del
directorio temporal al cerrar la sesión, matando el proceso *después* de escribir el
informe. Ya ocurrió en F12 y F13. **El veredicto se lee del XML, no del código de
salida.** Se documenta aquí porque es una trampa real para quien repita la auditoría.

## 6. Mutación

| Bloque | Resultado registrado |
|---|---|
| F1-F2 | 35/35 |
| Redacción | 8/8 |
| F3 | 8/8 |
| F4 | 8/8 |
| F5 | 6/6 |
| F6 | 14/14 |
| F7 | 12/12 |
| F8 | 9/9 |
| F9 | 8/8 |
| M2 | 7/7 |
| F10 | **12/13** — una no cazada: guardia de concurrencia dependiente de temporización |
| F12 | 8/8 |
| F13 | 4/4 |
| F14 | 5/5 |
| **Total definido** | **137 mutaciones** |

> **No re-ejecutadas en esta auditoría.** Se registran los resultados de los cierres
> de fase. Ejecutar el arnés completo tardaría horas y **no** era necesario para el
> propósito de la auditoría. La única que conviene mirar es la de F10: es una prueba
> de concurrencia con hilos, y su veredicto **depende de la temporización**.

## 7. Conclusión

**IMPLEMENTED_AND_VERIFIED.** La suite es amplia (601 casos), corre offline, y las
funcionalidades críticas están protegidas con evidencia fuerte. La cultura de
mutación es real y está automatizada.

**Debilidades:**
1. El frontend se verifica **fuera** de pytest (`AUD-07`).
2. Una mutación de F10 no es fiablemente cazada.
3. Sin pruebas de las rutas de excepción/limpieza del worktree.
