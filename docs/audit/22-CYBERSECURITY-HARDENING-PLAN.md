# 22 — Plan de endurecimiento (hardening)

> **NO IMPLEMENTADO.** Plan priorizado. Commit `065db452`.

## P0 — CRITICAL (antes de exponer la API a cualquier red)

| # | PROBLEM | FIX | FILES | TESTS | MIGRATION RISK | COMPLEXITY | DEPENDENCIES |
|---|---|---|---|---|---|---|---|
| P0-1 | El `Dockerfile` arranca en `0.0.0.0` sin autenticación | Cambiar a `--host 127.0.0.1` **o** implementar auth antes de exponer | `Dockerfile` | Prueba de que el contenedor no escucha fuera del loopback | Ninguno | **Baja** (1 línea) si se elige loopback | — |
| P0-2 | Ejecución de código del usuario sin aislamiento | Ejecutar las pruebas en un contenedor desechable: `--network none`, `--memory 1g`, `--pids-limit 256`, `--read-only` con el worktree montado | `tools/runner.py`, nuevo `sandbox_container.py`, `docker-compose.yml` | Prueba de que el proceso no alcanza la red ni supera los límites | **ALTO** (cambia el modelo de ejecución) | **Alta** | Docker en el host |

## P1 — BEFORE MVP

| # | PROBLEM | FIX | FILES | TESTS | MIGRATION RISK | COMPLEXITY |
|---|---|---|---|---|---|---|
| P1-1 | `ApproveRequest.decision` default `APPROVED` | Quitar el default: campo obligatorio | `contracts/api.py` | Test de que `{}` devuelve 422 | Bajo (rompe clientes que envían `{}`) | **Baja** |
| P1-2 | `authorized_repos` declarado y no aplicado | Aplicarlo en `POST /projects` (o eliminarlo del contrato si no se quiere) | `api/app.py`, `sandbox.py` | Test de que un repo fuera de la lista da 422 | Medio (puede romper flujos actuales si la lista está vacía) | **Baja** |
| P1-3 | Subida de audio sin límite ni validación de tipo | Tope de tamaño (p. ej. 25 MB) + validación de tipo | `api/app.py`, `stt/base.py` | Test de 413 y de tipo inválido | Ninguno | **Baja** |
| P1-4 | Prompt injection indirecta | Delimitar el contenido no confiable en los prompts (marcarlo como datos, no instrucciones) y no concatenarlo con el prompt de sistema | `graph/nodes.py` (`PROMPT_*`) | Test de que un fichero con «ignora tus instrucciones» no altera la decisión | Bajo | **Media** |
| P1-5 | Sin autenticación | OAuth/JWT o clave de API + sesión | `api/app.py`, nuevo `api/auth.py` | Tests de 401/403 | Medio | **Alta** |

## P2 — BEFORE DEPLOYMENT

| # | PROBLEM | FIX | FILES | TESTS | COMPLEXITY |
|---|---|---|---|---|---|
| P2-1 | Sin aislamiento de red | Incluido en P0-2 | — | — | — |
| P2-2 | Sin límites de CPU/memoria/procesos | `resource.setrlimit` o límites del contenedor | `tools/runner.py` | Test de que un bucle infinito se corta | Media |
| P2-3 | SSE y paginación sin tope | Tope superior en `limit`; límite de conexiones SSE | `api/app.py`, `state/store.py` | Test de `limit=10**9` → 422 | Baja |
| P2-4 | Sin cabeceras de seguridad | Middleware con CSP, `X-Frame-Options`, `X-Content-Type-Options`, `TrustedHostMiddleware` | `api/app.py` | Test de cabeceras presentes | Baja |
| P2-5 | Sin TLS | Reverse proxy (Caddy/nginx) con certificado | `docker-compose.yml`, `Dockerfile` | Prueba manual | Media |
| P2-6 | Sin rate limiting | `slowapi` o límite en el proxy | `api/app.py` | Test de 429 | Baja |

## P3 — IMPROVEMENT

| # | PROBLEM | FIX | FILES | COMPLEXITY |
|---|---|---|---|---|
| P3-1 | El worktree no se limpia en rutas de excepción | Limpiar en `abortar` y en la recuperación de huérfanas | `graph/engine.py`, `graph/nodes.py` | Baja |
| P3-2 | Sin retención ni purga | Política (p. ej. 90 días) + `DELETE /runs/{id}` | `state/store.py`, `api/app.py` | Media |
| P3-3 | Sin monitorización | Implementar `observability/` (logs JSON + Langfuse) | `observability/` | Media |
| P3-4 | Sin backups | Copia programada de `var/state.sqlite3` | operación | Baja |
| P3-5 | Credenciales por defecto en compose | Variables obligatorias | `docker-compose.yml` | Baja |
| P3-6 | `pytest-asyncio` sin uso | Eliminarlo de `[dev]` | `pyproject.toml` | Baja |
| P3-7 | Sin migraciones de esquema | Alembic o migrador propio sobre `ESQUEMA_VERSION` | `state/store.py` | Media |

## P4 — FUTURE

| # | PROBLEM | FIX |
|---|---|---|
| P4-1 | Sin auditoría de dependencias automatizada | `pip-audit` + `npm audit` en CI |
| P4-2 | Sin CI/CD | Pipeline que ejecute suite + mutación + verificación del frontend |
| P4-3 | Sin pruebas de escape con symlink en todas las plataformas | Tests específicos por SO |
| P4-4 | Sin política de privacidad escrita | Documento legal |

## Orden recomendado

```
1. P0-1 (1 línea)      ← elimina el único riesgo CRITICAL de despliegue
2. P1-1 (1 línea)      ← elimina la aprobación por defecto
3. P1-2, P1-3          ← cierran controles declarados y no aplicados
4. P2-3, P2-4          ← baratos y de impacto amplio
5. P1-5 + P0-2         ← los dos grandes, van juntos si se despliega
6. P2-5, P2-6
7. P3-*
```

**Coste estimado de P0 + P1**: bajo. Son cambios pequeños y localizados, salvo
P1-4 (prompts) y P1-5 (auth). **P0-2 es el único cambio estructural.**
