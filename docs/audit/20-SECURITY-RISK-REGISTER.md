# 20 — Registro de riesgos de seguridad

> Severidad calibrada: **no se exagera**. La mayoría de estos riesgos son
> aceptables hoy porque el sistema está pensado para ejecutarse **en local, por su
> propio autor**. Lo que cambia la severidad es **desplegarlo**.
> Commit `065db452`. Clasificación: `VULNERABILITY` · `SECURITY_WEAKNESS` ·
> `HARDENING_RECOMMENDATION` · `THEORETICAL_RISK`.

## Tabla de hallazgos

| ID | TITLE | ASSET | ATTACK VECTOR | LIKELIHOOD | IMPACT | SEVERITY | EVIDENCE | CURRENT CONTROL | RECOMMENDED CONTROL | PRIORITY |
|---|---|---|---|---|---|---|---|---|---|---|
| **SEC-01** | API expuesta sin autenticación en el contenedor | A6, A7 | Red | **Alta si se despliega** | **Crítico** | **CRITICAL** | `Dockerfile:38` → `--host 0.0.0.0`; no hay auth en ninguna ruta | Binding `127.0.0.1` **solo** en `__main__.py`; el Dockerfile lo anula | Autenticación + TLS, o `--host 127.0.0.1` | **P0** |
| **SEC-02** | Ejecución de código del usuario sin aislamiento de proceso | A6 | Repositorio registrado con `tests/` malicioso | Media (hoy local) | **Crítico** | **HIGH** | `tools/runner.py` lanza `pytest` del repo en el mismo usuario del SO | Worktree (no aísla el proceso) + timeout | Contenedor desechable con `--network none`, `--memory`, `--pids-limit` | **P0** |
| **SEC-03** | `ApproveRequest.decision` con default `APPROVED` | A7 | Petición vacía `{}` al endpoint de aprobación | **Media** | **Alto** (promueve al repo real) | **HIGH** | `contracts/api.py::ApproveRequest.decision: ApprovalDecision = ApprovalDecision.APPROVED` | Ninguno | Hacer `decision` **obligatorio** (sin default) | **P1** |
| **SEC-04** | Lista blanca de repositorios declarada y **no aplicada** | A1, A7 | Registrar cualquier ruta con `.git` | Media | Alto | **HIGH** | `Settings.authorized_repos` — `grep` en `src/` solo encuentra la declaración | Ninguno (`validar_repositorio` solo exige `.git`) | Aplicarla en `POST /projects` | **P1** |
| **SEC-05** | Sin límite de tamaño ni validación de tipo en la subida de audio | A6 | `POST /transcriptions` con fichero enorme | Media | Medio (DoS) | **MEDIUM** | `await audio.read()` sin tope; no se comprueba MIME ni extensión | Ninguno | Límite de tamaño + validación de tipo | **P1** |
| **SEC-06** | Prompt injection indirecta desde el repositorio | A5, A7 | Fichero del repo con instrucciones para el LLM | Media | Medio | **MEDIUM** | Researcher lee ficheros; Coder recibe el diff | Confinamiento de escritura + aprobación humana | Delimitar el contenido no confiable en los prompts y no mezclarlo con instrucciones | **P1** |
| **SEC-07** | Sin aislamiento de red en la ejecución de pruebas | A1, A6 | Test que exfiltra o descarga | Media | Medio | **MEDIUM** | `AI_SWE_NETWORK_EGRESS_ENABLED` nunca se lee | Ninguno | Aislar la red del proceso de pruebas | **P2** |
| **SEC-08** | Sin límites de CPU / memoria / procesos | A6 | Fork bomb o bucle infinito en `tests/` | Media | Medio | **MEDIUM** | Solo `timeout` | Timeout | `setrlimit` / límites del contenedor | **P2** |
| **SEC-09** | Conexiones SSE y paginación sin tope | A6 | Muchas conexiones o `limit=10^9` | Baja-Media | Medio | **MEDIUM** | `limit: int = 50` con `max(1, limit)`; sin límite de conexiones | Ninguno | Tope superior + límite de conexiones | **P2** |
| **SEC-10** | Sin cabeceras de seguridad HTTP ni `TrustedHost` | A1 | XSS/clickjacking en el navegador | Baja | Bajo-Medio | **LOW** | No hay middleware de cabeceras | Frontend sin `innerHTML` ni dependencias de UI | CSP, `X-Frame-Options`, `TrustedHostMiddleware` | **P2** |
| **SEC-11** | El worktree no se limpia en las rutas de excepción | A8 | Ejecución que falla o muere | Media | Bajo | **LOW** | `abortar` no llama a `finalize`; `destruir` no se invoca | `crear()` limpia al recrear con el mismo `run_id` | Limpiar en `abortar` y en la recuperación de huérfanas | **P3** |
| **SEC-12** | Credenciales por defecto en `docker-compose` (perfil observability) | A10 | Despliegue descuidado de Langfuse | Baja | Medio | **LOW** | `NEXTAUTH_SECRET: cambiar-en-despliegue-real`, `POSTGRES_PASSWORD: langfuse` | Perfil `observability` (no arranca por defecto) | Variables obligatorias sin valor por defecto | **P3** |
| **SEC-13** | Sin observabilidad ni alertas | A9 | Incidente sin traza | Media | Bajo | **LOW** | `observability/` es un placeholder; `langfuse_*` no se lee | Logs JSON con redacción | Implementar M6 | **P3** |
| **SEC-14** | `RunState.schema_version` sin migraciones | A3 | Cambio de esquema en caliente | Baja | Bajo | **LOW** | El campo se escribe y no se lee | — | Sistema de migraciones | **P4** |
| **SEC-15** | Sin retención ni purga de datos | A3, A4, A5 | Acumulación indefinida | Alta | Bajo | **LOW** | Nada se borra | — | Política de retención | **P3** |

## Severidad por contexto

| Escenario | Riesgos críticos |
|---|---|
| **Uso local, un solo usuario, loopback** (el previsto) | Ninguno **CRITICAL**. SEC-03 y SEC-04 siguen siendo reales |
| **Expuesto en una LAN** | **SEC-01 CRITICAL**, SEC-02 HIGH |
| **Desplegado en producción** | SEC-01, SEC-02, SEC-05..SEC-09 |

> **Nota de honestidad.** Si este proyecto se entrega y se ejecuta en local tal y
> como está, **no tiene una vulnerabilidad crítica explotable por un tercero**: no
> hay red, no hay usuarios y no hay secretos versionados. El riesgo crítico aparece
> en cuanto alguien despliega el `Dockerfile` tal cual.

## Lo que NO es un riesgo (evitar falsos positivos)

| Elemento | Por qué no |
|---|---|
| `shell=True` | **No existe** en producción |
| `eval` / `exec` / `pickle.loads` | **No existen** |
| Path traversal en el sandbox | Mitigado por 4 barreras, con tests |
| Secretos en el repositorio | Escaneo negativo |
| Secretos en logs o SSE | Redactor central + mutaciones que lo protegen |
| XSS en el frontend | Sin `innerHTML`, sin `dangerouslySetInnerHTML`, sin deps de UI |
| SQL injection | Todo el acceso usa sentencias parametrizadas (`?`) |
| El audio llegando al LLM | Imposible por contrato |
| Promoción sin aprobación | La única arista pasa por la puerta humana |

## TOP 10 (Fase 40)

> Sólo se listan riesgos **reales**. No se rellena hasta diez.

**#1**
- **Risk**: API sin autenticación arrancada en `0.0.0.0` por el `Dockerfile`.
- **Severity**: **CRITICAL** (en despliegue).
- **Evidence**: `Dockerfile:38` `CMD [... "--host", "0.0.0.0" ...]`; ninguna ruta valida identidad.
- **Impact**: cualquiera que alcance el puerto puede lanzar ejecuciones que escriben y **promueven** código en un repositorio.
- **Exploitability**: Trivial (un `curl`).
- **Required action**: autenticación **antes** de exponer; o `--host 127.0.0.1`.

**#2**
- **Risk**: ejecución de código del usuario sin aislamiento de proceso.
- **Severity**: **HIGH**.
- **Evidence**: `tools/runner.py` lanza `pytest` del repositorio registrado con el usuario del servidor.
- **Impact**: RCE con los privilegios del servidor; sin límites de CPU/memoria/red/procesos.
- **Exploitability**: Media (requiere registrar un repositorio malicioso).
- **Required action**: contenedor desechable con límites y `--network none`.

**#3**
- **Risk**: `ApproveRequest.decision` tiene default `APPROVED`.
- **Severity**: **HIGH**.
- **Evidence**: `contracts/api.py` — `decision: ApprovalDecision = ApprovalDecision.APPROVED`.
- **Impact**: una petición vacía **aprueba y promueve** al repositorio del usuario.
- **Exploitability**: Media (bug de cliente, petición vacía, reintento mal formado).
- **Required action**: campo obligatorio.

**#4**
- **Risk**: `authorized_repos` declarado y no aplicado.
- **Severity**: **HIGH**.
- **Evidence**: `grep authorized_repos src/` → solo la declaración en `config.py`.
- **Impact**: el operador cree tener una allowlist que no existe.
- **Exploitability**: Trivial.
- **Required action**: aplicarla en `POST /projects` — o eliminarla del contrato.

**#5**
- **Risk**: subida de audio sin límite de tamaño ni validación de tipo.
- **Severity**: **MEDIUM**.
- **Evidence**: `POST /transcriptions` → `await audio.read()` sin tope.
- **Impact**: DoS por memoria.
- **Exploitability**: Trivial.
- **Required action**: límite de tamaño + validación de tipo.

**#6**
- **Risk**: prompt injection indirecta desde el contenido del repositorio.
- **Severity**: **MEDIUM**.
- **Evidence**: el Researcher lee ficheros del repo; el Coder los recibe en el prompt.
- **Impact**: el modelo propone cambios guiados por el atacante (acotados por el confinamiento).
- **Exploitability**: Media.
- **Required action**: marcar el contenido no confiable y separarlo de las instrucciones.

**#7**
- **Risk**: sin aislamiento de red en la ejecución de pruebas.
- **Severity**: **MEDIUM**.
- **Evidence**: `AI_SWE_NETWORK_EGRESS_ENABLED` declarado, nunca leído.
- **Impact**: exfiltración o descarga de payloads desde un test.
- **Exploitability**: Media.
- **Required action**: aislar la red del proceso de pruebas.

**#8**
- **Risk**: sin límites de CPU/memoria/procesos en el sandbox.
- **Severity**: **MEDIUM**.
- **Evidence**: solo `timeout`.
- **Impact**: agotamiento de la máquina.
- **Exploitability**: Media.
- **Required action**: `setrlimit` o límites de contenedor.

**#9**
- **Risk**: conexiones SSE y paginación sin tope.
- **Severity**: **MEDIUM**.
- **Evidence**: `limit: int = 50` con `max(1, limit)`; sin límite de conexiones concurrentes.
- **Impact**: DoS.
- **Exploitability**: Media.
- **Required action**: tope superior y límite de conexiones.

**#10**
- **Risk**: el worktree no se limpia en las rutas de excepción.
- **Severity**: **LOW**.
- **Evidence**: `abortar` escribe el estado pero no llama a `finalize`.
- **Impact**: worktrees y entradas en `.git/worktrees/` acumulados en el repo del usuario.
- **Exploitability**: N/A (higiene).
- **Required action**: limpiar en `abortar` y en la recuperación de huérfanas.
