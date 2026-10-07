# Flujo de ejecución e implementación

> ⚠️ **AVISO `SUPERSEDED` (parcial) — 2026-10-06.**
> Este documento es **vigente** como registro del plan y del resultado de M1
> (§3.13, §3.14). La traza de ejemplo de §2 describe el flujo **objetivo** y usa
> herramientas (MCP, `run_tests` real) que **todavía no existen**; es una
> ilustración del objetivo, no del comportamiento actual.
>
> El **roadmap de fases** de §3.11 ha sido reemplazado por el de 17 fases (`F0`–`F16`)
> de `docs/auditoria-2026-10-06/09_ROADMAP.md`, que añade versionado y
> reproducibilidad como pasos previos y coloca la autenticación antes de cualquier
> exposición.
>
> **Fuente de verdad sobre el estado:** `docs/auditoria-2026-10-06/00_ESTADO_ACTUAL.md`.

> Secciones 20, 21 y 22 de la solicitud: diagrama arquitectónico, flujo paso a paso con un
> ejemplo práctico, y el plan de implementación por incrementos.

---

## 1. Diagrama arquitectónico

El diagrama completo está en **`docs/diagrama-arquitectura.svg`** (y su versión rasterizada
en `docs/diagrama-arquitectura.png`). No es un dibujo hecho a mano: se genera desde una
**única definición de layout** en `tools/build_diagram.py`, que valida la geometría **antes**
de dibujar y aborta el build si algo falla.

### 1.1 Qué muestra el diagrama

| Elemento exigido [DOC, §15.2] | Dónde aparece |
|---|---|
| Usuarios | Nodo `Usuario` (voz o texto), fuera del límite de confianza. |
| Clientes | Nodo `Frontend` con captura de audio y confirmación de transcripción. |
| Servicios | `API / Backend`, `Supervisor`, agentes, `Policy Engine`. |
| Modelos | `Foundation Model` (servicio externo, sustituible). |
| Bases de datos | `Shared State` con *checkpointer*. |
| Vector Databases | **Ausente a propósito** (`DEC-04`). Se declara en §0 de `02-tecnologias.md`. |
| APIs | El contrato HTTP del backend, con progreso por SSE. |
| Agentes | `Researcher`, `Coder`, `Reviewer`. |
| Herramientas | `Tools / MCP` con `filesystem`, `git`, `run_tests`. |
| Servicios externos | `Foundation Model`, `Observabilidad`, `Text-to-Speech`. |
| Flujo de información | Aristas continuas. Flujo opcional/transversal en discontinuo. |
| Límites del sistema | Zona `LÍMITE DE CONFIANZA · APLICACIÓN` y zona `SERVICIOS EXTERNOS`. |

### 1.2 Por qué el diagrama se genera con código

Un diagrama puede estar geométricamente mal y **verse bien**: una etiqueta con fondo opaco
tapa limpiamente lo que invade. La vista no es una verificación fiable. Por eso el generador
comprueba, sobre la definición del layout:

1. Que toda arista referencia nodos existentes.
2. Que todo nodo cabe en el lienzo.
3. Que no hay dos nodos solapados.
4. Que ninguna etiqueta pisa una caja ni cruza el borde de una zona.
5. Que ninguna etiqueta cruza el trazo de una arista.

Además se afirma el **número esperado** de elementos (16 nodos, 20 aristas, 5 etiquetas,
3 líneas de leyenda, 2 zonas). Sin esa afirmación, un layout vacío pasaría la validación: no
distinguiría *"no hay nada malo"* de *"no hay nada"*.

**Esta comprobación ya encontró un defecto real:** la leyenda inferior, que se emitía fuera
del modelo validado, pisaba las cajas `Resultado validado` y `Text-to-Speech`. Era invisible
en el render porque el texto es gris claro sobre un relleno claro. Se incorporó la leyenda al
modelo validado y se reubicó.

**Y el validador a su vez se verificó:** se introdujeron seis defectos a propósito —etiqueta
sobre un nodo, nodo fuera del lienzo, nodos solapados, arista a un nodo inexistente, etiqueta
cruzando una arista, nodo cruzando una zona— y los seis fueron detectados. Una validación que
nunca ha fallado no ha demostrado nada.

---

## 2. Flujo de ejecución paso a paso

### 2.1 Instrucción del ejemplo

> **"Analiza este proyecto, identifica los errores principales, corrige el código y
> posteriormente revisa que las modificaciones funcionen correctamente."**

Repositorio de ejemplo: un proyecto Python pequeño donde `parse_duration()` falla con
duraciones de más de una hora, y `create_user()` acepta correos sin validar.

### 2.2 Traza completa

| # | Paso | Componente | Qué ocurre exactamente | Estado resultante |
|---|---|---|---|---|
| 1 | Captura de audio | Frontend | El usuario mantiene pulsado el micrófono. `MediaRecorder` produce un `Blob` de audio (WebM/Opus). | — |
| 2 | Transcripción | STT | `POST /transcriptions` con el audio. `faster-whisper` transcribe con el vocabulario sesgado del repositorio. Devuelve `text`, `language`, `confidence`, `duration_s`. **No se crea ninguna ejecución.** | — |
| 3 | Confirmación | Frontend | Se muestra la transcripción **editable**. El usuario corrige `parse duration` → `parse_duration` y confirma. | — |
| 4 | Creación | API | `POST /runs` con el texto confirmado, el repositorio autorizado y el alcance declarado. Se valida la forma y se crea `run_id`. | `planned` |
| 5 | Interpretación | Supervisor | Clasifica la intención: `modify`. Extrae restricciones y alcance. Salida validada contra `TaskInterpretation`. | `planned` |
| 6 | Planificación | Supervisor | Aplica el patrón `modify`: `Researcher → Coder → Reviewer`, con `max_review_cycles = 2`. El modelo rellena los detalles: qué archivos, qué criterio de término. Salida validada contra `RunPlan`. | `planned` |
| 7 | Publicación del plan | API → Frontend | El plan se envía al frontend. **El usuario puede verlo antes de que ocurra nada.** | `running` |
| 8 | Subtarea 1: investigación | Researcher | `list_files` → `search_text("def parse_duration")` → `read_file`. Reúne la firma, las pruebas existentes y el *issue* en un comentario del código. Escribe `ResearchOutput` con `path`, `symbol`, `line_range`, `snippet`, `why_relevant`. | subtarea `completed` |
| 9 | Verificación de evidencia | Supervisor | Comprueba de forma **determinista** que cada `path` y `symbol` citado existe realmente. *(Aquí es donde se detecta si el Researcher inventó evidencia.)* | — |
| 10 | Subtarea 2: corrección | Coder | Recibe `ResearchOutput` y el criterio. Propone un parche sobre `parse_duration` y añade validación de correo en `create_user`. Aplica en el **worktree aislado**, no en el repositorio del usuario. | subtarea `completed` |
| 11 | Ejecución de pruebas | Coder → Tools/MCP | `run_tests("pytest.unit")`. Pasa por el **Policy Engine** (`allow`), cruza a MCP, corre en el contenedor sin red. Devuelve `exit_code`, `stdout`, `duration_s`. | evidencia registrada |
| 12 | Subtarea 3: revisión | Reviewer | Recibe el **diff** y los **resultados de pruebas**, no el razonamiento del Coder. Re-ejecuta `pytest.unit` para confirmar que el resultado es reproducible. Detecta que `parse_duration` no maneja el caso `"1:00:00"` (solo `"90m"`). | `decision = request_changes` |
| 13 | Ciclo de corrección | Supervisor → Coder | Reasigna al Coder con el hallazgo concreto. `review_cycles_used = 1`. | `running` |
| 14 | Corrección 2 | Coder | Añade el manejo del formato `H:MM:SS`. Re-ejecuta pruebas. | subtarea `completed` |
| 15 | Revisión 2 | Reviewer | Verifica el nuevo *diff*, re-ejecuta. `decision = accept`. | `review_cycles_used = 1` |
| 16 | Puerta de aprobación | Policy Engine → HITL | Promover los cambios al repositorio del usuario es una **acción con efectos**. El Engine devuelve `require_approval`. **El grafo se pausa** y persiste el estado. | `awaiting_approval` |
| 17 | Aprobación | Frontend → API | El usuario ve el *diff*, los archivos afectados y el resultado de las pruebas. Aprueba. Se registra actor, momento y hash del contenido. | `running` |
| 18 | Reanudación | Supervisor | El grafo **se reanuda desde el punto de pausa**. Las subtareas 1, 2 y 3 siguen `completed`: no se repite trabajo. | `running` |
| 19 | Promoción | Tools/MCP | Los cambios se promueven del *worktree* al repositorio del usuario. *(El `git commit` también está tras aprobación; `git push` está fuera de alcance.)* | `completed` |
| 20 | Informe final | Supervisor → API → Frontend | Se emite el informe con cuatro secciones: cambios aplicados, pruebas ejecutadas, resultado de la revisión y pendientes. | `completed` |
| 21 | Salida por voz (opcional) | TTS | Si está habilitado, el resumen se convierte en audio. El informe textual siempre existe. | — |

### 2.3 Qué muestra este flujo

- **El STT no participa en la decisión.** Ocupa los pasos 1–3 y desaparece. Podría sustituirse
  por texto tecleado sin cambiar un solo paso posterior. Eso es exactamente lo que significa
  "adaptador de borde".
- **El ciclo de revisión es real.** El paso 12 no aprobó por complacencia: encontró un caso no
  cubierto y lo devolvió. Ese es el valor de la revisión independiente.
- **La pausa es del grafo, no de la interfaz.** Si el proceso se cae entre los pasos 16 y 17,
  al reiniciar la ejecución sigue en `awaiting_approval`.
- **La aprobación está donde debe estar.** No se pidió permiso para leer ni para escribir en
  el *worktree* (aislado). Se pidió una sola vez, para la acción que rompe el aislamiento.
- **El informe distingue cuatro cosas.** "Cambios aplicados", "pruebas ejecutadas",
  "revisión" y "pendientes" no se mezclan en un párrafo.

---

## 3. Plan de implementación

El documento pide definir diez cosas antes de escribir código [solicitud, §22]. Van en orden.

### 3.1 Arquitectura

Congelada en `01-arquitectura.md`. Resumen de las decisiones: `DEC-01` a `DEC-10`.

### 3.2 Estructura del proyecto

```
proyecto4-ai-swe/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── docs/
│   ├── 01-arquitectura.md
│   ├── 02-tecnologias.md
│   ├── 03-flujo-e-implementacion.md
│   ├── 04-defensa.md
│   ├── diagrama-arquitectura.svg
│   └── diagrama-arquitectura.png
├── tools/
│   └── build_diagram.py            # layout + validación geométrica + emisión SVG
├── src/ai_swe/
│   ├── config.py                   # configuración validada
│   ├── contracts/                  # CONTRATOS: la definición de las interfaces
│   │   ├── state.py                # RunState y todo lo que contiene
│   │   ├── tasks.py                # TaskInterpretation, RunPlan, Subtask
│   │   ├── outputs.py              # ResearchOutput, CodeChange, ReviewVerdict
│   │   └── tools.py                # ToolCall, ToolResult, PolicyDecision
│   ├── tools/
│   │   ├── policy.py               # matriz de permisos + decide()
│   │   └── registry.py             # catálogo de herramientas y sus esquemas
│   ├── api/                        # FastAPI: rutas y streaming de progreso
│   ├── graph/                      # supervisor.py, workflow.py (nodos y aristas)
│   ├── agents/                     # base.py, researcher.py, coder.py, reviewer.py
│   ├── mcp/                        # cliente MCP y definición de servidores
│   ├── stt/                        # base.py (protocolo), faster_whisper.py, fake.py
│   ├── observability/              # tracing.py, redacción de secretos
│   └── evaluation/                 # arnés de evaluación y métricas
├── frontend/
│   └── index.html                  # captura, confirmación, panel, aprobaciones
├── tests/
│   ├── test_contracts.py           # contratos y serializabilidad
│   ├── test_policy.py              # matriz de permisos y decide()
│   └── test_diagram_layout.py      # validación geométrica del diagrama
└── data/
    └── tasks/                      # suite de evaluación con verdad conocida
```

### 3.3 Dependencias

Núcleo:

```
python >= 3.12
fastapi, uvicorn[standard]      # API
pydantic >= 2, pydantic-settings # contratos y configuración
langgraph                       # orquestación
mcp                             # SDK del protocolo
faster-whisper                  # STT local
httpx                           # cliente HTTP para el proveedor de modelo
sse-starlette                   # progreso incremental
```

Desarrollo y evaluación:

```
pytest, pytest-asyncio          # pruebas
langfuse                        # observabilidad (opcional en ejecución)
ruff                            # lint (declarado, no obligatorio)
```

**Regla de dependencias:** ninguna dependencia entra sin responder las ocho preguntas de
`02-tecnologias.md`. Las versiones se fijan en `pyproject.toml`; los secretos **nunca** se
escriben en el repositorio.

### 3.4 Interfaces entre componentes

Las interfaces son **contratos Pydantic**, no convenciones. Están en
`src/ai_swe/contracts/` y son la fuente de verdad del JSON Schema que se usa tanto para el
*tool calling* como para la validación de salidas.

| Frontera | Contrato | Quién produce | Quién consume |
|---|---|---|---|
| Frontend → API | `RunRequest` | Frontend | API |
| STT → Frontend | `Transcript` | Adaptador STT | Frontend |
| API → Supervisor | `RunRequest` validado | API | Supervisor |
| Supervisor → agentes | `Subtask` | Supervisor | Agentes |
| Researcher → Estado | `ResearchOutput` | Researcher | Supervisor, Coder, Reviewer |
| Coder → Estado | `CodeChange` | Coder | Reviewer, Supervisor |
| Reviewer → Estado | `ReviewVerdict` | Reviewer | Supervisor |
| Agente → Herramientas | `ToolCall` | Agentes | Policy Engine |
| Policy Engine → MCP | `PolicyDecision` | Policy Engine | Capa de herramientas |
| Todo → Observabilidad | `TraceEvent` | Todos | Langfuse / registros |

**Regla de frontera:** lo que no tiene contrato ni validación **no cruza un borde**. Una
salida que no valida contra su esquema no se propaga: se reintenta o se marca como error.

### 3.5 Flujo de agentes

Grafo de LangGraph, con los nodos y aristas siguientes:

```
START
  │
  ▼
[interpret]  ──(intención = question)──► [answer_direct] ──► END
  │
  ├──(intención = out_of_scope)──► [explain_limits] ──► END
  │
  ├──(intención = inspect)──► [researcher] ──► [finalize] ──► END
  │
  └──(intención = modify)──► [researcher] ──► [coder] ──► [run_tests] ──► [reviewer]
                                                                              │
                            ┌───────────(request_changes y quedan ciclos)──────┘
                            ▼
                          [coder]   (vuelve a run_tests → reviewer)
                            │
                            └──(accept)──► [approval_gate] ──(requiere aprobación)──► ⏸ PAUSA
                                                                                       │
                            ┌────────────────────(aprobado)────────────────────────────┘
                            ▼
                       [promote_changes] ──► [finalize] ──► END
```

Reglas del grafo, verificables en código:

- El **Researcher** y el **Reviewer** no tienen aristas hacia nodos de escritura. La
  separación de permisos está en la topología, no solo en un *prompt*.
- `max_review_cycles` se evalúa en la arista condicional. Agotado el límite, se va a
  `needs_human`, no a un bucle.
- Toda arista que sale de un nodo con efectos pasa por `approval_gate`.
- Cada nodo valida su salida contra el esquema antes de escribir en el estado.

### 3.6 Estado

Definido en `01-arquitectura.md` §14.2. Reglas de mutación en §14.3. Resumen operativo:

- El **Supervisor** es el único que escribe campos de control.
- Cada agente escribe **solo** su propio campo de salida.
- El estado es serializable y versionado (`schema_version`).
- Cada transición deja un punto de control.

### 3.7 Herramientas

Catálogo en `01-arquitectura.md` §13.2, matriz de permisos en §10.4. Implementación: la
matriz es **dato** en `tools/policy.py`, y `decide()` es una función pura sin red ni modelo.

### 3.8 MCP

Dos servidores en el prototipo: **sistema de archivos** y **Git**. Justificación en
`01-arquitectura.md` §12.3. Consideraciones de implementación:

- El servidor de archivos valida cada ruta resolviéndola y comprobando que queda dentro del
  directorio autorizado. **No se usa `Roots`** (deprecado en la revisión `2026-07-28`).
- `run_tests` recibe un **identificador de enumeración**, no una cadena de comando.
- El cliente propaga el contexto de traza W3C para que la traza no se rompa al cruzar a MCP.

### 3.9 Seguridad

Modelo de amenazas en `01-arquitectura.md` §16.1 (`AM-01` a `AM-12`), defensa en profundidad
en §16.2, Policy Engine en §16.3. La capa que realmente protege es la **contención de
capacidades**: el agente no tiene la herramienta peligrosa.

### 3.10 Evaluación

Métricas en `01-arquitectura.md` §18.1 (`MET-01` a `MET-14`), conjunto de tareas en §18.2,
experimentos en §18.3 (`EXP-01` a `EXP-07`). El arnés debe poder correr la **misma** suite
bajo distintas configuraciones (un agente vs. multiagente; con y sin MCP) y producir una
tabla comparativa.

### 3.11 Fases de implementación

Cada fase termina con algo **verificable**. No se avanza sin que la fase anterior pase sus
pruebas.

| Fase | Entregable | Verificación |
|---|---|---|
| **M0 — Diseño** ✅ | Documentos 01–04, diagrama validado, contratos, matriz de permisos. | Validación geométrica + pruebas de contratos y política. **Completada en este incremento.** |
| **M1 — Esqueleto ejecutable** ✅ | API con `POST /runs`, `POST /transcriptions`; estado en SQLite; grafo con nodos deterministas que aún no razonan. | Una ejecución recorre el grafo de principio a fin y termina en estado terminal. `MET-13 = 0`. **Completada** — ver §3.13. |
| **M2 — Agentes reales** | Researcher, Coder, Reviewer con herramientas en proceso (sin MCP todavía) y salidas validadas. | `EXP-01` ejecutable con el conjunto base de tareas. |
| **M3 — MCP y política** | Servidores MCP de archivos y Git; Policy Engine aplicado en cada llamada; *worktree* aislado. | `EXP-03` y `EXP-06`: 0 acciones no autorizadas con el conjunto adversarial. |
| **M4 — Human-in-the-Loop** | Puerta de aprobación con pausa y reanudación reales; promoción al repositorio. | `RF-11`, `RF-12`: la ejecución sobrevive a la caída del proceso mientras espera. |
| **M5 — Voz** | Adaptador STT con `faster-whisper`, frontend con captura y confirmación. | `EXP-04`: WER medido sobre el corpus propio. |
| **M6 — Observabilidad y evaluación** | Langfuse, métricas agregadas, tabla comparativa de `EXP-01`/`EXP-02`. | Informe de evaluación con todos los `MET-xx` medidos. |
| **M7 — Capa de contexto** *(fuera del camino crítico)* | Mapa de símbolos del repositorio (`repo_map`, determinista, en proceso, ~1 000 tokens). Solo si `EXP-08` lo justifica: consulta a grafo por MCP, con recorte obligatorio y filtro de procedencia. | `EXP-08` con las tres configuraciones, sobre un repositorio que **no cabe en contexto**. Si el repositorio cabe, el experimento se declara inválido. |

**Orden deliberado:** MCP (M3) llega **después** de que los agentes funcionen (M2). Así se
puede ejecutar `EXP-03` —con y sin MCP— sobre un sistema que ya funciona, en lugar de
construir MCP y no tener con qué compararlo.

**Y la voz llega en M5**, penúltima. Es coherente con §0 de `01-arquitectura.md`: es un
adaptador de borde, y el sistema debe estar completo sin ella.

### 3.12 Verificación previa de los supuestos de M1

Antes de escribir la fase M1 se verificaron las suposiciones de las que depende. No es
ceremonia: si la reanudación entre procesos no funciona, el diseño cambia a nivel de `DEC-01`,
no de código. Es más barato descubrirlo con un guion que después de construir los agentes
encima.

`tools/verify_m1_assumptions.py` ejecuta un grafo de tres nodos **en dos procesos separados**
que comparten el mismo fichero SQLite. Que sean procesos distintos es el punto: una
reanudación dentro del mismo proceso no demuestra nada sobre `RNF-D1`.

| Supuesto | Resultado |
|---|---|
| **A1** Grafo con estado tipado se compila y ejecuta | ✅ |
| **A2** El grafo se pausa y persiste su estado en disco | ✅ |
| **A3** Ese estado se reanuda **desde otro proceso** | ✅ |
| **A3** El trabajo ya confirmado **no se repite** | ✅ `nodo_uno` se ejecutó 1 vez |
| **A4** La ejecución alcanza un estado terminal explícito | ✅ |

**Entorno verificado:** LangGraph `1.2.14`, `langgraph-checkpoint-sqlite` `3.1.1`,
FastAPI `0.141.1`.

**El guion se verifica a sí mismo.** Una verificación que nunca ha fallado no demuestra nada,
así que `--self-check` introduce tres formas distintas de romper la persistencia y comprueba
que se detectan:

| Mutación | ¿Cazada? | Cómo |
|---|---|---|
| Checkpointer en memoria en lugar de SQLite | ✅ | `nodo_uno` se ejecuta dos veces |
| Sin checkpointer | ✅ | Falla al invocar `interrupt` |
| Reanudar en un hilo distinto al que escribió | ✅ | `nodo_uno` se ejecuta dos veces |

Las dos primeras mutaciones producen el registro `['nodo_uno', 'nodo_uno']` frente al
`['nodo_uno', 'nodo_dos:aprobado']` de la línea base. Es decir, **las caza la aserción que
vigila el trabajo repetido, por el motivo correcto** — no una excepción colateral.

**Y la auto-verificación encontró un fallo en la propia prueba:** la primera versión de la
mutación del hilo aplicaba el mismo identificador cambiado a *las dos* fases, con lo que
seguían siendo coherentes entre sí y la mutación no rompía nada. Una mutación inerte habría
producido un "3/3 cazadas" falso. Ahora la mutación es asimétrica a propósito.

**Hallazgo de diseño para M1 [PROP]:** al reanudar sobre un hilo **sin punto de control**,
LangGraph entrega un **estado vacío** y los nodos fallan con `KeyError` dentro de sí mismos.
Por tanto, M1 debe **comprobar que existe punto de control antes de reanudar** y devolver un
error tipado, en lugar de dejar que un nodo falle con un estado vacío. Un fallo dentro de un
nodo es un fallo en el peor lugar posible: no es diagnosticable y no respeta la taxonomía de
errores de §9.8 de `01-arquitectura.md`.

---

### 3.13 Resultado de la fase M1

**Completada.** El sistema arranca, recorre el grafo y termina en un estado terminal
explícito. La verificación no es una impresión: son **141 pruebas** (1 omitida, por
privilegios de Windows) y **17 de 17 mutaciones cazadas** por
`tools/mutation_check.py`.

#### Qué funciona de verdad

| Componente | Estado |
|---|---|
| Grafo con estado tipado (`RunState` como esquema de LangGraph) | ✅ |
| Persistencia por punto de control y reanudación | ✅ |
| Clasificación de intención determinista | ✅ |
| Researcher con **lectura real** del repositorio, confinada | ✅ |
| Policy Engine integrado en el nodo de pruebas | ✅ |
| Puerta de aprobación con pausa y reanudación | ✅ |
| Registro de eventos y progreso por SSE | ✅ |
| API completa, verificada sobre HTTP real | ✅ |
| Red de seguridad de `MET-13` | ✅ |

#### Qué NO funciona todavía, y se declara

- **No hay modelo conectado.** El Coder no produce parches, así que ninguna tarea de
  modificación completa. Termina en `needs_human` con el error tipado
  `CODER_PRODUCED_NO_CHANGES`. **Es el comportamiento correcto**: inventar un parche
  sería peor que admitir que no hay modelo.
- **No hay ejecutor de pruebas.** El nodo correspondiente pasa por el Policy Engine y
  después registra `TEST_EXECUTOR_NOT_IMPLEMENTED`. **No devuelve un `TestRun` con
  éxito falso.** Un sistema que se inventa que las pruebas pasaron es peor que uno que
  admite que no las ejecutó.
- **La puerta de aprobación es inalcanzable de punta a punta hoy.** Es una consecuencia
  directa de los dos puntos anteriores: sin parche no hay nada que probar, y sin
  evidencia de pruebas el Reviewer no puede aceptar. Se prueba sustituyendo `coder` y
  `run_tests` por lo que M2 implementará, de modo que la **topología completa** —
  incluida la pausa y la reanudación— sí queda ejercitada. Es una señal de integridad
  del diseño: el sistema se niega a llegar a "promover cambios" sin evidencia.
- **`RF-16` (cancelar) devuelve 501.** La ejecución corre dentro de la petición, así que
  no hay nada en curso que cancelar. Devolver 501 con el motivo es mejor que un endpoint
  a medias que parece funcionar.
- **La ejecución es síncrona.** Moverla fuera del hilo de la petición es requisito de
  `RNF-E3` y llega cuando haya trabajo lento de verdad, es decir con el modelo (M2).

#### Fallos encontrados durante la implementación

Se listan porque cada uno produjo un cambio en el código o una prueba nueva.

| # | Fallo | Causa | Corrección |
|---|---|---|---|
| 1 | **Pérdida silenciosa de datos en el checkpoint** | La lista de tipos permitidos se construía desde `__all__`, que no exportaba `Outputs`, `Artifacts` ni `Evidence`. El checkpoint los descartaba **sin error**. | Recorrer los módulos del paquete en lugar de confiar en los exports, y una prueba de ida y vuelta con **igualdad profunda** sobre un estado completamente poblado. |
| 2 | `invoke` y `get_state` devuelven un `dict`, no el modelo | Comportamiento de LangGraph con esquemas Pydantic | Reconstruir con `RunState.model_validate`. Los nodos **sí** reciben el modelo, lo que se comprobó explícitamente. |
| 3 | El estado persistido nunca mostraba `awaiting_approval` | `interrupt()` no confirma las escrituras parciales del nodo donde se llama, porque el nodo se reejecuta al reanudar | Nodo `mark_awaiting` separado, antes de la puerta. |
| 4 | Un 422 limpio se convertía en **500** | Cuando un `model_validator` lanza `ValueError`, Pydantic guarda la **instancia de la excepción** en `ctx`, y FastAPI no puede serializarla | Proyectar solo los campos serializables de cada error. |
| 5 | Ejecución inexistente en `approve` devolvía **409** en lugar de 404 | El motor comprobaba "¿está esperando?" antes que "¿existe?" | Invertir el orden. 404 y 409 son respuestas distintas para un cliente. |
| 6 | La API no arrancaba | Faltaba `python-multipart` en las dependencias: FastAPI la necesita para `UploadFile` | Añadida a `pyproject.toml`. Lo detectó una prueba de la API, no una revisión. |
| 7 | Aviso de recolección de pytest en cada ejecución | El contrato `TestRun` empieza por "Test" y pytest intenta recolectarlo como clase de prueba | `__test__ = False` en el contrato. |
| 8 | Suite de 0,3 s por prueba convertida en **92 s** | El borrado de directorios temporales pasa en este entorno por un interceptor que reintenta | `tmp_path_retention_policy = "none"`. Bajó a 8 s. El código nunca fue el problema: `start()` tarda 0,14 s. |
| 9 | `TemporaryDirectory` fallaba al limpiar en Windows | Conexión SQLite abierta: un descriptor abierto impide borrar el fichero | Cerrar la conexión en un `finally`. |

El fallo 1 es el más importante de la fase. No producía ningún error: producía **datos
faltantes**. Es exactamente la clase de defecto que una prueba de camino feliz no
detecta, porque el grafo no rellena los campos que se perdían.

### 3.14 Corrección del modelo de ejecución: el navegador como interfaz

**Qué cambió y por qué.** M1 ejecutaba la tarea dentro de la petición HTTP. Mientras la
interfaz fuera una terminal eso era aceptable. **Con un navegador como interfaz principal,
deja de serlo**, y el motivo es estructural, no de rendimiento:

```
POST /runs ─────────────────────────────► el cliente recibe el run_id
            (bloquea hasta que termina)    cuando la ejecución YA TERMINÓ
```

El cliente **no puede suscribirse a una ejecución cuyo identificador aún no tiene**. El
flujo SSE solo podía reproducir eventos ya ocurridos, nunca emitirlos en vivo. El
progreso en vivo era imposible, no lento.

**Medición de la corrección:**

| | Antes | Ahora |
|---|---|---|
| `POST /runs` | 166 ms bloqueando | **5 ms** devolviendo el `run_id` |
| Estado al volver | `needs_human` (ya terminó) | `planned` (aún no empezó) |
| Progreso | Reproducción de 3 eventos ya ocurridos | **8 eventos en vivo**, uno por nodo |
| Concurrencia | No aplica | 6 ejecuciones simultáneas, todas correctas |
| Reconexión | No soportada | `Last-Event-ID` devuelve exactamente lo que falta |

**Decisión `DEC-11`:** la ejecución no ocurre dentro de la petición. El detalle está en
`docs/06-contrato-frontend-backend.md`, junto con los cinco puntos de coordinación entre
frontend y backend y el contrato exportado.

#### Fallos encontrados al hacer el cambio

| # | Fallo | Causa | Corrección |
|---|---|---|---|
| 10 | **Una conexión SQLite compartida entre el hilo de la petición y los trabajadores** producía `SystemError: error return without exception set` en el `commit` | SQLite serializa las sentencias, pero no la transacción completa | El grafo se compila **por hilo**, y cada uno obtiene su propia conexión al mismo fichero |
| 11 | **`database is locked`** bajo concurrencia | `PRAGMA journal_mode=WAL` necesita un bloqueo exclusivo momentáneo: aplicarlo en cada conexión nueva chocaba con las escrituras en curso | El modo se fija **una vez**, al crear la base. Es persistente en el fichero |
| 12 | **`database is locked`**, segunda causa | Las **lecturas** (`events`, `summary`) usaban la conexión compartida **sin el cerrojo**, así que corrían a la vez que una escritura del trabajador sobre la misma conexión | El cerrojo cubre también las lecturas. Una conexión de SQLite se usa desde un hilo a la vez, y eso incluye leer |
| 13 | **El flujo SSE cerraba antes de tiempo y el cliente perdía eventos** | El bucle cerraba cuando el índice decía «terminal», y el índice se sincroniza **antes** de escribir los eventos | La señal de fin es el **evento** `run.done`, no un estado consultado. Con una red de seguridad de 2 s por si el evento no llega nunca |
| 14 | **`GET /runs/{id}` devolvía 404 justo después de crear** | Entre el 202 y el primer nodo hay una ventana en la que la ejecución existe pero no tiene punto de control | `get()` cae al **estado inicial** cuando no hay punto de control |
| 15 | **Tras un aborto, `GET /runs/{id}` seguía diciendo `running`** | El aborto solo actualizaba el índice; `GET /runs/{id}` lee el punto de control. Dos vistas del mismo hecho que no coincidían | El aborto escribe en el **punto de control** con `update_state`. Requiere el estado **completo**: con un esquema Pydantic, `update_state` valida en lugar de fusionar |
| 16 | **Cerrar el almacén bajo un trabajador activo** lo hacía fallar con `Cannot operate on a closed database` | El apagado no esperaba a las ejecuciones en curso | El apagado **espera** a las ejecuciones aceptadas antes de cerrar. El orden importa |

Los fallos 10 a 12 son la misma lección desde tres ángulos: **compartir una conexión SQLite
entre hilos no es seguro, aunque se pase `check_same_thread=False`.** El 13 es el más
peligroso de todos, porque no producía ningún error: producía **eventos ausentes**.

#### Fallos de las herramientas de verificación

Estos no están en el sistema, están en **cómo se comprueba** el sistema. Se documentan
igual, porque una verificación que miente es peor que no tener verificación.

| # | Fallo | Causa | Corrección |
|---|---|---|---|
| 17 | El verificador de mutaciones abortaba con «la línea base falla» **y sin decir por qué** | En este entorno pytest sale con **código 1 y sin resumen** aunque no falle nada | El veredicto se lee del **informe XML** que pytest escribe. Lección: cuando la señal que usas para verificar está corrompida, no la rodees con reintentos — **cambia de señal** |
| 18 | El verificador se colgaba **más de dieciocho minutos** sin producir una línea | Chromium deja **hijos que sobreviven al padre**: se acumularon ocho navegadores y cada verificación agotaba su tiempo de espera | Matar el **árbol** de procesos (`taskkill /F /T`), no solo el padre |
| 19 | **Una mutación quedó aplicada** en el frontend y las verificaciones siguientes medían código mutado | El original solo se restauraba en un `finally`, y el proceso fue interrumpido desde fuera | El original se escribe a un **diario en disco** antes de mutar, y al arrancar se restaura lo pendiente. **Un `finally` no protege contra que maten el proceso** |
| 20 | El diario del fallo 19 **volvió a colgar el verificador** | El entorno bloquea los borrados tras 50 por turno, y el diario creaba y borraba un fichero por mutación: el propio mecanismo de seguridad disparaba el límite | El diario es **un solo fichero que nunca se borra, solo se vacía**. Y el informe de pytest se detecta por fecha en lugar de borrarlo |
| 21 | La verificación del navegador **no era reproducible** | Usaba la base de datos por defecto, que crecía entre ejecuciones: los números cambiaban sin que cambiara el código | El almacén se puede sobrescribir por entorno (`AI_SWE_STATE_DB_PATH`) y la verificación arranca con base limpia |
| 22 | **Tres mutaciones del frontend se reportaron como cazadas sin que la comprobación llegara a ejecutarse** | El fallo 20 hacía morir la verificación a los 1,3 s, y el verificador interpretaba «código de salida distinto de cero» como «mutación cazada». **Un verificador que se cae no ha comprobado nada** | La herramienta debe **emitir un veredicto**; si no lo emite, el resultado es **NO CONCLUYENTE** y no cuenta como cazada. Y un no concluyente impide que el verificador termine con éxito |

El fallo 19 es el más incómodo de todos y conviene decirlo sin rodeos: **lo causé yo** al
interrumpir el verificador. El síntoma era que la interfaz no pintaba eventos, y apuntaba a
la aplicación. La aplicación estaba bien; el instrumento era el que mentía.

El fallo 22 es el más peligroso de la lista entera. Un verificador que deja el árbol
modificado produce fallos que no existen; uno que **cuenta como comprobado lo que no llegó a
comprobar** produce lo contrario: una confianza que no está respaldada por nada. El primero
se nota, porque algo falla. El segundo no se nota nunca. Y apareció justo al arreglar el
anterior, que es cuando uno está más inclinado a dar por bueno el resultado.

#### Verificación del frontend

`tools/verify_frontend.py` arranca el servidor, abre la interfaz en **Chrome headless
real** y **pulsa el botón**, en lugar de leer el HTML. Cubre lo que un simulador de DOM
no puede: si la página pintó, si el navegador se quejó, y si los eventos llegaron de
verdad. Y la verificación **se verifica**: se introdujeron cuatro defectos a propósito en
el frontend y los cuatro se detectan. Están incorporados en `tools/mutation_check.py`.

---

## 4. Estado de este incremento

**Fases M0 (diseño) y M1 (esqueleto ejecutable) completadas.**

**M0 — Diseño:**

- `docs/01-arquitectura.md` — problema, objetivos, alcance, requerimientos, arquitectura,
  justificación de Multi-Agent, Supervisor, agentes, STT, MCP, herramientas, State/Memory,
  HITL, seguridad, observabilidad, evaluación.
- `docs/02-tecnologias.md` — stack con las ocho preguntas por tecnología.
- `docs/03-flujo-e-implementacion.md` — este documento.
- `docs/04-defensa.md` — defensa arquitectónica.
- `docs/05-graphify-evaluacion.md` — evaluación de la capa de contexto basada en grafo.
- `docs/diagrama-arquitectura.svg` / `.png` — diagrama validado geométricamente.
- `tools/build_diagram.py` — generador con validador y contador de elementos.
- `src/ai_swe/contracts/` — contratos Pydantic del estado, tareas, salidas y herramientas.
- `src/ai_swe/tools/policy.py` — matriz de permisos como dato + `decide()`.

**M1 — Esqueleto ejecutable:**

- `src/ai_swe/state/store.py` — checkpointer, índice de ejecuciones y registro de eventos.
- `src/ai_swe/graph/nodes.py` — nodos deterministas; Researcher con lectura real.
- `src/ai_swe/graph/workflow.py` — topología del grafo.
- `src/ai_swe/graph/engine.py` — arranque, reanudación y red de seguridad de `MET-13`.
- `src/ai_swe/api/app.py` — API completa, verificada sobre HTTP real.
- `src/ai_swe/stt/base.py` — contrato del adaptador y `FakeAdapter`.
- `tools/verify_m1_assumptions.py` — verificación auto-verificable de la pausa y reanudación.
- `tests/` — 141 pruebas (1 omitida), 17/17 mutaciones cazadas.

**Siguiente paso propuesto: M2 — agentes reales.** Conectar el modelo, sustituir el
clasificador determinista por interpretación real, y hacer que el Coder produzca parches
sobre un *worktree* aislado. Es la fase que convierte el esqueleto en un sistema que
resuelve tareas, y la que hace alcanzable de punta a punta la puerta de aprobación.
