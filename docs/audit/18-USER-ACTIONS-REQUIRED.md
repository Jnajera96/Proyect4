# 18 — Acciones requeridas del usuario

> Lo que el software **no puede** completar por sí mismo. Commit `065db452`.

## REQUIRED_NOW — bloquea la verificación real

| # | ACCIÓN | WHY | WHEN | HOW | RISK_IF_NOT_DONE | MVP | PROD |
|---|---|---|---|---|---|---|---|
| 1 | **Obtener una clave de proveedor de modelo** (`AI_SWE_MODEL_API_KEY`) y elegir `AI_SWE_MODEL_NAME` | El sistema funciona sin ella (fallbacks deterministas), pero **nunca se ha ejecutado contra un modelo real**. `TD-01` está abierto desde F2 | Ahora, antes de la defensa | Copiar `.env.example` a `.env`, rellenar `AI_SWE_MODEL_PROVIDER` + `AI_SWE_MODEL_NAME` + `AI_SWE_MODEL_API_KEY`; ejecutar `AI_SWE_RUN_REAL_PROVIDER_TESTS=1 python -m pytest tests/test_model_gateway_real.py -m real_provider` | **ALTO**: no se puede afirmar que la cadena con un LLM real funciona. La defensa se apoya en fallbacks | ✅ | ✅ |
| 2 | **Decidir qué proveedor** (OpenAI / Anthropic / local) y su `base_url` | `PROVEEDORES_CON_CLAVE` incluye 5; solo hay adaptador *OpenAI-compatible* | Ahora | Documentar la decisión en `docs/` | MEDIO: ambigüedad en la defensa | ✅ | ✅ |
| 3 | **Rellenar `AI_SWE_MODEL_PRICING`** con tarifas reales | Sin tarifas, `used_cost` es `None` y `MET-06` (coste por tarea) **no tiene datos** | Antes de la defensa | Copiar las tarifas publicadas del proveedor al JSON | MEDIO: una métrica del informe queda vacía | ✅ | ✅ |
| 4 | **Ejecutar la suite con el extra `voice`** si se va a defender el STT real | `faster-whisper` no está instalado; el test real está saltado | Antes de la defensa | `pip install -e ".[voice]"` y `AI_SWE_RUN_REAL_STT_TESTS=1 pytest tests/test_f13_stt.py -m real_stt` (descarga un modelo) | MEDIO: el STT solo está probado con dobles | ⚪ | ✅ |
| 5 | **Decidir si se expone la API** y, si sí, **implementar autenticación primero** | Hoy no hay auth. El `Dockerfile` arranca en `0.0.0.0` ⇒ expone la capacidad de ejecutar código | Ahora (decisión) | Si se expone: añadir auth + TLS + rate limiting. Si no: corregir el `Dockerfile` a `127.0.0.1` | **CRÍTICO** si se despliega tal cual | ⚪ | ✅ |

## REQUIRED_BEFORE_MVP

| # | ACCIÓN | WHY | HOW | RISK | MVP |
|---|---|---|---|---|---|
| 6 | **Decidir el alcance de la entrega**: ¿prototipo local o producto? | Determina si hacen falta auth, multi-usuario y despliegue | Decisión del Arquitecto | ALTO: cambia el trabajo restante | ✅ |
| 7 | **Resolver las contradicciones de documentación** (`README` y `__init__.py` dicen «fase M0/F2») | Un tribunal que lea el README creerá que el proyecto está a medias | Reescribir esas dos secciones | MEDIO: percepción | ✅ |
| 8 | **Autorizar la limpieza** de los ~74 artefactos scratch y 2 `tmp*` | Ensucian el árbol de trabajo | Ver `04-…` y `30-…` | BAJO | ✅ |
| 9 | **Decidir el destino de `docs/auditoria-2026-10-06/` y los `BASELINE-*`** | Documentación histórica valiosa pero desordenada | Archivar en `docs/history/` | BAJO | ⚪ |
| 10 | **Decidir si se conservan los placeholders** `agents/`, `mcp/`, `observability/` | MCP está en el temario: puede interesar dejarlo declarado | Decisión | BAJO | ⚪ |

## REQUIRED_BEFORE_DEPLOYMENT

| # | ACCIÓN | WHY | HOW | RISK |
|---|---|---|---|---|
| 11 | **Autenticación** (OAuth, JWT o sesión) | Sin ella, cualquiera que alcance el puerto ejecuta código | Diseñar e implementar | CRÍTICO |
| 12 | **Aislamiento real del sandbox** (contenedor con `--network none`, `--memory`, `--pids-limit`) | El worktree no aísla el proceso | Rediseñar la ejecución de pruebas | ALTO |
| 13 | **TLS / reverse proxy** | Hoy HTTP en claro | nginx/Caddy + certificados | ALTO |
| 14 | **Dominio y certificados** | Para servir la app | DNS + ACME | MEDIO |
| 15 | **Destino de backup y política de retención** | Nada se purga hoy; la BD crece sin límite | Decidir retención y destino | MEDIO |
| 16 | **Gestión de secretos** (no `.env` en disco) | `.env` es aceptable en local, no en producción | Vault / secret manager | ALTO |
| 17 | **Límites de subida y de conexiones SSE** | Sin ellos, un cliente puede agotar memoria | Implementar | MEDIO |
| 18 | **Decisiones legales/privacidad**: qué se almacena, cuánto, y aviso al usuario | El sistema guarda prompts, código y transcripciones | Redactar política | ALTO |
| 19 | **Monitorización y alertas** | No hay observabilidad (M6 sin implementar) | Langfuse o equivalente | MEDIO |
| 20 | **`HF_TOKEN`** si se van a descargar modelos de Hugging Face en un entorno con límites | La descarga anónima puede estar limitada | Variable de entorno | BAJO |

## OPTIONAL

| # | ACCIÓN | Nota |
|---|---|---|
| 21 | Elegir un modelo distinto para el Reviewer (`AI_SWE_REVIEWER_MODEL`) | La capacidad existe; es una decisión de calidad/coste |
| 22 | Configurar `AI_SWE_AUTHORIZED_REPOS` | **Ojo: hoy no se aplica** (`25-…`). Configurarlo no protege nada todavía |
| 23 | Configurar Langfuse (`AI_SWE_LANGFUSE_*`) | La integración **no está implementada** (solo hay ajustes) |
| 24 | Añadir un `git remote` y publicar el repositorio | Hoy no hay remoto |

## FUTURE

| # | ACCIÓN | Nota |
|---|---|---|
| 25 | Decidir si se implementa MCP (Fase 3 del temario) | Hay un placeholder declarado |
| 26 | Decidir si se implementa la capa de contexto con grafo (`docs/05-graphify-evaluacion.md`) | Propuesta `[PROP]` |
| 27 | Decidir si se añade TTS | `tts_enabled` declarado, sin implementación |

---

## Resumen ejecutivo para el usuario

**Si sólo puede hacer cinco cosas antes de la defensa:**

1. Obtener y configurar una clave de modelo real y ejecutar el test opt-in (→ cierra `TD-01`).
2. Rellenar `AI_SWE_MODEL_PRICING` (→ da datos a `MET-06`).
3. Decidir si la API se expone; si sí, **no desplegar el `Dockerfile` actual** (abre `0.0.0.0` sin auth).
4. Corregir el `README` y el docstring de `ai_swe/__init__.py` (dicen «fase M0/F2»).
5. Autorizar la limpieza de los artefactos scratch.

**Lo que el software NO puede decidir por usted:** el alcance de la entrega, si se
expone a red, qué datos se retienen y cuánto, y qué proveedor de modelo usar.
