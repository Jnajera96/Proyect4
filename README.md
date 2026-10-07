# Proyecto 4 — AI Software Engineering System

**Equipo 4** — *Agentic Workflows, Multi-Agent, MCP, State y coordinación*
Arquitectura de Sistemas de Inteligencia Artificial

Sistema multiagente que convierte una instrucción de ingeniería de software
—dictada o escrita— en un **plan acotado y verificable** sobre un repositorio
autorizado, coordina especialistas con permisos distintos, mantiene el estado de
la ejecución de forma trazable y entrega un resultado revisado con evidencia.

---

## Estado del proyecto

**Fases M0 (diseño) y M1 (esqueleto ejecutable) completadas.**

> **Documentación.** El **estado real verificado** está en
> [`docs/auditoria-2026-10-06/`](docs/auditoria-2026-10-06/) (derivado de la
> auditoría técnica del 2026-10-06) y el **diseño** en `docs/01..06`.
> Índice y jerarquía de evidencia: [`docs/README.md`](docs/README.md).
> Reporte de la sesión de integración documental:
> [`docs/BASELINE-M1-POST-DOCUMENTACION.md`](docs/BASELINE-M1-POST-DOCUMENTACION.md).

| Componente | Estado |
|---|---|
| Documento de arquitectura (diseño, M0) | ✅ `docs/01-arquitectura.md` |
| Selección de tecnologías | ✅ `docs/02-tecnologias.md` |
| Flujo de ejecución y plan de implementación | ✅ `docs/03-flujo-e-implementacion.md` |
| Defensa arquitectónica | ✅ `docs/04-defensa.md` |
| Evaluación de Graphify como capa de contexto | 🔵 propuesta `[PROP]`, **no implementada** |
| Contrato entre frontend y backend | ✅ `docs/06-contrato-frontend-backend.md` |
| Diagrama arquitectónico | ✅ `docs/diagrama-arquitectura.svg` / `.png` |
| Auditoría externa y estado verificado | ✅ `docs/AUDITORIA-EXTERNA.md`, `docs/auditoria-2026-10-06/` |
| Contratos entre componentes | ✅ `src/ai_swe/contracts/` |
| Policy Engine y matriz de permisos | ✅ `src/ai_swe/tools/` |
| Supuestos de M1 verificados (pausa y reanudación entre procesos) | ✅ `tools/verify_m1_assumptions.py` |
| **M1: grafo, almacén de estado, API y frontend** | ✅ `src/ai_swe/`, `frontend/` |
| Ejecución asíncrona con progreso en vivo por SSE | ✅ `graph/worker.py`, `api/app.py` |
| Contrato exportado para el navegador | ✅ `frontend/contracts.json` |
| Suite de pruebas (153 pruebas, 24/24 mutaciones cazadas) | ✅ `tests/` |
| **Model Gateway + LLM conectado** | 🔴 **no existe** — fase `F2` |
| **Requirements Analyst** | 🔴 **no existe** — fase `F3` |
| **Supervisor con razonamiento / `RunPlan`** | 🔴 **no existe** — fase `F4` |
| **Coder que genere parches** | 🔴 **no existe** — produce cambio vacío |
| **Test Runner real** | 🔴 **no existe** — registra error tipado |
| **Reviewer semántico** | 🔴 **no existe** — determinista |
| **MCP** | 🔴 **no implementado** — fase `F13` |
| **Graphify / Knowledge Graph** | 🔴 **no implementado** — fase `F12` |
| **STT real (faster-whisper)** | 🔴 **no implementado** — fase `F14` |
| **Observabilidad completa (Langfuse, logs JSON, métricas)** | 🔴 **no implementada** — fase `F15` |
| **Autenticación** | 🔴 **no implementada** — fase `F16` |

**Qué funciona hoy:** el sistema arranca, **acepta una instrucción y devuelve el
`run_id` en 5 ms** (antes bloqueaba 166 ms), la ejecuta en un trabajador, y publica
el progreso **nodo a nodo** por eventos que el navegador consume en vivo. Toda
ejecución termina en un estado terminal explícito (`MET-13 = 0`). La puerta de
**aprobación humana** funciona de verdad: aprobar y rechazar se han verificado
de extremo a extremo.

**Qué no funciona todavía, y se declara:** no hay modelo conectado, así que el Coder no
produce parches y las tareas de modificación terminan en `needs_human` con un error tipado.
No hay ejecutor de pruebas, así que **no se registra evidencia de pruebas inventada**. El
sistema prefiere admitir que no puede hacer algo antes que simular que lo hizo.
**Y no hay autenticación:** cualquier navegador ve todas las ejecuciones.

**No se atribuya al sistema nada que no pueda demostrarse.** En concreto, hoy **no
hay** agentes inteligentes, ni MCP, ni Graphify, ni Coder funcional, ni STT real, ni
`ModelGateway`. Lo que existe es una infraestructura de orquestación, estado,
persistencia y verificación **sólida y probada**, esperando el componente que le da
nombre: el modelo.

El plan vigente por fases es el de **17 fases `F0`–`F16`** en
`docs/auditoria-2026-10-06/09_ROADMAP.md`. El plan histórico por hitos `M0`–`M6`
está en `docs/03-flujo-e-implementacion.md` §3.11 y el resultado de M1 en §3.13.
El orden es deliberado: **MCP y Graphify llegan después** de que el flujo
funcione de extremo a extremo; la voz es un adaptador de borde y llega tarde.

---

## Instalación

Requiere Python 3.12 o superior.

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

> ⚠️ **Sin lockfile todavía.** Las dependencias se declaran con mínimos (`>=`), de modo
> que dos instalaciones en fechas distintas pueden resolver versiones diferentes. Es la
> deuda de reproducibilidad conocida y se aborda en la fase `F1`. El mecanismo
> propuesto y su justificación están en
> [`docs/auditoria-2026-10-06/12_GIT_REPRODUCIBILIDAD.md`](docs/auditoria-2026-10-06/12_GIT_REPRODUCIBILIDAD.md).

## Ejecución de las pruebas

```bash
pytest
```

Verificación de que la suite **protege** el código (introduce cada defecto a
propósito y comprueba que alguna prueba falla):

```bash
python tools/mutation_check.py
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
`docs/06-contrato-frontend-backend.md` §4.

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
   `docs/06-contrato-frontend-backend.md`.

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
