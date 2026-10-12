# 10 — Auditoría de infraestructura de modelo

> `src/ai_swe/models/` (11 ficheros). Commit `065db452`.

## 1. Componentes

| Componente | Fichero | Estado |
|---|---|---|
| `ModelGateway` (fachada única) | `gateway.py` | IMPLEMENTED_AND_VERIFIED |
| `ModelRequest` / `ModelResponse` / `ModelMessage` / `ModelUsage` | `contracts.py` | IMPLEMENTED_AND_VERIFIED |
| `ProviderAdapter` (Protocol) | `providers/base.py` | IMPLEMENTED_AND_VERIFIED |
| `FakeModelAdapter` | `providers/fake.py` | IMPLEMENTED_AND_VERIFIED |
| `OpenAICompatibleAdapter` | `providers/openai_compatible.py` | IMPLEMENTED_AND_VERIFIED |
| Registro de proveedores | `registry.py` | IMPLEMENTED_AND_VERIFIED |
| Consumo de presupuesto | `budget.py` | IMPLEMENTED_AND_VERIFIED |
| Tabla de tarifas | `pricing.py` | IMPLEMENTED_AND_VERIFIED |
| Errores tipados | `errors.py` | IMPLEMENTED_AND_VERIFIED |

## 2. Verificación de las comprobaciones exigidas

| Comprobación | Resultado | Evidencia |
|---|---|---|
| **Ningún agente importa directamente un SDK de proveedor** | ✅ **CUMPLE** | `grep -rn "import openai\|import anthropic\|import httpx" src/ai_swe/graph/` → 0 resultados. Solo `providers/openai_compatible.py` usa `httpx` |
| Secretos protegidos | ✅ CUMPLE | `model_api_key: SecretStr`; `registrar_secretos()` los inscribe en el redactor central al cargar ajustes |
| Modelos configurables | ✅ CUMPLE | `AI_SWE_MODEL_PROVIDER`, `MODEL_NAME`, `REVIEWER_MODEL`, `BASE_URL`, `PRICING` |
| Fallbacks verificables | ✅ CUMPLE | Cada nodo cae a su versión determinista y **deja `MODEL_FALLBACK`** en `errors`. Probado en F3/F4/F6/F9 |
| Budget aplicado | ✅ CUMPLE | `gateway.consume(budget, response)` en los 4 puntos de uso |
| Tests offline | ✅ CUMPLE | `test_model_gateway.py` con `FakeModelAdapter`; toda la suite corre sin red |
| Test real opt-in | ✅ CUMPLE | `test_model_gateway_real.py`, marcador `real_provider`, requiere `AI_SWE_RUN_REAL_PROVIDER_TESTS=1` + clave |
| Salida estructurada validada | ✅ CUMPLE | `generate_structured` inyecta el JSON Schema derivado del contrato Pydantic y **revalida** la respuesta |
| Contabilidad de tokens | ✅ CUMPLE | `used_tokens` + (F14) `used_input_tokens`/`used_output_tokens` |
| Contabilidad de coste | ✅ PARCIAL | Se aplica **solo si** el proveedor reporta `cost`. `pricing.py` existe pero `AI_SWE_MODEL_PRICING` está vacío por defecto ⇒ coste `None` («no se sabe»). Honesto, pero hoy **nunca hay coste real** |
| Reintentos / backoff | ❌ **NO VERIFICADO** | No se localizó política de reintentos. Hay `timeout_s` |
| Enrutado por rol | ✅ PARCIAL | Existe `reviewer_model`; no hay tabla de enrutado general |

## 3. Hallazgo: **no existe un adaptador de Hugging Face**

El enunciado de la auditoría menciona `HuggingFaceAdapter`. **En el código no
existe.** Lo que hay:

- `PROVEEDORES_CON_CLAVE = {openai, anthropic, azure, openrouter, mistral}` (`config.py`)
- Un único adaptador HTTP real: `OpenAICompatibleAdapter`

**Hugging Face se usa como *catálogo de modelos descargables* para el STT local**
(`faster-whisper` descarga pesos de HF), no como proveedor LLM. Si el proyecto
quiere invocar modelos de HF como LLM, hay que escribir el adaptador: hoy no existe.

> Esto es una **corrección de expectativa**, no un defecto. Conviene decirlo así en
> la defensa para no prometer algo que no está.

## 4. Modelo de confianza

```
Nodo (interpret/plan/coder/reviewer)
   │  pide: messages + response_model (contrato Pydantic)
   ▼
ModelGateway.generate_structured()
   │  · deriva el JSON Schema del contrato
   │  · añade el esquema como mensaje de sistema
   │  · aplica timeout
   ▼
ProviderAdapter (Fake | OpenAICompatible)
   │  · Fake: determinista, sin red
   │  · OpenAICompatible: httpx + clave desde SecretStr
   ▼
ProviderResponse → validación Pydantic → StructuredOutputError si no cumple
   │
   ▼
gateway.consume(budget, response)  → Budget nuevo (llamadas, tokens, coste)
```

**El modelo propone; el contrato dispone.** La validación ocurre en el borde del
gateway, no en el nodo, de modo que ningún nodo puede recibir un objeto que no
cumpla el contrato.

## 5. Riesgos

| Riesgo | Severidad | Detalle |
|---|---|---|
| Prompt injection indirecta vía contenido del repo | **MEDIA-ALTA** | El Coder/Reviewer leen diff y hallazgos. Sin defensa específica |
| `model_base_url` configurable ⇒ SSRF si se apunta a un host interno | MEDIA | Es configuración del operador, no del usuario; riesgo real solo si se expone el ajuste |
| Sin reintentos ⇒ un fallo transitorio degrada al fallback determinista | BAJA | El fallback es correcto y se declara; el efecto es menor calidad, no error |
| Coste nunca contabilizado (tarifas vacías) | BAJA | `None` = «no se sabe»; correcto pero limita la métrica `MET-06` |
| `httpx` con `HTTP_PROXY` del entorno | INFO | Documentado en memoria del proyecto: puede enrutar `127.0.0.1` por proxy |

## 6. Conclusión

**IMPLEMENTED_AND_VERIFIED.** Es una de las piezas mejor construidas: fachada única,
adaptadores intercambiables, contrato validado en el borde, presupuesto aplicado,
fallback honesto y tests offline + opt-in.

**Faltan**: adaptador de Hugging Face (si se quiere), política de reintentos y
tarifas reales para que `MET-06` tenga datos.
