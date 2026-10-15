# Fase C — candidato local de entrega

Fecha: 14 de octubre de 2026, America/Mexico_City (evidencias UTC del 15).
Estado: **RELEASE CANDIDATE LOCAL**, con las limitaciones enumeradas abajo.
No es una certificación de producción ni de proveedores/STT reales.

## Baseline y alcance

Se ejecutaron primero `git rev-parse --show-toplevel`, `git branch --show-current`,
`git rev-parse HEAD`, `git status --short`, `git log --oneline -15`,
`git diff --check`, `git tag` y `git remote -v`.

- Raíz: `C:/Users/jose_/Desktop/repo_proyect/proyecto4-ai-swe`.
- Branch: `main`; HEAD inicial `1dbd5b62b46f6ad3bf12dc9e880b657ac3fc82bf`.
- Árbol inicial limpio; diff check sin errores; sin remotos configurados.
- Tag preexistente: `m1-verified-baseline`.
- Preservación `f095729`, Fase A `245a4a8`, Fase B `1dbd5b6` comprobadas en historial.
- Correcciones verificadas: `94256f3a2c01febb9b1a34689e3b2ee59b6cb61a`.
- Sin push, rebase, configuración remota, limpieza destructiva o nuevas funciones.
  No se creó un tag de release: el identificador del candidato es el commit local.

## Entorno encontrado

Se reutilizó `.venv`, creada con uv y el lock del proyecto en la fase anterior.
Python 3.13.14, pytest 9.1.1, FastAPI 0.142.2, LangGraph 1.2.14,
langgraph-checkpoint-sqlite 3.1.1, Pydantic 2.13.5 y Ruff 0.16.10.
El inventario se consultó con `importlib.metadata`: este entorno uv no incluye
pip. El launcher `py -0p` no enumeró intérpretes, pero el ejecutable de `.venv`
funciona. No se instaló pytest global ni se actualizaron dependencias.

## Defectos reproducidos y correcciones acotadas

### C-01 — bytecode invalida el diff revisado

Primera suite: 679 aprobadas, 7 fallidas y 3 omitidas. Los fallos de promoción
incluían `PROMOTION_DENIED`. Diagnóstico con repositorio descartable: pytest había
creado `tests/__pycache__/*.pyc`; `Sandbox.diff()` los añadía al diff después de
haber guardado el diff de código, por lo que la comprobación estricta de integridad
denegaba correctamente la promoción.

Corrección: el entorno del proceso de pruebas fija `PYTHONDONTWRITEBYTECODE=1`.
No se ignoran archivos arbitrarios ni se relaja la comparación de integridad.
Una regresión ejecuta pytest real en un repositorio sin reglas de ignore y exige
que no aparezca bytecode ni cambie el diff. Esto no impide escrituras deliberadas
de código de pruebas: el runner sigue sin ser un aislamiento de procesos.

### C-02 — transporte de parches altera saltos de línea en Windows

El navegador reprodujo `PROMOTION_FAILED`: `git apply --check` rechazaba un parche
válido contra un archivo LF. Las regresiones confirmaron además que `text=True`
normalizaba contenido CRLF literal devuelto por Git.

Corrección: pipes binarios para Git, con conversión UTF-8/surrogateescape en el
límite público. Se evita la traducción automática de saltos de línea de stdin y
stdout. Se mantienen autorización, alcance, diff esperado, comprobación previa y
verificación byte a byte posterior; no se cambió la configuración global de Git.
Regresiones con core.autocrlf true/false y contenido CRLF sin normalización Git.
El producto sigue denegando/revirtiendo una promoción que no reproduzca el
worktree; no se promete conversión universal de formatos o filtros Git.

### C-03 — Solicitar cambios enviaba un enum de otro contrato

Navegador real: el botón enviaba `request_changes`; `/approve` respondía 422 porque
la decisión humana debe ser `approved`, `rejected` o `modified`. `request_changes`
pertenece al veredicto del Reviewer, no a la aprobación humana.

Corrección: el botón envía `modified`; callback y cliente HTTP usan el tipo
`ApprovalDecision` ya existente. El mismo escenario pasó de HTTP 422 a HTTP 200,
persistió comentario y ciclo, volvió a la puerta y luego promovió al aprobar.
No se modificó el contrato del backend.

## Evidencia nueva y resultados

| Verificación | Resultado |
| --- | --- |
| Suite Python completa inicial | 679 PASS, 7 FAIL, 3 SKIP |
| Cuatro regresiones nuevas antes de corregir | 4 FAIL |
| Suite Python completa final, 693 casos | **690 PASS, 0 FAIL, 3 SKIP**, 243.22 s |
| Componentes frontend | **24/24 PASS** |
| TypeScript y build Vite del frontend final | **PASS** |
| Navegador final local + autenticado | **114 comprobaciones PASS** |
| Promoción funcional en navegador con checkpoint real | **29 comprobaciones PASS**, tres escenarios |
| Ruff en Python afectado y herramientas nuevas | **PASS** |
| git diff --check | **PASS** |

Las tres omisiones son explícitas:

1. STT real: exige opt-in y descarga de modelo; no ejecutado.
2. Proveedor real: exige opt-in/credenciales/modelo; no ejecutado.
3. Construcción de un vector con enlace simbólico: Windows rechazó crearlo con
   WinError 1314. Esa prueba no se considera aprobada; permanece sin verificar
   en esta máquina, aunque las demás pruebas de confinamiento sí se ejecutaron.

La validación de navegador conserva seis tamaños (1920×1080, 1440×900, 1366×768,
1024×768, 834×1112 y 390×844), ambos temas, autenticación, scope, gates, SSE,
errores de arranque, voz fake, 401/403, foco y controles nativos de teclado.
No equivale a una auditoría completa de accesibilidad.

## Promoción E2E auténtica

`tools/phase_c_server.py` es una factory exclusiva de verificación. Inyecta una
propuesta determinista mediante FakeModelAdapter; usa la aplicación, grafo,
trabajador, SQLite/checkpointer, runner y promoter reales. No siembra runs ni
finge el resultado de promoción. Solo se permite pytest.unit, el target de los
repositorios mínimos creados para el ensayo.

`tools/verify_phase_c_promotion.cjs` crea tres repositorios Git descartables. Cada
uno comienza con `return 1` y una prueba que exige `return 42`; comprueba que la
prueba falla antes del cambio. El runner real la ejecuta después del parche.
Los clics de requisitos y aprobación/rechazo/cambios ocurren en navegador.

- Aprobar: `completed`, bytes idénticos al worktree revisado, únicamente el archivo
  previsto modificado, índice vacío, HEAD conservado y worktree eliminado.
- Rechazar: `cancelled`, hash original y árbol limpio conservados, sin commit ni
  worktree restante.
- Solicitar cambios y aprobar: HTTP 200, decisión `modified` y ciclo persistidos,
  repositorio intacto mientras espera; aprobación posterior promueve exactamente
  el contenido revisado y termina `completed`.

Las comprobaciones negativas de rutas protegidas, alcance, repositorio distinto
y alteración posterior al review forman parte de la suite Python completa.

## Reproducción y ubicación de evidencia

Desde la raíz, con el entorno local y navegador ya instalados:

```powershell
.venv\Scripts\python.exe -m pytest --junitxml=_tmp/phase-c-final-pytest.xml
npm.cmd --prefix frontend run build
node --test frontend/tests/estados.test.mjs
node tools/verify_delivery.cjs _tmp/phase-c-rc-browser
node tools/verify_phase_c_promotion.cjs
.venv\Scripts\python.exe -m ruff check tests/test_phase_c_release.py tools/phase_c_server.py src/ai_swe/sandbox.py src/ai_swe/tools/runner.py
git diff --check
```

Evidencia local generada, ignorada por Git:

- `_tmp/phase-c-pytest.xml`: ejecución inicial fallida.
- `_tmp/phase-c-regressions-red.xml`: regresiones antes de las correcciones.
- `_tmp/phase-c-final-pytest.xml`: suite final completa.
- `_tmp/phase-c-promotion/1792038558636/report.json`: respuesta 422 reproducida.
- `_tmp/phase-c-promotion/1792038690976/report.json`: 29 checks y tres resultados.
- `_tmp/phase-c-rc-browser/1792038642991/report.json`: 114 checks y capturas finales.

Estos archivos/capturas no viajan en el commit; scripts, regresiones y este acta
permiten reproducirlos. No se ejecutaron mutaciones en esta fase; las seis de
Fase B son evidencia histórica y no se cuentan como una nueva ejecución de C.

## Límites y veredicto

**Candidato aceptable para revisión y entrega del prototipo local en el alcance
offline verificado.** Las tres omisiones anteriores acompañan el candidato.
Micrófono/Whisper real, proveedores externos, Docker y despliegue no se probaron.
La comparación experimental de modelos reales tampoco se certifica con adapters
deterministas. No se ejecutó una auditoría completa con lector de pantalla.

No hay preparación para producción ni ampliación a multiusuario. Continúan TD-02,
TLS, secretos operativos, auditoría persistente, aislamiento de procesos/red,
retención y cancelación funcional (501). Jupyter/Hugging Face Model Lab, MCP,
Graphify/Knowledge Graph, Langfuse y TTS siguen fuera de esta fase.
