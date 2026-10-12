# 13 — Auditoría de sandbox y ejecución de código

> `src/ai_swe/sandbox.py` (327 líneas) + `tools/runner.py` + `tools/patcher.py`.
> Commit `065db452`.

## 1. Mecanismo

| Aspecto | Implementación |
|---|---|
| Aislamiento | **`git worktree`** por ejecución en `var/workspaces/<run_id>` |
| Modo | `--detach` (sin rama con nombre ⇒ no deja ramas en el repo del usuario y no colisiona entre ejecuciones) |
| Validación previa | `validar_repositorio()` exige `.git`; se rechaza crear el worktree **dentro** del repo fuente |
| Reutilización | `crear()` limpia cualquier worktree previo con el mismo `run_id` |
| Limpieza | `destruir()` → `git worktree remove --force` + `git worktree prune` + `rmtree` |
| Cuándo se limpia | En `finalize` (F12). **Antes de F12 nunca se limpiaba** (DEC-16) |
| Identidad git | `-c user.name=… -c user.email=…` (no depende de la config del usuario) |
| Timeout de git | `_TIEMPO_GIT_S = 120 s` |

## 2. Confinamiento de rutas: las barreras

```
ruta pedida
   │
   ├─ 1. normalize_rel_path()      ← rechaza absolutas, unidades Windows, `..` que sale
   ├─ 2. path_within_scope()       ← pertenencia al allowed_paths declarado
   ├─ 3. decide() [Policy Engine]  ← rol, subtarea, protegidas, presupuesto
   └─ 4. resolver_destino()        ← COMPROBACIÓN FÍSICA: la ruta resuelta sigue dentro de la raíz
```

La barrera 4 es la que importa: compara rutas **ya resueltas** contra la raíz, así
que atrapa lo que la validación sintáctica no ve (enlaces simbólicos, junctions,
nombres cortos 8.3 en Windows). Está documentado explícitamente como «la segunda es
física».

## 3. Búsqueda activa de patrones inseguros

| Patrón | Resultado | Evidencia |
|---|---|---|
| `shell=True` | **0 en producción** | `grep -rn "shell=True" src/` solo encuentra docstrings que lo **niegan** |
| `os.system` | **0** | — |
| `eval(` / `exec(` | **0** en producción | — |
| `pickle.loads` | **0** | La persistencia usa `msgpack` con `msgpack_allowlist` |
| `yaml.load` | **0** | — |
| `subprocess` | **3 puntos**, todos con **lista de argumentos** y `shell=False`: `sandbox.git()`, `tools/runner.py`, `evaluation/runner.py` | Verificado |
| Concatenación de comandos | **No existe**: el comando se construye como `tuple` desde una tabla cerrada | `TARGET_COMMANDS` |
| Path traversal | **Mitigado** por las 4 barreras | `test_f7_sandbox.py` |
| Escape por symlink/junction | **Mitigado** por la barrera física | Documentado y probado |

## 4. Verificación de la invariante central

> «El Coder **no** puede escribir arbitrariamente fuera del workspace.»

**Cumple**, con tres evidencias independientes:

1. `patcher.aplicar` valida **cada archivo** antes de escribir (las 4 barreras).
2. `sandbox.escribir` vuelve a confinar en el borde del efecto (defensa en
   profundidad: aunque el llamante fallara, el efecto no ocurre).
3. El trabajo del Coder ocurre en el **worktree**, no en el repositorio del usuario:
   la promoción al repo real es un paso **separado**, posterior y con aprobación
   humana explícita (`promoter.promover`, F12).

## 5. Lo que el sandbox **NO** es

Es importante decirlo con precisión, porque el nombre puede inducir a error:

| Expectativa | Realidad |
|---|---|
| «Es un contenedor» | **No.** Es un `git worktree`: un directorio más en el mismo sistema de archivos |
| «Aísla el proceso» | **No.** El subproceso de pytest corre con el **mismo usuario y el mismo entorno** que el servidor |
| «Limita CPU / memoria / disco» | **No.** Solo hay **timeout** (`_TIEMPO_GIT_S`, timeout del runner) |
| «Bloquea la red» | **No.** `network_egress_enabled` está declarado en `Settings` y **nunca se lee**. Un test del repositorio puede abrir sockets |
| «Impide leer ficheros de fuera del repo» | **No.** Un test ejecutado en el worktree puede leer `C:\Users\...` o `/etc/passwd` |
| «Protege de un fork bomb» | **No.** No hay límite de procesos |
| «Aísla por sistema de ficheros» | **Parcial.** Aísla la *escritura del Coder*; no aísla la *ejecución de código del usuario* |

> **Consecuencia honesta.** El sandbox cumple su objetivo declarado —**el Coder no
> ensucia el repositorio del usuario antes de que un humano apruebe**— y lo cumple
> bien. **No** es una jaula de seguridad para código no confiable. Ejecutar las
> pruebas de un repositorio de usuario es, por definición, ejecutar su código.

## 6. Riesgos

| # | Riesgo | Tipo | Severidad | Evidencia |
|---|---|---|---|---|
| 1 | **Ejecución de código del usuario sin aislamiento de proceso** (RCE por diseño) | VULNERABILITY (aceptada) | **ALTA si se expone**; BAJA hoy (127.0.0.1, sin auth) | `runner.ejecutar_target` lanza `pytest` del repositorio del usuario en el mismo usuario del SO |
| 2 | **Sin límite de CPU/memoria/disco** ⇒ un test del usuario puede agotar la máquina | SECURITY_WEAKNESS (DoS) | MEDIA | No hay `resource.setrlimit` ni `--memory` |
| 3 | **Sin aislamiento de red** ⇒ un test puede exfiltrar datos o descargar payloads | SECURITY_WEAKNESS | MEDIA | `network_egress_enabled` nunca leído |
| 4 | **Sin límite de procesos** ⇒ fork bomb posible desde un test | SECURITY_WEAKNESS | MEDIA | — |
| 5 | El worktree **no se limpia** en las rutas de excepción y de huérfanas | FUNCTIONAL | MEDIA | `abortar` no llama a `finalize` |
| 6 | `rmtree(ignore_errors=True)` en `destruir` puede dejar restos silenciosamente | HARDENING | BAJA | — |
| 7 | El sandbox vive bajo `var/`, dentro del proyecto: un `git clean` del proyecto no lo toca (ignorado), pero un borrado manual sí | INFO | BAJA | — |

## 7. Comparación con las expectativas de la Fase 19.10

| Pregunta | Respuesta |
|---|---|
| ¿RCE? | **Sí, por diseño**: se ejecuta el código de pruebas del usuario. Mitigado por binding local + sin auth expuesta… hasta que el `Dockerfile` abre `0.0.0.0` |
| ¿Escape del sandbox? | **No** para la *escritura del Coder* (4 barreras). **Sí** para la *ejecución*: el proceso no está confinado |
| ¿Agotamiento de recursos? | **No mitigado** |
| ¿Fork bombs? | **No mitigado** |
| ¿Acceso a red? | **No mitigado** |
| ¿Aislamiento de procesos? | **No existe** |
| ¿Límites de CPU/memoria/disco? | **No existen** |

## 8. Conclusión

**IMPLEMENTED_AND_VERIFIED** para su objetivo declarado (contención de la escritura
del Coder y promoción controlada). **NOT_IMPLEMENTED** como mecanismo de aislamiento
de ejecución de código no confiable.

Para un despliegue real, la recomendación no es «endurecer el worktree», sino
**ejecutar las pruebas en un contenedor desechable con límites** (`--network none`,
`--memory`, `--pids-limit`, `--read-only`). El `Dockerfile` actual no sirve para eso:
ejecuta el servidor, no el sandbox.
