# 25 — Auditoría de configuración

> `src/ai_swe/config.py` (`Settings`) + `.env.example` + `os.environ` disperso.
> Commit `065db452`. Prefijo: `AI_SWE_`.

## 1. Inventario de variables

| NAME | PROPÓSITO | REQUERIDA | DEFAULT | ¿SECRETO? | USADA POR | ¿DOCUMENTADA? | ESTADO |
|---|---|---|---|---|---|---|---|
| `AI_SWE_MODEL_PROVIDER` | Proveedor del modelo | No | `openai` | No | `registry.py` | ✅ `.env.example` | ✅ |
| `AI_SWE_MODEL_NAME` | Modelo a usar | **Sí, si el proveedor exige clave** | `""` | No | `registry.py` | ✅ | ✅ |
| `AI_SWE_REVIEWER_MODEL` | Modelo del Reviewer | No | `""` (= `model_name`) | No | `nodes.py:1511` | ❌ **no está en `.env.example`** | ⚠️ |
| `AI_SWE_MODEL_API_KEY` | Clave del proveedor | **Sí, si el proveedor exige clave** | `""` | **SÍ** (`SecretStr`) | `openai_compatible.py` | ✅ | ✅ |
| `AI_SWE_MODEL_BASE_URL` | URL base (proveedor local) | No | `None` | No | `registry.py` | ✅ | ✅ |
| `AI_SWE_MODEL_PRICING` | Tarifas por modelo (JSON) | No | `""` (coste = `None`) | No | `pricing.py` | ✅ | ✅ |
| `AI_SWE_STATE_DB_PATH` | Ruta de la BD | No | `var/state.sqlite3` | No | `api/app.py` — **vía `os.environ`, no vía `Settings`** | ✅ | ⚠️ **ver §3** |
| `AI_SWE_WORKSPACE_ROOT` | Raíz de worktrees | No | `var/workspaces` | No | `nodes.py:1234` | ✅ | ✅ |
| `AI_SWE_AUTHORIZED_REPOS` | Lista blanca de repositorios | No | `[]` | No | **NADIE** | ✅ | ❌ **declarada y no aplicada** |
| `AI_SWE_ALLOWED_TEST_TARGETS` | Targets ejecutables | No | 3 targets | No | `nodes.py:1242` | ✅ | ✅ |
| `AI_SWE_ALLOWED_PACKAGES` | Paquetes instalables | No | `[]` | No | `policy.py` | ✅ | ✅ |
| `AI_SWE_NETWORK_EGRESS_ENABLED` | Salida de red del sandbox | No | `false` | No | **NADIE** | ✅ | ❌ **declarada y no aplicada** |
| `AI_SWE_MAX_TOKENS_PER_RUN` | Presupuesto de tokens | No | 200.000 | No | **NADIE** | ✅ | ❌ **declarada y no aplicada** |
| `AI_SWE_MAX_TOOL_CALLS_PER_RUN` | Presupuesto de herramientas | No | 60 | No | **NADIE** | ✅ | ❌ **no aplicada** |
| `AI_SWE_MAX_SECONDS_PER_RUN` | Presupuesto de tiempo | No | 900 | No | **NADIE** | ✅ | ❌ **no aplicada** |
| `AI_SWE_MAX_REVIEW_CYCLES` | Ciclos de revisión | No | 2 | No | `nodes.py:504,620` | ✅ | ✅ |
| `AI_SWE_STT_PROVIDER` | Adaptador STT | No | `faster-whisper` | No | `stt/base.py:272` | ✅ | ✅ |
| `AI_SWE_STT_MODEL` | Modelo de voz | No | `large-v3` | No | `stt/base.py:277` | ✅ | ✅ |
| `AI_SWE_STT_LANGUAGE` | Idioma | No | `es` | No | idem | ✅ | ✅ |
| `AI_SWE_STT_CONFIDENCE_WARN_THRESHOLD` | Umbral de aviso | No | 0.75 | No | idem | ✅ | ✅ |
| `AI_SWE_TTS_ENABLED` | Salida por voz | No | `false` | No | **NADIE** | ✅ | ❌ no implementado |
| `AI_SWE_LANGFUSE_ENABLED` | Observabilidad | No | `false` | No | **NADIE** | ✅ | ❌ no implementado |
| `AI_SWE_LANGFUSE_PUBLIC_KEY` | Clave Langfuse | No | `""` | **SÍ** | **NADIE** | ✅ | ❌ no implementado |
| `AI_SWE_LANGFUSE_SECRET_KEY` | Secreto Langfuse | No | `""` | **SÍ** | **NADIE** | ✅ | ❌ no implementado |
| `AI_SWE_LANGFUSE_HOST` | Host Langfuse | No | `http://localhost:3000` | No | **NADIE** | ✅ | ❌ no implementado |
| `AI_SWE_LOG_LEVEL` | Nivel de log | No | `INFO` | No | `api/app.py` | ✅ | ✅ |
| `AI_SWE_PORT` | Puerto (solo `__main__`) | No | 8000 | No | `__main__.py` | ❌ **no está en `.env.example`** | ⚠️ |
| `AI_SWE_RUN_REAL_PROVIDER_TESTS` | Opt-in del test real | No | — | No | `test_model_gateway_real.py` | ❌ | ⚠️ |
| `AI_SWE_RUN_REAL_STT_TESTS` | Opt-in del test real STT | No | — | No | `test_f13_stt.py` | ❌ | ⚠️ |
| `AI_SWE_STT_TEST_MODEL` | Modelo del test real | No | `tiny` | No | idem | ❌ | ⚠️ |

## 2. Hallazgo principal: **cuatro ajustes de seguridad/presupuesto declarados y no aplicados**

| Ajuste | Qué promete | Realidad |
|---|---|---|
| `AI_SWE_AUTHORIZED_REPOS` | «Lista blanca de repositorios que el sistema puede tocar» | **No se lee en ningún sitio.** `POST /projects` solo exige que exista `.git` |
| `AI_SWE_NETWORK_EGRESS_ENABLED` | «Salida de red desde el entorno de ejecución. Desactivada por defecto» | **No se lee.** El subproceso de pruebas hereda el entorno y la red del servidor |
| `AI_SWE_MAX_TOKENS_PER_RUN` | Límite de tokens por ejecución | **No se lee.** El `Budget` se construye con los defaults del **contrato**, no de `Settings` |
| `AI_SWE_MAX_TOOL_CALLS_PER_RUN` | Límite de llamadas a herramienta | **No se lee.** Idem |
| `AI_SWE_MAX_SECONDS_PER_RUN` | Límite de tiempo | **No se lee.** Idem |

> **Este es el hallazgo más importante de la auditoría de configuración.** Cinco
> variables documentadas en `.env.example` como controles **no tienen efecto**. Un
> operador que las configure creerá estar limitando el sistema y no lo estará.
>
> Consecuencia práctica: cambiar `AI_SWE_MAX_TOKENS_PER_RUN=1000` **no** reduce el
> presupuesto; el valor efectivo sigue siendo 200.000 (el default del contrato).
> Solo `AI_SWE_MAX_REVIEW_CYCLES` llega al `Budget`, y lo hace **indirectamente**
> (el nodo `plan` lo copia al plan, y de ahí al presupuesto).

## 3. Hallazgo secundario: `state_db_path` se lee por dos vías distintas

```python
# config.py — declarado y NO usado
state_db_path: Path = Field(default=Path("var/state.sqlite3"))

# api/app.py — leído directamente del entorno
ruta_estado = os.environ.get("AI_SWE_STATE_DB_PATH", "var/state.sqlite3")
```

**Consecuencia real**: `pydantic-settings` lee `.env`, pero `os.environ.get` **no**.
Por tanto, definir `AI_SWE_STATE_DB_PATH` en un fichero `.env` **se ignora** para la
ruta de la base de datos (solo funciona si se exporta como variable de entorno real).

## 4. Feature flags

| Flag | Efecto real |
|---|---|
| `AI_SWE_TTS_ENABLED` | Ninguno |
| `AI_SWE_LANGFUSE_ENABLED` | Ninguno |
| `AI_SWE_NETWORK_EGRESS_ENABLED` | Ninguno |
| `AI_SWE_STT_PROVIDER` | **Sí**: elige el adaptador |

**Un solo flag con efecto real de los cuatro declarados.**

## 5. Configuración correcta y verificada

| Aspecto | Valoración |
|---|---|
| Prefijo único `AI_SWE_` | ✅ Sin colisiones |
| `extra="ignore"` | ✅ Una variable desconocida no rompe el arranque |
| Validación de `log_level` | ✅ Lista cerrada |
| `SecretStr` para claves | ✅ |
| `registrar_secretos()` al cargar | ✅ Los secretos entran al redactor central |
| `require_model_credentials()` | ✅ **No** exige clave al arrancar; solo al usar el modelo, con error tipado que nombra el campo y **nunca** el valor |
| `.env.example` sin valores | ✅ Documenta nombres |

## 6. Conclusión

La **infraestructura** de configuración es sólida (pydantic-settings, `SecretStr`,
validación, sin secretos en el repo). Pero hay una **brecha real entre lo declarado y
lo aplicado**: cinco variables que se presentan como controles y no lo son, y una
ruta que se lee por dos caminos con semánticas distintas.

**Acción recomendada (P1)**: o se aplican esos cinco ajustes en el punto donde
construyen el `Budget` y en `POST /projects`, o se retiran del contrato y de
`.env.example`. Un control declarado que no existe es peor que no tenerlo: crea
confianza injustificada.
