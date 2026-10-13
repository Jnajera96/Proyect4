# BASELINE — Fase 2: contratos y configuración efectiva

Acta de cierre de la **Fase 2** del plan de estabilización
(`docs/BASELINE-PRE-STABILIZATION.md` §5). Objetivo: **eliminar configuraciones
falsas y contratos engañosos** — que un ajuste documentado haga lo que promete, o
que deje de existir.

Este documento se escribe **después** de verificar, no antes. Todo lo que afirma
está respaldado por una prueba que corre en la suite offline.

---

## 1. Qué cambió de comportamiento

### 2.1 — La decisión humana es obligatoria

`ApproveRequest.decision` y `ConfirmRequirementsRequest.decision` tenían
`default=APPROVED`. Un `POST /runs/{id}/approve` con cuerpo `{}` **aprobaba y
promovía el parche al repositorio del usuario**.

Ahora `decision` es un campo requerido. Un cuerpo vacío es **422**, y el 422
ocurre **antes** del manejador (la ejecución sigue esperando en la puerta, no se
reclama ninguna reanudación). Se comprueba en las dos puertas, porque las dos
toman una decisión humana.

### 2.2 — Los cinco ajustes declarados y no aplicados

| Ajuste | Antes | Ahora |
|---|---|---|
| `AI_SWE_AUTHORIZED_REPOS` | Se documentaba como límite; **ningún código lo leía** | Se aplica: alta de proyecto y arranque de ejecución devuelven **403** fuera de alcance |
| `AI_SWE_MAX_TOKENS_PER_RUN` | No se leía | Construye `RunState.budget.max_tokens` |
| `AI_SWE_MAX_TOOL_CALLS_PER_RUN` | No se leía | Construye `budget.max_tool_calls` |
| `AI_SWE_MAX_SECONDS_PER_RUN` | No se leía | Construye `budget.max_seconds` |
| `AI_SWE_NETWORK_EGRESS_ENABLED` | Se describía como bloqueo | **Se declara NO aplicado**: hoy la ejecución hereda el entorno del padre. Se conectará al aislamiento real de proceso en su fase |

Se añadieron además `AI_SWE_MAX_MODEL_CALLS_PER_RUN` y `AI_SWE_MAX_COST_PER_RUN`,
que el contrato `Budget` ya soportaba y la configuración no exponía.

**La distinción de `authorized_repos` es explícita y deliberada:** lista vacía =
modo local mono-usuario (sin restricción adicional, la autorización es registrar
el proyecto a mano); lista poblada = solo se aceptan rutas **dentro** de esas. La
comparación es sobre rutas **resueltas**, no sobre el texto recibido: sin
resolver, `repo/../otro` o un enlace simbólico esquivarían la lista.

### 2.3 — Una sola fuente de configuración

`crear_app` leía la ruta del almacén con `os.environ.get("AI_SWE_STATE_DB_PATH")`,
al margen de `Settings`. Ahora la configuración se carga **una vez** al construir
la aplicación y la ruta sale de `Settings.state_db_path`: `AI_SWE_STATE_DB_PATH`
funciona igual desde el entorno **o** desde `.env`, y no hay dos copias que puedan
discrepar.

`src/ai_swe/__main__.py` también dejó de leer `AI_SWE_PORT` a mano: la validación
la hace `Settings` y el arranque solo traduce el fallo a `SystemExit`. El puerto
por defecto se **deriva** del contrato (`Settings.model_fields["port"].default`) en
lugar de repetir el literal.

### 2.4 — Documentación de configuración

`.env.example` incorpora lo que faltaba y solo lo que el código **lee**: el puerto,
el modelo del Reviewer, `max_model_calls`, `max_cost` y las tres variables de las
pruebas opt-in. Se retiró la mención a numeración de fase antigua.

**Ajustes sin consumidor.** El encabezado de la plantilla promete documentar solo
ajustes que el código lee, y su propio contenido lo contradecía: `AI_SWE_TTS_ENABLED`
y `AI_SWE_LANGFUSE_ENABLED`/`HOST` no los lee **ningún** código. Se marcan
explícitamente como **NO IMPLEMENTADO** en la plantilla y en `Settings`, en lugar de
retirarlos, porque `docs/01-arquitectura.md` declara el TTS como propuesta (`[PROP]`)
y Langfuse llega en la fase de observabilidad: retirarlos borraría un enganche de
diseño documentado, y marcarlos resuelve la contradicción sin destruir información.
Las **claves** de Langfuse sí se conservan: las registra el redactor central. También
se corrigió la descripción de `tts_active`, que prometía una comprobación («si el STT
está configurado») que su cuerpo no hacía.

### 2.5 — Campos que prometían algo inexistente

| Campo | Situación | Decisión |
|---|---|---|
| `RunOptions.dry_run` | Declaraba "ejecuta el flujo sin tocar el repositorio"; ningún código lo leía, y es redundante (el repositorio no se toca hasta la aprobación) | **RETIRADO** |
| `TestRun.reproducible` | Prometía que "el Reviewer re-ejecuta para confirmar"; el Reviewer no re-ejecuta. El valor solo lo ponían las pruebas: la insignia del frontend estaba **permanentemente apagada** | **RETIRADO** (y su insignia en el frontend) |
| `RunState.schema_version` | Se escribía en cada estado y **no lo leía nadie** | **IMPLANTADO**: un validador rechaza un estado de otra versión; la **ausencia** del sello sigue siendo válida (regla de compatibilidad) |
| `Subtask.status` / `Subtask.attempts` | Nadie los actualiza | **CONSERVADOS** a propósito: la Fase 7 (cierre de capacidades) los rellena y el frontend los necesita. Quedan declarados como **pendientes**, no como implementados |

### 2.6 — El presupuesto sale de la configuración

`Settings.presupuesto()` es la **única** traducción de configuración a contrato, y
`RunEngine` la usa al crear la ejecución. Antes, `Budget` se construía con sus
propios valores por defecto: los seis `AI_SWE_MAX_*_PER_RUN` existían, se
documentaban y no hacían nada.

---

## 2. Hallazgos de la fase

Los tres son defectos **reales**, encontrados al verificar — no al leer.

### H1 — El arnés de mutaciones convertía a CRLF los ficheros que solo debía leer

`Path.read_text()` traduce los finales de línea a `\n` y `Path.write_text()` los
traduce de vuelta al terminador del sistema. En un fichero CRLF el viaje de ida y
vuelta es neutro; en uno **LF convierte el fichero entero a CRLF**.

Como `.gitattributes` declara `* text=auto eol=lf`, Git normaliza al comparar y
**no lo muestra**: el árbol parecía limpio mientras el arnés modificaba bytes de
ficheros que solo debía inspeccionar. Se detectó al preparar la primera mutación
sobre `config.py` (LF). Ya había ocurrido antes: los ficheros CRLF del proyecto
son, en buena parte, los que el arnés muta con más frecuencia.

**Corregido**: `_leer_contenido` / `_escribir_contenido` preservan el terminador
original, y el diario de recuperación lo guarda. Verificado empíricamente: ida y
vuelta **byte-exacta** en LF y en CRLF, con y sin mutación.

### H2 — Faltaba la prueba extremo a extremo que el plan pide

El plan exige "config → Run → Budget efectivo". Lo que existía comprobaba
`Settings.presupuesto()` **en aislamiento**: no demostraba que el motor lo usara.
Si `RunEngine` recibiera los ajustes y aun así creara la ejecución con el `Budget`
por defecto, la traducción sería correcta y el resultado el de siempre.

**Añadidas** dos pruebas que cubren las dos ramas de `RunEngine._presupuesto()`:
con configuración y sin ella (esta última ata la equivalencia entre los valores
por defecto del contrato y los de `Settings`).

### H3 — El 403 de la lista blanca no tenía prueba a nivel de API

`repositorio_autorizado` se probaba aislada, pero **el cableado en la API no**.
Si alguien hubiera borrado la comprobación de `crear_proyecto` o la de
`crear_run`, ninguna prueba habría fallado: el control se creería aplicado.

**Añadidas** dos pruebas de API: un repositorio fuera de la lista devuelve 403 en
las **dos** rutas, y un repositorio dentro se acepta (control positivo: una lista
que rechaza todo no protege nada, solo rompe el sistema).

---

## 3. Verificación

| | |
|---|---|
| Comando | `python -m pytest tests/ -q` |
| **Recogidos** | **618** |
| **Fallos** | **0** |
| **Errores** | **0** |
| **Saltos** | **2** (opt-in por diseño: proveedor real y STT real) |
| Entorno | local, offline, sin credenciales, sin red |
| **Mutaciones F2** | **6/6 cazadas**, línea base verde, `árbol restaurado y suite en verde` |
| `tsc --noEmit` (frontend) | limpio |
| `vite build` | `dist/index.html` + 9,37 kB CSS + 164,25 kB JS |

**Desglose del recuento**, para que el número sea auditable:

```
601  (F14, verificado)
+13  (pruebas que trae la propia Fase 2: 2 en test_f10_api, 4 en test_contracts, 7 en test_config_budget)
+ 2  (extremo a extremo config → Run → Budget, añadidas en esta fase)
+ 2  (403 de la lista blanca en la API, añadidas en esta fase)
= 618
```

Mutaciones F2 (cada una ataca una regresión que la fase previene):

1. el presupuesto configurado no llega a la ejecución;
2. la lista blanca de repositorios no se aplica (función);
3. aprobar sin decisión humana vuelve a promover;
4. el sello de esquema no se comprueba;
5. el alta de proyecto no comprueba la lista blanca (API);
6. lanzar una ejecución no comprueba la lista blanca (API).

Las mutaciones 5 y 6 existen **por H3**: sin ellas, el cableado en la API habría
quedado verificado solo por la función, que no es lo mismo.

---

## 4. Riesgos

- **Eliminados en esta fase:** ninguno de la lista `SEC-*`. La Fase 2 no es una
  fase de seguridad, sino de coherencia.
- **Reducidos:** `SEC-04` (aprobación por defecto) queda **cerrado**: el default
  afirmativo ya no existe y hay prueba de las dos puertas. La lista blanca de
  repositorios (`SEC-*` de alcance) pasa de **declarada** a **aplicada y probada**.
- **Abiertos:** el resto de la lista de `docs/BASELINE-PRE-STABILIZATION.md` §4.
  `AI_SWE_NETWORK_EGRESS_ENABLED` **sigue sin aplicarse** y ahora se declara así
  de forma explícita, en el código y en `.env.example`; se conectará al
  aislamiento real de proceso en su fase.

---

## 5. Limitaciones

- **`Subtask.status` / `attempts` siguen sin actualizarse.** Es deliberado: se
  implementan en la Fase 7. La prueba lo deja escrito para que no se lea como
  deuda olvidada.
- **El aislamiento de red sigue sin existir.** `network_egress_enabled` es
  configuración futura, no un control presente.
- **`graph/nodes.py` no se ha tocado** (monolito pendiente de la Fase 14).
- **La verificación en navegador no se ejecutó** en esta fase: el contrato cambió
  y el frontend sigue enviando `decision` de forma explícita en las dos puertas
  (comprobado por inspección), pero la comprobación de navegador corresponde a la
  fase de frontend.

---

## 6. Siguiente fase

**Fase 3 — Hardening local P0/P1/P2.** Objetivo: endurecer el producto local
antes de añadir frontend nuevo — binding de red, límites de subida de audio,
paginación acotada, límites de SSE, cabeceras de seguridad, **inyección de prompt
indirecta** (tratar el contenido del repositorio como datos no confiables), limpieza
de worktrees en las rutas de error y rate limiting preparado para una exposición
futura. Requiere autorización explícita.

---

## 7. Git

| | |
|---|---|
| Rama | `main` |
| Commit anterior | `5aa4cf7 chore: clean repository and consolidate documentation` |
| Commit de esta fase | `fix: enforce configuration and contract invariants` |
| Árbol de trabajo | limpio tras el commit |
| Remoto | ninguno · sin push |
