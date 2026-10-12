# 29 — Matriz de completitud del proyecto

> Commit `065db452`. ✅ = sí · ⚠️ = parcial · ❌ = no · — = no aplica.
> `Evidence` apunta a la prueba o al fichero que lo sostiene.

| Component | Implemented | Connected | Tested | Documented | Secure | Frontend | Production Ready | Evidence |
|---|---|---|---|---|---|---|---|---|
| **Projects** | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ (oculto en `<details>`) | ⚠️ | `POST /projects`, `test_f10_api.py` |
| **Runs** | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | `POST /runs` 202, `test_api.py` |
| **Events (SSE)** | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | `GET /runs/{id}/events`, `test_f10_api.py` |
| **FastAPI** | ✅ | ✅ | ✅ | ✅ | ⚠️ | — | ⚠️ | 12 endpoints, 6 handlers |
| **Database** | ✅ | ✅ | ✅ | ✅ | ⚠️ | — | ❌ | SQLite + checkpoint; sin migraciones ni purga |
| **LangGraph** | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | 17 nodos, red de seguridad `MET-13` |
| **RunState** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `contracts/state.py`; `schema_version` sin migraciones |
| **HITL** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 2 puertas; `test_m2_e2e.py`, `test_f10_api.py` |
| **ModelGateway** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | `models/gateway.py`; 73 tests |
| **Hugging Face (como LLM)** | ❌ | ❌ | ❌ | ❌ | — | ❌ | ❌ | **No existe adaptador** |
| **Hugging Face (como origen de pesos STT)** | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ❌ | ⚠️ | `faster-whisper` descarga pesos |
| **Requirements Analyst** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_f3_interpret_analyst.py` |
| **Supervisor** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_f4_supervisor_plan.py` |
| **Researcher** | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | Determinista; `test_f5_…` |
| **Coder** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_f6_real_coder.py` |
| **Reviewer** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_f9_reviewer.py`; `AUD-14` resuelto en F14 |
| **Tools** | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | 11 declaradas, 6 con executor |
| **Policy Engine** | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | `test_policy.py` (conjuntos exactos) |
| **Sandbox** | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | — | ❌ | Confina escritura; **no aísla el proceso** |
| **Tests** | ✅ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ✅ | 601 casos; frontend fuera de pytest (`AUD-07`) |
| **STT** | ✅ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ⚠️ | Backend completo; **sin UI** |
| **Knowledge Graph** | ❌ | ❌ | ❌ | ⚠️ (propuesta) | — | ❌ | ❌ | `docs/05-graphify-evaluacion.md` `[PROP]` |
| **Graphify** | ❌ | ❌ | ❌ | ⚠️ | — | ❌ | ❌ | Idem |
| **MCP** | ❌ | ❌ | ❌ | ⚠️ | — | ❌ | ❌ | Placeholder de 13 líneas |
| **Frontend** | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | 1 pantalla, 2.311 líneas; verificado 15/15 aparte |
| **Authentication** | ❌ | ❌ | ❌ | ✅ (declarado) | ❌ | ❌ | ❌ | `AUD-06` |
| **Observability** | ❌ | ❌ | ❌ | ⚠️ | — | ❌ | ❌ | Placeholder; ajustes sin consumidor |
| **Evaluation** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ⚠️ | F14: 13 tareas, `EXP-01`; informe GENERADO |
| **Promotion (F12)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_f12_promotion.py` |
| **Secret redaction** | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | `test_redaction.py` + mutaciones |
| **Configuration** | ✅ | ⚠️ | ✅ | ✅ | ⚠️ | — | ⚠️ | 5 ajustes declarados y no aplicados |
| **Deployment** | ⚠️ | ❌ | ❌ | ⚠️ | ❌ | ❌ | ❌ | `Dockerfile` abre `0.0.0.0`; sin TLS/CI/backups |

## Agregados

| Dimensión | ✅ | ⚠️ | ❌ |
|---|---|---|---|
| **Implemented** | 22 | 3 | 6 |
| **Connected** | 21 | 2 | 8 |
| **Tested** | 20 | 3 | 8 |
| **Documented** | 24 | 7 | 1 |
| **Secure** | 12 | 10 | 4 |
| **Frontend** | 11 | 3 | 13 |
| **Production Ready** | 13 | 10 | 7 |

## Lectura

- **El núcleo funcional está completo y conectado**: proyectos, ejecuciones, eventos,
  las dos puertas HITL, los cuatro agentes, el Model Gateway, las herramientas, la
  política, el sandbox (en su objetivo), la evaluación y la promoción.
- **Lo que falta es de tres tipos concretos**:
  1. **Periferia declarada y no implementada**: MCP, observabilidad, auth, TTS.
  2. **Controles declarados y no aplicados**: allowlist, límites de red y presupuesto.
  3. **Capacidades reales sin interfaz**: presupuesto, alcance, voz, trazabilidad.
- **`Secure` es la columna con más ámbar**: 10 componentes en `⚠️`. No porque haya
  vulnerabilidades explotables en local, sino porque **no están preparados para
  exponerse**.
- **`Production Ready` refleja la realidad**: el sistema está listo para ejecutarse
  **en la máquina de su autor**, no para desplegarse.

## Estado global

**PROJECT_FUNCTIONAL_STATUS = COMPLETE** para el alcance declarado (prototipo local
de un usuario), **INCOMPLETE** si se mide contra un producto desplegable.
