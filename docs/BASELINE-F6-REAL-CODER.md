# Acta de cierre — FASE F6 (The Real Coder)

**Fecha:** 2026-10-07
**Estado:** IMPLEMENTADA — pendiente de aprobacion del Arquitecto
**Veredicto:** `F6_REAL_CODER_READY = YES`

---

## 1. Entregable

Convertir `coder` en un agente real conectado al `ModelGateway`, con la separacion
mas importante de la fase:

> **El modelo propone contenido; el codigo deriva los metadatos.**

El modelo genera un `CodeProposal` (que archivos, que operacion, que contenido, por
que). El nodo calcula de forma determinista el diff unificado, el conteo de lineas
anadidas y eliminadas, y los `sha256`. El modelo **nunca** aporta un hash: no puede
conocer el hash de un fichero que aun no ha escrito, y pedirselo solo produciria un
dato inventado.

Alcance respetado: el Coder **propone**, no escribe. Aplicar el parche es F7.

---

## 2. Reglas de la fase

| # | Regla |
|---|-------|
| 1 | El modelo genera `CodeProposal`; **jamas** un `CodeChange` |
| 2 | El sistema deriva diff, conteo de lineas y `sha256`; el modelo no aporta ninguno |
| 3 | `FileOperation` distingue `create` / `modify` / `delete`; el validador rechaza la incoherencia contenido-operacion |
| 4 | Exceder el `Scope` recorta **y lo declara** (`SCOPE_TRIMMED`); nunca en silencio |
| 5 | Fallo del modelo => cambio **vacio** controlado + error recuperable `MODEL_FALLBACK`; nunca un parche inventado |
| 6 | El Coder consume presupuesto (`gateway.consume()`) |
| 7 | El Coder **no escribe en disco**; deja el resultado en `RunState.outputs.coder_output` |
| 8 | Un fallo del modelo **anade** su error a los previos; nunca pisa los de fases anteriores |

---

## 3. Los contratos nuevos (`contracts/outputs.py`)

```python
class FileOperation(StrEnum):
    """Que le hace la propuesta a un archivo. Sin esto, crear y borrar se confunden.

    Un fichero eliminado con `added=0, removed=N` es indistinguible de uno
    modificado que borro N lineas. La operacion es lo que desambigua.
    """
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


class FileProposal(BaseModel):
    """**Lo que el modelo genera (F6).** Una edicion propuesta sobre un archivo.

    Se distingue de `FileChange` a proposito: aqui vive el **contenido** que el
    modelo si sabe producir, y no los metadatos derivados (`added`, `removed`,
    `sha256`) que el modelo **no puede** calcular.
    """
    path: str = Field(min_length=1, max_length=500)
    operation: FileOperation
    new_content: str | None = Field(default=None, max_length=500_000)
    rationale: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def _content_matches_operation(self) -> FileProposal:
        if self.operation is FileOperation.DELETE and self.new_content is not None:
            raise ValueError(f"'{self.path}': una operacion 'delete' no lleva new_content")
        if self.operation is not FileOperation.DELETE and self.new_content is None:
            raise ValueError(f"'{self.path}': la operacion '{self.operation.value}' exige new_content")
        return self


class CodeProposal(BaseModel):
    """**Lo que el modelo genera (F6).** La propuesta de cambio del Coder."""
    files: list[FileProposal] = Field(default_factory=list, max_length=50)
    rationale: str = Field(min_length=1, max_length=4000)
```

El `CodeChange` existente **no se toco**: sigue siendo el contrato derivado
(`files_changed`, `diff`, `rationale`, `diff_sha256`).

---

## 4. Codigo del nodo `coder`

### 4.1 Derivacion determinista

```python
def _contar_lineas(texto: str) -> int:
    """Cuenta lineas de la forma en que `diff` las cuenta."""
    if not texto:
        return 0
    lineas = texto.split("\n")
    if lineas and lineas[-1] == "":
        lineas.pop()
    return len(lineas)


def _cambio_desde_propuesta(propuesta: CodeProposal) -> CodeChange:
    """Convierte la propuesta del modelo en el `CodeChange` derivado.

    Aqui se calcula **toda** la metainformacion de forma determinista: conteo de
    lineas, diff unificado y hashes. El modelo nunca aporta un hash, porque no
    puede conocerlo; si lo aportara, seria un dato inventado.
    """
    cambios: list[FileChange] = []
    trozos_dif: list[str] = []

    for archivo in propuesta.files:
        contenido = archivo.new_content or ""
        nuevo_sha = hashlib.sha256(contenido.encode("utf-8")).hexdigest()
        if archivo.operation is FileOperation.DELETE:
            anadidas, eliminadas = 0, 0
        else:
            anadidas, eliminadas = _contar_lineas(contenido), 0
        cambios.append(FileChange(path=archivo.path, added=anadidas,
                                  removed=eliminadas, sha256=nuevo_sha))
        trozos_dif.append(_diff_unificado(archivo))

    diferencias = "".join(trozos_dif)
    return CodeChange(
        files_changed=cambios,
        diff=diferencias,
        rationale=propuesta.rationale,
        diff_sha256=hashlib.sha256(diferencias.encode("utf-8")).hexdigest(),
    )
```

El diff es **de lineas completas**: sin el contenido viejo (que solo F7 tendra) no
se puede hacer mejor. `create` trata el fichero previo como vacio (`--- /dev/null`),
`delete` como eliminado del todo (`+++ /dev/null`).

### 4.2 Limites del `Scope`

```python
def _respetar_limites(propuesta: CodeProposal, scope: Scope) -> tuple[CodeProposal, str | None]:
    """Recorta la propuesta a los limites del `Scope`. Devuelve (propuesta, motivo).

    **Por que recortar y no rechazar en bloque.** El alcance declara cuanto se
    permite cambiar, no que el trabajo entero se descarte. Recortar deja el cambio
    parcial y **declarado**; rechazar entero convierte un exceso de una linea en
    cero progreso.
    """
    if not propuesta.files:
        return propuesta, None

    motivo: str | None = None
    archivos = list(propuesta.files)

    if len(archivos) > scope.max_files_changed:
        motivo = (f"la propuesta tocaba {len(archivos)} archivos y el alcance permite "
                  f"{scope.max_files_changed}: se conservan los primeros")
        archivos = archivos[: scope.max_files_changed]

    def _lineas(fs: list[FileProposal]) -> int:
        return sum(_contar_lineas(f.new_content or "") for f in fs)

    while archivos and _lineas(archivos) > scope.max_lines_changed:
        quitado = archivos.pop()
        extra = (f"la propuesta superaba {scope.max_lines_changed} lineas y el alcance "
                 f"permite {scope.max_lines_changed}: se descarto '{quitado.path}'"
                 if motivo is None
                 else f"; ademas se descarto '{quitado.path}' por el limite de lineas")
        motivo = (motivo or "") + extra if motivo else extra

    return propuesta.model_copy(update={"files": archivos}), motivo
```

`_alcance` **se corrigio en F6**: ahora prefiere `state.interpretation.scope`, que
es el unico que lleva los limites de tamano; el `Scope` derivado de `RunOptions` no
los tiene. Sin ese cambio, el recorte nunca se disparaba.

### 4.3 Las tres salidas del nodo

```python
def coder(state: RunState) -> dict:
    """Coder real (F6). Propone un parche **estructurado**; no escribe en disco."""
    errores = list(state.errors)
    avisos: list[str] = []
    try:
        resultado = _coder_del_modelo(state)
    except Exception as exc:  # noqa: BLE001 - la frontera convierte cualquier fallo
        if not _es_fallo_esperado(exc):
            raise
        motivo = f"{type(exc).__name__}: {exc}"[:500]
        log.warning("coder: el modelo no respondio, se usa el fallback (%s)", motivo)
        cambio = _cambio_vacio(
            "cambio vacio de respaldo: el modelo no se pudo usar "
            f"({motivo}). No se propone ningun parche inventado."
        )
        return {
            "outputs": _con_salidas(state, coder_output=cambio),
            "errors": _error(state, "MODEL_FALLBACK", AgentRole.CODER.value,
                             f"cambio determinista de respaldo: el modelo no se pudo usar ({motivo})",
                             recuperable=True),
            "plan_index": state.plan_index + 1,
            "next_step": "run_tests",
            "updated_at": _ahora(),
        }

    if resultado is None:
        # Sin gateway: cambio vacio, SIN error -no tener modelo no es un fallo-.
        cambio = _cambio_vacio("cambio vacio de respaldo: no hay modelo conectado. ...")
        return {..., "plan_index": state.plan_index + 1, "next_step": "run_tests", ...}

    cambio, presupuesto, avisos = resultado
    for aviso in avisos:                       # el recorte no puede quedar sin rastro
        errores = _error(state, "SCOPE_TRIMMED", AgentRole.CODER.value, aviso, recuperable=True)
    salida = {
        "outputs": _con_salidas(state, coder_output=cambio),
        "budget": presupuesto,
        "plan_index": state.plan_index + 1,
        "next_step": "run_tests",
        "updated_at": _ahora(),
    }
    if avisos:
        salida["errors"] = errores
    return salida
```

Las tres rutas avanzan `plan_index` (regla F5) y ninguna escribe en disco.

---

## 5. El punto ciego que encontro la mutacion

Primera ejecucion de F6: **13/14**. La mutacion *«el fallo del modelo se traga sin
dejar rastro»* **no fue cazada**.

**Causa.** La mutacion cambiaba `_error(state, ...)` por `list(state.errors) or
_error(state, ...)`. Con un estado **sin errores**, `list([])` es falso y el `or`
cae al `_error(...)` correcto: la mutacion era invisible. Todas las pruebas de
fallback partian de `_estado()`, que no lleva errores.

**Por que importa.** No es un artefacto de laboratorio. En una ejecucion real el
estado puede llegar con errores: si el plan cayo a su fallback en F4, ya hay un
`MODEL_FALLBACK`. Con la lista no vacia, el `or` la daria por buena y **el error del
Coder se perderia** — justo el dato que el sistema existe para no perder.

**Cierre.** No se debilito la mutacion; se anadio la prueba que faltaba:

```python
def test_el_fallo_no_pisa_los_errores_previos() -> None:
    """Un fallo del Coder debe *anadir* su error a los que ya hubiera."""
    previo = RunError(error_class="MODEL_FALLBACK", agent="supervisor",
                      message="el plan uso el fallback determinista",
                      recoverable=True, occurred_at=datetime.now(UTC))
    estado = _estado().model_copy(update={"errors": [previo]})

    nodes.usar_gateway(ModelGateway([FakeModelAdapter(fault="auth_error")], max_retries=0))
    delta = nodes.coder(estado)

    clases = [e.error_class for e in delta["errors"]]
    assert len(clases) == 2
    assert clases[0] == "MODEL_FALLBACK" and delta["errors"][0].agent == "supervisor"
    assert clases[1] == "MODEL_FALLBACK" and delta["errors"][1].agent == "coder"
```

Verificado por mutacion **antes** de darlo por bueno: con la mutacion aplicada la
prueba falla (`['MODEL_FALLBACK']`, 1 error en vez de 2); restaurada, pasa. Segunda
ejecucion: **14/14**.

**Leccion.** Un resultado vacio hace que la comprobacion parezca verde. La prueba
existia, se llamaba «el fallo deja un error» y no comprobaba el caso que importa.

---

## 6. Verificacion

### 6.1 Suite completa

```
suite: pytest | tests: 399 | failures: 0 | errors: 0 | skipped: 1
```

El unico skip es la prueba contra proveedor real (TD-01), que no se ejecuta por
falta de credenciales.

### 6.2 Mutaciones F6: 14/14 cazadas

| Mutacion | Resultado |
|----------|-----------|
| el sha256 del fichero no se deriva del contenido | cazada |
| el diff no se deriva del contenido del fichero | cazada |
| el sha256 del diff se fabrica en lugar de derivarse | cazada |
| el conteo de lineas anadidas es siempre cero | cazada |
| el limite de ficheros del alcance no se respeta | cazada |
| el limite de lineas del alcance no se respeta | cazada |
| el recorte por alcance no se declara | cazada |
| el presupuesto no se consume al proponer el modelo | cazada |
| el fallo del modelo se traga sin dejar rastro | cazada *(tras cerrar el punto ciego)* |
| el fallback devuelve un parche inventado | cazada |
| el coder escribe en disco en lugar de solo proponer | cazada |
| el modelo se ignora y siempre se usa el fallback | cazada |
| una operacion delete sin contenido deja de rechazarse | cazada |
| una operacion create/modify sin contenido deja de rechazarse | cazada |

**14/14.** Acumulado del proyecto: 35/35 (F1-F2) + 8/8 (redaccion) + 8/8 (F3) +
8/8 (F4) + 6/6 (F5) + 14/14 (F6).

### 6.3 Pruebas de F6: 33

Ocho secciones: contrato `CodeProposal`; derivacion determinista (incluida
`test_el_sha256_lo_calcula_el_sistema_no_el_modelo`); limites del `Scope`;
el modelo propone; presupuesto; fallback; **el Coder no toca el disco**; e
integracion F5.

### 6.4 Arbol limpio

```
git status --short
 M src/ai_swe/contracts/__init__.py
 M src/ai_swe/contracts/outputs.py
 M src/ai_swe/graph/nodes.py
 M tests/test_model_gateway.py
 M tools/mutation_check.py
?? tests/test_f6_real_coder.py
```

Sin `_mutation_journal.json` pendiente: la restauracion dejo el arbol limpio.

---

## 7. Ficheros

| Fichero | Cambio |
|---------|--------|
| `src/ai_swe/contracts/outputs.py` | `FileOperation`, `FileProposal`, `CodeProposal` nuevos |
| `src/ai_swe/contracts/__init__.py` | exporta los tres contratos |
| `src/ai_swe/graph/nodes.py` | `coder` real, `_coder_del_modelo`, `_cambio_desde_propuesta`, `_respetar_limites`, `_diff_unificado`, `_contar_lineas`, `_cambio_vacio`, `PROMPT_CODIFICACION`; `_alcance` corregido |
| `tests/test_f6_real_coder.py` | nuevo, 33 pruebas |
| `tests/test_model_gateway.py` | la prueba estructural autoriza `_coder_del_modelo` (F6 conecta `coder`) |
| `tools/mutation_check.py` | 14 mutaciones F6 |
| `frontend/contracts.json` | regenerado (15 contratos) |
| `PROJECT_SNAPSHOT.json` | fase F6, contadores, reglas y caveats |

---

## 8. Deuda tecnica

**TD-01 — Validacion E2E con modelo real.** Sigue ABIERTA. El mecanismo esta listo
y la prueba existe, pero se **salta** en vez de pasar en falso. La cadena completa
no se ha ejecutado contra un proveedor real por falta de credenciales.

**Nueva — el diff es de lineas completas.** Sin el contenido previo, `modify` no
puede producir un diff minimo: hoy trata el fichero como si se anadiera entero. Es
una limitacion **declarada**, no un defecto oculto. Se cerrara en F7, que tendra
ambas versiones.

---

## 9. Veredicto

**F6_REAL_CODER_READY = YES.**

El Coder propone de verdad y el sistema verifica de verdad: el modelo aporta
contenido, el codigo aporta los metadatos que el modelo no puede calcular. El
fallback es un cambio vacio honesto, nunca un parche inventado. El Coder no escribe
en disco. 399 pruebas en verde, 14/14 mutaciones cazadas y un punto ciego
encontrado y cerrado con una prueba real.
