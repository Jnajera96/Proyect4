# Selección de tecnologías

> **Estado (2026-10-06): VIGENTE.** Las tecnologías aquí seleccionadas son las que
> el proyecto usa realmente, verificadas contra el entorno instalado. Ver
> `docs/auditoria-2026-10-06/00_ESTADO_ACTUAL.md`.
>
> Una salvedad: **`mcp` figura como dependencia obligatoria en `pyproject.toml`
> pero no está instalada ni se importa**, porque pertenece a una fase futura
> (`F13`). Su clasificación correcta es *extra opcional*, no dependencia base.

> Sección 19 de la solicitud. Para cada tecnología se responden las ocho preguntas
> que exige el documento [DOC, §5]: qué problema resuelve, por qué es necesaria, qué
> alternativas existen, por qué se selecciona, qué ventajas ofrece, qué limitaciones
> introduce, qué ocurriría si se elimina, y cómo cambiaría la arquitectura al crecer.

**Principio rector [DOC, §13]:** *"Agregar más tecnologías no significa tener una mejor
arquitectura."* Cada tecnología de esta lista está justificada. Lo que no está, se declara
en §0.

---

## 0. Resumen: el stack completo

| Capa | Tecnología | Estado | Por qué en una línea |
|---|---|---|---|
| Lenguaje | **Python 3.12+** | Núcleo | Ecosistema de agentes, tipado moderno, mismo lenguaje para backend y evaluación. |
| API | **FastAPI** + Uvicorn | Núcleo | Contratos tipados con Pydantic, asíncrono, documentación automática. |
| Contratos y configuración | **Pydantic v2** + `pydantic-settings` | Núcleo | Validación de salidas del modelo y de configuración en un solo lugar. |
| Orquestación | **LangGraph** | Núcleo | Grafo explícito con estado tipado, puntos de control y pausa/reanudación. |
| Protocolo de herramientas | **MCP** (revisión `2026-07-28`) | Núcleo | Frontera de proceso para las herramientas que tocan el exterior. |
| Modelo | **Proveedor abstracto** (nube por defecto, local opcional) | Núcleo | Sustituible sin tocar agentes; permite medir costo y precisión. |
| Estado | **SQLite** (checkpointer) | Núcleo | Persistencia sin servidor, suficiente para el prototipo y reanudable. |
| Voz | **faster-whisper** | Núcleo de la demo, borde del sistema | Local, privado, sin costo marginal. Ver `01-arquitectura.md` §11. |
| Observabilidad | **Langfuse** (autoalojable) + registros JSON | Soporte | Trazas de LLM con árbol, tokens y costo. |
| Pruebas y evaluación | **pytest** + arnés propio | Núcleo | La evaluación es un entregable, no un extra. |
| Empaquetado | **Docker** + `docker-compose` | Soporte | Reproducibilidad del entorno y aislamiento de la ejecución. |
| Frontend | **HTML + JS nativo** (`MediaRecorder`, SSE) | Soporte | Sin *build step*. Un framework no aporta a los ejes evaluados. |
| Control de versiones | **Git** | Núcleo | El *worktree* aislado es el mecanismo de contención. |

### Lo que NO está en el stack, y por qué

| Descartado | Motivo | Referencia |
|---|---|---|
| Vector Database (Qdrant, pgvector, Pinecone, Weaviate, Milvus, Chroma) | Sin corpus que lo justifique; la búsqueda por texto sobre código es exacta y superior. | `DEC-04` |
| RAG / GraphRAG | Ídem. El repositorio se lee directamente. | `DEC-04` |
| **Capa de contexto basada en grafo** (Graphify, `codebase-memory-mcp`, Axon, `code-review-graph`, `claude-context`) | El ahorro de tokens lo produce el **recorte**, no el grafo, y el recorte ya es un requisito nuestro. Solo paga cuando el repositorio **no cabe en contexto**. Introduce `AM-13` (destila contenido no confiable en resúmenes con mayor autoridad aparente) y rompe la reproducibilidad de `EXP-01`. | `docs/05-graphify-evaluacion.md`, `EXP-08` |
| **Mapa de símbolos del repositorio** (`repo_map`) | **No descartado — pendiente de medición.** Es la forma mínima del principio anterior: determinista, ~150 líneas, ~1 000 tokens, sin riesgo de inyección semántica. Primer paso de `EXP-08`. | `EXP-08` |
| **Compresores de salida de terminal** (RTK y similares) | Resuelven un problema que no tenemos: el Coder no ejecuta comandos libres, y `run_tests` devuelve una salida estructurada y acotada. | `01-arquitectura.md` §13.2 |
| Memoria persistente de largo plazo | Beneficio no demostrado; riesgo de fuga entre ejecuciones. | `DEC-05` |
| CrewAI, AutoGen, PydanticAI | Se comparan en §6; ninguno resuelve mejor nuestro requisito de control. | §6 |
| Kubernetes | Se diseña la estrategia de escalado; no se despliega infraestructura de escala empresarial. | `01-arquitectura.md` §6.8 |
| Colas de mensajes (RabbitMQ, Kafka) | El prototipo no tiene el volumen que las justifique. El punto de extensión está documentado. | §3 |
| PostgreSQL | SQLite cubre el prototipo; Postgres es la ruta de crecimiento documentada. | §3 |
| Fine-tuning | No es un problema de pesos, es un problema de orquestación. | `01-arquitectura.md` §4.2 |
| Framework de frontend (React, Vue) | Añade cadena de herramientas y dependencias sin aportar a los ejes evaluados. | §12 |
| Framework de guardrails (NeMo, Guardrails AI, Llama Guard) | Nuestros guardrails son deterministas y verificables. Un guardrail que razona es un guardrail que se puede convencer. Ver §11. | `01-arquitectura.md` §16.2 |

---

## 1. Python 3.12+

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Lenguaje de implementación del sistema completo. |
| **¿Por qué es necesaria?** | Es el lenguaje del ecosistema de agentes (LangGraph, SDK de MCP, Pydantic) y permite que backend, agentes y arnés de evaluación compartan tipos. |
| **¿Qué alternativas existen?** | TypeScript/Node (mejor integración con frontend), Go o Rust (mejor rendimiento y despliegue), Java/Kotlin (mejor en entornos empresariales). |
| **¿Por qué la seleccionamos?** | Usar **un solo lenguaje** para contratos, orquestación y evaluación evita duplicar el modelo de datos. Con TypeScript habría que redefinir los esquemas de estado en dos sitios, y divergirían. |
| **¿Qué ventajas ofrece?** | Tipado moderno (`Protocol`, `Literal`, `TypeVar`), `asyncio` maduro, Pydantic para validación, y todo el ecosistema de agentes disponible. |
| **¿Qué limitaciones introduce?** | El despliegue requiere un intérprete; el rendimiento en cómputo puro es menor que Go o Rust (irrelevante: nuestro cuello de botella son las llamadas al modelo). El *release* de 3.12+ es reciente; algunas bibliotecas pueden no estar actualizadas. |
| **¿Qué ocurriría si se elimina?** | El proyecto no existe. Es una elección de sustrato, no un componente. |
| **¿Cómo cambia al crecer?** | No cambia. Se fija la versión mínima en `pyproject.toml` y se empaqueta en contenedor para eliminar la variabilidad del entorno. |

---

## 2. FastAPI + Uvicorn

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Exponer el sistema como servicio HTTP: crear ejecuciones, transmitir progreso, recibir aprobaciones, recuperar resultados y trazas. |
| **¿Por qué es necesaria?** | Un sistema agentic necesita una frontera que valide entradas no confiables y publique estado de forma incremental. |
| **¿Qué alternativas existen?** | Flask (maduro, sincrónico por defecto), Django REST (completo pero pesado para esto), Litestar (rendimiento similar, menor adopción), Node/Express (otro lenguaje), gRPC (mejor rendimiento, peor ergonomía para el frontend). |
| **¿Por qué la seleccionamos?** | Integración nativa con Pydantic (el mismo modelo que valida las salidas del modelo), soporte asíncrono para *streaming*, y documentación OpenAPI automática —que es un entregable útil para la defensa. |
| **¿Qué ventajas ofrece?** | Validación declarativa, `async` para concurrencia de E/S, `StreamingResponse`/SSE para el progreso, y pruebas sencillas con `TestClient`. |
| **¿Qué limitaciones introduce?** | El proceso de la API **no debe** ejecutar tareas largas: si lo hace, degrada la atención de todas las peticiones. Esto obliga a separar la ejecución del proceso que sirve HTTP (`RNF-E3`), lo que añade un componente. Uvicorn en un solo proceso no usa varios núcleos; requiere un gestor de procesos. |
| **¿Qué ocurriría si se elimina?** | No habría servicio. Alternativa: el sistema sería una CLI. Válido académicamente, pero perderíamos la interfaz de voz, el panel de aprobaciones y la demostración del flujo. |
| **¿Cómo cambia al crecer?** | Varias réplicas detrás de un *balanceador*, sin sesiones fijas (el estado vive en el almacén, `RNF-E1`). Los trabajadores de ejecución escalan por separado. |

---

## 3. Pydantic v2 + pydantic-settings

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Dos problemas con la misma herramienta: **validar las salidas del modelo** y **validar la configuración**. |
| **¿Por qué es necesaria?** | Es el punto donde un LLM deja de ser texto y pasa a ser datos. Sin validación por esquema, el flujo de inferencia no tiene contrato (`01-arquitectura.md` §7.3). |
| **¿Qué alternativas existen?** | `dataclasses` + validación manual, `attrs` + `cattrs`, Marshmallow, `msgspec`, JSON Schema con validador independiente, TypedDict (sin validación en tiempo de ejecución). |
| **¿Por qué la seleccionamos?** | Genera **JSON Schema** a partir del modelo, y ese esquema es exactamente lo que se necesita para el *tool calling* y para los `inputSchema` de MCP. Un solo origen de verdad para el contrato del modelo, el contrato HTTP y el contrato de la herramienta. |
| **¿Qué ventajas ofrece?** | Validación en tiempo de ejecución, coerción controlada, mensajes de error que sirven como realimentación al modelo, y serialización a JSON verificada. |
| **¿Qué limitaciones introduce?** | Costo de validación en objetos muy grandes (irrelevante a nuestra escala). Riesgo de acoplar la lógica de negocio al modelo de serialización. Requiere disciplina: un campo mal tipado se convierte en una defensa inútil. |
| **¿Qué ocurriría si se elimina?** | Las salidas del modelo se consumirían como diccionarios sin verificar. Un campo ausente o mal tipado fallaría más tarde, en un lugar peor. La sección de seguridad pierde su capa 2. |
| **¿Cómo cambia al crecer?** | No cambia. Se versionan los esquemas (`schema_version` en el estado) para poder evolucionar sin romper ejecuciones en curso. |

**Nota crítica:** los modelos de estado **deben ser serializables**. Se verifica con una
prueba que recorre el árbol completo y falla si encuentra un `callable` en cualquier nivel.
Un objeto con un método escondido deja de ser datos y solo se descubre al intentar
persistirlo.

---

## 4. LangGraph

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Orquestar un flujo de múltiples agentes con estado explícito, transiciones verificables, presupuesto por nodo, pausa y reanudación. |
| **¿Por qué es necesaria?** | Es la diferencia entre un sistema **auditable** y un bucle conversacional. El documento pide *Agentic Workflows*, *State* y coordinación [DOC, §19]; el grafo es el mecanismo que lo hace visible. |
| **¿Qué alternativas existen?** | **CrewAI** (equipos por rol, más declarativo), **AutoGen** (conversación multiagente; **fusionado con Semantic Kernel en Microsoft Agent Framework 1.0**, abril 2026), **PydanticAI** (agentes tipados, más ligero), **OpenAI Agents SDK**, **LlamaIndex Workflows**, o **orquestación propia** con una máquina de estados. |
| **¿Por qué la seleccionamos?** | Tres requisitos son decisivos y LangGraph los da de forma nativa: (a) **estado tipado y persistido por punto de control**; (b) **pausa y reanudación** reales —necesarias para `RF-11`/`RF-12`; (c) **transiciones explícitas**, que es lo que permite defender el diagrama componente por componente. CrewAI y AutoGen se centran en la conversación entre agentes, que es justo el patrón que decidimos **no** usar (§5). |
| **¿Qué ventajas ofrece?** | El grafo es un artefacto inspeccionable; el *checkpointer* resuelve la reanudación; los nodos son funciones, lo que los hace testeables sin llamar a un modelo. |
| **¿Qué limitaciones introduce?** | Dependencia del ecosistema LangChain, que cambia con frecuencia. Curva de aprendizaje en el manejo de estado y reducers. El *checkpointer* introduce un requisito de almacén. Y una tentación real: usarlo para todo, incluso donde una función bastaría. |
| **¿Qué ocurriría si se elimina?** | Habría que implementar a mano la máquina de estados, la persistencia por punto de control y la pausa/reanudación. Es factible (es unas 300–500 líneas) pero es trabajo no evaluado, con más superficie de error. Perderíamos la reanudación fiable y el razonamiento visual del grafo. |
| **¿Cómo cambia al crecer?** | El *checkpointer* pasa de SQLite a Postgres; los nodos pesados se convierten en tareas en una cola; el grafo no cambia. Es precisamente la ventaja de tener el flujo separado del transporte. |

**Respuesta preparada para la defensa:** *"¿Por qué no orquestación propia?"* — Porque el
objetivo de la materia es demostrar comprensión de la arquitectura de un sistema de IA, no
implementar un motor de *workflow*. Reimplementarlo añadiría riesgo sin aportar a ningún
criterio de evaluación, y el documento pide usar la **menor complejidad necesaria** para
satisfacer los requerimientos [DOC, §13]. Aquí, la complejidad menor es usar el grafo y
dedicar el esfuerzo a los agentes, los permisos y la evaluación.

---

## 5. MCP — Model Context Protocol

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Conectar agentes con capacidades externas mediante una interfaz común, en lugar de acoplar cada herramienta al código del agente. |
| **¿Por qué es necesaria?** | Es un eje de especialización del Equipo 4 [DOC, §9.5, §19] y aporta algo concreto: una **frontera de proceso** para las herramientas con efectos, con esquemas validables. |
| **¿Qué alternativas existen?** | *Tool calling* nativo del proveedor (funciones en proceso), servidores de herramientas propios por HTTP/RPC, plugins específicos de cada framework, A2A (agent-to-agent, orientado a otro problema), o simplemente funciones locales. |
| **¿Por qué la seleccionamos?** | Para las herramientas que tocan el exterior, MCP aporta tres cosas que una función local no da: **aislamiento en otro proceso**, **esquemas declarados y validados** (`inputSchema`/`outputSchema`) y **sustituibilidad**. Ver el análisis honesto en `01-arquitectura.md` §12.3. |
| **¿Qué ventajas ofrece?** | Contratos validables antes de ejecutar; frontera de permisos real; trazabilidad distribuida (el protocolo documenta el contexto de traza W3C en `_meta`); y una ruta estándar de autorización (OAuth 2.1 con RFC 9728/8707) si algún día el servidor deja de ser local. |
| **¿Qué limitaciones introduce?** | Latencia adicional por el salto de proceso; un artefacto más que desplegar y observar; y **una superficie de protocolo en movimiento**. La revisión vigente (`2026-07-28`) es la mayor desde su publicación: elimina el *handshake* y las sesiones, depreca `Roots`, `Sampling` y `Logging`, y formaliza la autorización. Cualquier servidor propio debe seguir esa migración. |
| **¿Qué ocurriría si se elimina?** | El sistema funciona: las herramientas serían funciones en proceso. Se perdería el aislamiento de las herramientas de escritura, la validación por esquema en el borde, y el eje de especialización del equipo. El costo medible se evalúa en `EXP-03`. |
| **¿Cómo cambia al crecer?** | El protocolo ya es desplegable en la nube sin sesiones fijas, así que los servidores pueden replicarse detrás de un *balanceador*. El punto de extensión natural es un servidor MCP de repositorio remoto (GitHub) cuando el flujo remoto entre en alcance. |

**Advertencia de diseño derivada del protocolo:** dado que `Roots` está deprecado, nuestra
restricción de rutas **no puede depender de él**. Se implementa resolviendo y validando cada
ruta contra el directorio autorizado, dentro del servidor (`RNF-S2`). Es un control propio,
no delegado.

**Componente de integración:** el **SDK oficial de MCP** para Python (o `langchain-mcp-adapters`
si se prefiere adaptar las herramientas a LangChain). Es una dependencia de biblioteca, no un
servicio.

---

## 6. Comparación de frameworks multiagente

Esta comparación existe porque el documento la pide explícitamente [DOC, §9.6] y porque es la
pregunta que más probablemente aparezca en la defensa.

| Criterio | **LangGraph** (elegido) | **CrewAI** | **AutoGen → Microsoft Agent Framework 1.0** | **PydanticAI** |
|---|---|---|---|---|
| **Modelo mental** | Grafo de estados con nodos y aristas explícitas | Equipo de roles con tareas delegadas | Conversación entre agentes | Agente tipado con salidas validadas |
| **Control del flujo** | **Total y explícito**: el grafo es el programa | Delegación declarativa; el flujo lo decide el framework | Emergente de la conversación | Secuencial, dentro de un agente |
| **Estado** | **Tipado y persistido por punto de control** | Compartido en memoria del equipo | Estado de conversación | Depende del agente |
| **Pausa / reanudación** | **Nativa** (`interrupt` + *checkpointer*) | Limitada | Limitada | No nativa |
| **Trazabilidad del flujo** | Alta: cada transición es un nodo identificable | Media | Baja: el flujo emerge de los mensajes | Media |
| **Adecuado para** | Workflows con control fino y requisitos de auditoría | Prototipos rápidos por roles | Investigación en conversación multiagente | Agentes únicos con contratos estrictos |
| **Encaje con nuestro proyecto** | **Alto** | Medio: no resuelve `RF-11`/`RF-12` | Bajo: la conversación libre es lo que decidimos evitar | Medio: excelente en tipado, pero no orquesta un grafo |
| **Decisión** | ✅ **Seleccionado** | ❌ Comparación | ❌ Comparación | ❌ Comparación |

**Nota sobre AutoGen [PROP]:** AutoGen ya no existe como proyecto independiente. En abril de
2026 se fusionó con Semantic Kernel en **Microsoft Agent Framework 1.0**, que integra MCP y
A2A. Se menciona aquí por fidelidad al documento, que lo lista como comparación, pero
compararlo como si fuera una opción viva sería un error técnico.

**Por qué no CrewAI:** su fortaleza es expresar un equipo de roles de forma declarativa, y eso
es atractivo. Pero nuestro requisito crítico es la **pausa y reanudación del grafo con estado
persistido** (`RF-11`, `RF-12`) y la **verificación de que un agente no puede escribir en el
campo de otro** (§9.6). LangGraph permite expresar esas restricciones en el código del grafo;
CrewAI las deja más difusas.

**Por qué no PydanticAI:** su propuesta —agentes con contratos de entrada/salida fuertemente
tipados— es exactamente la que adoptamos **dentro** de cada agente. Pero no es un motor de
orquestación con estado persistido. No compite con LangGraph: compite con nuestra capa de
contratos, y ahí Pydantic ya nos da lo que necesitamos. Usar ambos sería duplicar.

---

## 7. Foundation Model (proveedor abstracto)

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Es la capacidad de razonamiento: planificar, generar código, revisar. |
| **¿Por qué es necesaria?** | Sin modelo no hay sistema. Es donde vive la IA (`01-arquitectura.md` §1.3). |
| **¿Qué alternativas existen?** | **API gestionada** (OpenAI, Anthropic, Google, Mistral), **modelo local** servido con Ollama o vLLM, **modelo autoalojado** en GPU propia, o **modelos abiertos vía proveedor de inferencia** (Groq, Together, Fireworks). |
| **¿Por qué la seleccionamos?** | **No seleccionamos un modelo: seleccionamos una abstracción de proveedor** (`DEC-10`). En el prototipo se usa una API gestionada por defecto, porque la calidad de razonamiento y de generación de código es lo que determina `MET-01` y `MET-07`, y porque no hay GPU garantizada en el equipo. Un modelo local queda soportado por configuración. |
| **¿Qué ventajas ofrece?** | Calidad alta sin infraestructura; costo variable y medible; cambio de proveedor sin tocar agentes. |
| **¿Qué limitaciones introduce?** | **Dependencia de red y de un tercero.** El código del usuario sale del equipo (consideración de privacidad que debe declararse). Costo por token. Latencia variable. Límites de tasa que se convierten en el primer cuello de botella a escala (§9). |
| **¿Qué ocurriría si se elimina?** | No hay sistema. Pero **la abstracción sí podría eliminarse** en un prototipo desechable; la mantenemos porque permite comparar proveedores y porque habilita la ruta local. |
| **¿Cómo cambia al crecer?** | Enrutamiento por modelo: un modelo económico para tareas simples (clasificar intención) y uno potente para las difíciles. Es el primer cambio de costo que haría un equipo en producción. |

---

## 8. SQLite como almacén de estado

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Persistir el estado por ejecución para poder reanudar y auditar. |
| **¿Por qué es necesaria?** | `RNF-D1` (reanudación) y `RNF-T3` (trazabilidad) son requisitos, no opciones. Sin almacén no hay punto de control. |
| **¿Qué alternativas existen?** | PostgreSQL, Redis (rápido, pero volátil sin persistencia), MySQL, MongoDB, o archivos JSON en disco. |
| **¿Por qué la seleccionamos?** | **Sin servidor que desplegar.** El prototipo corre en una máquina, y añadir Postgres significa añadir un contenedor, credenciales y configuración, a cambio de un beneficio que solo aparece con concurrencia real. SQLite soporta el *checkpointer* de LangGraph de forma directa. |
| **¿Qué ventajas ofrece?** | Cero configuración, un archivo, transaccional, y migrar a Postgres es cambiar una cadena de conexión (la interfaz del *checkpointer* es la misma). |
| **¿Qué limitaciones introduce?** | **Un solo escritor a la vez.** No soporta concurrencia de escritura. El archivo es local: no sirve para varias réplicas. |
| **¿Qué ocurriría si se elimina?** | Sin almacén no hay reanudación ni auditoría. El sistema funcionaría solo en memoria, y `RNF-D1` quedaría incumplido. |
| **¿Cómo cambia al crecer?** | **Es el primer componente que se sustituye.** A partir de ~10 ejecuciones concurrentes, SQLite se convierte en el cuello de botella de escritura y se cambia a PostgreSQL. Está documentado como el primer paso de escalado. |

---

## 9. faster-whisper (Speech-to-Text)

Justificación completa en `01-arquitectura.md` §11. Resumen de las ocho preguntas:

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Convertir audio en texto para permitir dictar la instrucción. |
| **¿Por qué es necesaria?** | Solo si se acepta la entrada por voz. **El sistema funciona sin ella**; es la única tecnología de la lista que es prescindible por diseño (§0 de `01-arquitectura.md`). |
| **¿Qué alternativas existen?** | Whisper large-v3 (referencia), whisper.cpp, large-v3-turbo, Distil-Whisper, Canary Qwen, Parakeet TDT; APIs: Deepgram Nova-3/Flux, AssemblyAI Universal-3 Pro, OpenAI GPT-4o-transcribe, Microsoft MAI-Transcribe-1, ElevenLabs Scribe v2, Google Chirp 3, Gladia Solaria. |
| **¿Por qué la seleccionamos?** | **Privacidad** (el audio no sale del equipo), **costo marginal cero** (la suite de evaluación se ejecuta muchas veces) y **latencia suficiente** (no necesitamos streaming sub-300 ms porque hay confirmación humana). |
| **¿Qué ventajas ofrece?** | Local, sin credenciales, multilingüe, con cuantización INT8 y buen rendimiento en GPU y CPU. |
| **¿Qué limitaciones introduce?** | Requiere descargar el modelo (~1.5 GB) y, sin GPU, la latencia crece. WER inferior al de los mejores servicios en la nube. Consumo de memoria. |
| **¿Qué ocurriría si se elimina?** | La entrada por voz desaparece. El sistema sigue completo: la interfaz de texto es el camino canónico. **Es la única eliminación que no rompe nada**, y eso es deliberado. |
| **¿Cómo cambia al crecer?** | El adaptador permite mover la transcripción a la nube o a un servicio dedicado sin tocar el backend. A escala, la transcripción se vuelve una preocupación de infraestructura aparte, no del grafo de agentes. |

---

## 10. Langfuse (observabilidad)

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Registrar y visualizar trazas de LLM: árbol de ejecución → agente → herramienta, con tokens, latencia y costo. |
| **¿Por qué es necesaria?** | La observabilidad es un criterio de evaluación del documento [DOC, §18: 5 %] y la única forma de producir la evidencia de §18 de `01-arquitectura.md`. |
| **¿Qué alternativas existen?** | OpenTelemetry + un backend propio (Grafana Tempo/Jaeger), Arize Phoenix, Helicone, W&B Weave, o registros estructurados con análisis manual. |
| **¿Por qué la seleccionamos?** | Es **autoalojable** (coherente con el principio de privacidad del proyecto), está instrumentado específicamente para LLM y agentes, y permite asociar evaluaciones a las trazas. |
| **¿Qué ventajas ofrece?** | Árbol de trazas sin construirlo a mano, cálculo de costo por token, y comparación entre ejecuciones. |
| **¿Qué limitaciones introduce?** | Un servicio más que desplegar y mantener. Riesgo de fuga si las trazas contienen secretos: se mitiga redactando antes de exportar (`AM-09`). |
| **¿Qué ocurriría si se elimina?** | El sistema funciona, pero la evaluación y la defensa se quedan sin evidencia visual. **Es prescindible en ejecución, no en evaluación.** Por eso los registros JSON estructurados son la fuente primaria y Langfuse es solo la capa de visualización: si Langfuse cae, la trazabilidad no se pierde. |
| **¿Cómo cambia al crecer?** | Se apunta a una instancia compartida, con muestreo si el volumen lo exige. El formato de traza es estándar (W3C), así que se puede migrar de backend. |

---

## 11. Seguridad: por qué NO usamos un framework de guardrails

Esta es una decisión de arquitectura que conviene defender explícitamente.

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve un framework de guardrails?** | Filtrar entradas y salidas con clasificadores: detectar PII, bloquear contenido, detectar inyección. |
| **¿Por qué NO lo usamos?** | Nuestros controles críticos son **deterministas**: listas de permitidos, confinamiento de rutas, intersección de permisos, aprobación humana. Un clasificador que decide si una acción es peligrosa introduce un componente **probabilístico** en la ruta de seguridad. Un guardrail que razona es un guardrail que se puede convencer. |
| **¿Qué alternativas existen?** | NeMo Guardrails, Guardrails AI, Llama Guard, Microsoft Presidio (para PII). |
| **¿Dónde sí tendrían sentido?** | Si el proyecto trabajara con **datos personales** (sería el caso del Equipo 2), Presidio para detección de PII estaría justificado. Nuestro objeto de trabajo es código de un repositorio del propio usuario, no datos de terceros. |
| **¿Qué limitaciones introduce no usarlos?** | No detectamos PII de forma automática. Se mitiga con redacción de secretos por patrón y con el hecho de que el alcance no incluye datos personales. |
| **¿Qué ocurriría si los añadiéramos?** | Añadiríamos latencia, un modelo más que ejecutar, y —lo más importante— **una falsa sensación de seguridad**: la defensa dejaría de apoyarse en la contención de capacidades, que es el control que realmente funciona. |

**Punto de defensa:** la pregunta *"¿cómo evitamos que un agente ejecute acciones
peligrosas?"* se responde con **"el agente no tiene la capacidad de ejecutarlas"**, no con
**"un modelo lo detecta"**. La primera respuesta es verificable; la segunda no.

---

## 12. Frontend: HTML + JavaScript nativo

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Capturar la instrucción (texto o audio), confirmar la transcripción, mostrar el progreso y gestionar las aprobaciones. |
| **¿Por qué es necesaria?** | Sin interfaz no hay demostración funcional, que es un entregable [DOC, §15.3]. |
| **¿Qué alternativas existen?** | React, Vue, Svelte, Streamlit, Gradio, o una interfaz de terminal. |
| **¿Por qué la seleccionamos?** | **Streamlit y Gradio serían la opción más rápida**, y se descartan deliberadamente: no permiten controlar bien un flujo de aprobación con pausa y reanudación ni la captura de audio con confirmación. Un framework de SPA añadiría `node_modules`, un *build step* y una cadena de herramientas que **no aporta a ningún criterio de evaluación**. HTML y JS nativos dan `MediaRecorder` y `EventSource` sin dependencias. |
| **¿Qué ventajas ofrece?** | Cero dependencias, cero compilación, un solo archivo que se sirve como estático. Despliegue trivial. |
| **¿Qué limitaciones introduce?** | Menos estructura para crecer; el manejo de estado en el cliente es manual; sin sistema de componentes. Para una interfaz de una sola pantalla, es suficiente. |
| **¿Qué ocurriría si se elimina?** | Queda una API. La demostración funcional se hace con `curl` o con las pruebas de integración. Es aceptable, pero pierde la voz y el panel de aprobaciones. |
| **¿Cómo cambia al crecer?** | Si la interfaz creciera, se migra a un framework con la API sin cambios: el contrato HTTP es el límite, y está documentado con OpenAPI. |

---

## 13. Docker y docker-compose

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Dos cosas distintas: reproducibilidad del entorno, y **aislamiento de la ejecución de código**. |
| **¿Por qué es necesaria?** | El segundo punto es de seguridad, no de comodidad. La ejecución de pruebas y la escritura de archivos ocurren en un entorno confinado (`RNF-S6`: sin salida de red por defecto). Sin contenedor, la contención depende de la disciplina del código. |
| **¿Qué alternativas existen?** | Entorno virtual sin contenedor, máquinas virtuales (más aisladas, más pesadas), `chroot`/`nsjail`/`bubblewrap` (aislamiento ligero en Linux), sandbox de proveedor en la nube. |
| **¿Por qué la seleccionamos?** | Es el mecanismo de aislamiento más portable y con mejor relación aislamiento/esfuerzo. Además resuelve la reproducibilidad del entregable (`Dockerfile` está en la lista de requisitos del repositorio [DOC, §15.4]). |
| **¿Qué ventajas ofrece?** | Entorno reproducible; límites de CPU, memoria y red declarativos; el mismo artefacto para desarrollo y para la demo. |
| **¿Qué limitaciones introduce?** | El *overhead* del contenedor; en Windows, la capa de virtualización añade latencia de E/S (relevante porque el *worktree* vive en un volumen montado); el aislamiento de un contenedor **no es** el de una máquina virtual. |
| **¿Qué ocurriría si se elimina?** | El sistema funciona, pero la contención de las herramientas con efectos pasa a depender solo del Policy Engine y del confinamiento de rutas. Se pierde una capa de defensa. |
| **¿Cómo cambia al crecer?** | Cada ejecución puede correr en su propio contenedor efímero, con límites y sin red, orquestado por el *worker*. Es la ruta natural a aislamiento fuerte por ejecución. |

---

## 14. pytest + arnés de evaluación

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Verificar el sistema y **producir la evidencia numérica** de §18. |
| **¿Por qué es necesaria?** | La evaluación es el 10 % de la nota [DOC, §18] y es la única forma de responder la pregunta central del Equipo 4 con datos (`EXP-01`). |
| **¿Qué alternativas existen?** | `unittest` (biblioteca estándar), `nose2`, o un script propio. Para evaluación de LLM: Ragas y DeepEval, que el documento menciona. |
| **¿Por qué la seleccionamos?** | `pytest` para las pruebas deterministas (contratos, política, geometría del diagrama). El **arnés de evaluación es propio** porque las métricas de §18 son específicas de este sistema: Ragas y DeepEval están orientados a RAG y a *groundedness*, que no son nuestros ejes. |
| **¿Qué ventajas ofrece?** | Pruebas parametrizadas para correr el mismo conjunto de tareas bajo distintas configuraciones (`EXP-01`, `EXP-02`, `EXP-03`), y comparación directa de resultados. |
| **¿Qué limitaciones introduce?** | El arnés hay que construirlo y mantenerlo. Las tareas de evaluación deben revisarse cuando el sistema cambia, o dejan de medir lo que dicen medir. |
| **¿Qué ocurriría si se elimina?** | No habría evaluación reproducible. Las afirmaciones sobre el sistema serían opiniones. |
| **¿Cómo cambia al crecer?** | El arnés se convierte en un conjunto de regresión: cada defecto encontrado se añade como tarea permanente. |

---

## 15. Git

| Pregunta | Respuesta |
|---|---|
| **¿Qué problema resuelve?** | Dos: control de versiones del proyecto, y **el mecanismo de contención de cambios**. |
| **¿Por qué es necesaria?** | El *worktree* de Git es lo que permite que el Coder escriba sin tocar el repositorio del usuario (`DEC-07`). Además, el *diff* es la unidad de revisión del Reviewer y la evidencia del informe final. |
| **¿Qué alternativas existen?** | Copiar el directorio y trabajar sobre la copia, sistema de archivos con instantáneas, parches en memoria sin escribir a disco. |
| **¿Por qué la seleccionamos?** | El *worktree* es **barato**, **nativo**, y produce un *diff* que es un formato estándar y legible. Un `git diff` es exactamente lo que el Reviewer necesita ver, y lo que el usuario necesita aprobar. |
| **¿Qué ventajas ofrece?** | Aislamiento sin duplicar el repositorio completo; reversión trivial (`git worktree remove`); trazabilidad por `base_commit`. |
| **¿Qué limitaciones introduce?** | `git worktree` requiere un repositorio Git válido y no funciona igual sobre todos los sistemas de archivos. En Windows, el rendimiento del *worktree* sobre volúmenes montados es sensible. |
| **¿Qué ocurriría si se elimina?** | Habría que implementar aislamiento con copias de directorio: más espacio, más lento, y sin *diff* nativo. La contención se debilitaría. |
| **¿Cómo cambia al crecer?** | Los *worktrees* se crean en un volumen efímero por ejecución y se destruyen al terminar. El `base_commit` permite reproducir el estado exacto de cualquier ejecución pasada. |

---

## 16. Trazabilidad de cada elección

| Decisión | Tecnología | Sección |
|---|---|---|
| `DEC-01` | LangGraph | §4 |
| `DEC-02` | Matriz de permisos (Pydantic + Policy Engine) | `01-arquitectura.md` §10.4, §16.3 |
| `DEC-03` | MCP solo en el borde | §5 |
| `DEC-04` | Sin Vector Database | §0, `01-arquitectura.md` §12.4 |
| `DEC-05` | Sin memoria persistente | `01-arquitectura.md` §14.4 |
| `DEC-06` | Se ejecutan pruebas, no código arbitrario | §13 |
| `DEC-07` | Git worktree | §15 |
| `DEC-08` | faster-whisper tras un adaptador | §9 |
| `DEC-09` | SQLite / proceso sin estado | §8 |
| `DEC-10` | Abstracción de proveedor de modelo | §7 |
