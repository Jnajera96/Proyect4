# Baseline pre-estabilización

> **Fase 0 del plan de evolución controlada.** Este documento congela el estado del
> proyecto **antes** de tocar una sola línea de código. Su función es poder
> responder, dentro de tres fases, a la pregunta «¿esto ya estaba así?».

## 1. Identificación

| Campo | Valor |
|---|---|
| Proyecto | AI Software Engineering System (Proyecto 4, Equipo 4) |
| Repositorio | `C:/Users/jose_/Desktop/repo_proyect/proyecto4-ai-swe` |
| Rama | `main` |
| **HEAD (padre de este baseline)** | `065db452ad7ea4a1fe3ee58299ee8f1c1f7a8567` |
| Último commit | `065db45 feat(f14): implement experimental evaluation suite comparing single-agent vs multi-agent execution` |
| Tags | `m1-verified-baseline` (1) |
| Remotos | **ninguno** |
| Submódulos | ninguno |
| Árbol de trabajo | **limpio** salvo `docs/audit/` (36 ficheros sin commitear) |

**El commit de este mismo baseline** (`audit: preserve final project audit baseline`)
añade `docs/audit/` y este documento. **No** modifica `src/`, `tests/`, `frontend/`,
configuración ni contratos.

## 2. Verificación de correspondencia con la auditoría

| Comprobación | Resultado |
|---|---|
| `audit_commit` registrado en `AUDIT-SNAPSHOT.json` | `065db452ad7ea4a1fe3ee58299ee8f1c1f7a8567` |
| `HEAD` real | `065db452ad7ea4a1fe3ee58299ee8f1c1f7a8567` |
| ¿Coinciden? | **SÍ** |
| Ficheros de la auditoría | 36, **todos** bajo `docs/audit/` |
| ¿Cambios no explicados posteriores a la auditoría? | **NO** |

> **Conclusión**: la auditoría describe **exactamente** el árbol que se está
> congelando. No hay deriva entre lo auditado y lo real.

## 3. Estado funcional en el momento del baseline

| Métrica | Valor |
|---|---|
| Ficheros first-party | 150 |
| Tests recogidos | **601** |
| Fallos / errores | **0 / 0** |
| Saltos | 2 (opt-in por diseño: `real_provider`, `real_stt`) |
| Duración de la suite | ~970 s |
| Fases cerradas | M0, M1, F1..F14 |
| Endpoints HTTP | 12 |
| Nodos del grafo | 17 |
| Mutaciones definidas | 137 |

**Modo de operación**: `LOCAL-FIRST`, un solo usuario, binding `127.0.0.1`, sin
autenticación.

## 4. Riesgos conocidos (heredados de la auditoría)

Registrados aquí para poder **comprobar su cierre** en fases posteriores.

| ID | Riesgo | Severidad | Fase que debería cerrarlo |
|---|---|---|---|
| SEC-01 | `Dockerfile` arranca en `0.0.0.0` sin autenticación | CRITICAL (al desplegar) | 3 |
| SEC-02 | Ejecución de código del usuario sin aislamiento de proceso | HIGH | **4** |
| SEC-03 | `ApproveRequest.decision` con default `APPROVED` | HIGH | **2** |
| SEC-04 | `authorized_repos` declarado y no aplicado | HIGH | **2** |
| SEC-05 | Subida de audio sin límite de tamaño ni validación de tipo | MEDIUM | 3 |
| SEC-06 | Prompt injection indirecta desde el contenido del repositorio | MEDIUM | 3 |
| SEC-07 | Sin aislamiento de red en la ejecución de pruebas | MEDIUM | **4** |
| SEC-08 | Sin límites de CPU/memoria/procesos | MEDIUM | **4** |
| SEC-09 | Conexiones SSE y paginación sin tope | MEDIUM | 3 |
| SEC-10 | Sin cabeceras de seguridad ni `TrustedHost` | LOW | 3 |
| SEC-11 | El worktree no se limpia en rutas de excepción | LOW | 3 |
| SEC-12 | Credenciales placeholder en `docker-compose` | LOW | 3 |
| SEC-13 | Sin observabilidad ni alertas | LOW | **8** |
| SEC-14 | Sin migraciones de esquema | LOW | 7 |
| SEC-15 | Sin retención ni purga de datos | LOW | 7 |
| TD-01 | **Nunca se ha ejecutado contra un modelo real** | ALTO (académico) | **5** |

## 5. Deuda técnica conocida (no de seguridad)

| ID | Deuda | Fase |
|---|---|---|
| D-01 | 74 ficheros scratch + 2 directorios `tmp*` en la raíz | **1** |
| D-02 | `README.md` y `src/ai_swe/__init__.py` dicen «fase M0/F2» | **1** |
| D-03 | Doble nomenclatura en `docs/` (`01-ARCHITECTURE` vs `01-arquitectura`) | **1** |
| D-04 | 3 placeholders vacíos: `agents/`, `mcp/`, `observability/` | **1** (parcial) |
| D-05 | Fragmento huérfano de M1: `answer_direct`, `route_after_research`, `_ruta_estatica_m1`, `route_intent` | **1** |
| D-06 | Campos muertos: `dry_run`, `TestRun.reproducible`, `Subtask.status/attempts`, `schema_version` | **2** |
| D-07 | 5 ajustes declarados y no aplicados | **2** |
| D-08 | `state_db_path` leído por `os.environ` en lugar de `Settings` | **2** |
| D-09 | `pytest-asyncio`, `langfuse`, `mcp` declarados sin consumidor | **1 / 8 / 9** |
| D-10 | `POST /runs/{id}/cancel` devuelve 501 | **7** |
| D-11 | `graph/nodes.py` concentra el dominio (~2.500 líneas) | **14** (solo tras validar) |

## 6. Invariantes que NO deben romperse en ninguna fase

1. `RF-03`: el audio crudo **nunca** llega al Supervisor ni al modelo.
2. La única arista al repositorio del usuario pasa por la **puerta humana**.
3. **Ningún** nodo importa directamente un SDK de proveedor: todo pasa por `ModelGateway`.
4. `shell=False` en **todo** `subprocess`; catálogo sin `run_shell` ni `git_push`.
5. La escritura del Coder se confina con **cuatro barreras** (la cuarta es física).
6. Ninguna ejecución queda sin estado terminal (`MET-13 = 0`).
7. Los secretos no se versionan, no se registran en claro y se redactan en SSE.

## 7. Próxima fase

| | |
|---|---|
| **Fase** | 1 — Limpieza segura y documentación |
| **Objetivo** | Eliminar ruido sin modificar comportamiento; consolidar documentación |
| **Riesgo estimado** | **BAJO** (borrado de scratch, archivado de histórico, corrección de README). El único punto medio es retirar el fragmento huérfano de M1, y solo si se demuestra inalcanzable |
| **Entregable** | `docs/BASELINE-POST-CLEANUP.md` + commit `chore: clean repository and consolidate documentation` |
| **Condición de parada** | Autorización humana explícita |

## 8. Veredicto

**PHASE_0_READY = YES**

El baseline está congelado, la auditoría commiteada y verificada, y el árbol queda
limpio. No se ha modificado ni una línea del código del producto.
