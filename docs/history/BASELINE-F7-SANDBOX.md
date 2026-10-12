# Acta de cierre — FASE F7 (Sandbox y Aplicacion de Parches)

**Fecha:** 2026-10-07
**Estado:** IMPLEMENTADA — pendiente de aprobacion del Arquitecto
**Veredicto:** `F7_SANDBOX_READY = YES`

---

## 1. Entregable

Hacer que el `CodeChange` que el Coder **propone** en F6 llegue fisicamente a un disco,
sin que ese disco sea el del usuario. F7 aporta tres piezas y resuelve una deuda:

1. **Sandbox por ejecucion** — un `git worktree` aislado, con teardown limpio.
2. **Aplicador de parches** — la logica determinista que escribe el cambio dentro del
   sandbox, con confinamiento de ruta **antes de cada escritura**.
3. **Diff unificado real** — la deuda declarada en el commit de F6: el diff ya no es de
   lineas completas, porque ahora hay contenido previo contra el que comparar.

> **La garantia que justifica la fase.** Los archivos se modifican en el sandbox; el
> repositorio original queda **100 % intacto**. No se afirma leyendo el codigo: se
> comprueba creando un repositorio git de verdad, aplicando el parche y verificando el
> contenido del original **y** su `git status`.

---

## 2. Reglas de la fase

| # | Regla |
|---|-------|
| 1 | El sandbox es un `git worktree` **detached** por ejecucion, bajo `workspace_root` (`var/workspaces/<run_id>`), ruta ignorada por git |
| 2 | El repositorio original **nunca** recibe una escritura de F7: el aislamiento es estructural (dos arboles), no por disciplina |
| 3 | La ruta se confina **por cada archivo**, no una vez al principio, y **antes** de cualquier efecto (`mkdir` incluido) |
| 4 | Cuatro barreras por escritura: sintactica + alcance declarado + Policy Engine + comprobacion fisica de raiz |
| 5 | Una ruta denegada es una **negativa de seguridad**, no una averia: se registra en `denegados` y **el resto del cambio se aplica** |
| 6 | El teardown es completo: `worktree remove` **y** `worktree prune`, para no dejar worktrees fantasma en el repo del usuario |
| 7 | `git add -N` antes del diff: sin el, `git diff HEAD` no ve los archivos nuevos y un `create` reporta un diff vacio |
| 8 | El diff es **real** (comparacion viejo/nuevo); sin contenido previo degrada declaradamente a la forma de F6 |
| 9 | El teardown **no propaga errores**: corre en un `finally` y un fallo al limpiar no debe tapar el resultado real |

---

## 3. El sandbox (`src/ai_swe/sandbox.py`)

### 3.1 Creacion: worktree, no clon

```python
def crear(repo: Path, run_id: str, *, workspace_root: Path) -> Sandbox:
    """Crea un worktree aislado para `run_id` a partir de `repo`."""
    repo = Path(repo).resolve()
    if not (repo / ".git").exists():
        raise SandboxError("crear", f"'{repo}' no es un repositorio git")

    raiz = (Path(workspace_root) / run_id).resolve()
    if raiz == repo or repo in raiz.parents:
        raise SandboxError(
            "crear",
            f"el sandbox '{raiz}' quedaria dentro del repositorio '{repo}': no aislaria nada",
        )
    ...
    _git("worktree", "add", "--detach", str(raiz), "HEAD", cwd=repo)
```

Tres decisiones que no son de estilo:

- **`worktree` en lugar de clonar.** Comparte el historial de git sin copiarlo ni
  duplicar el `.git`. Un clon de un repositorio grande por ejecucion es un coste que no
  compra nada: lo que se necesita es un arbol de trabajo, no una historia.
- **`--detach`.** Una rama con nombre permitiria a una ejecucion dejar una rama suelta
  en el repositorio del usuario, y dos ejecuciones simultaneas no pueden tener la misma
  rama "cogida" a la vez. Detached no nombra nada y no colisiona.
- **Se rechaza crear el sandbox dentro del repositorio fuente.** Un worktree que cuelga
  del arbol que pretende aislar no aisla: el `git status` del original lo veria como
  sucio. Es una comprobacion explicita, no una convencion de configuracion.

### 3.2 La cuarta barrera: resolver, no normalizar

```python
def resolver_destino(self, ruta_relativa: str) -> Path:
    normalizada = normalize_rel_path(ruta_relativa)
    if normalizada is None:
        raise EscapeDetectado(ruta_relativa, "es absoluta o escapa del area de trabajo autorizada")
    if not normalizada:
        raise EscapeDetectado(ruta_relativa, "no nombra ningun archivo")

    destino = (self.raiz / normalizada).resolve()
    raiz_resuelta = self.raiz.resolve()
    if destino != raiz_resuelta and raiz_resuelta not in destino.parents:
        raise EscapeDetectado(ruta_relativa, "resuelve fuera de la raiz del sandbox")
    return destino
```

La diferencia entre las dos primeras lineas y las ultimas es **normalizar texto frente a
resolver una ruta**. La barrera sintactica mira la cadena; la fisica construye la ruta y
comprueba adonde lleva de verdad. `raiz.resolve()` se resuelve tambien porque en Windows
la raiz temporal puede pasar por un nombre corto (8.3) y una comparacion de prefijos sin
resolver fallaria por esa razon, no por un escape.

### 3.3 El diff: `git add -N` no es opcional

```python
def diff(self) -> str:
    _git("add", "-N", "--", ".", cwd=self.raiz, check=False)
    result = _git("diff", "HEAD", "--no-color", cwd=self.raiz, check=False)
    return result.stdout or ""
```

`git diff HEAD` **no ve los archivos nuevos**: un `create` recien escrito aparece como un
diff vacio. Se descubrio con una prueba de humo, no leyendo documentacion, y es la peor
clase de fallo — el instrumento no dice "no lo se", dice "no hay nada". `-N`
(intent-to-add) registra la intencion sin preparar el contenido, y el archivo nuevo
entra al diff. No altera lo que se confirma: aqui no hay `git commit`.

### 3.4 Teardown

```python
def destruir(sandbox: Sandbox, *, force: bool = True) -> None:
    if not sandbox.creado_por_nosotros:
        return
    orden = ["worktree", "remove"]
    if force:
        orden.append("--force")
    orden.append(str(sandbox.raiz))
    try:
        _git(*orden, cwd=sandbox.repo_original, check=False)
        if sandbox.raiz.exists():
            shutil.rmtree(sandbox.raiz, ignore_errors=True)
    except SandboxError as exc:
        log.warning("no se pudo destruir el sandbox %s: %s", sandbox.raiz, exc)
```

`worktree remove` deja el arbol si hay cambios sin confirmar; `worktree prune` — que se
ejecuta en `_quitar_worktree` — es lo que finalmente borra la referencia administrativa
en `.git/worktrees/`. Olvidar el prune hace que el repositorio del usuario acumule
worktrees fantasma ejecucion tras ejecucion. Y el teardown **no propaga**: corre en un
`finally`, y un fallo al limpiar no debe tapar el resultado real de la ejecucion.

---

## 4. El aplicador (`src/ai_swe/tools/patcher.py`)

### 4.1 Cuatro barreras por escritura

```python
def _veredicto_de_escritura(sandbox, ruta, *, herramienta, allowed_paths,
                            protected_paths, subtask_allowed_tools) -> tuple[bool, str]:
    # 1. Sintactica: rechaza absolutas, unidades de Windows y `..` que salga arriba.
    normalizada = normalize_rel_path(ruta)
    if normalizada is None:
        return False, f"la ruta '{ruta}' es absoluta o escapa del area autorizada"

    # 2. Alcance declarado.
    if not path_within_scope(normalizada, allowed_paths):
        return False, f"la ruta '{normalizada}' queda fuera del alcance declarado"

    # 3. Politica: rol, subtarea, proteccion, presupuesto. El MISMO motor que decide
    #    para cualquier otra herramienta, no una copia de sus reglas.
    ctx = _contexto(sandbox, allowed_paths=allowed_paths, protected_paths=protected_paths,
                    subtask_allowed_tools=subtask_allowed_tools)
    decision = decide(herramienta, {"path": normalizada}, ctx)
    if decision.effect is not PolicyEffect.ALLOW:
        return False, f"{decision.matched_rule}: {decision.reason}"

    # 4. Fisica: que la ruta resuelta siga dentro de la raiz del sandbox.
    try:
        sandbox.resolver_destino(normalizada)
    except EscapeDetectado as exc:
        return False, exc.motivo

    return True, ""
```

Cuatro barreras para una escritura. Suena redundante y no lo es: cada una atrapa una
clase distinta — sintaxis, alcance declarado, permisos por rol y subtarea, y resolucion
real del sistema de archivos. Un escape que pase las tres primeras sigue sin poder salir
del sandbox.

**El orden importa.** Se confina la ruta, se pide el veredicto a la politica, y solo si
es `ALLOW` se escribe. Una ruta denegada no llega nunca a `mkdir`: no crea ni el
directorio padre.

### 4.2 Una denegacion no aborta el cambio

```python
    for archivo in cambio.files_changed:
        permitido, motivo = _veredicto_de_escritura(...)
        if not permitido:
            resultado.denegados[ruta] = motivo
            log.warning("sandbox: ruta denegada %r: %s", ruta, motivo)
            continue
```

Un intento de salir del area de trabajo **no es una averia, es una negativa**. Se
registra y la ejecucion sigue, porque los demas archivos de la propuesta siguen siendo
legitimamente aplicables. Abortar todo por un archivo malicioso castigaria al resto del
cambio. `ResultadoAplicacion` distingue tres desenlaces —`aplicados`, `denegados`,
`fallos`— y `hubo_escapes` es la senal de ataque.

### 4.3 De donde sale el contenido

`FileChange` solo lleva metadatos (`path`, `added`, `removed`, `sha256`); el contenido
vive en `diff`. `_contenido_de` reconstruye, por archivo, el contenido nuevo leyendo las
lineas `+` de cada trozo. Un archivo `delete` no tiene lineas `+`, su entrada queda a
`None`, y **eso es lo que `aplicar` interpreta como borrado**. El parser
(`_trozos_por_archivo`) es deliberadamente literal: no interpreta hunks ni contextos,
solo separa bloques por `+++ b/<ruta>` y clasifica lineas por su primer caracter. Un diff
que no sigue esa forma no produce contenido, y el resultado lo declara en lugar de
inventar un archivo.

---

## 5. La deuda de F6, resuelta: diff unificado real

En F6 el diff era de **lineas completas** porque el nodo no tenia el contenido previo
—no habia sandbox donde leerlo—. F7 lo tiene, y la generacion cambio a `difflib`:

```python
def _diff_unificado(propuesta: FileProposal, contenido_previo: str | None = None) -> str:
    ...
    return "".join(difflib.unified_diff(
        previas, nuevas, fromfile=f"a/{ruta}", tofile=f"b/{ruta}", lineterm="\n",
    ))
```

Con contexto real y hunks minimos. Cuando el contenido previo no existe (un `create`, o
una ejecucion sin sandbox) el diff **degrada declaradamente** al comportamiento de F6 y
una prueba lo afirma explicitamente, en lugar de fingir que siempre es minimo.

`difflib` no emite nada cuando ambos lados estan vacios —un `delete` sobre un archivo ya
vacio—, asi que `_diff_unificado` **sintetiza la cabecera** `--- a/x` / `+++ /dev/null`
para que un borrado siempre produzca un trozo. Sin esa sintesis, el `delete` desaparecia
del parche; se descubrio porque la prueba
`test_delete_marca_dev_null_como_destino` fallo con un diff `''`.

---

## 6. El punto ciego que encontro la mutacion (importante)

### 6.1 La cuarta barrera: parecia decorativa y no lo era

La mutacion *«F7: la comprobacion fisica de raiz deja de hacerse»* **NO fue cazada** en
la primera pasada. Al retirar la cuarta barrera, la suite seguia en verde: todos los
casos de `../../` ya los atrapaba la barrera sintactica (`normalize_rel_path`), asi que
la cuarta parecia decorativa.

**No lo es, y el punto ciego era mio, no del codigo.** El diagnostico: la cuarta barrera
existe para lo que la sintactica **no puede** ver —una ruta que normaliza a algo valido
pero que el sistema de archivos resolveria fuera—. Ninguna de las rutas de la suite
llegaba a esa situacion.

**Intentos fallidos, y por que.** El vector real es un enlace dentro del arbol que apunte
fuera. Se intento construir de dos formas y ambas fallaron **por la plataforma**:
`os.symlink` para directorios crea en este Windows un enlace que ni `Path.resolve()` ni
`os.path.realpath()` siguen (comprobado a mano). Un enlace que el sistema no resuelve no
prueba nada sobre el codigo que comprueba el resultado de resolver: la barrera 4 no llega
a tener ocasion de actuar.

**El cierre.** Se aisla el **contrato** de la barrera 4 —«si la resolucion cae fuera, ¿se
rechaza?»— inyectando la resolucion para la ruta destino y solo para ella:

```python
    def resolve_que_escapa(self: Path, *args, **kwargs) -> Path:
        if self == destino_esperado:
            return fuera / ruta          # el sistema "resuelve" fuera del sandbox
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_que_escapa)
    with pytest.raises(EscapeDetectado):
        sandbox.resolver_destino("app.py")   # ruta relativa y valida: la barrera 1 la aprueba
```

La ruta pedida (`"app.py"`) es relativa y valida —la barrera 1 la aprueba sin
discusion—, de modo que la unica linea capaz de lanzar es la comprobacion fisica.

**Verificado por mutacion antes de aceptarlo:**

| Estado | Resultado |
|--------|-----------|
| Sin mutacion | la prueba **pasa** |
| Con la barrera 4 retirada (`if False:`) | la misma prueba **falla** (`DID NOT RAISE EscapeDetectado`) |

Y se deja constancia honesta del limite de plataforma en
`test_la_plataforma_no_permite_construir_el_vector_de_enlace`, que **afirma el hecho
observable** en lugar de saltarse fingiendo cobertura.

### 6.2 Otros puntos ciegos de las pruebas (cerrados)

La primera pasada completa dejo **cuatro** mutaciones sin cazar. Una -la de `--detach`- no
era cazable porque atacaba una linea redundante; se trata en §6.3. Las otras tres se
analizan aqui: la primera era un **defecto real de la prueba**, las dos siguientes
resultaron ser tambien **redundancias** del codigo (§6.3). En los tres casos se cerro
verificando **primero que la mutacion mata la prueba** y solo despues dandola por buena:

| Mutacion | Por que no se cazaba | Cierre |
|----------|----------------------|--------|
| `el aplicador no comprueba el alcance declarado` | La barrera 2 devuelve el motivo **desnudo** y la 3 lo devuelve con prefijo `POLICY-PATH-OUTSIDE-SCOPE`. La prueba afirmaba `"alcance" in motivo`, que es cierto con **las dos** | Se afirma el motivo **literal** de la barrera 2, sin prefijo. Ahora retirarla cambia el texto observable y la prueba falla |
| `el teardown deja la entrada de worktree registrada` | La mutacion retiraba solo `prune`, y `worktree remove --force` ya limpia por si solo | Se sustituye por una mutacion **observable**: retirar `remove` y `prune` a la vez |
| `el teardown no elimina el directorio del sandbox` | `worktree remove --force` ya borra el directorio; el `rmtree` es red de seguridad | Se sustituye por una mutacion **observable**: retirar el guard `creado_por_nosotros` |

### 6.3 Un hallazgo incomodo: redundancias reales en el teardown

Al cerrar los puntos ciegos anteriores aparecio la verdad, y se documenta en lugar de
esconderse. **En este git (2.55.0)** se comprobo a mano que:

- `git worktree remove --force <ruta absoluta>` **ya** borra el arbol **y** la entrada
  administrativa de `.git/worktrees/`, tanto si el arbol esta como si su directorio ya
  desaparecio (el caso del fantasma).
- Por tanto, **`prune` y el `rmtree` posterior son redundantes** en `destruir()`: hoy su
  efecto observable es nulo.
- Y `git worktree add <ruta> HEAD` **ya** detacha por si solo, porque `HEAD` es un
  commit-ish; `--detach` es redundante **siempre que se pase `HEAD`**.

**Ni se retiran ni se finge que una prueba los cubre.** Se conservan como defensa en
profundidad -son baratos y cubren versiones de git u otros fallos donde `remove` no
bastara-, y se **corrigieron las tres mutaciones** para que ataquen lo que **si** es
observable:

| Mutacion corregida | Ataca |
|--------------------|-------|
| `sin remove ni prune` | que el teardown deje la entrada registrada |
| `destruye tambien el sandbox que no creamos nosotros` | el guard `creado_por_nosotros` |
| `sin --detach ni HEAD (crea una rama en el repo del usuario)` | que se cree una rama: la forma `worktree add <ruta>` sin commit-ish **si** la crea |

Se anadieron tres pruebas para esos contratos: el fantasma, el sandbox ajeno y la rama
que no debe nacer.

> **Leccion de F7, mas fina que la de F6:** no basta con que la mutacion se aplique. Hay
> que **comprobar que describe un fallo que el codigo puede cometer**. Una mutacion sobre
> una linea redundante no verifica nada -pasa en verde con y sin ella- y contarla como
> "cazada" infla la confianza sin comprar seguridad. La redundancia hay que **demostrarla
> con el sistema de archivos**, no suponerla.

---

## 7. Verificacion

### 7.1 Suite completa

```
tests=435  failures=0  errors=0  skipped=1
```

El skip es `TD-01` (proveedor real sin credenciales), declarado desde F3. La suite paso de
429 a 435 pruebas: +6 de F7 respecto al recuento previo del fichero (30 → 36), que son las
pruebas de aislamiento, confinamiento, diff real y los contratos de teardown/rama.

### 7.2 Mutaciones F7

`python tools/mutation_check.py "F7:"` — 12 mutaciones sobre `sandbox.py`, `patcher.py` y
`nodes.py`. La primera pasada dio **8/12**: cuatro mutaciones **no se cazaban**. Tres
eran puntos ciegos **de las pruebas** (cerrados, ver §6.2); la cuarta no era cazable
porque la mutacion describia un fallo que el codigo no puede cometer (ver §6.3).

**Correccion metodologica previa, imprescindible.** Con `LIMITE_PYTEST=300s` varias
mutaciones tardaban 300.1-300.2s: **cortaban** y el verificador las contaba como
"cazadas" sin que ninguna prueba hubiera fallado. Se corrigieron **las dos cosas**:

- `LIMITE_PYTEST` **300 → 600 s** (la suite mutada es mas lenta que la base).
- Un corte por tiempo devuelve ahora **`None`** -NO CONCLUYENTE-, no `False` -cazada-.
  Un corte por tiempo no es una mutacion cazada: no se ejecuto ninguna prueba que
  fallara. Verificado con una prueba dirigida: al simular el corte, el veredicto es
  `None`, y por tanto **no se confunde con cazada**.

Sin esa correccion, tres veredictos de esta fase habrian sido **falsos positivos**.

**Resultado final: 12/12 cazadas.** Las cuatro que fallaban al principio ahora se cazan
tras cerrar los puntos ciegos y corregir las mutaciones (§6.2 y §6.3):

| # | Mutacion | Antes | Ahora |
|---|----------|-------|-------|
| 1 | el confinamiento deja pasar una ruta que escapa | cazada | cazada (124 s) |
| 2 | la comprobacion fisica de raiz deja de hacerse | NO CAZADA | **cazada** (122 s) |
| 3 | el aplicador escribe sin pasar por el Policy Engine | cazada | cazada (112 s) |
| 4 | el aplicador no comprueba el alcance declarado | NO CAZADA | **cazada** (117 s) |
| 5 | el aplicador escribe en el repositorio original | cazada | cazada (112 s) |
| 6 | el teardown deja la entrada de worktree registrada | NO CAZADA | **cazada** (99 s) |
| 7 | el teardown destruye el sandbox que no creamos | NO CAZADA | **cazada** (113 s) |
| 8 | un archivo nuevo no aparece en el diff (falta `add -N`) | cazada | cazada (114 s) |
| 9 | el diff vuelve a ser de lineas completas | cazada¹ | cazada (113 s) |
| 10 | un borrado puede producir un diff vacio | cazada | cazada (125 s) |
| 11 | el conteo de lineas se toma del contenido entero | cazada | cazada (124 s) |
| 12 | el sandbox se crea sin `--detach` ni `HEAD` | NO CAZADA | **cazada** (131 s) |

¹ En la primera pasada figuraba como cazada **por corte de tiempo** (300.2 s), no por
fallo real. Tras la correccion del instrumento se caza de verdad a 113 s.

### 7.3 Aislamiento: la prueba central

`test_el_repositorio_original_queda_intacto` es la que da sentido a toda la fase: crea un
repositorio real, aplica el parche en el sandbox, y comprueba que en el original el
archivo nuevo **no existe**, el contenido del modificado **no cambio**, y `git status`
sigue **limpio**.

---

## 8. Ficheros

| Fichero | Estado |
|---------|--------|
| `src/ai_swe/sandbox.py` | **nuevo** |
| `src/ai_swe/tools/patcher.py` | **nuevo** |
| `src/ai_swe/graph/nodes.py` | modificado (diff real con `difflib`) |
| `tests/test_f7_sandbox.py` | **nuevo** (36 pruebas, 5 secciones) |
| `tools/mutation_check.py` | modificado (12 mutaciones F7; corte devuelve NO CONCLUYENTE; `LIMITE_PYTEST` 90 → 600 s) |
| `docs/BASELINE-F7-SANDBOX.md` | **nuevo** (esta acta) |
| `PROJECT_SNAPSHOT.json` | modificado (fase, contadores, flags, caveats, reglas) |

---

## 9. Deuda tecnica y limites declarados

- **El sandbox NO esta cableado al grafo.** F7 aporta el mecanismo (crear / aplicar /
  destruir) y sus pruebas; la promocion de cambios al repositorio del usuario **no esta
  implementada** y es el objeto de M3.
- **El vector de enlace no es construible en esta plataforma.** La cobertura de la cuarta
  barrera vive en una prueba que inyecta la resolucion, no en una que planta un enlace
  real. Si el sistema empieza a seguir los enlaces, la prueba
  `test_la_plataforma_no_permite_construir_el_vector_de_enlace` lo dira.
- **`LIMITE_PYTEST` subio a 600 s** (via 300). Motivo: la suite crecio con las pruebas de
  `git worktree` y el limite original (90 s) cortaba la **linea base misma**. Al subirlo a
  300 s se descubrio que varias mutaciones cortaban a 300.1-300.2 s y **se contaban como
  cazadas**; el limite se subio a 600 s **y** el corte dejo de contarse como cazada. Es un
  auto-timeout del instrumento, no un fallo del codigo, y se documento como tal.
- **Tres mutaciones de F7 atacaban lineas redundantes** (`prune`, `rmtree`, `--detach`) y
  se reescribieron para atacar comportamiento observable. La redundancia se **comprobo
  contra el sistema de archivos**, no se supuso. Ver §6.3.
- **`delete_file` esta vedado al Coder por politica** (es privilegio del Supervisor y
  pasa por aprobacion). F7 lo respeta: una propuesta de borrado se **deniega**, y el
  archivo sobrevive. Es correcto, no una carencia.

---

## 10. Veredicto

`F7_SANDBOX_READY = YES`

El Coder propone (F6); el Sandbox aplica (F7) sin tocar el arbol del usuario. La deuda
del diff de lineas completas queda resuelta. Sin commit (no solicitado): pendiente de
aprobacion del Arquitecto.
