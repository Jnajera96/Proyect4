# 23 — Auditoría de infraestructura y despliegue

> Commit `065db452`. **No existe despliegue real**: no hay remotos, ni dominio, ni
> CI/CD, ni proxy. Se audita lo que hay y lo que falta.

## 1. Lo que existe

| Elemento | Estado | Observación |
|---|---|---|
| `Dockerfile` | **PARTIAL** | Bien escrito para desarrollo (usuario sin privilegios `aiswe`, `--factory`, `git` instalado). **Tres problemas** (abajo) |
| `docker-compose.yml` | **PARTIAL** | Servicio `api` + Langfuse tras perfil `observability`. Volúmenes correctos |
| `.python-version` | ✅ | `3.13` — **no coincide** con el `python:3.12-slim` del Dockerfile (ambos válidos: `requires-python >= 3.12`) |
| `uv.lock` | ✅ | Lockfile de Python versionado |
| `frontend/package-lock.json` | ✅ | Lockfile de npm versionado |
| `.env.example` | ✅ | Documenta nombres, nunca valores |
| Healthcheck en compose | ✅ | `python -c "import ai_swe; print(ai_swe.__version__)"` — `__version__` existe ⇒ funciona |
| Proceso manager | ❌ | Uvicorn directo, sin supervisión |
| CI/CD | ❌ | **No hay ningún pipeline** |
| Reverse proxy / TLS | ❌ | Nada |
| Backups | ❌ | Nada |
| Monitorización | ❌ | Nada (Langfuse declarado, no integrado) |
| Límites de recursos | ❌ | Nada |

## 2. Problemas del `Dockerfile`

| # | Problema | Evidencia | Impacto |
|---|---|---|---|
| D1 | **Arranca en `0.0.0.0`** | `CMD [... "--host", "0.0.0.0", "--port", "8000"]` | **CRÍTICO**: anula la mitigación del binding local y expone una API sin autenticación capaz de ejecutar código |
| D2 | **No copia el frontend** | `COPY pyproject.toml README.md ./` + `COPY src ./src` — no hay `COPY frontend` | La app construida en `/app` no existe en la imagen ⇒ `GET /app` da 404. **`docker-compose` lo mitiga parcialmente** montando `./frontend:/app/frontend:ro`, pero entonces se sirve el **fuente** y no `dist/` |
| D3 | El comentario dice «sin salida de red» | El contenedor tiene la red por defecto | Documentación que no se corresponde con el comportamiento |

## 3. Problemas del `docker-compose.yml`

| # | Problema | Evidencia |
|---|---|---|
| C1 | El comentario dice que la ausencia de red «se declara cuando exista (fase M3)» | M3 está cerrada y **no se declaró** (`network_mode: none` no aparece) |
| C2 | `NEXTAUTH_SECRET: cambiar-en-despliegue-real` y `SALT: ...` | Credenciales placeholder; están tras el perfil `observability`, pero se arrancarían con valores conocidos |
| C3 | `POSTGRES_PASSWORD: langfuse` | Idem (base de datos de Langfuse) |
| C4 | El volumen `./frontend:/app/frontend:ro` monta el fuente | La API sirve `frontend/dist`, que **no está construido** dentro del contenedor |
| C5 | `healthcheck` comprueba que el paquete importa, no que la API responde | Un contenedor con la API caída pasaría el healthcheck |

## 4. Qué falta para un despliegue real

| # | Falta | Prioridad |
|---|---|---|
| 1 | Autenticación | P0 |
| 2 | Aislamiento de la ejecución de pruebas (contenedor) | P0 |
| 3 | TLS + reverse proxy | P2 |
| 4 | CI/CD (suite + mutación + verificación frontend) | P3 |
| 5 | Backups de `var/state.sqlite3` | P3 |
| 6 | Monitorización y alertas | P3 |
| 7 | Límites de recursos en el servicio | P2 |
| 8 | Gestión de secretos (no `.env` en disco) | P2 |
| 9 | Build multi-etapa del frontend dentro de la imagen | P2 |
| 10 | Política de retención de datos | P3 |

## 5. Conclusión

**La infraestructura está en nivel de desarrollo, no de despliegue.** Los ficheros
existen y están razonablemente escritos, pero: el `Dockerfile` abre la API a la red,
no incluye el frontend, y no hay nada de lo que hace falta para operar (proxy, TLS,
copias, monitorización, CI).

**Recomendación**: tratar `Dockerfile` y `docker-compose.yml` como material de
**reproducibilidad del entorno de desarrollo** (que es lo que su comentario declara
en su primera línea: «Sirve para dos cosas distintas: 1. Reproducibilidad del
entorno. 2. Aislamiento de la ejecución de código») y **no** como artefactos de
despliegue. El punto 2 del comentario **no se cumple**: el contenedor ejecuta el
servidor, no el sandbox.
