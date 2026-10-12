# Baseline del Model Gateway (`F2`)

**Fecha:** 2026-10-06
**Fase:** `F2` — Model Gateway.
**Estado de partida:** `M1` y `F1` cerradas; `READY_FOR_MODEL_GATEWAY = YES`.
**Estado de llegada:** el gateway existe, es sustituible de proveedor y está
probado; **no está conectado todavía a LangGraph**.

> **Qué es este documento.** El acta de cierre de `F2`. Registra qué se construyó,
> qué se verificó y con qué evidencia, y termina con un veredicto explícito. No es
> un plan: es un registro de lo que quedó hecho.
>
> **Regla de evidencia.** Un componente no cuenta por existir como fichero. Cada
> afirmación va con la prueba que la sostiene. Lo que no se pudo verificar se dice.

---

## 1. Arquitectura implementada

```
        Requirements Analyst ─┐
        Supervisor ───────────┤
        Researcher ───────────┼──> ModelGateway ──> ProviderAdapter ──> proveedor
        Coder ────────────────┤         │
        Reviewer ─────────────┘         ├── FakeModelAdapter
                                        ├── OpenAICompatibleAdapter
                                        └── (futuros adapters)
```

Ningún agente importa un SDK de proveedor. El reparto de responsabilidades es:

| Capa | Sabe de | No sabe de |
|---|---|---|
| Agente | su tarea | HTTP, proveedores, presupuesto |
| `ModelGateway` | presupuesto, reintentos, fallback, validación, redacción | HTTP, SDK, forma cruda |
| `ProviderAdapter` | HTTP, cabeceras, forma cruda del proveedor | presupuesto, reintentos, fallback |

**Decisión de arquitectura principal: el gateway es síncrono, no `async`.** El
encargo lo describía como `async generate(...)`. No se implementó así porque la
llamada al modelo ocurre en el **hilo del trabajador** (`ThreadPoolExecutor`), no en
el camino `async` de la petición: un adapter `async` obligaría a cada nodo síncrono a
abrir un bucle de eventos por llamada y a convertir LangGraph, que está fuera del
alcance de la fase. Justificación completa en
[`MODEL-GATEWAY-DESIGN.md`](MODEL-GATEWAY-DESIGN.md) §1.

---

## 2. Archivos creados

| Fichero | Qué contiene |
|---|---|
| `src/ai_swe/models/__init__.py` | API pública del paquete |
| `src/ai_swe/models/contracts.py` | `ModelRequest`, `ModelResponse`, `ModelUsage`, `ProviderConfig`, `ModelMessage`, `FinishReason` |
| `src/ai_swe/models/errors.py` | jerarquía `ModelGatewayError` |
| `src/ai_swe/models/budget.py` | consumo del presupuesto (funciones puras) |
| `src/ai_swe/models/pricing.py` | tabla de precios enchufable (vacía por defecto) |
| `src/ai_swe/models/registry.py` | registro explícito de proveedores |
| `src/ai_swe/models/gateway.py` | `ModelGateway` |
| `src/ai_swe/models/providers/__init__.py` | adapters |
| `src/ai_swe/models/providers/base.py` | `ProviderAdapter` (protocolo) + `ProviderResponse` |
| `src/ai_swe/models/providers/fake.py` | `FakeModelAdapter` |
| `src/ai_swe/models/providers/openai_compatible.py` | adapter real (httpx) |
| `tests/test_model_gateway.py` | suite del gateway (sin red) |
| `tests/test_model_gateway_real.py` | prueba real, opt-in |
| `docs/MODEL-GATEWAY.md` | referencia de uso |
| `docs/MODEL-GATEWAY-DESIGN.md` | diseño previo (FASE 1) |
| `docs/BASELINE-MODEL-GATEWAY.md` | este documento |

## 3. Archivos modificados

| Fichero | Cambio |
|---|---|
| `pyproject.toml` | marcador `real_provider` registrado (`--strict-markers` lo exige) |
| `tools/mutation_check.py` | **11 mutaciones** nuevas del gateway |
| `.gitignore` | **corrección importante** — ver §21 |
| `README.md` | estado, tabla de componentes y recuento de pruebas |
| `docs/README.md` | índice: documentos nuevos |
| `docs/auditoria-2026-10-06/09_ROADMAP.md` | `F2` marcada como hecha |
| `PROJECT_SNAPSHOT.json` | estado y reservas |

**No se modificó ningún nodo de LangGraph, ni el almacén, ni la API, ni el
frontend.** Es deliberado: así se comprueba que `F2` no degradó `M1`.

---

## 4. Contratos

`ModelRequest` (mensajes, modelo, temperatura, `max_output_tokens`, `json_schema`,
`timeout_s`, y correlación `run_id`/`trace_id`/`agent_role`/`metadata`),
`ModelResponse`, `ModelUsage`, `ProviderConfig`, `ModelMessage`, `FinishReason`.

**Reutilización, no duplicación.** `Budget` y `AgentRole` se toman de
`ai_swe.contracts`; no se redefinen. Se verificó antes de empezar que no había
contratos de modelo preexistentes.

**Sin secretos en la petición.** No hay campo donde poner una credencial. Es
estructural: una petición serializada no puede filtrar una clave. Hay una prueba que
comprueba por partes de nombre que ningún campo es de credencial (y que no marca
`max_output_tokens`, que es un contador).

---

## 5. `ProviderAdapter`

Protocolo en `providers/base.py`: propiedad `name` y `generate(request) ->
ProviderResponse`. Es un `Protocol`, no una clase base, para que un doble de prueba
sea válido sin ceremonia. Es `runtime_checkable`.

`ProviderResponse` es la respuesta **cruda**; el gateway la normaliza. Esa frontera
es lo que permite que el gateway no conozca ningún proveedor y que un adapter no
conozca la política.

---

## 6. `FakeModelAdapter`

Determinista, sin red, configurable por constructor (sin estado global). Provoca a
voluntad: `timeout`, `rate_limit`, `unavailable`, `auth_error`, `invalid_response`,
y secuencias (`faults=[...]`) para probar «falla, falla, funciona». Registra las
peticiones en `.calls`. Valida en el constructor que el nombre del fallo sea
conocido.

---

## 7. Adapter real

`OpenAICompatibleAdapter`, sobre `httpx` contra `/chat/completions`. Se eligió HTTP
y no un SDK porque «compatible con OpenAI» es un contrato HTTP: el mismo adapter
sirve para OpenAI, Ollama, vLLM, OpenRouter y cualquier endpoint compatible, sin
dependencia nueva.

Mapea: 401/403 → autenticación; 429 → límite de tasa (respeta `Retry-After`); 5xx →
no disponible; 408/504 → timeout; otros 4xx → respuesta inválida; `httpx.TimeoutException`
→ timeout; `httpx.HTTPError` → no disponible; JSON inválido o sin `choices` →
respuesta inválida.

**Es el único módulo que conoce un proveedor**, y hay una prueba estructural que lo
comprueba: ningún fichero fuera de `models/providers/` importa `httpx`, y ningún
módulo importa un SDK de proveedor.

---

## 8. Registry

Diccionario explícito `{nombre → factoría}`: `fake`, `openai_compatible`, `openai`,
`ollama`, `vllm`. Un nombre no registrado lanza `UnknownProviderError` **con la
lista de los registrados**, para que el error sea accionable.

**Sin import dinámico.** Resolver el proveedor con `importlib` a partir de un valor
de configuración sería una vía de ejecución arbitraria. Se comprueba de dos formas:
por comportamiento (nombres peligrosos como `os` o `subprocess` no resuelven) y
sobre el **AST** del fichero (no hay `Import`/`ImportFrom`/`import_module` de
`importlib`). Se usa el AST y no una búsqueda de subcadena porque el docstring
explica precisamente por qué no se usa, y una búsqueda de texto daría un falso
positivo —el mismo cepo que ya apareció midiendo otros módulos—.

---

## 9. Structured output

`gateway.generate_structured(request, response_model=Contrato)`. Flujo: se deriva el
esquema con `Contrato.model_json_schema()`, se añade a los mensajes y a
`request.json_schema`, el adapter responde, se extrae el JSON (tolerando cercas de
bloque de código) y se valida con `model_validate`. Si falla, `StructuredOutputError`
y **no continúa en silencio**.

**Una sola fuente de verdad: el contrato Pydantic.** El JSON Schema no se escribe a
mano en paralelo; hay una prueba que afirma que lo enviado es exactamente
`Contrato.model_json_schema()`.

`ModelResponse.structured_data` es un `dict` ya validado (serializable, apto para un
punto de control); `structured_as(Contrato)` lo rehidrata al tipo si se prefiere.

---

## 10. Retry

Centralizado en el gateway. Solo se reintenta lo que el **tipo** de error declara
recuperable: timeout, límite de tasa, no disponible. No se reintenta autenticación,
respuesta inválida, configuración, proveedor desconocido ni presupuesto agotado.

Backoff exponencial con techo (`base × 2^n`, `max_backoff_s`). Si el proveedor manda
`Retry-After`, se respeta (también acotado por el techo). La función de espera es
inyectable, de modo que la suite no duerme.

---

## 11. Fallback

`adapters[0]` es el primario; el resto, respaldos. Se pasa al siguiente **solo** si
el fallo es recuperable. Un error de credencial o de configuración se propaga: se
repetiría igual en el respaldo, y no debe quedar oculto tras un éxito ajeno.

La respuesta registra `provider_requested`, `provider` y `fallback_used` — una
respuesta del respaldo no puede parecer del primario. `fallback_reason` va redactado.

En esta fase no se conectaron dos proveedores reales: el soporte se implementó y se
probó con adapters falsos.

---

## 12. Timeout

Dos niveles, y el efectivo es el menor: el de la petición y el que queda de
presupuesto (`max_seconds − elapsed_seconds`), con un mínimo para que una llamada no
nazca imposible. Hay dos pruebas: una de que el valor acotado llega al objeto de
petición, y otra de que llega **de verdad a httpx** (se inspecciona
`request.extensions["timeout"]`), que es lo que demuestra que no se queda en un
campo decorativo.

---

## 13. Budget

**Antes de llamar**: `assert_budget_available` lanza `BudgetExceededError` con los
motivos si está agotado, **sin gastar la llamada** (hay una prueba de que el adapter
no recibió nada). Solo se comprueban los límites que el modelo consume: `tokens`,
`model_calls`, `seconds`, `cost`. `tool_calls` y `review_cycles` son de otras capas
y no bloquean al modelo.

**Después**: `gateway.consume(presupuesto, respuesta)` devuelve un `Budget` **nuevo**
con `used_model_calls + 1`, `used_tokens += total` (si se conoce) y `used_cost += cost`
(si se conoce).

**Concurrencia**: el gateway **no tiene estado global mutable**. Recibe el
presupuesto y devuelve el delta. Sin estado compartido no hay carrera que proteger:
dos ejecuciones concurrentes quedan aisladas por construcción, no por cerrojo.

---

## 14. Token usage

`ModelUsage` con `input_tokens`, `output_tokens`, `total_tokens` y opcionales
`cached_tokens` y `reasoning_tokens`. **Si el proveedor no reporta un valor, queda en
`None`**, que es distinto de `0`: `0` afirma que no se consumió nada, `None` admite
que no se sabe. El total se deriva **solo** si se conocen las dos partes.

Una llamada cuenta **siempre**, aunque no haya tokens: el contador de llamadas es lo
que evita un bucle infinito de peticiones.

---

## 15. Cost accounting

`pricing.py` con una tabla **vacía por defecto**: sin entrada, `cost = None`. **No se
inventan precios.** `None` («no se sabe») es distinto de `0.0` («gratis»). La tabla
está separada de la lógica del gateway y de los agentes, y se rellena por
configuración. `ModelPricing` rechaza precios negativos.

---

## 16. `RNF-S3`

| Vía de fuga | Cobertura |
|---|---|
| Mensaje y detalle de error | el constructor de `ModelGatewayError` redacta |
| Cuerpo de error del proveedor | redacción en el adapter **y** en el constructor |
| Log del gateway | `redact()` explícito |
| `repr` de la configuración | `SecretStr` |
| Petición serializada | la clave no está en el contrato |
| Credencial del adapter | se registra en el redactor **al construir el adapter** |

**El último punto se descubrió con una prueba, no leyendo el código.** Una prueba
construía el adapter con una clave **sin prefijo reconocible** y comprobaba que un
401 que la devuelve en el cuerpo no la filtra. Falló: la garantía dependía de que
alguien hubiera llamado antes a `load_settings()`. Se corrigió en el **código** —el
adapter registra su propia credencial, porque es quien la posee—, no en la prueba.

Además, hay una prueba que **aísla** la redacción del constructor de errores. Sin
ella, la redacción del adapter enmascara a la del constructor: se puede desactivar
cualquiera de las dos y la suite sigue verde. Es el mismo fallo de capas que ya
apareció en el redactor de secretos, y se detectó porque una mutación no caía.

---

## 17. Tests añadidos

`tests/test_model_gateway.py` (**72 pruebas**) y `tests/test_model_gateway_real.py`
(1, opt-in).

Cobertura de los 20 casos exigidos:

| # | Caso | Prueba |
|---|---|---|
| 1 | FakeAdapter éxito | `test_fake_adapter_exito` |
| 2 | Structured output válido | `test_structured_output_valido` |
| 3 | Structured output inválido | `test_structured_output_invalido_lanza` |
| 4 | Provider desconocido | `test_provider_desconocido_lanza_y_dice_cuales_hay` |
| 5 | Configuración incompleta | `test_proveedor_con_credencial_sin_credencial_falla_en_el_borde` |
| 6 | Timeout | `test_timeout_es_recuperable` |
| 7 | Rate limit | `test_rate_limit_es_recuperable` |
| 8 | Retry exitoso | `test_reintento_exitoso` |
| 9 | Retry agotado | `test_retry_agotado_propaga_el_ultimo_error` |
| 10 | Error no reintentable | `test_error_no_reintentable_no_se_reintenta` |
| 11 | Fallback exitoso | `test_fallback_exitoso` |
| 12 | Fallback agotado | `test_fallback_agotado_propaga_el_ultimo_error` |
| 13 | Budget model calls | `test_budget_model_calls_agotado_no_gasta_la_llamada` |
| 14 | Budget tokens | `test_budget_tokens_agotado` |
| 15 | Budget deadline | `test_budget_deadline_agotado` |
| 16 | Budget cost | `test_budget_coste_agotado` |
| 17 | Redacción de secretos | `test_un_error_del_proveedor_no_filtra_la_clave` + 4 más |
| 18 | Usage aggregation | `test_usage_agregado_al_presupuesto` |
| 19 | Provider selection | `test_el_registro_construye_el_adapter_del_proveedor_pedido` |
| 20 | No serialización de API key | `test_la_configuracion_no_serializa_la_clave` + 2 más |

Además: adapter real sin red (éxito, 401, 429 con `Retry-After`, 5xx, timeout, JSON
malformado, sin `choices`, timeout aplicado a httpx), extracción de JSON, mapeo de
`finish_reason`, `consume` puro, precios, y cinco pruebas estructurales
(ningún SDK de proveedor, solo los adapters conocen HTTP, ningún nodo llama al
gateway, el registro no usa import dinámico, el código fuente no está excluido por
`.gitignore`).

---

## 18. Mutaciones añadidas

**11 mutaciones** nuevas en `tools/mutation_check.py`. Cada una demuestra una
propiedad; ninguna es de relleno.

| Mutación | Propiedad que demuestra |
|---|---|
| el gateway deja de comprobar el presupuesto | el presupuesto se comprueba **antes** |
| el timeout deja de acotarse al presupuesto | el tiempo se acota al presupuesto |
| la salida estructurada se acepta sin validar | la validación Pydantic es real |
| la llamada al modelo deja de contarse | `used_model_calls` se incrementa |
| los tokens dejan de sumarse al presupuesto | los tokens se contabilizan |
| los errores dejan de redactar el mensaje | la redacción de errores es real |
| el adapter real deja de registrar su credencial | la credencial queda protegida |
| una credencial inválida pasa a reintentarse | autenticación **no** se reintenta |
| el gateway ignora los proveedores de respaldo | el fallback es real |
| el registro resuelve proveedores por import dinámico | el registro no importa dinámicamente |
| el `.gitignore` vuelve a excluir el paquete del gateway | el código fuente es versionable |

---

## 19. Resultado de la suite completa

| Verificación | Resultado |
|---|---|
| Suite completa | **284 / 284** (1 omitida: la prueba real) |
| Pruebas de `M1` intactas | **211 / 211** |
| Pruebas del gateway | **72 / 72** |
| Mutaciones del proyecto | **35 / 35** cazadas |
| Mutaciones de la redacción | **8 / 8** cazadas |
| Supuestos de `M1` | **5 / 5** (+3/3 automutación) |
| Frontend en navegador real | **11 / 11** |
| `uv lock --check` | verde |
| Sin Internet | ✅ toda la suite |
| Sin credenciales | ✅ toda la suite |

---

## 20. Test real de proveedor

### `REAL_PROVIDER_TEST = NOT_EXECUTED_NO_CREDENTIALS`

No hay credencial configurada en el entorno, así que la prueba de integración real
**no se ejecutó**. La fase lo prevé explícitamente: no se pide al usuario que pegue
una clave en el chat, no se escribe una en el código y no se inventa una.

La prueba existe, está marcada (`@pytest.mark.real_provider`), separada en su propio
fichero y es opt-in por dos condiciones a la vez
(`AI_SWE_RUN_REAL_PROVIDER_TESTS=1` **y** `AI_SWE_MODEL_API_KEY`). Se omite en la
suite normal; nunca convierte una API externa en dependencia del CI.

**Qué queda sin verificar por esto:** que la cadena `config → adapter → gateway →
proveedor → respuesta → usage → Pydantic` funcione contra un servicio real. Todo lo
demás —incluido el adapter real, ejercitado entero con un transporte falso— sí está
verificado. Es la única afirmación de esta acta que no se pudo comprobar.

---

## 21. Riesgos restantes

1. **`.gitignore` excluía el paquete del gateway (corregido, y es el hallazgo más
   serio de la fase).** La regla `models/`, pensada para los pesos de STT
   descargados, no estaba anclada: un patrón sin barra inicial no significa «en la
   raíz» sino «en cualquier sitio», así que coincidía con `src/ai_swe/models/`. El
   paquete habría quedado **fuera del control de versiones en silencio**: las
   pruebas pasaban, `git status` no avisaba, y el commit no lo habría incluido. Se
   detectó al notar que no aparecía como nuevo. Corregido anclando `/models/`, y
   también `/var/`, `/tmp*/` y `/_tmp/`, que tenían el mismo defecto. Hay una prueba
   y una mutación que lo guardan.

2. **El gateway no está conectado a LangGraph.** Ningún nodo lo llama. Es el
   objetivo de la fase, no un olvido — pero significa que la integración real está
   sin ejercitar de punta a punta.

3. **Sin prompts de agente.** Solo existen mensajes mínimos de prueba. La
   arquitectura de prompts es trabajo de `F3`+.

4. **`max_cost` sigue sin fuente de precio.** La tabla está vacía por defecto; hasta
   que se rellene, `cost` es `None` y el límite de coste no actúa.

5. **La prueba real no se ejecutó** (§20). Es la única verificación pendiente.

6. **Sin autenticación.** Sigue abierto desde la auditoría externa. No bloquea `F2`,
   pero afecta a cualquier despliegue.

7. **El adapter real no se ha probado contra un proveedor real**, solo contra
   respuestas simuladas. El mapeo de errores se cubre con todos los códigos
   relevantes, pero un proveedor con peculiaridades no anticipadas podría necesitar
   ajustes.

---

## 22. Próximo paso recomendado

**`F3` — Requirements Analyst**, conectando por fin el gateway a un nodo, y solo a
uno. Es el primer punto en el que `F2` se ejerce de verdad de punta a punta, y hacerlo
con un solo nodo mantiene el cambio acotado y verificable.

Antes de eso, dos cosas baratas y valiosas:

1. **Ejecutar la prueba real** con una credencial, para cerrar el único punto sin
   verificar (§20). Es una llamada pequeña y barata.
2. **Rellenar la tabla de precios** del modelo que se vaya a usar, para que el
   presupuesto de coste deje de ser un campo decorativo.

---

## Veredicto

### `MODEL_GATEWAY_READY = YES`

**Con qué respaldo.** Todos los criterios de salida de la fase se cumplen:

- `ModelGateway`, `ProviderAdapter`, `FakeAdapter` y un adapter real existen.
- Ningún agente importa un proveedor: comprobado estructuralmente.
- Structured output funciona y **Pydantic valida la respuesta**; un `dict` inválido
  no cruza.
- Los errores están tipados y `recoverable` es propiedad de la clase.
- Timeout, reintentos y fallback existen y están probados.
- El `Budget` está integrado; tokens y llamadas se contabilizan; el coste admite
  `None` sin inventar.
- `RNF-S3` protege errores y logs, incluida la credencial del adapter.
- La suite pasa **sin Internet y sin credenciales**.
- `M1` sigue intacto (211/211), LangGraph **no** llama al gateway, y MCP, Graphify y
  los agentes reales siguen sin implementarse.
- **35/35** mutaciones cazadas, incluidas las 11 de esta fase.

**Con qué reserva.** `MODEL_GATEWAY_READY = YES` significa «la frontera está
construida y probada», **no** «el sistema ya usa un modelo». Concretamente:

- **No hay ninguna llamada real verificada** (§20). Es la reserva principal.
- El gateway **no está conectado** a ningún nodo: `F2` entrega la pieza, no la
  instalación.
- `max_cost` no actúa hasta que se rellene la tabla de precios.
- El adapter real solo se ha probado contra respuestas simuladas.

**Siguiente paso:** `F3` (Requirements Analyst), conectando el gateway a un único
nodo. **No se inicia en esta sesión.**
