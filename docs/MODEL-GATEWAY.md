# Model Gateway

**Fase:** `F2` — implementado.
**Paquete:** `src/ai_swe/models/`.
**Diseño y decisiones:** [`MODEL-GATEWAY-DESIGN.md`](MODEL-GATEWAY-DESIGN.md).

> Esta es la **referencia de uso**. El porqué de cada decisión está en el documento
> de diseño; aquí está el qué y el cómo.

---

## Responsabilidad

Una **frontera única** entre el sistema y cualquier modelo. Ningún agente importa un
SDK de proveedor; todos hablan con `ModelGateway`.

```
Agente ──> ModelGateway ──> ProviderAdapter ──> proveedor externo
```

Hace: comprobar el presupuesto antes de gastar, reintentar solo lo reintentable,
pasar a un proveedor de respaldo, acotar el tiempo de espera, validar la salida
estructurada contra un contrato Pydantic, contabilizar tokens y coste, y redactar
secretos.

No hace: conocer el proveedor (eso es el adapter), ni razonar sobre la tarea (eso
son los agentes).

---

## Arquitectura

| Capa | Sabe de | No sabe de |
|---|---|---|
| Agente | su tarea | HTTP, proveedores, presupuesto |
| `ModelGateway` | presupuesto, reintentos, fallback, validación, redacción | HTTP, SDK, forma cruda |
| `ProviderAdapter` | HTTP, cabeceras, forma cruda del proveedor | presupuesto, reintentos, fallback |

Ese reparto es lo que hace que cambiar de proveedor sea cambiar una línea de
configuración.

---

## Contratos

En `models/contracts.py`. Los tipos de presupuesto (`Budget`) y de rol
(`AgentRole`) se **reutilizan** de `ai_swe.contracts`; no se duplican.

### `ModelRequest`

| Campo | Tipo | Nota |
|---|---|---|
| `messages` | `list[ModelMessage]` | mínimo 1 |
| `model` | `str \| None` | si es `None`, el de configuración |
| `temperature` | `float \| None` | |
| `max_output_tokens` | `int \| None` | |
| `json_schema` | `dict \| None` | lo rellena el gateway en structured output |
| `timeout_s` | `float \| None` | timeout efectivo, acotado por el presupuesto |
| `run_id`, `trace_id`, `agent_role`, `metadata` | | correlación para observabilidad |

**No hay campo para una credencial.** Es estructural: una petición serializada no
puede filtrar una clave porque no hay dónde ponerla.

### `ModelResponse`

`content`, `structured_data`, `provider`, `provider_requested`, `model`,
`finish_reason`, `usage`, `latency_ms`, `provider_request_id`, `fallback_used`,
`fallback_reason`, `cost`, y la correlación (`run_id`, `trace_id`, `agent_role`).

`provider_requested` y `provider` se registran **los dos**: una respuesta servida
por un respaldo no puede parecer que la sirvió el primario.

### `ModelUsage`

`input_tokens`, `output_tokens`, `total_tokens`, y opcionales `cached_tokens` y
`reasoning_tokens`. **Si el proveedor no reporta un valor, queda en `None`** — que
es distinto de `0`. El total se calcula solo si se conocen las dos partes.

---

## Adapters

### `FakeModelAdapter`

Determinista y sin red. Es la base de la suite y permite trabajar sin credenciales.

```python
from ai_swe.models import FakeModelAdapter

FakeModelAdapter(content="hola")                       # respuesta fija
FakeModelAdapter(structured={"valor": 42})            # structured output
FakeModelAdapter(fault="timeout")                     # falla siempre
FakeModelAdapter(faults=["timeout", "rate_limit"])    # falla en secuencia y luego responde
```

Fallos disponibles: `timeout`, `rate_limit`, `unavailable`, `auth_error`,
`invalid_response`. El registro de llamadas está en `fake.calls`.

### `OpenAICompatibleAdapter`

Habla HTTP contra cualquier endpoint `/chat/completions` compatible con OpenAI:
OpenAI, Ollama, vLLM, OpenRouter, Together… Sin SDK adicional.

```python
from ai_swe.models import OpenAICompatibleAdapter

adapter = OpenAICompatibleAdapter(
    name="openai",
    model="gpt-4o-mini",
    api_key="...",                      # se registra en el redactor al construir
    base_url="https://api.openai.com/v1",
)
```

Acepta `client=` inyectable: con un `httpx.MockTransport` se prueba **sin abrir un
socket**.

---

## Errores

En `models/errors.py`. `recoverable` es una propiedad de la **clase**, así que la
política de reintento es una consecuencia del tipo y no una decisión repetida.

| Error | Reintentable | Cuándo |
|---|---|---|
| `ModelConfigurationError` | no | falta configuración |
| `ModelAuthenticationError` | no | credencial rechazada |
| `UnknownProviderError` | no | proveedor no registrado |
| `InvalidResponseError` | no | respuesta ininterpretable |
| `StructuredOutputError` | no | no cumple el contrato Pydantic |
| `BudgetExceededError` | no | presupuesto agotado |
| `ModelRateLimitError` | **sí** | 429 |
| `ModelTimeoutError` | **sí** | no respondió a tiempo |
| `ProviderUnavailableError` | **sí** | 5xx, error de red |

Todos llevan `error_class` (identificador estable para trazas) y redactan su mensaje
y su detalle.

---

## Retry

Centralizado en el gateway, nunca en un agente. Solo se reintenta lo que el tipo
declara recuperable. Backoff exponencial (`base × 2^n`) con techo; si el proveedor
manda `Retry-After`, se respeta (también con techo).

```python
ModelGateway([adapter], max_retries=2, backoff_base_s=1.0, max_backoff_s=8.0)
```

La función de espera es inyectable (`sleep=`), de modo que las pruebas no duermen.

---

## Fallback

`adapters[0]` es el primario; el resto, respaldos. Se pasa al siguiente **solo** si
el fallo es recuperable; un error de credencial o de configuración se propaga, para
no quedar oculto tras un éxito ajeno.

```python
ModelGateway([primario, respaldo_a, respaldo_b])
```

La respuesta registra `provider_requested`, `provider` y `fallback_used`.

---

## Timeout

Dos niveles, y el efectivo es el menor: el de la petición (`timeout_s`) y el que
queda de presupuesto (`max_seconds − elapsed_seconds`). Un agente no puede esperar
más de lo que le queda.

---

## Budget

**Antes de llamar** se comprueba el presupuesto; si está agotado se lanza
`BudgetExceededError` **sin gastar la llamada**. **Después**, el consumo se aplica
con una función pura:

```python
respuesta = gateway.generate(request, budget=presupuesto)
presupuesto = gateway.consume(presupuesto, respuesta)   # devuelve uno NUEVO
```

El gateway **no tiene estado global mutable**: no hay carrera que proteger. Dos
ejecuciones concurrentes quedan aisladas por construcción.

Los contadores que el modelo consume: `used_model_calls`, `used_tokens`,
`used_cost`. Una llamada cuenta **siempre**, aunque el proveedor no reporte tokens
—el contador de llamadas es lo que evita un bucle infinito de peticiones.

---

## Coste

`pricing.py` tiene una tabla **vacía por defecto**: sin entrada, `cost = None`. **No
se inventan precios.** `None` («no se sabe») es distinto de `0.0` («gratis»).

```python
from ai_swe.models import ModelPricing, PricingTable

tabla = PricingTable({"gpt-4o-mini": ModelPricing(input_per_1k=0.00015, output_per_1k=0.0006)})
gateway = ModelGateway([adapter], pricing=tabla)
```

---

## Seguridad (`RNF-S3`)

| Vía de fuga | Qué la cubre |
|---|---|
| Mensaje de error | el constructor de `ModelGatewayError` redacta |
| Cuerpo de error del proveedor (puede repetir la clave) | redacción en el adapter **y** en el constructor |
| Log del gateway | `redact()` explícito |
| `repr` de la configuración | `SecretStr` |
| Petición serializada | la clave no está en el contrato |
| Credencial del adapter | se registra en el redactor **al construir el adapter** |

Ese último punto importa: la garantía no depende de que el llamante haya pasado por
`load_settings()`. Un adapter construido a mano también queda protegido. Se
descubrió con una prueba, no leyendo el código.

---

## Structured output

```python
from pydantic import BaseModel
from ai_swe.models import MessageRole, ModelMessage, ModelRequest

class Veredicto(BaseModel):
    aprobado: bool
    motivos: list[str]

respuesta = gateway.generate_structured(
    ModelRequest(messages=[ModelMessage(role=MessageRole.USER, content="...")]),
    response_model=Veredicto,
)
datos = respuesta.structured_data          # dict ya validado
objeto = respuesta.structured_as(Veredicto)  # o la instancia tipada
```

El JSON Schema que se envía al modelo se **deriva** con `model_json_schema()`: hay
una sola fuente de verdad. Si la respuesta no valida, lanza `StructuredOutputError`
y **no continúa en silencio**. Se toleran las cercas de bloque de código.

---

## Ejemplo de uso

```python
from ai_swe.config import load_settings
from ai_swe.models import MessageRole, ModelMessage, ModelRequest, gateway_from_settings

ajustes = load_settings()               # no exige clave si no se va a usar el modelo
gateway = gateway_from_settings(ajustes)  # exige credencial aquí, en el borde

try:
    respuesta = gateway.generate(
        ModelRequest(
            messages=[ModelMessage(role=MessageRole.USER, content="Hola")],
            run_id="run-1",
            trace_id="trace-1",
        )
    )
finally:
    gateway.close()

print(respuesta.content, respuesta.usage.total_tokens, respuesta.latency_ms)
```

Con presupuesto y salida estructurada:

```python
from ai_swe.contracts import Budget

presupuesto = Budget(max_model_calls=10, max_tokens=50_000)
respuesta = gateway.generate_structured(peticion, response_model=Veredicto, budget=presupuesto)
presupuesto = gateway.consume(presupuesto, respuesta)
```

---

## Cómo añadir un proveedor

1. Crear el adapter en `src/ai_swe/models/providers/mi_proveedor.py`. Debe cumplir
   `ProviderAdapter`: una propiedad `name` y un método `generate(request)` que
   devuelva `ProviderResponse` y lance errores de `models.errors`.
2. Registrarlo en `models/registry.py`:

```python
def _fabrica_mi_proveedor(config: ProviderConfig) -> ProviderAdapter:
    return MiProveedorAdapter(name=config.name, model=config.model, api_key=...)

_REGISTRO["mi_proveedor"] = _fabrica_mi_proveedor
```

3. Si no necesita credencial, añadirlo a `PROVEEDORES_SIN_CREDENCIALES`.
4. Añadir su prueba con un transporte falso. **Sin red.**

**No hace falta tocar el gateway ni ningún agente.** Si hubiera que tocarlos, el
reparto de responsabilidades estaría mal.

---

## Verificación

| Comprobación | Dónde |
|---|---|
| Suite del gateway (sin red) | `tests/test_model_gateway.py` |
| Prueba real, opt-in | `tests/test_model_gateway_real.py` (`-m real_provider`) |
| Que ningún módulo importe un SDK de proveedor | `test_ningun_modulo_importa_un_sdk_de_proveedor` |
| Que solo los adapters conozcan HTTP | `test_solo_los_adapters_conocen_la_libreria_http` |
| Que LangGraph no llame todavía al gateway | `test_ningun_nodo_llama_al_gateway_todavia` |
| Mutaciones | `tools/mutation_check.py` |
