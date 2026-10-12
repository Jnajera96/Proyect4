# 03 — Security

> **Capa de índice.** Alias de nomenclatura. El contenido canónico vive en los
> documentos y el código enlazados.

## Documentos

| Documento | Qué contiene |
|---|---|
| [`auditoria-2026-10-06/08_SEGURIDAD_SANDBOX_TOOLS.md`](auditoria-2026-10-06/08_SEGURIDAD_SANDBOX_TOOLS.md) | Flujo de *tool call* y HITL obligatorio |
| [`AUDITORIA-EXTERNA.md`](AUDITORIA-EXTERNA.md) | Auditoría técnica externa completa (50 secciones + 25 preguntas). Origen de las decisiones de seguridad |
| [`04-defensa.md`](04-defensa.md) | Defensa arquitectónica: preguntas probables y respuesta técnica |
| [`BASELINE-PRE-M2.md`](BASELINE-PRE-M2.md) | Acta del *hardening* de seguridad previo a M2 |

## Las capas de seguridad, y dónde vive cada una

| Capa | Mecanismo | Código |
|---|---|---|
| **Catálogo cerrado de herramientas** | `run_shell` y `git_push` **no existen**. Denegar por defecto | [`tools/registry.py`](../src/ai_swe/tools/registry.py) |
| **Mínimo privilegio por rol** | Conjuntos de herramientas **disjuntos**: Researcher y Reviewer no escriben; el Supervisor no ejecuta código | [`tools/registry.py`](../src/ai_swe/tools/registry.py) |
| **Policy Engine** | Decisión pura y determinista, antes de todo efecto | [`tools/policy.py`](../src/ai_swe/tools/policy.py) |
| **Confinamiento de rutas** | Cuatro barreras por escritura | [`sandbox.py`](../src/ai_swe/sandbox.py), [`tools/patcher.py`](../src/ai_swe/tools/patcher.py) |
| **Aislamiento de ejecución** | `git worktree` por ejecución; el repositorio del usuario no se toca | [`sandbox.py`](../src/ai_swe/sandbox.py) |
| **Ejecución de pruebas sin comandos libres** | Enumeración cerrada de *targets*; `subprocess` con listas, `shell=False` | [`tools/runner.py`](../src/ai_swe/tools/runner.py) |
| **Redacción de secretos** | Centralizada: `redact`, `redact_deep`, `sanitize`, filtro de logging | [`security/redaction.py`](../src/ai_swe/security/redaction.py), [`security/logging.py`](../src/ai_swe/security/logging.py) |
| **Secretos en configuración** | `SecretStr`; `.env.example` documenta **nombres**, nunca valores | [`config.py`](../src/ai_swe/config.py) |
| **Aprobación humana** | Puerta `approval_gate` con `interrupt()`; acciones con efectos requieren aprobación | [`graph/nodes.py`](../src/ai_swe/graph/nodes.py) |

## Las cuatro barreras de confinamiento (F7)

Antes de **cada** escritura, no una vez al principio:

1. **Sintáctica** — `normalize_rel_path`: rechaza rutas absolutas, unidades de
   Windows y cualquier `..` que salga por arriba.
2. **Alcance declarado** — `path_within_scope`: la ruta debe caer dentro de lo
   que el usuario autorizó.
3. **Policy Engine** — `decide()`: rol, subtarea, protección y presupuesto.
4. **Física** — la ruta **resuelta** debe seguir dentro de la raíz del sandbox.

Las barreras 2 y 3 son **deliberadamente redundantes** para el alcance (ambas
llaman a `path_within_scope`): el patcher confina antes de consultar la política,
de modo que un cambio en el motor de política no puede abrir un agujero sin que
la barrera del patcher lo note. Está comprobado empíricamente y fijado en una
prueba.

## Deuda de seguridad abierta

- **Sin autenticación en la API** (`AUD-06`). Mitigado solo por exposición
  localhost. Regla del proyecto: **nada más allá de localhost antes de auth**.
- El vector de escape por enlace simbólico **no es construible** en la plataforma
  Windows de desarrollo: `os.symlink` de directorios no lo siguen ni
  `Path.resolve()` ni `os.path.realpath()`. La barrera 4 se cubre con una prueba
  que **inyecta la resolución**, y hay una prueba que afirma el hecho observable
  en lugar de saltarse fingiendo cobertura.
