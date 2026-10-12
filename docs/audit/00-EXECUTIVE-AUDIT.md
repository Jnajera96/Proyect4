# 00 — Resumen ejecutivo de la auditoría

**AI SOFTWARE ENGINEERING SYSTEM** · Equipo 4
**Commit auditado**: `065db452ad7ea4a1fe3ee58299ee8f1c1f7a8567` (`feat(f14)`, rama `main`, árbol limpio)
**Fecha**: 2026-10-12 · **Modalidad**: auditoría de **solo lectura** — no se modificó,
borró, movió ni refactorizó nada del proyecto. Los únicos ficheros creados son los de
`docs/audit/`.

---

## Las quince preguntas

### 1. ¿Qué tenemos realmente?

Un **sistema multiagente local y funcional** para tareas de ingeniería de software
sobre un repositorio autorizado. 150 ficheros first-party, 76 de código Python
(~8.500 líneas en `src/`), 601 pruebas, 12 endpoints HTTP, una SPA React de una
pantalla y 35 documentos.

No es un prototipo de laboratorio: **ejecuta de verdad**. Crea un `git worktree`
real, ejecuta `pytest` real dentro, revisa con evidencia real, se detiene en **dos
puertas humanas**, y **promueve** el cambio aprobado al repositorio del usuario.

### 2. ¿Qué funciona?

Lo verifiqué ejecutando, no leyendo:

| Comprobación | Resultado |
|---|---|
| Suite completa | **601 tests, 0 fallos, 0 errores, 2 saltos** (969 s) |
| Cadena funcional | Proyecto → ejecución → SSE → puerta 1 → plan → research → coder → sandbox → pruebas → reviewer → puerta 2 → promoción → informe |
| Policy Engine + catálogo cerrado | Conjuntos de permisos **afirmados por tests** |
| Confinamiento del sandbox | 4 barreras, con tests |
| Promoción con integridad SHA256 | `test_f12_promotion.py` |
| Invariante `RF-03` (audio) | Protegida en **tres capas** independientes |
| Frontend en motor real | 15/15 (`tools/verify_frontend.py`) |
| Evaluación comparativa | 13 tareas × 2 modos, reproducible |

### 3. ¿Qué no funciona?

- **Nada del núcleo está roto.** No encontré ninguna funcionalidad declarada como
  implementada que no funcione.
- Lo que **no funciona** es lo que **no existe**: MCP, observabilidad, autenticación,
  TTS, cancelación (`501`), adaptador de Hugging Face como LLM.

### 4. ¿Qué está incompleto?

**Cinco controles declarados que no se aplican** — el hallazgo más importante:

| Ajuste | Promete | Realidad |
|---|---|---|
| `AI_SWE_AUTHORIZED_REPOS` | Lista blanca de repositorios | **No se lee en ningún sitio** |
| `AI_SWE_NETWORK_EGRESS_ENABLED` | Bloquear red del sandbox | **No se lee** |
| `AI_SWE_MAX_TOKENS_PER_RUN` | Límite de tokens | **No se lee** (el `Budget` usa defaults del contrato) |
| `AI_SWE_MAX_TOOL_CALLS_PER_RUN` | Límite de llamadas | **No se lee** |
| `AI_SWE_MAX_SECONDS_PER_RUN` | Límite de tiempo | **No se lee** |

Un operador que los configure creerá estar limitando el sistema y **no lo estará**.

### 5. ¿Qué sobra?

- **74 ficheros scratch** (`_*.txt|xml|log`) y **2 directorios `tmp*`** olvidados en la raíz.
- **3 módulos placeholder** sin una sola línea de código ni importadores: `agents/`,
  `mcp/`, `observability/`.
- **Un fragmento huérfano de M1**: `answer_direct` (nodo inalcanzable),
  `route_after_research`, `_ruta_estatica_m1`, `route_intent`.
- **4 campos muertos** en contratos: `dry_run`, `TestRun.reproducible`,
  `Subtask.status`/`attempts` (nadie los escribe), `schema_version` (nadie lo lee).
- **Doble nomenclatura en `docs/`**: `01-ARCHITECTURE.md` y `01-arquitectura.md`
  coexisten; `06-EVALUATION.md` y `06-contrato-frontend-backend.md` comparten número
  sin relación.

### 6. ¿Qué puede eliminarse?

Con alta confianza: los scratch, los temporales y las cachés. Con confianza media:
los placeholders y `data/tasks/README.md`. Detalle y riesgo en `04-…` y `30-…`.
**No he borrado nada.**

### 7. ¿Qué debe conservarse?

- `contracts/` — fuente única de verdad, con exportación verificada.
- El **Policy Engine + catálogo cerrado + sandbox**: mínimo privilegio real.
- Las **dos puertas HITL** y la promoción con integridad.
- Los 7 `BASELINE-*.md` — son la prueba de que cada fase se cerró.
- El frontend **sin dependencias de UI** (3 paquetes de runtime).

### 8. ¿Qué necesita completar el usuario?

**Cinco cosas antes de la defensa** (detalle en `18-…`):

1. Configurar una clave de modelo real y ejecutar el test opt-in → cierra `TD-01`.
2. Rellenar `AI_SWE_MODEL_PRICING` → da datos a `MET-06`.
3. **Decidir si la API se expone.** Si sí: **no desplegar el `Dockerfile` actual**.
4. Corregir `README.md` y `ai_swe/__init__.py` (dicen «fase M0/F2»).
5. Autorizar la limpieza.

### 9. ¿Cuáles son los principales riesgos de seguridad?

**Ninguno es crítico en uso local.** El riesgo crítico aparece al desplegar:

| # | Riesgo | Severidad |
|---|---|---|
| 1 | El `Dockerfile` arranca en `0.0.0.0` **sin autenticación** | **CRITICAL (al desplegar)** |
| 2 | Ejecución de código del usuario **sin aislamiento de proceso** | HIGH |
| 3 | `ApproveRequest.decision` tiene **default `APPROVED`**: un `{}` promueve cambios | HIGH |
| 4 | Lista blanca de repositorios **declarada y no aplicada** | HIGH |
| 5 | Subida de audio **sin límite de tamaño** | MEDIUM |

Y lo que está **bien**: sin `shell=True`, sin `eval`/`exec`/`pickle.loads`, sin
secretos versionados, sin `innerHTML` en el frontend, escritura confinada por cuatro
barreras, y redacción de secretos protegida por mutaciones.

### 10. ¿Qué hay que corregir antes del MVP?

`ApproveRequest.decision` (1 línea), la allowlist de repositorios, el límite de
subida de audio, y decidir el alcance de la entrega. **Coste bajo.**

### 11. ¿Qué hay que corregir antes de producción?

Autenticación, aislamiento real de la ejecución (contenedor con `--network none`,
`--memory`, `--pids-limit`), TLS, límites de recursos, monitorización, backups,
retención de datos y `--host 127.0.0.1` en el `Dockerfile`. **Es trabajo de otra
fase, no de esta entrega.**

### 12. ¿Está listo para rediseñar el frontend?

**SÍ.** 22 de 28 capacidades del backend **ya tienen datos disponibles** y solo 6
(todas de ajustes) requieren backend nuevo. El frontend actual **no tiene mocks ni
datos simulados**. Con tres correcciones pequeñas, se puede rediseñar sin tocar el
backend.

### 13. ¿Está listo para exposición académica?

**SÍ, y con margen.** El proyecto tiene lo que un tribunal valora: una **pregunta
central** respondida con evidencia reproducible (`docs/06-EVALUATION.md`), una
**arquitectura defendible** (mínimo privilegio, HITL, estado tipado), y una
**cultura de verificación real** (601 tests, 137 mutaciones, un arnés de navegador).

Lo que hay que corregir antes de exponerlo son **dos frases**: el `README` y el
docstring del paquete dicen que el proyecto está en la fase M0/F2.

### 14. ¿Está listo para uso real?

**SÍ, para uso local por su autor.** No para desplegarse, ni para varios usuarios, ni
sobre código de terceros sin revisar.

### 15. ¿Cuál debe ser el siguiente paso?

```
1. Corregir el README y el docstring del paquete        (30 min)
2. ApproveRequest.decision obligatorio                   (5 min)
3. Decidir el alcance de la entrega                     (decisión)
4. Cerrar la limpieza de scratch y placeholders         (1 h)
5. Rediseñar el frontend sobre las 22 capacidades       (trabajo real)
```

---

## Veredictos finales

| VEREDICTO | VALOR | Explicación |
|---|---|---|
| **PROJECT_FUNCTIONAL_STATUS** | **COMPLETE** | Para el alcance declarado (prototipo local, un usuario), la cadena funcional está cerrada y verificada. Medido contra un producto desplegable sería **INCOMPLETE**: faltan auth, aislamiento de ejecución y operación |
| **CLEANUP_READY** | **YES** | Los candidatos de alta confianza (scratch, temporales, cachés) son de riesgo nulo. Los de confianza media están identificados con su riesgo |
| **CYBERSECURITY_HARDENING_READY** | **YES** | El plan está priorizado (`22-…`) y las dos acciones P0 son pequeñas; la única estructural (aislar la ejecución) está acotada |
| **FRONTEND_REDESIGN_READY** | **YES** | 22 capacidades con datos disponibles hoy; sin mocks; contrato estable y verificado |
| **PRODUCTION_READY** | **NO** | Sin autenticación, sin aislamiento de la ejecución de código, sin TLS, sin límites de recursos, sin backups, sin monitorización. Y el `Dockerfile` **abre la API a la red** |

---

## Una frase

**El proyecto está mucho mejor construido de lo que su documentación dice de sí
mismo.** El código afirma ser un prototipo de la fase M0 y es un sistema completo
con 601 pruebas y una evaluación empírica; el `README` promete menos de lo que hay.
El problema no es lo que falta, sino **cinco controles que se declaran y no se
aplican** y **dos frases desactualizadas** que harían pensar a un tribunal que el
trabajo está a medias.
