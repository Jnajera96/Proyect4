# Informe maestro de auditoría — AI Software Engineering System

> **Auditoría integral de solo lectura.** Commit `065db452ad7ea4a1fe3ee58299ee8f1c1f7a8567`
> (`feat(f14)`, rama `main`, árbol limpio, sin remotos, sin submódulos, 1 tag).
> Fecha 2026-10-12. **No se modificó nada del proyecto**; los únicos ficheros
> creados están en `docs/audit/`.

---

## 1. Executive summary

Sistema multiagente local para tareas de ingeniería de software sobre un repositorio
autorizado. **150 ficheros first-party**, 76 de código Python, 601 pruebas, 12
endpoints, una SPA React y 35 documentos.

**Funciona de verdad**: crea un `git worktree`, ejecuta `pytest` real, revisa con
evidencia, se detiene en dos puertas humanas y promueve el cambio aprobado.

**Verificado en esta auditoría**: 601 tests / 0 fallos / 0 errores / 2 saltos.

**El hallazgo más importante**: **cinco controles declarados que no se aplican**
(allowlist de repositorios, bloqueo de red, y tres límites de presupuesto).

**El segundo**: `ApproveRequest.decision` tiene **default `APPROVED`** — una petición
vacía promueve cambios al repositorio del usuario.

**El tercero**: el `Dockerfile` abre la API en `0.0.0.0` **sin autenticación**,
anulando la mitigación que el código implementa deliberadamente.

**Lo mejor**: el eje `Policy Engine + catálogo cerrado + confinamiento en 4 barreras
+ puertas HITL + promoción con integridad`. Es mínimo privilegio real, no declarado.

## 2. Identidad del proyecto

| Campo | Valor |
|---|---|
| Nombre | AI Software Engineering System (Proyecto 4) |
| Equipo | Equipo 4 — *Agentic Workflows, Multi-Agent, MCP, State y coordinación* |
| Materia | Arquitectura de Sistemas de Inteligencia Artificial |
| Versión | `0.1.0` |
| Alcance declarado | Prototipo local de un usuario; sin autenticación (`AUD-06`) |
| Fases | M0, M1, F1..F14 (todas cerradas) |

## 3. Estado del repositorio

```
raíz          C:/Users/jose_/Desktop/repo_proyect/proyecto4-ai-swe
rama          main
HEAD          065db452ad7ea4a1fe3ee58299ee8f1c1f7a8567
árbol         limpio
tags          m1-verified-baseline
remotos       (ninguno)
submódulos    (ninguno)
```

## 4. Inventario completo

150 ficheros versionados: 76 `.py`, 43 `.md`, 12 frontend, 12 configuración.
Detalle en `01-FILE-INVENTORY.md` y `file-inventory.json`.

**Ruido**: 74 ficheros `_*` y 2 directorios `tmp*` en la raíz (ignorados, presentes).
**Dependencias**: `frontend/node_modules` (2.544 ficheros, 62,8 MB, ignorado),
`frontend/dist` (5 ficheros, ignorado), `var/` (parcialmente versionado).

## 5. Arquitectura funcional

`interpret → [puerta 1] → plan → researcher → coder → apply_sandbox → run_tests →
reviewer → (ciclo) → mark_awaiting → [puerta 2] → promote_changes → finalize`

17 nodos, 2 puertas HITL, 1 único punto de escritura irreversible. Detalle en
`02-FUNCTIONAL-INVENTORY.md` y `08-WORKFLOW-AUDIT.md`.

## 6. Backend

12 endpoints FastAPI, 6 handlers de error tipados, SSE con reconexión
(`Last-Event-ID`), reserva atómica de reanudación. **Sin autenticación**, sin rate
limiting, sin límite de subida, sin tope en paginación. Detalle en
`06-BACKEND-API-AUDIT.md`.

## 7. Frontend

React 18 + TS + Vite, **1 pantalla** (`App.tsx`, 476 líneas), 5 componentes, sin
router, sin mocks, **3 dependencias de runtime**. Cubre el ciclo completo. Verificado
15/15 en motor real, **fuera de pytest** (`AUD-07`). Detalle en `15-FRONTEND-AUDIT.md`.

## 8. Arquitectura de IA

`ModelGateway` como fachada única; **ningún agente importa un SDK de proveedor**
(verificado). Salida estructurada validada contra Pydantic en el borde del gateway.
Fallback determinista por nodo, **declarado** (`MODEL_FALLBACK`). Presupuesto
aplicado en los 4 puntos de uso. Detalle en `10-MODEL-INFRASTRUCTURE-AUDIT.md`.

## 9. Agentes

**4 puntos de uso del modelo** (`interpret`, `plan`, `coder`, `reviewer`). El
`researcher` es **determinista**. Decir «cinco agentes de IA» sería inexacto.
Los agentes viven en `graph/nodes.py`; `src/ai_swe/agents/` está **vacío**.
Detalle en `09-AGENT-AUDIT.md`.

## 10. Hugging Face

**No existe adaptador de Hugging Face como LLM.** Lo que hay es
`OpenAICompatibleAdapter`. Hugging Face aparece como **origen de los pesos** de
`faster-whisper` (STT). Es una **corrección de expectativa**, no un defecto.

## 11. Speech-to-Text

`FasterWhisperAdapter` local, carga perezosa, `health()` sin cargar el modelo,
dependencia opcional (503 si falta). **`RF-03` protegida en tres capas**: el
adaptador no puede devolver audio, el contrato exige confirmación y la API lo mapea
a 422. **No existe el camino `voz → ejecución automática`.** Detalle en `11-STT-AUDIT.md`.

## 12. LangGraph

17 nodos, topología fija, dos puertas, bucles acotados, red de seguridad `MET-13`.
**Fragmento huérfano de M1**: `answer_direct` (inalcanzable), `route_after_research`,
`_ruta_estatica_m1`, `route_intent`. **Rutas de excepción no limpian el worktree.**
Detalle en `08-WORKFLOW-AUDIT.md`.

## 13. Herramientas

11 en el catálogo (**6 con executor real**), matriz de permisos por rol afirmada por
tests, Policy Engine puro con 6 reglas en orden justificado. **Sin `run_shell` ni
`git_push`.** `shell=False` en los 3 puntos de `subprocess`. Detalle en
`12-TOOLS-POLICY-AUDIT.md`.

## 14. Sandbox

`git worktree` por ejecución, confinamiento en **4 barreras** (la cuarta es física).
Cumple su objetivo: **el Coder no ensucia el repo del usuario antes de la aprobación**.
**No es una jaula**: sin límites de CPU/memoria/procesos, sin aislamiento de red, sin
aislamiento de proceso. Detalle en `13-SANDBOX-EXECUTION-AUDIT.md`.

## 15. Datos

SQLite con checkpoint de LangGraph + índice de ejecuciones + registro de eventos.
**Sin migraciones**, **sin retención**, **sin purga**. `schema_version` se escribe y
no se lee. Detalle en `07-CONTRACTS-DATA-AUDIT.md` y `27-DATA-PRIVACY-AUDIT.md`.

## 16. Tests

**601 casos, 0 fallos, 2 saltos, 969 s.** 22 ficheros. Frontend fuera de pytest.
137 mutaciones definidas (una de F10 no es fiablemente cazada). Detalle en
`14-TEST-COVERAGE-AUDIT.md`.

## 17. Documentación

43 Markdown. **Dos contradicciones graves**: `README.md` dice «fases M0, M1, F1, F2
completadas» y `ai_swe/__init__.py` dice «fase M0 (diseño)». **Doble nomenclatura**
en `docs/`. Detalle en `05-DOCUMENTATION-AUDIT.md`.

## 18. Dependencias

Lockfiles presentes, techos de versión mayor justificados, extras bien separados.
**Tres declaradas sin consumidor**: `langfuse`, `mcp`, `pytest-asyncio`. **`ruff`
está configurado y no instalado** (el lint no se ejecuta). Detalle en
`24-DEPENDENCY-AUDIT.md`.

## 19. Seguridad

**Sin secretos versionados** (escaneo negativo; `.env` ausente y no versionado).
Sin `shell=True`, sin `eval`/`exec`/`pickle.loads`. Redacción de secretos en logs
**y** en SSE, protegida por mutaciones. **15 hallazgos** registrados en `20-…`.
Detalle en `19-THREAT-MODEL.md` y `20-SECURITY-RISK-REGISTER.md`.

## 20. Threat model

Activos, actores, 6 fronteras de confianza, 10 superficies, 7 casos de abuso.
El caso de abuso más accionable es **CU-4: aprobación por defecto**. Detalle en
`19-THREAT-MODEL.md`.

## 21. Infraestructura

`Dockerfile` + `docker-compose` de desarrollo. **D1**: abre `0.0.0.0`.
**D2**: no copia el frontend. Sin CI/CD, TLS, proxy, backups ni monitorización.
Detalle en `23-INFRASTRUCTURE-AUDIT.md`.

## 22. Privacidad

**La voz está resuelta de forma ejemplar**: el audio nunca se persiste.
**El código no**: la instrucción, los hallazgos y el diff se envían al proveedor del
modelo **sin que la interfaz lo advierta**, y nada se borra nunca. Detalle en
`27-DATA-PRIVACY-AUDIT.md`.

## 23. Rendimiento

Adecuado para el caso previsto. Puntos a arreglar (baratos): `GET /health` hace dos
consultas con hasta 2.000 filas por sonda; `limit` sin tope; `_locks` no se limpia.
El límite estructural (SQLite, un escritor) está declarado. Detalle en
`26-PERFORMANCE-AUDIT.md`.

## 24. Acciones del usuario

**5 antes de la defensa**, 5 antes del MVP, 10 antes del despliegue. Detalle en
`18-USER-ACTIONS-REQUIRED.md`.

## 25. Candidatos de limpieza

74 scratch + 2 temporales + 3 placeholders + 1 fragmento huérfano + 4 campos muertos
+ doble nomenclatura de `docs/`. Detalle en `04-CLEANUP-CANDIDATES.md`.

## 26. Brechas funcionales

10 planeadas y no implementadas, 10 parciales, 10 necesarias para cerrar, 8
eliminables, 9 opcionales. Detalle en `28-FEATURE-GAP-ANALYSIS.md`.

## 27. Preparación del frontend

**22 de 28 capacidades con datos disponibles hoy.** Solo 6 (ajustes) requieren
backend nuevo. Sin mocks. Detalle en `16-…`, `17-…`, `31-…` y `32-…`.

## 28. Hoja de ruta de ciberseguridad

P0 (2), P1 (5), P2 (6), P3 (7), P4 (4). Detalle en `22-CYBERSECURITY-HARDENING-PLAN.md`.

## 29. Secuencia de limpieza recomendada

```
1. Borrar scratch + temporales + cachés         (riesgo nulo)
2. Reescribir README y docstring del paquete    (riesgo nulo)
3. Resolver la doble nomenclatura de docs/      (bajo)
4. Archivar docs/history/                       (bajo)
5. Decidir placeholders + fusionar verify_redaction (bajo)
6. Retirar el fragmento huérfano de M1          (medio)
7. Dividir graph/nodes.py                       (ALTO — solo tras la entrega)
```

## 30. Secuencia del frontend recomendada

```
A. Router + URL por ejecución + historial + panel de presupuesto   (sin backend)
B. Formulario de alcance + trazabilidad + estado por subtarea      (sin backend)
C. Voz (grabar → transcribir → confirmar) + panel de seguridad     (sin backend)
D. Pantallas de escalada/fallo/cancelado + accesibilidad           (sin backend)
E. Ajustes (modelo, coste) + cancelar + purga                      (CON backend)
```

## 31. Secuencia de endurecimiento recomendada

```
P0-1  --host 127.0.0.1 en el Dockerfile (1 línea)   ← elimina el único CRITICAL
P1-1  ApproveRequest.decision obligatorio (1 línea) ← elimina la aprobación por defecto
P1-2  Aplicar (o retirar) authorized_repos
P1-3  Límite y validación en la subida de audio
P2-3  Tope en limit + límite de conexiones SSE
P2-4  Cabeceras de seguridad
P1-5 + P0-2  Auth + aislamiento real de la ejecución (los dos grandes, juntos)
```

## 32. Veredicto final

| VEREDICTO | VALOR |
|---|---|
| `PROJECT_FUNCTIONAL_STATUS` | **COMPLETE** (para el alcance declarado) |
| `CLEANUP_READY` | **YES** |
| `CYBERSECURITY_HARDENING_READY` | **YES** |
| `FRONTEND_REDESIGN_READY` | **YES** |
| `PRODUCTION_READY` | **NO** |

**El proyecto está mucho mejor construido de lo que su documentación dice de sí
mismo.** El problema no es lo que falta, sino **cinco controles que se declaran y no
se aplican** y **dos frases desactualizadas** que harían pensar a un tribunal que el
trabajo está a medias.

---

## Índice de documentos

`00-EXECUTIVE-AUDIT` · `01-FILE-INVENTORY` (+`file-inventory.json`) ·
`02-FUNCTIONAL-INVENTORY` · `03-INTERNAL-DEPENDENCY-MAP` · `04-CLEANUP-CANDIDATES` ·
`05-DOCUMENTATION-AUDIT` · `06-BACKEND-API-AUDIT` · `07-CONTRACTS-DATA-AUDIT` ·
`08-WORKFLOW-AUDIT` · `09-AGENT-AUDIT` · `10-MODEL-INFRASTRUCTURE-AUDIT` ·
`11-STT-AUDIT` · `12-TOOLS-POLICY-AUDIT` · `13-SANDBOX-EXECUTION-AUDIT` ·
`14-TEST-COVERAGE-AUDIT` · `15-FRONTEND-AUDIT` · `16-FRONTEND-BACKEND-MAPPING` ·
`17-FRONTEND-CAPABILITY-PLAN` · `18-USER-ACTIONS-REQUIRED` · `19-THREAT-MODEL` ·
`20-SECURITY-RISK-REGISTER` · `21-CYBERSECURITY-MATURITY` ·
`22-CYBERSECURITY-HARDENING-PLAN` · `23-INFRASTRUCTURE-AUDIT` · `24-DEPENDENCY-AUDIT` ·
`25-CONFIGURATION-AUDIT` · `26-PERFORMANCE-AUDIT` · `27-DATA-PRIVACY-AUDIT` ·
`28-FEATURE-GAP-ANALYSIS` · `29-PROJECT-COMPLETENESS-MATRIX` ·
`30-PROPOSED-CLEAN-ARCHITECTURE` · `31-FRONTEND-FUNCTIONAL-SPEC` ·
`32-FRONTEND-DESIGN-READINESS` · `AUDIT-SNAPSHOT.json` · `FINAL-PROJECT-AUDIT`
