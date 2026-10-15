# Hugging Face Agent Model Lab

Fecha de consulta: 14 de octubre de 2026, America/Mexico_City.
Estado: **PARTIAL — descubrimiento público y arnés offline preparados**.
No hay todavía resultados de inferencia real ni selección validada de modelos.

## Arquitectura y límite de esta entrega parcial

`notebooks/01_HF_AGENT_MODEL_LAB.ipynb` es interfaz experimental; importa la lógica
reutilizable de `tools/model_lab.py` y `tools/model_lab_cases.py`. El runtime del
producto no los importa y no depende de Jupyter, transformers, PyTorch ni cloud GPU.
La modalidad GPU cloud opcional está en `tools/model_lab_cloud.py`, con imports
perezosos y revisión Hub fijada por SHA. No se ha ejecutado ni descargado pesos.

Flujo: laboratorio externo → evidencia/recomendación → configuración futura de
ModelGateway. No hay frontend → notebook → backend ni nuevos endpoints de producto.
Researcher sigue siendo determinista. No se ha avanzado a routing real (Fase E).

## Fuentes oficiales actuales

Se consultaron estas páginas antes de implementar el laboratorio:

| Tema | Fuente oficial | Aplicación |
| --- | --- | --- |
| Router y selección de proveedor | [Inference Providers](https://huggingface.co/docs/inference-providers/en/index) | Base `https://router.huggingface.co/v1`, provider fijado como sufijo del modelo |
| Descubrimiento y precios/contexto/capacidades | [Hub API](https://huggingface.co/docs/inference-providers/en/hub-api) | GET público `/models`, campos opcionales desconocidos permanecen null |
| Chat, usage, tools y parámetros | [Chat Completion](https://huggingface.co/docs/inference-providers/en/tasks/chat-completion) | messages, max_tokens, usage prompt/completion/total; contrato HTTP compatible |
| JSON Schema | [Structured Outputs](https://huggingface.co/docs/inference-providers/guides/structured-output) | Distinguir validación local del gateway de garantía estructural del proveedor |
| Tool calling | [Function Calling](https://huggingface.co/docs/inference-providers/guides/function-calling) | Marca de catálogo no equivale a prueba funcional o integración en runtime |
| Autenticación y seguridad | [User access tokens](https://huggingface.co/docs/hub/en/security-tokens) | Token externo, mínimo privilegio y permiso de Inference Providers; no se exporta |
| Facturación/créditos | [Pricing and Billing](https://huggingface.co/docs/inference-providers/en/pricing) | Precio publicado no demuestra saldo incluido disponible en una cuenta |
| Rate limits del Hub | [Hub Rate limits](https://huggingface.co/docs/hub/en/rate-limits) | HTTP 429 y cuotas del Hub; no se extrapolan esos límites a todos los proveedores |
| Modalidad GPU opcional | [Transformers Pipeline](https://huggingface.co/docs/transformers/en/pipeline_tutorial) | Entorno externo, generación local opcional y carga sin código remoto |

Los precios del catálogo son USD por millón de tokens cuando están presentes.
Se conserva su procedencia y fecha; no se deducen precios ausentes ni se usa una
tabla fija de modelos. Las disponibilidades y promociones pueden cambiar.

## Adapter existente: conclusión provisional

Se reutiliza `OpenAICompatibleAdapter`; no se creó HuggingFaceAdapter.
Pruebas offline del adapter real con MockTransport confirman URL, Bearer,
identificador `model:provider`, messages, límite de salida, timeout y lectura de usage.
También prueban JSON inválido/esquema incorrecto/truncamiento, timeout, 400,
401/403 sin reintento y 429/5xx con reintento acotado.

**Límite:** el adapter actual envía `response_format=json_object`; el gateway
instruye el esquema Pydantic y valida la respuesta localmente. Esto NO es la
modalidad `json_schema/strict` garantizada por el servidor. La compatibilidad
efectiva y la necesidad de un cambio genérico en esa abstracción se decidirán con
evidencia real, no creando un adapter HF paralelo por anticipado.

**Tool calls:** el contrato runtime actual ModelMessage/ModelRequest no transporta
tools ni tool_calls. El catálogo se registra; `tool_call_compatibility=not_probed`
en los ensayos. No se afirma integración ni compatibilidad verificada. Un probe
aislado real y sin ejecución de herramientas queda pendiente del gate de consumo.

## Casos y métricas

Ocho casos pequeños, dos por rol: interpretar modificación/inspección con alcance;
planificar modificación con dependencias o solo lectura; proponer retorno 42 o
suma de dos argumentos; revisar un cambio correcto o uno cuyo test falla.
Se usan TaskInterpretation, RunPlan, CodeProposal y ReviewVerdict existentes.
El Coder propone contenido; diff/hashes los calcula el runtime, nunca el modelo.
La evaluación de código solo inspecciona AST: no ejecuta código del proveedor.

Por intento: JSON válido, esquema válido, éxito semántico, latencia de extremo a
extremo, usage reportado o null, error tipado, reintento, fallback (cero porque no
hay respaldo en el laboratorio), coste estimado con precios del catálogo o null.
No se guardan headers, credenciales ni texto bruto de respuestas.

La preselección dinámica usa proveedores live, capacidades estructuradas
anunciadas y precios/contexto conocidos. No se llama a eso selección por calidad.
Para recomendar un modelo por rol se exigen todos sus casos correctos al menos
dos veces, sin errores; luego latencia, coste, contexto y tools anunciadas.
No se obliga a elegir modelos distintos. Esta batería no pretende sustituir una
evaluación amplia de calidad o seguridad de modelos.

## Gate antes de inferencia

La presencia de HF_TOKEN se comprueba solo como condición; nunca se imprime.
CLI: `.venv\Scripts\python.exe -m tools.model_lab check-gate`.
Lee el entorno de proceso o `.env` de la raíz ignorado por Git. No importa un
archivo del usuario en outputs ni devuelve su contenido. No infiere un saldo
gratuito por tipo de cuenta, precio o bandera promocional.

La inferencia requiere un límite monetario positivo autorizado expresamente.
Reserva conservadora por intento: contexto máximo × tarifa de entrada + salida
máxima de 512 tokens × tarifa de salida. Se reserva también cada posible
reintento y no se devuelven reservas por fallo/usage ausente. No hay reintentos
ocultos del gateway ni fallback durante el benchmark. Auth aborta la batería.
Los controles de facturación del proveedor son necesarios para un techo externo
de cuenta; un guard local no puede garantizar cargos ajenos a sus peticiones.

Con tres candidatos, ocho casos y dos repeticiones, la batería base tiene **48
llamadas**, sin retries. El coste/reserva se calcula con el catálogo fresco antes
de ejecutarla; no se efectuó ninguna de ellas. Probes de tools y E2E posterior
necesitarán contabilidad dentro del mismo límite autorizado o una ampliación.

## Evidencia del checkpoint

`var/model_lab_results.json`: catálogo público obtenido realmente, **268** pares
modelo/proveedor; status DISCOVERY_ONLY, measurements vacío y routing vacío.
Consulta de metadatos sin credencial; cero llamadas de inferencia.

Pruebas focalizadas: **19 PASS**, sin credenciales ni red. Ruff: PASS para cuatro
archivos Python nuevos. Suite completa nueva: **709 PASS, 3 SKIP, 0 FAIL** en
205.49 s (`_tmp/productization-d-offline.xml`). Las tres omisiones continúan siendo
proveedor real, STT real y el vector de enlace simbólico no permitido por Windows.
Notebook sin outputs guardados. Pausa explícita del usuario antes del gate HF.

La Fase D no se declara completada hasta obtener benchmarks reales y resolver
probes de capabilities. No hay ejecutable, instalador ni tag v0.1.0 todavía.
