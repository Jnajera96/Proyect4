# 01 — Inventario de ficheros

> **Auditoría de solo lectura.** Commit auditado: `065db452ad7ea4a1fe3ee58299ee8f1c1f7a8567`
> (`feat(f14)`, rama `main`, árbol limpio). Datos medidos mecánicamente por
> `file-inventory.json` (mismo directorio). No se modificó nada.

## Resumen

| Métrica | Valor |
|---|---|
| Ficheros first-party versionados | **150** |
| Ficheros `.py` | 76 |
| Ficheros `.md` | 43 |
| Ficheros `.tsx` / `.ts` | 7 / 5 |
| Ficheros de configuración / build | 12 |
| Artefactos scratch en la raíz (`_*`) | **74** |
| Directorios temporales olvidados (`tmp*`) | **2** (`tmp8g9yx7zt`, `tmpq6zgqajo`) |
| Repositorio | git, sin remotos, sin submódulos, 1 tag (`m1-verified-baseline`) |

## Distribución por propietario

| Owner | Ficheros | Función |
|---|---|---|
| `docs/` | 44 | Documentación (diseño, actas de fase, auditorías, diagramas) |
| `tests/` | 22 | Suites de prueba (22 ficheros, 601 casos) |
| `frontend/` | 18 | SPA React + TypeScript + Vite |
| `tools/` | 12 | Arnés de verificación (mutación, contratos, frontend, diagrama) |
| `(raíz)` | 12 | Manifiestos, contenedor, README, snapshot |
| `models/` | 11 | Model Gateway, proveedores, presupuesto, tarifas |
| `contracts/` | 7 | Contratos Pydantic (estado, tareas, salidas, API, herramientas) |
| `graph/` | 5 | Motor, nodos, topología, trabajador |
| `(paquete raíz)` | 4 | `__init__`, `__main__`, `config`, `sandbox` |
| `evaluation/` | 3 | Arnés de evaluación experimental (F14) |
| `security/`, `state/`, `stt/`, `api/`, `tools(pkg)` | resto | Seguridad, persistencia, STT, HTTP, herramientas |

## Directorios de dependencias y artefactos

| Ruta | Ficheros | Tamaño | ¿Ignorado? | Función |
|---|---|---|---|---|
| `frontend/node_modules` | 2.544 | 62,8 MB | **Sí** (`frontend/node_modules/`) | Dependencias npm |
| `frontend/dist` | 5 | 0,2 MB | **Sí** (`frontend/dist/`) | Build de Vite; **es lo que sirve la API** |
| `var/` | 2 | 0,7 MB | **Parcial** | `evaluation_results.json` **se versiona** (excepción F14); el resto (BD, workspaces) se ignora |
| `.pytest_cache` | 5 | ~0 | Sí | Caché de pytest |
| `.pytest_tmp` | 6 | 0,4 MB | Sí | Temporal de pytest |

> **Nota sobre `var/`.** El `.gitignore` pasó de `/var/` a `/var/*` +
> `!/var/evaluation_results.json` en F14. La consecuencia es que `git check-ignore`
> ya **no** marca `var/` como ignorado (solo su contenido salvo la excepción). Es
> correcto, pero conviene saberlo: un `git add var/` añadiría el fichero de
> resultados y nada más.

## Ruido en la raíz del repositorio

**74 ficheros `_*.txt|xml|log` y `_repro_*.py`, más 2 directorios `tmp*`.** Todos
están cubiertos por `.gitignore` (`_*.xml`, `_*.txt`, `_*.log`, `_repro_*.py`,
`/tmp*/`), así que **no están versionados** — pero sí están en disco y ensucian el
árbol de trabajo. Son registros de las suites y mutaciones de F7..F14 que el propio
`.gitignore` declara como scratch de sesión.

Ejemplos: `_f10_final_suite.xml`, `_mut_m2.log`, `_suite_verbose.txt`,
`_repro_concurrencia.py`, `_audit_suite.log`, `tmp8g9yx7zt/`, `tmpq6zgqajo/`.

→ Ver `04-CLEANUP-CANDIDATES.md`. **No se ha borrado nada.**

## Estado por área (evidencia en los documentos de cada fase)

| Área | Ficheros | Estado real |
|---|---|---|
| `contracts/` | 7 | IMPLEMENTED_AND_VERIFIED — fuente única de verdad, exportada a `frontend/contracts.json` |
| `graph/` | 5 | IMPLEMENTED_AND_VERIFIED — 17 nodos, motor con red de seguridad `MET-13` |
| `models/` | 11 | IMPLEMENTED_AND_VERIFIED — gateway, 2 proveedores, presupuesto, tarifas |
| `tools/` (pkg) | 5 | IMPLEMENTED_AND_VERIFIED — catálogo, política, patcher, runner, promoter |
| `sandbox.py` | 1 | IMPLEMENTED_AND_VERIFIED — `git worktree` confinado |
| `state/` | 2 | IMPLEMENTED_AND_VERIFIED — SQLite + checkpoint |
| `security/` | 3 | IMPLEMENTED_AND_VERIFIED — redacción de secretos + filtro de logging |
| `api/` | 2 | IMPLEMENTED_AND_VERIFIED — 12 endpoints + SSE |
| `stt/` | 2 | IMPLEMENTED_AND_VERIFIED (F13) — `FasterWhisperAdapter` local |
| `evaluation/` | 3 | IMPLEMENTED_AND_VERIFIED (F14) — 13 tareas, comparativa |
| `agents/` | 1 | **PLACEHOLDER** — solo docstring, 0 importadores |
| `mcp/` | 1 | **PLACEHOLDER** — solo docstring, 0 importadores |
| `observability/` | 1 | **PLACEHOLDER** — solo docstring, 0 importadores |
| `frontend/src` | 12 | IMPLEMENTED_AND_VERIFIED (F11) — 1 pantalla única, 2.311 líneas |
| `tools/*.py` (raíz) | 6 | IMPLEMENTED — arnés de verificación (no es código de producto) |

## Cómo leer el inventario

`file-inventory.json` contiene, por fichero: `path`, `type`, `size_bytes`,
`lines`, `owner_module`, `runtime_relevance` y `tracked`. Las columnas de
clasificación semántica (`purpose`, `imported_by`, `test_coverage`,
`current_status`, `recommendation`) se razonan en
`02-FUNCTIONAL-INVENTORY.md`, `03-INTERNAL-DEPENDENCY-MAP.md` y
`04-CLEANUP-CANDIDATES.md`, porque exigen juicio y no una regla de ruta.
