# Proyecto 4 — AI Software Engineering System

> Frontend de entrega: [baseline vigente](docs/BASELINE-FRONTEND-DELIVERY.md) y
> [roadmap](docs/ROADMAP.md). La Fase C integral requiere autorización separada.
> Jupyter / Hugging Face Agent Model Lab está **PLANNED**, fuera del runtime.


**Equipo 4** — *Agentic Workflows, Multi-Agent, MCP, State y coordinación*
Arquitectura de Sistemas de Inteligencia Artificial

Sistema multiagente que convierte una instrucción de ingeniería de software
—dictada o escrita— en un **plan acotado y verificable** sobre un repositorio
autorizado, coordina especialistas con permisos distintos, mantiene el estado de
la ejecución de forma trazable y entrega un resultado revisado con evidencia.

---

## Estado del proyecto

**14 fases completadas y verificadas: `M0`, `M1`, `F1`–`F14`.**

El sistema está **funcional de extremo a extremo** en su alcance declarado:
**prototipo local, un solo usuario, `127.0.0.1`, sin autenticación**.

> **Documentación.** Índice único: [`docs/README.md`](docs/README.md).
> Estado verificado: [`PROJECT_SNAPSHOT.json`](PROJECT_SNAPSHOT.json) y la auditoría
> integral de [`docs/audit/`](docs/audit/). Actas de las fases anteriores:
> [`docs/history/`](docs/history/). Modelo: [`docs/MODEL-GATEWAY.md`](docs/MODEL-GATEWAY.md).

| Capacidad | Estado | Dónde |
|---|---|---|
| Grafo de orquestación (17 nodos, 2 puertas HITL) | ✅ verificado | `src/ai_swe/graph/` |
| API REST + SSE (12 endpoints) | ✅ verificado | `src/ai_swe/api/app.py` |
| Persistencia (SQLite + checkpoint) | ✅ verificado | `src/ai_swe/state/` |
| Model Gateway + 2 proveedores + presupuesto | ✅ verificado | `src/ai_swe/models/` |
| Requirements Analyst (`F3`) | ✅ verificado | `graph/nodes.py` |
| Supervisor / `RunPlan` (`F4`) | ✅ verificado | `graph/nodes.py` |
| Ejecución iterativa por subtareas (`F5`) | ✅ verificado | `graph/nodes.py` |
| Coder con parches reales (`F6`) | ✅ verificado | `graph/nodes.py` |
| Sandbox por `git worktree` (`F7`) | ✅ verificado | `src/ai_swe/sandbox.py` |
| Test Runner real con targets cerrados (`F8`) | ✅ verificado | `src/ai_swe/tools/runner.py` |
| Reviewer semántico + guardas deterministas (`F9`) | ✅ verificado | `graph/nodes.py` |
| Frontend React + TypeScript + Vite (`F11`) | ✅ verificado | `frontend/` |
| Promoción al repositorio del usuario (`F12`) | ✅ verificado | `src/ai_swe/tools/promoter.py` |
| STT local `faster-whisper` (`F13`) | ✅ verificado | `src/ai_swe/stt/` |
| Evaluación single vs multi agent (`F14`) | ✅ verificado | `src/ai_swe/evaluation/` |
| Policy Engine y matriz de permisos | ✅ verificado | `src/ai_swe/tools/` |
| Redacción centralizada de secretos (`RNF-S3`) | ✅ verificado | `src/ai_swe/security/` |
| Contrato exportado para el navegador | ✅ verificado (GENERATED) | `frontend/contracts.json` |
| Diagrama arquitectónico | ✅ generado con validación geométrica | `docs/diagrama-arquitectura.svg` |
| **Autenticación** | 🔴 no implementada (`AUD-06`) | — |
| **MCP** | 🔴 no implementado | `src/ai_swe/mcp/` (placeholder) |
| **Observabilidad / Langfuse** | 🔴 no implementada | `src/ai_swe/observability/` (placeholder) |
| **Knowledge Graph / Graphify** | 🔵 propuesta `[PROP]`, no implementada | `docs/05-graphify-evaluacion.md` |
| **TTS** | 🔴 no implementado | — |
| **Cancelación de ejecución** (`RF-16`) | 🔴 devuelve 501 | `api/app.py` |
| **Aislamiento de proceso del sandbox** | 🔴 no implementado — solo confina escritura | ver `docs/audit/13-SANDBOX-EXECUTION-AUDIT.md` |

**Qué funciona hoy, de verdad:** el sistema arranca, acepta una instrucción y devuelve
el `run_id` de inmediato; la ejecuta en un trabajador; publica el progreso **nodo a
nodo** por SSE; se detiene en **dos puertas humanas** (confirmar requisitos y aprobar
el cambio); aplica el parche en un `git worktree` aislado; ejecuta `pytest` real
dentro; lo revisa con evidencia; y **promueve al repositorio del usuario** el cambio
aprobado, con verificación de integridad SHA256. Toda ejecución termina en un estado
terminal explícito (`MET-13 = 0`).

**Suite de pruebas: 601 casos, 0 fallos, 2 saltos opt-in** (sin red ni credenciales).

**Qué no está listo, y se declara:**
- **No hay autenticación** (`AUD-06`). Mitigado con el binding fijo a `127.0.0.1`.
- **El «sandbox» no aísla el proceso.** Confina la *escritura* del Coder con cuatro
  barreras, pero ejecuta el `pytest` del repositorio del usuario con el mismo usuario
  del sistema, sin límites de CPU/memoria/procesos ni aislamiento de red. **No debe
  exponerse a una red.**
- **El sistema nunca se ha ejecutado contra un modelo real** (`TD-01`): funciona con
  los fallbacks deterministas y con el proveedor falso.
- **Cinco ajustes declarados en `.env.example` no se aplican todavía** (allowlist de
  repositorios, bloqueo de red y tres límites de presupuesto).

El detalle completo, con evidencia, está en la auditoría integral:
[`docs/audit/00-EXECUTIVE-AUDIT.md`](docs/audit/00-EXECUTIVE-AUDIT.md).

**No se atribuya al sistema nada que no pueda demostrarse.** Lo que existe es una
cadena funcional completa y verificada —orquestación, estado, sandbox, pruebas,
revisión, HITL, promoción y frontend— sobre la que la evolución controlada trabaja
fase a fase.

---

## Instalación

Requiere Python 3.12 o superior (versión del entorno verificado: **3.13**, fijada en
`.python-version`).

Con `uv` (recomendado, reproducible — usa el lockfile):

```bash
uv sync --frozen           # instala exactamente lo resuelto en uv.lock
uv sync --frozen --extra dev   # + herramientas de desarrollo
```

Con `pip` (sin garantía de resolución exacta):

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Para la entrada por voz y la observabilidad, extras opcionales:

```bash
pip install -e ".[voice]"           # faster-whisper (Speech-to-Text local)
pip install -e ".[observability]"   # Langfuse
pip install -e ".[mcp]"             # servidores MCP (FASE FUTURA, no usado todavía)
```

> ✅ **Reproducibilidad resuelta.** Existe `uv.lock` (99 paquetes), generado con `uv lock`
> desde `pyproject.toml`. Se verificó que un entorno reconstruido desde el lockfile, en
> una ubicación distinta, reproduce **211/211 pruebas** con las mismas versiones. El
> lockfile **no** se generó con `pip freeze` a propósito: el entorno de trabajo contiene
> paquetes ajenos al proyecto y congelarlos habría declarado como dependencias cosas que
> el proyecto nunca pidió.

## Ejecución de las pruebas

```bash
pytest
```

Verificación de que la suite **protege** el código (introduce cada defecto a
propósito y comprueba que alguna prueba falla):

```bash
python tools/mutation_check.py            # 24/24 mutaciones backend+frontend
python tools/verify_redaction_mutations.py  # 8/8 mutaciones de la redacción
```

Regeneración y validación del diagrama:

```bash
python tools/build_diagram.py
```

El generador **valida la geometría antes de dibujar** y aborta si algo falla.
Esta comprobación ya encontró un defecto real: la leyenda inferior pisaba dos
cajas, y era invisible en el render porque el texto es gris claro sobre un
relleno claro.

Verificación de los supuestos de la fase M1 (pausa y reanudación del grafo
**entre procesos distintos**):

```bash
python tools/verify_m1_assumptions.py
```

Ejecuta un grafo de tres nodos en dos procesos separados que comparten el mismo
SQLite, y se **auto-verifica**: introduce tres formas distintas de romper la
persistencia y comprueba que las detecta. Ver `docs/03-flujo-e-implementacion.md`
§3.12.

Verificación del frontend en un **navegador real**, sin ventana:

```bash
python tools/verify_frontend.py
```

Arranca el servidor, abre la interfaz en Chrome headless y **pulsa el botón**, en
lugar de leer el HTML. Comprueba lo que un simulador de DOM no puede: si la página
pintó, si el navegador se quejó y si los eventos llegaron de verdad. Ver
`docs/07-contrato-frontend-backend.md` §4.

Regeneración del contrato que consume el navegador:

```bash
python tools/export_contracts.py
```

Los contratos son modelos Pydantic y se exportan a `frontend/contracts.json`. Una
prueba comprueba que el fichero está al día, así que no puede quedarse obsoleto en
silencio.

## Ejecución del sistema

```bash
uvicorn ai_swe.api.app:crear_app --factory --reload --port 8000
```

**La interfaz está en <http://localhost:8000/app/>**. Se sirve desde el **mismo origen**
que la API, así que el prototipo no necesita CORS. La documentación interactiva de la
API está en `/docs`.

Flujo completo, tal como lo hace el navegador:

```bash
# 1. Crear la ejecución. Responde 202 DE INMEDIATO, con el run_id.
#    No espera a que la ejecución termine: eso es lo que permite suscribirse al progreso.
curl -i -X POST localhost:8000/runs -H "Content-Type: application/json" \
     -d '{"instruction":"¿Dónde se valida el token de sesión?"}'

# 2. Suscribirse al progreso en vivo. Cada evento lleva id, event y data.
#    Se reanuda con `Last-Event-ID` si la conexión se corta.
curl -N localhost:8000/runs/<run_id>/events

# 3. Aprobar o rechazar una acción pendiente (si la ejecución la pide)
curl -X POST localhost:8000/runs/<run_id>/approve \
     -H "Content-Type: application/json" -d '{"decision":"approved"}'

# 4. Estado final, informe y lista de ejecuciones
curl localhost:8000/runs/<run_id>
curl localhost:8000/runs

# Transcribir audio. NO crea ninguna ejecución.
curl -X POST localhost:8000/transcriptions -F "audio=@instruccion.webm"

# Una instrucción de voz sin confirmar se rechaza con 422 (RF-03)
curl -X POST localhost:8000/runs -H "Content-Type: application/json" \
     -d '{"instruction":"corrige el parser","source":"voice"}'
```

El estado vive en `var/state.sqlite3` (ignorado por git).

---

## Estructura del proyecto

```
proyecto4-ai-swe/
├── docs/                       Documento de arquitectura y diagrama
├── tools/
│   ├── build_diagram.py        Layout + validación geométrica + emisión SVG
│   ├── export_contracts.py     Exporta los contratos a JSON Schema para el navegador
│   ├── mutation_check.py       Verifica que la suite de pruebas protege el código
│   ├── verify_frontend.py      Pulsa la interfaz en un Chrome real, sin ventana
│   └── verify_m1_assumptions.py  Pausa y reanudación del grafo entre procesos
├── src/ai_swe/
│   ├── config.py               Configuración validada al arrancar
│   ├── contracts/              CONTRATOS: la definición de las interfaces
│   ├── tools/                  Catálogo, matriz de permisos y Policy Engine
│   ├── state/                  Checkpointer, estado inicial, índice y eventos
│   ├── api/                    FastAPI (M1, completo)
│   ├── graph/                  Grafo, nodos, motor y trabajador (M1; agentes en M2)
│   ├── agents/                 Researcher, Coder, Reviewer (fase M2)
│   ├── mcp/                    Cliente y servidores MCP (fase M3)
│   ├── stt/                    Adaptador de Speech-to-Text (contrato en M1, real en M5)
│   ├── observability/          Trazas y redacción de secretos (fase M6)
│   └── evaluation/             Arnés de evaluación y métricas (fase M2/M6)
├── frontend/
│   ├── index.html              Interfaz real: crea, sigue el progreso y aprueba
│   └── contracts.json          GENERADO. No editar a mano.
├── tests/                      153 pruebas: contratos, política, almacén, grafo, API
├── data/tasks/                 Suite de evaluación con verdad conocida
├── pyproject.toml
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

---

## Configuración

Todas las variables llevan el prefijo `AI_SWE_`. `.env.example` documenta los
**nombres**; los valores y los secretos nunca se almacenan en el repositorio.

| Variable | Para qué sirve |
|---|---|
| `AI_SWE_MODEL_PROVIDER`, `AI_SWE_MODEL_NAME`, `AI_SWE_MODEL_API_KEY` | Proveedor del Foundation Model. |
| `AI_SWE_MODEL_BASE_URL` | Proveedor local (Ollama, vLLM). |
| `AI_SWE_STATE_DB_PATH` | Almacén del estado por ejecución (SQLite). |
| `AI_SWE_WORKSPACE_ROOT` | Raíz donde se crean los *worktrees* de cada ejecución. |
| `AI_SWE_AUTHORIZED_REPOS` | Lista blanca de repositorios que el sistema puede tocar. |
| `AI_SWE_ALLOWED_TEST_TARGETS` | **Enumeración cerrada** de objetivos de prueba ejecutables. |
| `AI_SWE_ALLOWED_PACKAGES` | Enumeración cerrada de paquetes instalables. Vacía = ninguno. |
| `AI_SWE_NETWORK_EGRESS_ENABLED` | Salida de red desde el entorno de ejecución. **Desactivada** por defecto. |
| `AI_SWE_MAX_TOKENS_PER_RUN`, `AI_SWE_MAX_TOOL_CALLS_PER_RUN`, `AI_SWE_MAX_SECONDS_PER_RUN`, `AI_SWE_MAX_REVIEW_CYCLES` | Presupuesto de la ejecución. Agotarlo corta y escala. |
| `AI_SWE_STT_*` | Proveedor, modelo, idioma y umbral de confianza del Speech-to-Text. |
| `AI_SWE_TTS_ENABLED` | Salida por voz. Opcional por diseño. |
| `AI_SWE_LANGFUSE_*` | Observabilidad. |
| `AI_SWE_LOG_LEVEL` | Nivel de registro. |

---

## Las siete decisiones que definen este sistema

1. **El Speech-to-Text es un adaptador de borde, no el núcleo.** El sistema
   funciona igual sin voz. Está en la fase M5, penúltima.
2. **La seguridad se apoya en contención de capacidades, no en un *prompt*.** El
   agente no tiene la herramienta peligrosa: no existe `run_shell`, no existe
   `git_push`. Un guardrail que razona es un guardrail que se puede convencer.
3. **`run_tests` no recibe un comando, recibe un identificador de una lista.**
   Eso convierte la inyección de comandos en un problema de validación de
   enumeración, que es trivialmente resoluble.
4. **Los agentes no se hablan.** Se comunican solo escribiendo campos tipados en
   el Shared State. No hay un canal por el que puedan acordar algo que nadie
   registró.
5. **Multi-Agent se justifica con evidencia, no con opinión.** `EXP-01` compara
   un agente contra varios sobre el mismo conjunto de tareas, y `EXP-02`
   elimina el Reviewer si no supera el umbral de detección.
6. **La optimización de tokens no se compra, se diseña.** Una capa de contexto
   basada en grafo (Graphify y similares) **no se adopta** en el prototipo: el
   ahorro lo produce el recorte, no el grafo, y el recorte ya es un requisito
   nuestro. Se adopta el principio en su forma mínima —un mapa de símbolos
   determinista de ~1 000 tokens— detrás de `EXP-08`. Ver
   `docs/05-graphify-evaluacion.md`.
7. **La ejecución no ocurre dentro de la petición** (`DEC-11`). `POST /runs`
   responde 202 con el `run_id` en 5 ms y un trabajador ejecuta; el progreso llega
   por eventos. Con un navegador como interfaz, el cliente **no puede suscribirse a
   una ejecución cuyo identificador aún no tiene**: el progreso en vivo era
   estructuralmente imposible, no lento. Ver
   `docs/07-contrato-frontend-backend.md`.

---

## Documentación

| Documento | Contenido |
|---|---|
| `docs/01-arquitectura.md` | Problema, objetivos, alcance, requerimientos, arquitectura, Multi-Agent, Supervisor, agentes, STT, MCP, herramientas, State/Memory, HITL, seguridad, observabilidad, evaluación. |
| `docs/02-tecnologias.md` | Cada tecnología con las ocho preguntas de justificación, y lo que **no** se usa. |
| `docs/03-flujo-e-implementacion.md` | Diagrama, flujo paso a paso con un ejemplo, y plan por fases. |
| `docs/04-defensa.md` | Preguntas del profesor con la respuesta técnica preparada. |
| `docs/05-graphify-evaluacion.md` | Evaluación de Graphify como capa de contexto: veredicto, riesgo `AM-13`, alternativa mínima y criterio de adopción (`EXP-08`). |

**Convención de trazabilidad:** `[DOC]` = requisito tomado del documento del
profesor · `[PROP]` = propuesta de diseño adicional · `[DEC]` = decisión de
arquitectura con alternativa descartada. Las decisiones se numeran `DEC-01`…,
los requisitos `RF-xx`/`RNF-xx`, las amenazas `AM-xx`, las métricas `MET-xx` y
los experimentos `EXP-xx`.
