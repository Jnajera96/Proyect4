# Auditoría arquitectónica del estado actual — para el Arquitecto Principal

**Proyecto:** AI Software Engineering System
**Fecha del reporte:** 2026-10-06
**Commit auditado:** `04b7581` — `F2 implement provider-agnostic model gateway`
**Árbol de trabajo:** limpio (sin cambios sin confirmar)
**Modo:** solo lectura. No se escribió código ni se avanzó de fase durante esta auditoría.

> **Regla aplicada a este documento.** Cada afirmación va acompañada de la evidencia
> que la sostiene (fichero y línea, comando o recuento). Lo que no está implementado
> se marca **`NOT_IMPLEMENTED`** de forma explícita. No se atribuye al sistema nada
> que no se pueda demostrar con el árbol actual.

---

## 1. Fase actual

### Fase del roadmap

| Hito histórico | Estado |
|---|---|
| `M0` — diseño | ✅ cerrada |
| `M1` — esqueleto ejecutable | ✅ cerrada (tag local `m1-verified-baseline` → `7446bdf`) |
| `F1` — reproducibilidad + hardening pre-M2 | ✅ cerrada (`d556960`) |
| **`F2` — Model Gateway** | ✅ **cerrada** (`04b7581`) — objeto de esta auditoría |
| **`M2` — agentes reales** | 🔶 **EN PROGRESO** (1 de ~9 fases) |
| `F3` — Requirements Analyst | ⬜ no iniciada |
| `F4`–`F16` | ⬜ no iniciadas |

Fuente: `docs/auditoria-2026-10-06/09_ROADMAP.md`.

### Valor exacto en `PROJECT_SNAPSHOT.json`

El campo `phase` dice, literalmente:

```
"M2 IN PROGRESS — F2 (Model Gateway) implemented; gateway NOT yet wired to LangGraph"
```

Otros campos relevantes del snapshot:

| Campo | Valor |
|---|---|
| `next_milestone` | `"F3 — Requirements Analyst"` |
| `ready_for_model_gateway` | `"YES"` |
| `model_gateway_ready` | `"YES"` |
| `tests_require_network` | `false` |
| `tests_require_credentials` | `false` |

### ⚠️ Discrepancia detectada en el propio snapshot

Al verificar el recuento real de pruebas contra el snapshot, aparecen **dos números
desactualizados**:

| Campo del snapshot | Valor declarado | Valor real verificado |
|---|---|---|
| `tests_passing` | `280` | **284** |
| `mutations_caught` | `"24/24 (project, pre-F2) + 8/8 (redaction) + F2 mutations"` | **`35/35` (proyecto, incluidas 11 de F2) + `8/8` (redacción)** |

Causa: se actualizó el snapshot antes de añadir las 4 últimas pruebas (3 de
aislamiento de redacción + 1 de higiene de `.gitignore`) y antes de añadir la
mutación nº 35. **Se corrigen en esta auditoría** (son datos de estado, no código).

Verificación del recuento real:

```
284 pruebas, 0 fallos, 0 errores, 1 omitida
  test_api: 26 · test_config_budget: 18 · test_contracts: 22
  test_diagram_layout: 13 · test_model_gateway: 72 · test_model_gateway_real: 1
  test_policy: 46 · test_redaction: 40 · test_store: 7 · test_workflow: 39
```

---

## 2. Estructura del proyecto

Árbol real (excluidos `.git`, `__pycache__`, `.pytest_cache`, `.ruff_cache`,
`node_modules`, `.venv`, `.egg-info`):

```
proyecto4-ai-swe/
├── .env.example              # documenta NOMBRES de variables, nunca valores
├── .gitattributes            # normalización LF
├── .gitignore
├── .python-version           # 3.13
├── Dockerfile                # aislamiento de ejecución (fase M3)
├── docker-compose.yml
├── README.md
├── pyproject.toml
├── uv.lock                   # 99 paquetes resueltos
│
├── data/tasks/README.md      # ⚠️ describe una suite de evaluación: 0 ficheros de tarea
│
├── docs/                     # 33 documentos
│   ├── 01-arquitectura.md … 06-contrato-frontend-backend.md   (diseño M0)
│   ├── AUDITORIA-EXTERNA.md
│   ├── BASELINE-M1-POST-DOCUMENTACION.md
│   ├── BASELINE-PRE-M2.md                    (cierre F1)
│   ├── BASELINE-MODEL-GATEWAY.md             (cierre F2)
│   ├── MODEL-GATEWAY.md / MODEL-GATEWAY-DESIGN.md
│   ├── README.md                             (índice y jerarquía de evidencia)
│   ├── diagrama-arquitectura.svg / .png
│   └── auditoria-2026-10-06/                 (18 ficheros + PROJECT_SNAPSHOT.json)
│
├── frontend/                 # ⚠️ SIN package.json — HTML estático, sin build
│   ├── index.html            # 404 líneas, un solo <script>, sin framework
│   ├── contracts.json        # contrato exportado, verificado por prueba
│   ├── _verify.html          # sonda de la verificación en navegador real
│   └── _verify_probe.js
│
├── src/ai_swe/
│   ├── __init__.py
│   ├── config.py                     # Settings (SecretStr) + validación de uso
│   ├── agents/__init__.py            # PLACEHOLDER — solo docstring (13 líneas)
│   ├── api/
│   │   ├── __init__.py
│   │   └── app.py                    # FastAPI + SSE + lifespan
│   ├── contracts/                    # 7 ficheros — contratos Pydantic
│   │   ├── __init__.py · api.py · outputs.py · state.py
│   │   ├── tasks.py · tools.py · validate.py
│   ├── evaluation/__init__.py        # PLACEHOLDER — solo docstring (16 líneas)
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── engine.py                 # RunEngine (ejecutar / reanudar / abortar)
│   │   ├── nodes.py                  # 12 nodos + 5 enrutadores (566 líneas)
│   │   ├── worker.py                 # RunWorker (ThreadPoolExecutor)
│   │   └── workflow.py               # ensamblado del StateGraph
│   ├── mcp/__init__.py               # PLACEHOLDER — solo docstring (13 líneas)
│   ├── models/                       # ★ NUEVO EN F2 — Model Gateway
│   │   ├── __init__.py · contracts.py · errors.py · budget.py
│   │   ├── pricing.py · registry.py · gateway.py
│   │   └── providers/
│   │       ├── __init__.py · base.py · fake.py · openai_compatible.py
│   ├── observability/__init__.py     # PLACEHOLDER — solo docstring (13 líneas)
│   ├── security/
│   │   ├── __init__.py · logging.py · redaction.py
│   ├── state/
│   │   ├── __init__.py
│   │   └── store.py                  # checkpointer + índice + registro de eventos
│   ├── stt/
│   │   ├── __init__.py
│   │   └── base.py                   # Protocol + FakeAdapter + FasterWhisper (stub)
│   └── tools/
│       ├── __init__.py
│       ├── policy.py                 # Policy Engine (función pura)
│       └── registry.py               # catálogo + matriz de permisos (dato)
│
├── tests/                    # 10 ficheros · 284 pruebas
├── tools/                    # 5 verificadores (no son pruebas)
└── var/                      # estado SQLite de ejecuciones (gitignored)
```

**Directorios que son solo `__init__.py` con docstring (placeholder declarado):**
`agents/`, `evaluation/`, `mcp/`, `observability/`.
**`NOT_IMPLEMENTED`** como código en todos ellos.

**Observación:** los tres directorios `tmp*/` y `var/` aparecen en disco; están
excluidos por `.gitignore` y no forman parte del árbol versionado. Los `tmp*/` son
residuos de pruebas que el entorno no deja borrar.

---

## 3. Contratos críticos (Pydantic)

> **Nota de precisión.** El encargo pedía `ProjectRequirements`. **Ese contrato no
> existe** — ver §3.1. Se documenta el equivalente real.

### 3.1 `ProjectRequirements` — **`NOT_IMPLEMENTED`**

```
grep -rn "ProjectRequirements" . --include="*.py" --include="*.json" --include="*.md"
→ sin resultados
```

El contrato más cercano que **sí** existe es **`TaskInterpretation`**
(`contracts/tasks.py`), que representa lo que el Supervisor **entendió** de la
instrucción — distinto de lo que el usuario **pidió** (`RunOptions`). Esa separación
es deliberada: permite comparar ambos y detectar una interpretación desviada.

```python
class TaskInterpretation(BaseModel):
    """Salida validada de la fase de interpretacion del Supervisor."""

    intent: Intent
    scope: Scope
    constraints: list[str] = Field(default_factory=list, ...)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=2000)
```

Y su `Scope`:

```python
class Scope(BaseModel):
    repo_path: str = Field(description="Raiz del repositorio autorizado.")
    allowed_paths: list[str] = Field(default_factory=list, ...)
    protected_paths: list[str] = Field(default_factory=list, ...)
    max_files_changed: int = Field(default=10, ge=1, le=100)
    max_lines_changed: int = Field(default=400, ge=1, le=10_000)
```

**Estado de `TaskInterpretation`:** el contrato existe y se usa, pero **lo rellena un
clasificador determinista por vocabulario**, no un modelo. Ver §6.

### 3.2 `RunState` — implementado y en uso

`src/ai_swe/contracts/state.py` (líneas 245–295). Código exacto:

```python
class RunState(BaseModel):
    """Estado completo de una ejecucion.

    Debe ser serializable: se verifica estructuralmente en tests/test_contracts.py.
    """

    schema_version: str = Field(default=SCHEMA_VERSION)
    run_id: str = Field(min_length=1, max_length=64)
    trace_id: str = Field(min_length=1, max_length=64)
    created_at: datetime
    updated_at: datetime

    instruction: Instruction
    options: RunOptions = Field(default_factory=RunOptions)
    interpretation: TaskInterpretation | None = None
    plan: RunPlan | None = None

    outputs: Outputs = Field(default_factory=Outputs)
    artifacts: Artifacts = Field(default_factory=Artifacts)
    evidence: Evidence = Field(default_factory=Evidence)
    approvals: list[Approval] = Field(default_factory=list, max_length=200)
    errors: list[RunError] = Field(default_factory=list, max_length=500)
    budget: Budget = Field(default_factory=Budget)
    final_report: FinalReport | None = None

    status: RunStatus = RunStatus.PLANNED
    next_step: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _timestamps_consistent(self) -> RunState:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at anterior a created_at")
        return self

    @model_validator(mode="after")
    def _terminal_requires_no_next_step(self) -> RunState:
        if self.status.is_terminal and self.next_step is not None:
            raise ValueError(
                f"una ejecucion en estado terminal ({self.status}) no debe tener next_step"
            )
        return self

    def subtask(self, subtask_id: str):
        """Devuelve la subtarea indicada, o None si el plan aun no existe."""
        if self.plan is None:
            return None
        for s in self.plan.subtasks:
            if s.id == subtask_id:
                return s
        return None
```

Notas verificables:
- `SCHEMA_VERSION = "1.0.0"`.
- `RunState` es el **esquema de estado del propio LangGraph** (`StateGraph(RunState)`),
  no un contrato paralelo.
- `plan: RunPlan | None` existe como campo, pero **nada lo rellena** todavía: ningún
  nodo construye un `RunPlan`. Ver §6.

### 3.3 `Budget` — implementado, preparado para M2

`src/ai_swe/contracts/state.py` (líneas 125–208). Código exacto:

```python
class Budget(BaseModel):
    """Presupuesto de la ejecucion. Agotarlo corta y escala, no continua (RNF-C1).

    **Por que estan los contadores aqui y no en el futuro `ModelGateway`.** El
    presupuesto es parte del estado persistido, no del cliente del modelo. Si el
    limite viviera solo en quien llama, una reanudacion tras un corte arrancaria
    con los contadores a cero y volveria a gastar lo ya gastado. Al vivir en el
    estado, el checkpoint los conserva y el limite sobrevive a un reinicio.

    **Compatibilidad.** Los campos nuevos entran con valor por defecto, de modo
    que un estado serializado antes de existir se deserializa sin error y sin
    necesidad de tocar `ESQUEMA_VERSION`. Solo un cambio que *elimine* o *renombre*
    un campo obligaria a subir la version.
    """

    # --- Tokens ---------------------------------------------------------------
    max_tokens: int = Field(default=200_000, ge=1)
    used_tokens: int = Field(default=0, ge=0)
    # --- Llamadas a herramienta ----------------------------------------------
    max_tool_calls: int = Field(default=60, ge=1)
    used_tool_calls: int = Field(default=0, ge=0)
    # --- Llamadas al modelo (M2) ---------------------------------------------
    # Se separan de las llamadas a herramienta porque el coste y el riesgo son
    # distintos: una herramienta toca el mundo, una llamada al modelo gasta dinero.
    max_model_calls: int = Field(default=120, ge=1)
    used_model_calls: int = Field(default=0, ge=0)
    # --- Tiempo ---------------------------------------------------------------
    max_seconds: float = Field(default=900.0, gt=0)
    elapsed_seconds: float = Field(default=0.0, ge=0)
    # --- Coste ----------------------------------------------------------------
    # En unidades de la moneda del proveedor. Se deja abierto a `None` como "sin
    # limite declarado", que es distinto de cero: cero significa "no se permite
    # gastar nada".
    max_cost: float | None = Field(default=None, ge=0)
    used_cost: float = Field(default=0.0, ge=0)
    # --- Ciclos de revision ---------------------------------------------------
    max_review_cycles: int = Field(default=2, ge=0, le=5)
    review_cycles_used: int = Field(default=0, ge=0)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.used_tokens)

    @property
    def remaining_tool_calls(self) -> int:
        return max(0, self.max_tool_calls - self.used_tool_calls)

    @property
    def remaining_model_calls(self) -> int:
        return max(0, self.max_model_calls - self.used_model_calls)

    @property
    def remaining_cost(self) -> float | None:
        """Coste restante, o `None` si no se declaro limite de coste."""
        if self.max_cost is None:
            return None
        return max(0.0, self.max_cost - self.used_cost)

    @property
    def exhausted(self) -> bool:
        return self.exhausted_reasons() != ()

    def exhausted_reasons(self) -> tuple[str, ...]:
        """Motivos por los que el presupuesto esta agotado. Vacio = queda margen.

        Se devuelve la lista de motivos, no un booleano, porque cuando el sistema
        se detiene hay que poder decir **por que** se detuvo. Un `True` obliga a
        adivinar cual de los seis limites salto.
        """
        motivos: list[str] = []
        if self.remaining_tokens == 0:
            motivos.append("tokens")
        if self.remaining_tool_calls == 0:
            motivos.append("tool_calls")
        if self.remaining_model_calls == 0:
            motivos.append("model_calls")
        if self.elapsed_seconds >= self.max_seconds:
            motivos.append("seconds")
        if self.remaining_cost == 0:
            motivos.append("cost")
        if self.review_cycles_used > self.max_review_cycles:
            motivos.append("review_cycles")
        return tuple(motivos)
```

**Grado de uso real, que conviene separar de su existencia:**

| Campo | ¿Lo usa algo hoy? |
|---|---|
| `max_review_cycles` / `review_cycles_used` | ✅ **sí** — `nodes.reviewer` y `route_after_review` |
| `exhausted` | ✅ **sí** — `nodes.run_tests` lo pasa al Policy Engine |
| `max_model_calls` / `used_model_calls` | ⚠️ **no** — existe, y `models/budget.py` sabe consumirlo, pero **ningún nodo llama al gateway** |
| `used_tokens`, `max_cost`, `used_cost` | ⚠️ **no** — igual: soportados por el gateway, sin uso en el grafo |
| `max_tool_calls` / `used_tool_calls` | ⚠️ **no** — declarados y comprobados por el Policy Engine vía `budget_exhausted`, pero nada incrementa `used_tool_calls` |

### 3.4 `ToolCall` — implementado, pero **no ejercitado de punta a punta**

`src/ai_swe/contracts/tools.py` (líneas 46–52). Código exacto:

```python
class ToolCall(BaseModel):
    """Una llamada propuesta por un agente. Se valida antes de ejecutarse."""

    tool: str = Field(min_length=1)
    args: dict[str, object] = Field(default_factory=dict)
    agent: AgentRole
    subtask_id: str | None = None
```

Su compañero `ToolResult`:

```python
class ToolResult(BaseModel):
    """Resultado de una herramienta, con la decision de politica que lo permitio."""

    tool: str
    ok: bool
    output: str = Field(default="", max_length=200_000)
    error_class: str | None = None
    duration_ms: float = Field(ge=0.0)
    policy_effect: PolicyEffect
    matched_rule: str
```

**Advertencia de estado:** `ToolCall` está definido y validado por pruebas de
contrato, pero **no hay ningún ejecutor de herramientas**. El único nodo que invoca
el Policy Engine es `run_tests`, y lo hace con argumentos construidos a mano
(`{"target": "pytest.unit"}`), no a partir de un `ToolCall`. No existe todavía el
bucle «el agente propone → se valida → se ejecuta».

### 3.5 Resumen de contratos

| Contrato | Fichero | Estado |
|---|---|---|
| `ProjectRequirements` | — | **`NOT_IMPLEMENTED`** (no existe) |
| `TaskInterpretation` + `Scope` | `contracts/tasks.py` | Implementado; lo rellena un clasificador determinista |
| `RunState` | `contracts/state.py` | Implementado y en uso |
| `Budget` | `contracts/state.py` | Implementado; solo la parte de revisión está en uso |
| `ToolCall` / `ToolResult` | `contracts/tools.py` | Implementado; sin ejecutor |
| `RunPlan` / `Subtask` | `contracts/tasks.py` | Implementado; **ningún nodo lo construye** |
| `Instruction` | `contracts/state.py` | Implementado; codifica que el audio crudo no llega al Supervisor |
| `ModelRequest`/`ModelResponse`/`ModelUsage`/`ProviderConfig` | `models/contracts.py` | **Nuevo en F2**; sin uso en el grafo |

---

## 4. Dependencias core

### `pyproject.toml` — dependencias obligatorias (9)

```toml
dependencies = [
    "fastapi>=0.115,<1",
    "uvicorn[standard]>=0.30,<1",
    # Necesaria para `UploadFile` y `Form`: sin ella FastAPI falla al arrancar las
    # rutas que reciben audio. Se descubrio al ejecutar las pruebas de la API.
    "python-multipart>=0.0.9,<1",
    "pydantic>=2.9,<3",
    "pydantic-settings>=2.5,<3",
    # LangGraph: el proyecto se construyo y verifico sobre la rama 1.x (1.2.14).
    # Declarar `>=0.2` era falso: prometia compatibilidad con una rama mayor que
    # nunca se probo y cuya API difiere. Se declara la rama REAL.
    "langgraph>=1.2,<2",
    "langgraph-checkpoint-sqlite>=3.1,<4",
    "httpx>=0.27,<1",
    "sse-starlette>=2.1,<4",
]
```

Extras opcionales: `mcp` (`mcp>=1.0`), `voice` (`faster-whisper>=1.0`),
`observability` (`langfuse>=2.50`), `dev` (`pytest`, `pytest-asyncio`, `ruff`).

**Ninguno de los extras está instalado ni importado.** `mcp` se movió de dependencia
obligatoria a extra en `F1` porque una instalación limpia instalaba un paquete que
ningún módulo usaba.

### `package.json` — **`NOT_IMPLEMENTED`**

```
find . -name "package.json" -not -path "*/node_modules/*"
→ sin resultados
```

El frontend es **un único `index.html` de 404 líneas** con un solo bloque `<script>`
inline. **Sin framework, sin bundler, sin gestor de paquetes, sin paso de
compilación.** No hay dependencias de frontend que declarar. La comunicación con el
backend es `fetch` + `EventSource` (SSE) contra el mismo origen.

### Versiones resueltas (`uv.lock`, 99 paquetes)

| Paquete | Versión |
|---|---|
| Python | 3.13.14 (`.python-version` = 3.13) |
| langgraph | 1.2.14 |
| langgraph-checkpoint-sqlite | 3.1.1 |
| pydantic | 2.13.5 |
| fastapi | 0.141.1 (lock: 0.142.2) |
| httpx | 0.28.1 |
| sse-starlette | 3.5.0 |
| pytest | 9.1.1 |

### Modelo de lenguaje — **`NOT_IMPLEMENTED`**

**No hay ningún SDK de modelo en las dependencias.** El único cliente HTTP es
`httpx`, usado por el adapter `openai_compatible` para hablar con cualquier endpoint
`/chat/completions` compatible con OpenAI.

---

## 5. Motor de políticas y seguridad

### 5.1 Policy Engine — implementado, función pura y determinista

`src/ai_swe/tools/policy.py`. Es una función **pura**: no llama a un modelo, no
accede a la red y no toca el sistema de archivos — por eso se puede probar de forma
exhaustiva (46 pruebas en `tests/test_policy.py`).

Orden de evaluación de `decide()`:

1. ¿La herramienta existe en el catálogo? → **denegar por defecto**
2. ¿El rol tiene permitida la herramienta? → **mínimo privilegio**
3. ¿Los argumentos son válidos? → **confinamiento de rutas, enumeraciones cerradas**
4. ¿Queda presupuesto? → si no, escalar
5. ¿La acción exige aprobación humana? → aprobación
6. Permitir

**Decisión de diseño destacable:** la validación de argumentos ocurre **antes** de la
aprobación. Una ruta que escapa del worktree se **deniega**, no se convierte en una
solicitud de aprobación. El comentario del propio código lo dice: «pedir permiso para
algo prohibido es una forma de normalizarlo».

### 5.2 Confinamiento de rutas (sandbox) — implementado

Dos mecanismos independientes:

**(a) Normalización léxica** — `normalize_rel_path()`:

```python
def normalize_rel_path(raw: str) -> str | None:
    """Normaliza una ruta relativa.

    Devuelve la ruta normalizada, o `None` si escapa del directorio autorizado
    o si es absoluta. Se rechazan rutas absolutas de forma explicita: el agente
    nunca debe poder nombrar una ubicacion fuera del area de trabajo.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = raw.replace("\\", "/").strip()
    if candidate.startswith("/") or _WINDOWS_DRIVE.match(candidate):
        return None

    segments: list[str] = []
    for segment in candidate.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not segments:
                return None  # escapa por arriba del limite
            segments.pop()
        else:
            segments.append(segment)
    return "/".join(segments)
```

Rechaza rutas absolutas (POSIX y con letra de unidad Windows) y colapsa `..`, de modo
que `../../etc/passwd` no puede nombrar nada fuera del área.

**(b) Confinamiento por resolución** — `nodes._dentro_de()`:

```python
def _dentro_de(raiz: Path, candidata: Path) -> bool:
    """Comprueba que una ruta resuelta sigue dentro del area autorizada (`RNF-S2`).

    Se resuelve **antes** de comparar: es lo que hace que un enlace simbolico que
    apunte fuera del repositorio no pueda ampliar el alcance. Se extrae a una
    funcion propia para poder comprobarla directamente, en lugar de confiar en que
    el bucle que la usa la ejercite.
    """
    try:
        return candidata.resolve().is_relative_to(raiz.resolve())
    except (OSError, ValueError):
        return False
```

Se usa en el bucle del nodo `researcher` para descartar cada ruta resuelta que salga
de la raíz autorizada. Cubre el caso que la normalización léxica no puede: un enlace
del sistema de archivos que apunte fuera.

**(c) Pertenencia al alcance declarado** — `path_within_scope()`: `allowed_paths`
vacío significa «todo el repositorio autorizado»; con contenido, la ruta debe ser
igual o estar por debajo de algún prefijo permitido.

**Pruebas de confinamiento** (`tests/test_workflow.py`): incluyen una que usa una
**unción de directorio real** (`mklink /J`) y comprueba la premisa antes de afirmar
nada. El comentario del código explica por qué: en este Windows `Path.symlink_to`
**no lanza error y crea un fichero normal**, así que una prueba basada en enlaces
simbólicos pasaría sin comprobar nada.

### 5.3 Catálogo de herramientas y matriz de permisos — implementado como **dato**

`src/ai_swe/tools/registry.py`. La matriz es dato, no comentarios ni instrucciones en
un prompt. Invariantes que las pruebas afirman:

- `run_shell` **no existe** en el catálogo.
- `git_push` **no existe** en el catálogo.
- El Researcher y el Reviewer **no pueden escribir**.

12 herramientas declaradas. Conjuntos de rol (disjuntos en lo que importa):

| Rol | Herramientas libres |
|---|---|
| Researcher | `list_files`, `read_file`, `search_text`, `git_status`, `git_log`, `git_diff` |
| Coder | las anteriores + `write_file`, `apply_patch`, `run_tests` |
| Reviewer | lectura + `run_tests` |
| Supervisor | **ninguna** (solo propone acciones con efectos, todas con aprobación) |

Las acciones con efectos (`git_commit`, `install_dependency`, `delete_file`) exigen
aprobación humana explícita.

### 5.4 Redacción de secretos (`RNF-S3`) — implementado

`src/ai_swe/security/redaction.py` con 5 capas (valores registrados → patrones de
prefijo → pares `clave=valor` → cabeceras de autorización → URL con credenciales),
más `security/logging.py` con un `RedactingFilter` instalado en el logger raíz al
arrancar la aplicación. 40 pruebas; **8/8 mutaciones cazadas**.

### 5.5 Ejecución de herramientas — **`NOT_IMPLEMENTED`**

**No hay ejecutor de herramientas.** No existe un módulo que reciba un `ToolCall`,
consulte `decide()` y ejecute la acción. Lo que sí existe:

- el Policy Engine que **decidiría** (`policy.decide`);
- el catálogo que **describe** cada herramienta y su riesgo;
- el nodo `run_tests`, que **consulta** al Policy Engine con argumentos fijos y,
  si se autoriza, registra el error tipado `TEST_EXECUTOR_NOT_IMPLEMENTED` en lugar
  de devolver un resultado falso.

La ejecución real de herramientas pertenece a `F7` (Worktree/Sandbox + Tool Executor).

### 5.6 Aislamiento por contenedor — declarado, **`NOT_IMPLEMENTED`**

Existen `Dockerfile` y `docker-compose.yml` con la intención documentada
(`network_mode: none` para `RNF-S6`), pero el comentario del compose lo sitúa en la
**fase M3** y no hay servicio de ejecución desplegado.

---

## 6. Agentes y flujo

### 6.1 Modelo de Hugging Face — **`NOT_IMPLEMENTED`**

**El sistema no usa ningún modelo de Hugging Face, ni real ni mockeado.** Es
importante decirlo sin ambigüedad porque la pregunta partía de esa premisa:

```
grep -rniE "huggingface|transformers|from_pretrained|torch|sentence-transformers" src/ pyproject.toml
→ sin resultados

grep -rn "hf_" src/
→ src/ai_swe/security/redaction.py:73
   re.compile(r"\bhf_[A-Za-z0-9]{30,}"),   # patrón de redacción de tokens de HF
```

La única aparición de `hf_` es una **expresión regular para redactar tokens de
Hugging Face** en logs, no una dependencia ni un modelo.

**Qué hay en su lugar:**

| Elemento | Estado |
|---|---|
| `ModelGateway` (frontera única) | ✅ implementado en F2 |
| `FakeModelAdapter` (determinista, sin red) | ✅ implementado — **pero no conectado al grafo** |
| `OpenAICompatibleAdapter` (httpx) | ✅ implementado — **sin credenciales configuradas** |
| Cualquier llamada real a un modelo | ❌ **`NOT_IMPLEMENTED`** — no se ha ejecutado ninguna |
| Modelo de Hugging Face | ❌ **`NOT_IMPLEMENTED`** — no existe |

La arquitectura es **agnóstica de proveedor por diseño**: ningún agente importa un
SDK; todos dependerían de `ModelGateway`. Se verificó estructuralmente que ningún
fichero fuera de `models/providers/` importa `httpx`, y que ningún módulo importa un
SDK de proveedor.

**Estado de la integración:** `NOT_IMPLEMENTED`. Hay una prueba
(`test_ningun_nodo_llama_al_gateway_todavia`) que **falla si alguien conecta el
gateway a un nodo** — es decir, la desconexión está verificada activamente, no es una
suposición.

### 6.2 Nodos de LangGraph — 12 nodos, todos deterministas y **sin modelo**

`src/ai_swe/graph/nodes.py` (566 líneas). **Ninguno llama a un modelo.**

| Nodo | Qué hace de verdad | Modelo |
|---|---|---|
| `interpret` | Clasifica la instrucción por **vocabulario** y produce `TaskInterpretation` con `confidence=0.5` | ❌ no |
| `researcher` | **Enumera el repositorio real** (`rglob`), lee la primera línea de cada archivo, aplica confinamiento de rutas | ❌ no |
| `answer_direct` | Redacta un informe que dice explícitamente que no hay modelo para responder | ❌ no |
| `explain_limits` | Rechaza una instrucción fuera de alcance explicando el límite (`RF-15`) | ❌ no |
| `coder` | Devuelve un `CodeChange` **vacío** con justificación textual | ❌ no |
| `run_tests` | Consulta el Policy Engine y registra `TEST_EXECUTOR_NOT_IMPLEMENTED` | ❌ no |
| `reviewer` | Veredicto **determinista** sobre `evidence.test_runs` | ❌ no |
| `mark_awaiting` | Marca `awaiting_approval` (nodo separado por una razón concreta) | ❌ no |
| `approval_gate` | `interrupt()` — **aprobación humana real** | ❌ no |
| `escalate` / `escalate_no_changes` | Escala al humano con error tipado | ❌ no |
| `finalize` | Cierra la ejecución respetando un estado terminal ya fijado | ❌ no |

**Topología** (`graph/workflow.py`), con tres invariantes que la forma del grafo
impone por sí misma:

- **Solo el Coder lleva a escritura.** No hay arista desde `researcher` ni desde
  `reviewer` hacia un nodo con efectos: la separación de permisos está en la forma
  del grafo, no solo en un prompt.
- **Toda promoción pasa por la puerta de aprobación.**
- **El ciclo de revisión está acotado** por `max_review_cycles`.

### 6.3 Los cuatro agentes del diseño — estado real

| Agente | Fase prevista | Estado real |
|---|---|---|
| **Requirements Analyst** | `F3` | **`NOT_IMPLEMENTED`** — el directorio `agents/` solo tiene un docstring. Su lugar lo ocupa el clasificador determinista de `interpret` |
| **Supervisor** (con razonamiento / `RunPlan`) | `F4` | **`NOT_IMPLEMENTED`** — no hay nodo que construya un `RunPlan`. `RunState.plan` existe y **nadie lo rellena** |
| **Researcher** | `F5` | 🔶 **Parcial**: enumera el repositorio de verdad (lectura real, confinada), pero **no selecciona evidencia semánticamente**. El propio nodo lo declara en `unknowns` |
| **Coder** | `F6` | **`NOT_IMPLEMENTED`** — devuelve un cambio vacío. Deliberadamente: no se fabrica un parche |
| **Test Runner** | `F8` | **`NOT_IMPLEMENTED`** — registra un error tipado en vez de inventar evidencia |
| **Reviewer** | `F9` | 🔶 **Parcial**: emite veredicto determinista sobre evidencia de pruebas; **no hay revisión semántica** |

**Regla de honestidad que el código respeta de forma explícita:** no se fabrica
evidencia. El nodo de pruebas registra `TEST_EXECUTOR_NOT_IMPLEMENTED` en lugar de
devolver un `TestRun` con éxito falso. Consecuencia declarada: **la puerta de
aprobación es inalcanzable de punta a punta hoy** — sin parche no hay nada que
probar, y sin evidencia el Reviewer no acepta. Se ejercita sustituyendo `coder` y
`run_tests` por lo que hará `M2`, de modo que la topología completa sí queda probada.

### 6.4 Speech-to-Text

| Adaptador | Estado |
|---|---|
| `FakeAdapter` | ✅ implementado — determinista, sin audio |
| `FasterWhisperAdapter` | ❌ **`NOT_IMPLEMENTED`** — `raise NotImplementedError`; su `health()` devuelve `False` |

El extra `voice` (`faster-whisper>=1.0`) **no está instalado**.

### 6.5 Lo que sí funciona hoy, verificado

- El sistema arranca y **acepta una instrucción devolviendo el `run_id` en ~5 ms**
  (antes bloqueaba 166 ms), ejecutando fuera del hilo de la petición.
- Progreso **nodo a nodo** por SSE, consumido por un navegador real.
- Toda ejecución termina en un **estado terminal explícito** (`MET-13 = 0`).
- La **puerta de aprobación humana** funciona de extremo a extremo: aprobar y
  rechazar verificados.
- Pausa y reanudación **entre procesos** sobre el mismo SQLite (5/5 supuestos).

---

## 7. Siguientes pasos

Lo que implementaría **si se autoriza**, sin ambigüedad y en orden:

### Inmediato, antes de tocar el grafo

1. **Ejecutar la prueba real de proveedor.** Es la **única afirmación del proyecto
   sin verificar**: `REAL_PROVIDER_TEST = NOT_EXECUTED_NO_CREDENTIALS`. Cerraría la
   cadena `config → adapter → gateway → proveedor → respuesta → usage → Pydantic`.
   Requiere una credencial en el entorno (no en el chat, no en el código). Es una
   llamada pequeña y barata.
2. **Rellenar la tabla de precios** del modelo que se vaya a usar, para que
   `max_cost` deje de ser un campo inerte (`models/pricing.py` está vacía a
   propósito: no se inventan precios).

### `F3` — Requirements Analyst

Conectar el `ModelGateway` a **un solo nodo**, y solo a uno:

- sustituir el clasificador por vocabulario de `interpret` por una llamada
  `generate_structured(response_model=TaskInterpretation)`;
- conservar la validación Pydantic como puerta: el modelo **propone**, el código
  determinista **valida**;
- aplicar `gateway.consume()` para que `used_model_calls` y `used_tokens` empiecen a
  moverse de verdad;
- mantener el clasificador determinista como *fallback* y como modo sin credenciales,
  de modo que la suite siga pasando sin Internet;
- escribir el primer prompt real (hoy solo existen mensajes mínimos de sonda).

**Por qué un solo nodo:** es el primer punto en que `F2` se ejerce de punta a punta, y
hacerlo con un nodo mantiene el cambio acotado y verificable. `M1` debe seguir verde.

### Después (no en la misma sesión)

`F4` Supervisor con `RunPlan` real → `F5` Researcher semántico → `F6` Coder que
proponga `CodeChange` → `F7` Worktree + Tool Executor → `F8` Test Runner real → `F9`
Reviewer semántico → `F10` MVP de punta a punta.

### Explícitamente **fuera** de las próximas fases

MCP (`F13`), Graphify (`F12`), STT real (`F14`), observabilidad Langfuse (`F15`),
autenticación (`F16`).

---

## Anexo — Hallazgos que el Arquitecto debería conocer

| # | Hallazgo | Severidad | Estado |
|---|---|---|---|
| 1 | `PROJECT_SNAPSHOT.json` declaraba 280 pruebas y `24/24` mutaciones; el valor real es **284** y **35/35** | Documental | **Corregido en esta auditoría** |
| 2 | `data/tasks/` describe una suite de evaluación con verdad conocida, pero contiene **0 ficheros de tarea** (solo el README) | Diseño | Abierto |
| 3 | **Sin autenticación**: cualquier navegador ve todas las ejecuciones | Seguridad | Abierto (hallazgo de la auditoría externa) |
| 4 | El flujo SSE hace `await asyncio.sleep(0.05)` por cliente (`api/app.py:287`): ~2 000 consultas/s con 100 pestañas | Rendimiento | Abierto |
| 5 | `RF-14` (`GET /runs/{id}/trace`) está documentada y **no existe**. Rutas reales declaradas: `/health`, `/transcriptions`, `/runs` (GET/POST), `/runs/{id}`, `/runs/{id}/events`, `/runs/{id}/approve`, `/runs/{id}/cancel` | Documental | Abierto |
| 6 | `POST /runs/{id}/cancel` devuelve **501** (`api/app.py:313`): cancelar no está implementado | Funcional | Declarado |
| 7 | La puerta de aprobación es **inalcanzable de punta a punta** hasta que exista el Coder | Funcional | Declarado y esperado |
| 8 | `RunState.plan` existe como campo y **ningún nodo lo construye** | Funcional | Declarado; es `F4` |
| 9 | `used_tool_calls` nunca se incrementa: nada ejecuta herramientas | Funcional | Declarado; es `F7` |
| 10 | `.gitignore` tenía `models/` **sin anclar**, lo que excluía `src/ai_swe/models/` del control de versiones | **Grave** | **Corregido en `F2`**, con prueba y mutación |

Todos los hallazgos de esta tabla se verificaron contra el árbol actual durante esta
auditoría, salvo el nº 3, que procede de la auditoría externa del 2026-10-06 y se
reproduce aquí sin volver a comprobarlo (no hay autenticación en ninguna ruta:
`api/app.py` no declara ninguna dependencia de identidad).
