# 24 — Auditoría de dependencias

> `pyproject.toml` + `uv.lock` + `frontend/package.json` + `package-lock.json`.
> Commit `065db452`. **`npm audit` / `pip-audit` NO se ejecutaron** (requieren red).

## 1. Python — runtime

| Dependencia | Restricción | Por qué | Consumidores | ¿Se usa? | Relevancia de seguridad |
|---|---|---|---|---|---|
| `fastapi>=0.115,<1` | techo mayor | API HTTP | `api/app.py` | ✅ | Alta (superficie HTTP) |
| `uvicorn[standard]>=0.30,<1` | techo mayor | Servidor ASGI | `__main__.py` | ✅ | Media |
| `python-multipart>=0.0.9,<1` | techo mayor | `UploadFile`/`Form` | `api/app.py` | ✅ | **Media-alta** (parsea subidas) |
| `pydantic>=2.9,<3` | techo mayor | Contratos | todo | ✅ | Media |
| `pydantic-settings>=2.5,<3` | techo mayor | `Settings` | `config.py` | ✅ | Media (lee entorno) |
| `langgraph>=1.2,<2` | techo mayor | Orquestación | `graph/` | ✅ | Media |
| `langgraph-checkpoint-sqlite>=3.1,<4` | techo mayor | Checkpoint | `state/store.py` | ✅ | Media |
| `httpx>=0.27,<1` | techo mayor | Cliente del proveedor | `providers/openai_compatible.py` | ✅ | Media (salida a red) |
| `sse-starlette>=2.1,<4` | techo mayor | SSE | `api/app.py` | ✅ | Media |

**Valoración**: política de versiones **correcta y documentada** (techo de versión
mayor cuando la API se usa de verdad). Sin dependencias declaradas sin consumidor.

## 2. Python — extras opcionales

| Extra | Dependencia | ¿Instalada? | ¿Se usa? | Veredicto |
|---|---|---|---|---|
| `voice` | `faster-whisper>=1.0` | **No** (test real saltado) | `stt/base.py` (import perezoso) | Correcto: opcional por diseño |
| `observability` | `langfuse>=2.50` | No | **Ningún código lo importa** | **Declarada sin consumidor** — la integración no existe |
| `mcp` | `mcp>=1.0` | No | **Ningún código lo importa** | Declarada para una fase no implementada; comentada como tal en `pyproject.toml` |

## 3. Python — desarrollo

| Dependencia | ¿Se usa? | Veredicto |
|---|---|---|
| `pytest>=8.0` | ✅ | Correcto |
| `pytest-asyncio>=0.24` | ❌ **NO** | **Declarada sin consumidor**: no hay tests `async`, ni `asyncio_mode` configurado, ni `@pytest.mark.asyncio` |
| `ruff>=0.6` | ⚠️ | Configurado en `pyproject.toml`, pero **no está instalado en el venv** (`No module named ruff`). La verificación de lint **no se está ejecutando** |

## 4. Node — frontend

| Dependencia | Versión | Tipo | ¿Se usa? |
|---|---|---|---|
| `react` | ^18.3.1 | runtime | ✅ |
| `react-dom` | ^18.3.1 | runtime | ✅ |
| `@types/node` | ^22.20.5 | **runtime** ⚠️ | Solo necesario en build (`vite.config.ts` usa `process`) — **debería estar en `devDependencies`** |
| `@types/react` | ^18.3.31 | dev | ✅ |
| `@types/react-dom` | ^18.3.7 | dev | ✅ |
| `@vitejs/plugin-react` | ^4.3.4 | dev | ✅ |
| `typescript` | ^5.6.3 | dev | ✅ |
| `vite` | ^5.4.11 | dev | ✅ |

**Superficie de runtime: 3 paquetes** (`react`, `react-dom`, `@types/node`). Es una
postura excelente: sin librerías de UI, sin router, sin cliente HTTP, sin gestor de
estado.

**Observación**: `@types/node` está en `dependencies` y se instalaría en producción.
Es un error de clasificación, no de seguridad.

## 5. Riesgos de cadena de suministro

| # | Riesgo | Estado | Severidad |
|---|---|---|---|
| 1 | Sin auditoría automatizada de vulnerabilidades | `pip-audit` / `npm audit` no configurados | MEDIA |
| 2 | Sin CI que verifique los lockfiles | No hay pipeline | MEDIA |
| 3 | Riesgo de typosquatting | Bajo: todas las dependencias son paquetes muy conocidos | BAJA |
| 4 | Dependencias obsoletas | **No evaluable sin red** | UNKNOWN |
| 5 | Scripts `postinstall` maliciosos | `npm install` con `esbuild` falló en este entorno y se usó `--ignore-scripts`; **no** se auditó | UNKNOWN |
| 6 | Dependency confusion | No hay registro privado; riesgo bajo | BAJA |
| 7 | `langfuse` y `mcp` declaradas y no usadas | Superficie innecesaria en el manifiesto (no se instalan por defecto) | BAJA |
| 8 | `pytest-asyncio` sin uso | Ruido en el manifiesto | INFO |
| 9 | `ruff` configurado pero no instalado | El lint no se ejecuta en este entorno | INFO |

## 6. Dependencias declaradas sin consumidores (resumen)

| Dependencia | Extra | Veredicto |
|---|---|---|
| `langfuse` | `observability` | **Sin consumidor** — no hay código que la importe |
| `mcp` | `mcp` | **Sin consumidor** — placeholder |
| `pytest-asyncio` | `dev` | **Sin consumidor** — no hay tests async |

Ninguna de las tres se instala por defecto, así que el impacto es de **exactitud del
manifiesto**, no de seguridad.

## 7. Conclusión

**IMPLEMENTED** con buena disciplina: lockfiles, techos de versión mayor justificados,
extras opcionales bien separados, y una superficie de runtime en el frontend
excepcionalmente pequeña.

**A mejorar**: ejecutar `pip-audit` y `npm audit`, instalar `ruff` (está configurado y
no se ejecuta), retirar `pytest-asyncio`, y mover `@types/node` a `devDependencies`.
