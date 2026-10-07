# Diseño del Model Gateway (`F2`)

**Estado:** diseño previo a la implementación.
**Fase:** `F2` — Model Gateway.
**Regla que se respeta:** ningún agente importa un SDK de proveedor. Todos dependen
de `ModelGateway`.

> Este documento existe para decidir **antes** de escribir código. Se conserva
> después como registro del porqué, porque las decisiones de aquí son las que
> hacen que el sistema sea sustituible de proveedor y no una colección de
> integraciones.

---

## 0. Verificación previa: qué NO hay que duplicar

Antes de definir nada, se revisó lo que ya existe. Tres cosas se **reutilizan** y
no se redefinen:

| Ya existe | Dónde | Por qué no se duplica |
|---|---|---|
| `Budget` | `contracts/state.py` | Ya tiene `max_model_calls`/`used_model_calls`, `max_cost`/`used_cost`, `max_tokens`/`used_tokens`, `max_seconds`, y `exhausted_reasons()`. El gateway lo **consume**, no lo redefine. |
| `AgentRole` | `contracts/tasks.py` | Es la identidad del solicitante. `ModelRequest.agent_role` usa este tipo. |
| `RunError` | `contracts/state.py` | Es un **registro persistido** de error de ejecución, no una excepción. La jerarquía de excepciones del gateway es otra cosa y no lo sustituye. |

Y una cosa **no** existe todavía, que es lo que `F2` crea: contratos de
petición/respuesta de modelo, jerarquía de errores de modelo, adapters y gateway.

**Conclusión de la verificación:** no hay duplicación. Se procede.

---

## 1. Decisión de arquitectura principal: **síncrono, no `async`**

El encargo describe la interfaz como `async generate(request)`. **No se
implementa así, y esta es la razón objetiva.**

El camino de ejecución real del proyecto es:

```
petición HTTP (async, FastAPI)
   └─ devuelve run_id en milisegundos        ← DEC-11: no bloquea
        └─ RunWorker: ThreadPoolExecutor      ← HILO, no corrutina
             └─ RunEngine.execute()           ← síncrono
                  └─ grafo LangGraph          ← síncrono
                       └─ nodos               ← funciones síncronas
```

La llamada al modelo ocurre **en el hilo del trabajador**, no en el camino de la
petición. Con un adapter `async`, cada nodo síncrono tendría que hacer
`asyncio.run(...)` para llamarlo: eso crea y destruye un bucle de eventos por
llamada, y varios clientes HTTP se ligan al bucle en que se crean. Es un
anti-patrón conocido, y además obligaría a convertir los nodos —y con ellos
LangGraph— a `async`, lo que **viola directamente la restricción de no tocar
LangGraph en esta fase**.

El propio proyecto ya documentó esta elección: `graph/worker.py` dice «son
**hilos**, no procesos. Suficiente porque el trabajo es espera de red (llamadas al
modelo)». El diseño síncrono es coherente con esa decisión, no una desviación.

**Consecuencia:** `ProviderAdapter.generate()` es síncrono. Si algún día hace falta
un camino `async`, se añade un envoltorio fino
(`await asyncio.to_thread(gateway.generate, request)`) sin tocar ni los adapters ni
los contratos. La puerta queda abierta; no se paga el coste hoy.

---

## 2. Decisión secundaria: **cliente HTTP, no SDK de proveedor**

El adapter real usa `httpx` (ya es dependencia del proyecto) contra la API HTTP
compatible con OpenAI. Razones:

1. **«Compatible con OpenAI» es un contrato HTTP**, no un SDK. Hablar HTTP
   directamente permite usar el mismo adapter con OpenAI, Ollama, vLLM, OpenRouter,
   Together y cualquier endpoint compatible sin escribir uno por proveedor.
2. **No añade dependencia.** El SDK `openai` traería su propio árbol de
   dependencias para hacer una petición POST.
3. **Es testeable sin red.** `httpx.MockTransport` permite ejercitar el adapter
   real —construcción de la petición, cabeceras, parseo de la respuesta, mapeo de
   errores— **sin abrir un socket**. Esto es lo que permite cumplir el requisito
   de que la suite pase sin Internet: se prueba el adapter de verdad, no un doble.

---

## 3. Estructura

```
src/ai_swe/models/
    __init__.py          API pública del paquete
    contracts.py         ModelRequest, ModelResponse, ModelUsage, ProviderConfig,
                         ModelMessage, FinishReason
    errors.py            ModelGatewayError y su jerarquía
    budget.py            consumo de Budget (puro, sin estado global)
    pricing.py           tabla de precios enchufable (vacía por defecto)
    registry.py          registro explícito de proveedores
    gateway.py           ModelGateway: orquesta
    providers/
        __init__.py
        base.py          ProviderAdapter (protocolo) + ProviderResponse
        fake.py          FakeModelAdapter (determinista + inyección de fallos)
        openai_compatible.py   adapter real (httpx)
```

Nombres en inglés para los tipos, como el resto de `contracts/` (`RunError`,
`ToolSpec`, `AgentRole`); documentación y comentarios en español, como el proyecto.

---

## 4. Contratos

### `ModelMessage`
`role` (`system` | `user` | `assistant`) + `content`. Es el mínimo; no se modela
tool-calling todavía porque ningún agente lo usa aún y sería superficie sin uso.

### `ModelRequest`
| Campo | Tipo | Nota |
|---|---|---|
| `messages` | `list[ModelMessage]` | mínimo 1 |
| `model` | `str \| None` | si es `None`, se usa el de configuración |
| `temperature` | `float \| None` | opcional, no todos los proveedores lo aceptan |
| `max_output_tokens` | `int \| None` | |
| `run_id` | `str \| None` | metadata de correlación |
| `trace_id` | `str \| None` | metadata de correlación |
| `agent_role` | `AgentRole \| None` | quién solicita |
| `metadata` | `dict[str, str]` | metadata interna acotada |

**No contiene secretos.** La clave vive en la configuración del adapter, nunca en
la petición: así una petición serializada (en un log, en un evento) no puede
filtrarla. Esto es una decisión, no una casualidad.

### `ModelUsage`
`input_tokens`, `output_tokens`, `total_tokens`; opcionales `cached_tokens`,
`reasoning_tokens`. Regla explícita: **si el proveedor no reporta un valor, el
campo queda en `None`, no se inventa.** `total_tokens` se calcula solo si ambos
sumandos existen.

### `ModelResponse`
`content`, `structured_data` (opcional), `provider`, `model`, `finish_reason`,
`usage`, `latency_ms`, `provider_request_id`, `provider_requested`,
`fallback_used`, `error` (`None` si tuvo éxito).

Los tres campos `provider_requested` / `provider` / `fallback_used` existen para
**no ocultar que hubo fallback**: una respuesta que vino del secundario no puede
parecer que vino del primario.

### `ProviderConfig`
`name`, `model`, `api_key` (`SecretStr`), `base_url`, `timeout_s`,
`max_retries`. `api_key` como `SecretStr` para que su `repr` no la filtre.

---

## 5. Errores

```
ModelGatewayError (base; tiene .error_class y .recoverable)
├── ModelConfigurationError      no reintentable
├── ModelAuthenticationError     no reintentable
├── UnknownProviderError         no reintentable
├── ModelRateLimitError          REINTENTABLE
├── ModelTimeoutError            REINTENTABLE
├── ProviderUnavailableError     REINTENTABLE
├── InvalidResponseError         no reintentable
├── StructuredOutputError        no reintentable
└── BudgetExceededError          no reintentable
```

`recoverable` es una propiedad de la **clase**, no un parámetro: así la política de
reintento es una consecuencia del tipo y no una decisión repetida en cada sitio.

**Requisito de seguridad:** ningún mensaje de error incluye clave, cabecera
`Authorization`, `Bearer`, ni valor de secreto. Todo mensaje pasa por
`ai_swe.security.redact`. Un proveedor puede devolver el secreto dentro del cuerpo
de un error 401; ese cuerpo se redacta antes de construir el mensaje.

---

## 6. `ProviderAdapter`

```
generate(request: ModelRequest) -> ProviderResponse
```

`ProviderResponse` es la respuesta **cruda del proveedor** (contenido, usage,
modelo, finish_reason, id). El gateway la normaliza a `ModelResponse`. Se separan
para que el gateway no conozca formas específicas de proveedor y el adapter no
conozca la política (presupuesto, reintentos, fallback).

Reparto de responsabilidades:

| Capa | Sabe de | No sabe de |
|---|---|---|
| Adapter | HTTP, cabeceras, forma de la respuesta del proveedor | presupuesto, reintentos, fallback |
| Gateway | presupuesto, reintentos, fallback, validación, redacción | HTTP, SDK, forma cruda |

---

## 7. `FakeModelAdapter`

Base de toda la suite. Determinista y **sin red**. Capacidades:

- respuesta de texto fija o programable por secuencia;
- structured output (devuelve el JSON que se le indique);
- usage simulado;
- inyección de fallos: `timeout`, `rate_limit` (429), `unavailable` (503),
  `invalid_response` (JSON malformado), `auth_error`, y `script` (una secuencia de
  resultados, para probar «falla, falla, funciona»).

Se controla por constructor, no por estado global: dos tests pueden tener dos fakes
distintos a la vez.

---

## 8. Registry

`{nombre → factoría}` explícito. **Sin import dinámico desde cadenas** controladas
por el usuario: un `importlib.import_module(lo_que_diga_la_config)` es una vía de
ejecución arbitraria. Un nombre no registrado lanza `UnknownProviderError`.

Se registran por defecto `fake` y `openai_compatible` (`openai`, `openai_compatible`,
y alias locales `ollama`/`vllm` que apuntan al mismo adapter con `base_url`).

---

## 9. Structured output

```
gateway.generate_structured(request, response_model=MiContrato)
   ├─ añade el JSON Schema de `MiContrato` a la petición (model_json_schema())
   ├─ llama al adapter
   ├─ extrae el JSON del contenido
   ├─ MiContrato.model_validate(...)
   └─ si falla → StructuredOutputError (no continúa en silencio)
```

**Fuente única de verdad: el contrato Pydantic.** El JSON Schema se **deriva** con
`model_json_schema()`; no se escribe a mano en paralelo, porque dos definiciones de
la misma estructura divergen y la que se envía al modelo deja de ser la que valida.

---

## 10. Retry

Centralizado en el gateway. Reintenta solo errores con `recoverable = True`
(timeout, rate limit, proveedor no disponible). **No** reintenta autenticación,
respuesta inválida, configuración, proveedor desconocido, presupuesto agotado.

Backoff exponencial `base * 2**intento` con techo (`max_backoff_s`), acotado por
`max_retries`. La función de espera es **inyectable** para que las pruebas no
duerman de verdad: un test que tarda 7 s por el backoff es un test que nadie
ejecuta.

---

## 11. Fallback

El gateway recibe una **cadena** de adapters: `[primario, ...fallbacks]`. Si el
primario agota sus reintentos con un error recuperable, pasa al siguiente. Se
registra `provider_requested`, `provider` (el que respondió) y `fallback_used`.
Si todos fallan, se propaga el **último** error, que es el más informativo.

En esta fase la cadena suele tener un solo adapter real; el soporte se implementa y
se prueba con fakes. No se conectan dos proveedores reales.

---

## 12. Timeout

Dos niveles, y el efectivo es el menor:

1. **Por petición**: `request_timeout_s` del gateway/adapter.
2. **Por presupuesto**: si el `Budget` trae `max_seconds` y `elapsed_seconds`, el
   tiempo restante acota el timeout. Un agente no puede esperar más de lo que le
   queda de presupuesto, aunque el proveedor esté dispuesto a responder.

Un timeout es un error **recuperable**: se reintenta, pero el reintento vuelve a
estar acotado por el mismo presupuesto.

---

## 13. Budget

**Decisión de concurrencia:** el gateway **no posee** el presupuesto y **no tiene
estado global mutable**. Recibe un `Budget` y:

- **antes de llamar**: comprueba `exhausted_reasons()`. Si está agotado, lanza
  `BudgetExceededError` sin gastar la llamada.
- **después de llamar**: devuelve el `usage` en la respuesta; el **dueño** del
  presupuesto aplica el consumo.

Para «aplicar el consumo» se ofrece una función **pura**:

```
consume(budget, usage, cost) -> Budget   # devuelve un Budget NUEVO
```

Sin estado compartido no hay carrera que proteger: dos ejecuciones concurrentes
tienen dos `Budget` distintos, y cada una aplica su propio delta. Es seguro por
construcción, no por cerrojo. Además encaja con el estilo funcional que ya usan los
nodos (`_con_presupuesto` devuelve un `Budget` nuevo).

---

## 14. Coste

`pricing.py` define `ModelPricing` y una tabla **vacía por defecto**. Si no hay
entrada para el modelo, `cost = None`. **No se inventan precios.** La tabla está
separada de la lógica de los agentes y se puede rellenar sin tocar el gateway.

`None` significa «no se sabe», distinto de `0.0`, que significa «gratis». El
presupuesto de coste solo actúa si el usuario declaró `max_cost`.

---

## 15. Redacción (`RNF-S3`)

Puntos por los que un secreto podría salir, y qué los cubre:

| Punto | Cobertura |
|---|---|
| Log del gateway | `redact()` en todo mensaje |
| Mensaje de error | `redact()` al construir la excepción |
| Cuerpo de error del proveedor (puede repetir la clave) | `redact()` antes de incluirlo |
| `base_url` con credenciales embebidas | patrón de URL del redactor |
| `repr` de la configuración | `SecretStr` |
| Volcado de la petición | la clave nunca está en `ModelRequest` |

Se añade una prueba explícita de que un error 401 que devuelve la clave en el
cuerpo **no** la filtra al mensaje final.

---

## 16. Observabilidad futura (sin implementar)

`ModelResponse` y los errores llevan ya los campos que Langfuse/OpenTelemetry
necesitarán: `run_id`, `trace_id`, `agent_role`, `provider`, `model`, `latency_ms`,
`usage`, `cost`, `fallback_used`, `error_class`. **No se implementa Langfuse.**
Se deja el dato listo para que la fase de observabilidad no obligue a rehacer la
frontera.

---

## 17. Qué queda explícitamente fuera

No se toca LangGraph. Ningún nodo llama al gateway. No hay prompts de agente (solo
mensajes mínimos de prueba). No hay MCP, ni Graphify, ni STT real, ni RAG, ni
memoria semántica, ni herramientas de escritura, ni ejecución de código generado.

---

## 18. Criterio de aceptación de la fase

`F2` está terminada cuando el gateway existe, es sustituible de proveedor, valida
structured output con Pydantic, tiene errores tipados, timeout, reintentos,
fallback, presupuesto integrado y redacción — y **la suite pasa sin Internet y sin
credenciales**, con `M1` intacto y LangGraph sin llamar todavía al gateway.
