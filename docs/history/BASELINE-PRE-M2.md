# Baseline pre-M2 — reproducibilidad y hardening de seguridad

**Fecha:** 2026-10-06
**Fase:** `F1` (reproducibilidad + hardening pre-M2) — **cerrada**
**Estado de partida:** `M1` cerrada y etiquetada
**Estado de llegada:** listo para empezar `M2`, sin haber conectado ningún modelo

> **Qué es este documento.** El cierre formal de la fase `F1`. Registra qué se
> cambió, por qué, qué se verificó y con qué evidencia, y termina con un veredicto
> explícito sobre si el proyecto está preparado para empezar el `ModelGateway`.
> No es un plan: es un acta de lo que quedó hecho y comprobado.
>
> **Regla de evidencia aplicada.** Un componente no cuenta como implementado por
> existir como fichero. Cada afirmación de este informe va acompañada del comando
> o la prueba que la sostiene. Cuando algo no se pudo verificar, se dice.

---

## 1. Objetivo de la fase F1

Cerrar `M1` con dos propiedades que hoy no tenía y que `M2` necesita de antemano:

1. **Reproducibilidad.** Que el entorno se pueda reconstruir de forma exacta y
   verificable, y no «parecerse» al que se usó. Sin esto, cualquier resultado de
   `M2` sería irrepetible.
2. **Hardening de seguridad.** Que la infraestructura para **no filtrar secretos**
   exista y esté probada **antes** de que exista el primer secreto real. Ponerla
   después de conectar un modelo es poner la valla después de que se escape el
   caballo.

Se descartó explícitamente empezar `M2`. La fase `F1` no conecta modelos: prepara
el terreno para hacerlo sin arrastrar dos deudas que se vuelven caras más tarde.

---

## 2. Punto de partida y protección del baseline

| Hecho | Valor |
|---|---|
| Repositorio | propio del proyecto, `proyecto4-ai-swe/` |
| Commit de cierre de `M1` | `7446bdf` |
| Etiqueta local | `m1-verified-baseline` (anotada, apunta a `7446bdf`) |
| Remotos | **ninguno** |
| Árbol de trabajo al empezar | limpio |

La etiqueta es **local**. No hay `push`, no hay repositorio remoto. La fase se
desarrolló sabiendo que existe un punto de retorno exacto y verificable
(`git rev-list -n1 m1-verified-baseline` → `7446bdf`).

---

## 3. Entorno real de ejecución (localizado y fijado)

| Elemento | Valor verificado |
|---|---|
| Intérprete del proyecto | venv aislado `~/.workbuddy-ai/binaries/python/envs/default` |
| Versión de Python | **3.13.14** |
| `pydantic` | 2.13.5 |
| `langgraph` | 1.2.14 |
| `langgraph-checkpoint` | 4.2.0 |
| `langgraph-checkpoint-sqlite` | 3.1.1 |
| `fastapi` / `uvicorn` | 0.141.1 / 0.53.0 |
| `sse-starlette` | 3.5.0 |
| `pytest` | 9.1.1 |

**Por qué se documenta el intérprete.** En esta máquina hay varios Python
instalados y ninguno es el del proyecto. Ejecutar las pruebas con el intérprete
equivocado da `ModuleNotFoundError` o, peor, mide un código distinto. El comando
canónico es:

```
PYTHONPATH=src <venv>/Scripts/python.exe -m pytest
```

---

## 4. Versión de Python declarada

`.python-version` contiene `3.13`. Se eligió por coherencia con el entorno
verificado y con `requires-python = ">=3.12"` en `pyproject.toml`. **No se cambió
la versión de Python** durante la fase: cambiar la versión del intérprete habría
invalidado la verificación de `M1` sin necesidad.

---

## 5. Inconsistencia de LangGraph, resuelta

**El problema.** `pyproject.toml` declaraba `langgraph>=0.2`, pero el entorno
verificado tenía `1.2.14`, y la aplicación y las pruebas se habían validado contra
la rama 1.2.x. Una declaración `>=0.2` sin cota superior promete compatibilidad con
una versión mayor distinta de la que realmente se probó.

**Resolución.** Se ajustó la declaración al **hecho verificado**:

```toml
"langgraph>=1.2,<2",
"langgraph-checkpoint-sqlite>=3.1,<4",
```

Criterio: el rango refleja la rama real (`1.2.x`) y cierra la puerta a una futura
`2.x` que rompiera la API. No se fijó `1.2.14` como única versión permitida —el
lockfile ya garantiza la resolución exacta— para no impedir parches menores
compatibles. Se verificó que `langgraph` requiere Python `>=3.10`, compatible con
el intérprete del proyecto.

Todas las dependencias base recibieron cota superior (`fastapi>=0.115,<1`,
`pydantic>=2.9,<3`, etc.) por el mismo motivo.

---

## 6. Lockfile (`uv.lock`)

| Hecho | Valor |
|---|---|
| Herramienta | `uv` 0.12.0 |
| Comando | `uv lock` |
| Paquetes resueltos | **99** |
| Verificación | `uv lock --check` → verde |
| Fuente | resuelto **desde `pyproject.toml`**, no desde el entorno |

**Por qué `uv` y no `pip freeze`.** El entorno de trabajo contiene paquetes
ajenos al proyecto (herramientas del propio agente). Congelarlos con `pip freeze`
habría producido un lockfile que declara como dependencias cosas que el proyecto
nunca pidió: falsa reproducibilidad, que es peor que no tener lockfile, porque
además da confianza.

**Coincidencia con el entorno verificado:** `langgraph 1.2.14`,
`langgraph-checkpoint-sqlite 3.1.1`, `pydantic 2.13.5`. Dos diferencias menores
hacia adelante (`fastapi` 0.142.2 sobre 0.141.1, `uvicorn` 0.54.0 sobre 0.53.0):
ambas son parches/minores, ninguna es una regresión. **No se degradó ninguna
dependencia.**

No se usaron indicadores de «actualizar todo». La resolución se ciñe al rango
declarado.

---

## 7. `mcp` permanece opcional

`mcp` estaba declarada como dependencia **base**: una instalación limpia instalaba
un paquete que nadie importaba. Se movió al extra `[mcp]`. En esta fase **no se
instaló, no se implementó y no se activó** ningún servidor MCP.

Instalar `mcp` sigue siendo una decisión posterior y explícita
(`pip install -e ".[mcp]"`).

---

## 8. Redacción centralizada de secretos (`RNF-S3`)

**Componente nuevo:** `src/ai_swe/security/redaction.py`, con envoltorio de paquete
en `src/ai_swe/security/__init__.py`.

El requisito era que ningún secreto conocido pudiera aparecer en: logs, errores,
excepciones serializadas, eventos, trazas, mensajes de observabilidad, salida de
depuración y representaciones de configuración. La solución es un **único sitio**
que decide qué es un secreto y cómo se sustituye, en lugar de una función por
módulo: basta que un módulo se olvide para que la garantía deje de serlo.

**Cinco capas, aplicadas en este orden:**

| # | Capa | Qué cubre |
|---|---|---|
| 1 | Valores registrados (`register_secret`) | claves cortas o con formato impredecible que ninguna heurística reconocería |
| 2 | Patrones de prefijo | `sk-`, `ghp_`, `AKIA`, `AIza`, `hf_`, Stripe, Slack |
| 3 | Pares `clave=valor` | `model_api_key=...`, `api_key: "..."`, JSON/YAML serializado |
| 4 | Cabeceras de autorización | `Authorization: Bearer <token>`, conservando el esquema |
| 5 | URL con credenciales | `https://usuario:clave@host` |

La representación del secreto es siempre `[REDACTED]`.

**Lo que NO hace, deliberadamente.** No intenta adivinar si una cadena cualquiera
«parece» un secreto. Una heurística agresiva destruye información legítima —un
identificador hexadecimal de 32 caracteres es indistinguible de un token para una
expresión regular— y un sistema de trazabilidad que redacta de más es tan inútil
como uno que redacta de menos. Se prefirió una garantía estrecha y verdadera a una
amplia y falsa.

Propiedades verificadas: **idempotencia** (aplicar la redacción dos veces no
degrada el texto), **no falsos positivos** sobre prosa normal (`password del
usuario`, `el token expiró`, `run_id=...` sobreviven), y **nunca lanza** (si algo
falla internamente, devuelve texto redactado en lugar de romper el log).

---

## 9. Integración con `logging`

**Componente nuevo:** `src/ai_swe/security/logging.py` — un `RedactingFilter`.

Se instala una vez en el logger raíz desde el arranque de la aplicación
(`api/app.py`, en el `lifespan`, **antes** de cualquier otra operación). Redacta el
mensaje ya formateado, los argumentos sueltos, el texto de excepción y `stack_info`.
Esto cubre el caso que más se olvida: `log.info("clave=%s", api_key)`, donde el
secreto está en el argumento y no en la plantilla.

Se verificó explícitamente que redacta **dentro de un traceback**, porque una
excepción arrastra el valor de las variables locales hasta el log.

---

## 10. Configuración: `SecretStr`

`model_api_key`, `langfuse_secret_key` y `langfuse_public_key` pasaron de `str` a
**`pydantic.SecretStr`**. Un `str` corriente acaba en un `repr`, en un
`model_dump()` o en un mensaje de error sin que nadie lo escriba a propósito;
`SecretStr` reduce el riesgo a un acto explícito (`.get_secret_value()`).

Verificado:

| Comprobación | Resultado |
|---|---|
| `repr(settings)` contiene la clave real | **No** |
| `str(settings.model_dump())` contiene la clave real | **No** |
| lectura explícita `.get_secret_value()` funciona | Sí |

`load_settings()` registra automáticamente los secretos en el redactor central
(`Settings.registrar_secretos()`), de modo que aunque un secreto llegue a un log
por un camino no previsto, se redacta.

---

## 11. Validación de configuración sin exigir clave para arrancar

**Componente nuevo:** `require_model_credentials(settings)` y la excepción tipada
`ConfiguracionInsuficiente` en `api/../config.py`.

Regla de diseño: **`M1` debe arrancar sin ningún proveedor.** El grafo se recorre,
la API responde y el frontend funciona sin credenciales. La exigencia de clave se
evalúa cuando se va a **usar el modelo**, no al arrancar.

- Proveedor local (`ollama`, `vllm`…): no exige clave.
- Proveedor con clave sin clave configurada: lanza `ConfiguracionInsuficiente` con
  el **nombre** del campo (`model_api_key`), nunca su valor.

Verificado: el mensaje de error no contiene el valor de la clave que sí estaba
configurada, solo el nombre del campo que falta.

---

## 12. `Budget` preparado para llamadas al modelo

Se extendió `Budget` (`src/ai_swe/contracts/state.py`) con los contadores que `M2`
necesitará, sin implementar todavía ninguna llamada.

| Campo | Valor por defecto | Estado |
|---|---|---|
| `max_tokens` / `used_tokens` | 200 000 / 0 | ya existía |
| `max_tool_calls` / `used_tool_calls` | 60 / 0 | ya existía |
| **`max_model_calls` / `used_model_calls`** | **120 / 0** | **nuevo** |
| `max_seconds` / `elapsed_seconds` | 900 / 0 | ya existía |
| **`max_cost` / `used_cost`** | **`None` / 0.0** | **nuevo** |
| `max_review_cycles` / `review_cycles_used` | 2 / 0 | ya existía |

**Decisiones de diseño.**

- `max_cost = None` significa «sin límite declarado», que es **distinto de cero**:
  cero significa «no se permite gastar nada». Se distingue porque confundirlos
  convertiría un presupuesto abierto en uno bloqueado.
- Los contadores viven en el **estado persistido**, no en el futuro cliente del
  modelo. Si el límite viviera solo en quien llama, una reanudación tras un corte
  arrancaría con los contadores a cero y volvería a gastar lo ya gastado.
- `exhausted_reasons()` devuelve la **lista de motivos**, no un booleano. Cuando el
  sistema se detiene hay que poder decir **por qué** se detuvo; un `True` obliga a
  adivinar cuál de los seis límites saltó.
- Todos los contadores llevan `ge=0`: un contador negativo es un dato imposible y
  falla al construirlo, no al usarlo.

**Compatibilidad de esquema.** Los campos nuevos entran **con valor por defecto**,
de modo que un estado serializado antes de existir se deserializa sin error. Por
eso **no se tocó `ESQUEMA_VERSION`** (sigue en 2). Solo un cambio que eliminara o
renombrara un campo obligatorio lo exigiría. No hubo migración destructiva.
`Budget` se verificó serializable (`model_dump` → `model_validate` = identidad).

---

## 13. Lo que NO se hizo (y es deliberado)

- **No se implementó el `ModelGateway`.**
- **No se conectó ningún modelo.** Ninguna llamada externa, ningún SDK de
  proveedor, ninguna clave real.
- **No se escribieron prompts.**
- **No se modificó ningún nodo para llamar a un modelo.** El `coder` sigue
  devolviendo un cambio vacío y `run_tests` sigue registrando
  `TEST_EXECUTOR_NOT_IMPLEMENTED`.
- **No se implementó MCP.**
- **No se implementó Graphify ni `repo_map`.**
- **No se implementó STT real** (`faster-whisper` sigue como adaptador de entrada
  sustituible, sin instalar).
- **No se subió nada a ningún remoto.** Sin `push`.

Estos puntos no son omisiones: son el límite de la fase `F1`, respetado.

---

## 14. Reproducibilidad comprobada en un entorno aislado

Se construyó un entorno **fuera del workspace** (`_tmp/f1_repro_env`), desde el
lockfile, y se ejecutó la suite completa allí:

| Entorno | Pruebas | Fallos |
|---|---|---|
| Original (venv del proyecto) | 211 | 0 |
| **Nuevo, construido desde `uv.lock`** | **211** | **0** |

Las versiones resueltas en el entorno nuevo coinciden: `langgraph 1.2.14`,
`langgraph-checkpoint-sqlite 3.1.1`, `pydantic 2.13.5`. El entorno temporal se
eliminó al terminar; **no se reemplazó ni borró ningún entorno existente.**

**Nota de honestidad sobre un falso negativo.** En una primera pasada, el entorno
nuevo mostró **1 fallo** (`test_el_confinamiento_de_rutas_rechaza_lo_que_esta_fuera`)
que no aparecía en el original. Al investigarlo se determinó que era un artefacto
de **concurrencia**: el verificador de mutaciones corría en paralelo y ambos
procesos compartían el directorio base temporal de pytest
(`AppData\Local\Temp\pytest-of-*`), destruyéndose entre sí —una trampa ya conocida
de este entorno—. Repetida la comprobación **en serie, sin concurrencia**, ambos
entornos dan 211/211. No era un defecto del código. Se documenta porque el primer
resultado era alarmante y el motivo real importa.

---

## 15. Verificación de la redacción por mutación

Que una prueba pase no significa que proteja el código. Para comprobarlo se
escribió `tools/verify_redaction_mutations.py`, que introduce fallos a propósito en
el redactor, ejecuta la suite, restaura el fichero e informa si alguna prueba cayó.
Aborta si la línea base no está verde.

**Resultado: 8/8 mutaciones cazadas.**

**El hallazgo más valioso de la fase.** La mutación «desactivar la capa de
cabeceras de autorización» **no caía** en la primera ejecución: la suite entera
pasaba con el fallo dentro. La causa era que la capa genérica `clave=valor` también
atrapaba `Authorization: <token>`, y **enmascaraba** el fallo de la capa
específica. Cuatro pruebas que «comprobaban» la redacción de cabeceras pasaban sin
comprobar nada.

El arreglo fue en el **código**, no en la prueba: se introdujo
`_CABECERAS_DELEGADAS`, de modo que el barrido genérico se aparta de esas
cabeceras y quedan cubiertas por su capa dedicada. Ahora la mutación cae. Lección
incorporada: **una prueba que pasa no prueba nada hasta que una mutación la hace
caer.**

---

## 16. Verificaciones de la línea base M1 (re-ejecutadas)

Ninguna de las validaciones de `M1` se degradó:

| Verificación | Resultado |
|---|---|
| Suite de pruebas completa | **211 / 211** (153 originales + 58 nuevas) |
| Supuestos de `M1` (`verify_m1_assumptions.py`) | **5 / 5** |
| Auto-mutación del verificador de supuestos | **3 / 3** cazadas |
| Frontend en motor real (`verify_frontend.py`) | **11 / 11** |
| Mutaciones del proyecto (`mutation_check.py`) | **24 / 24** cazadas |
| Mutaciones de la redacción (nuevo) | **8 / 8** cazadas |
| Contrato exportado (`frontend/contracts.json`) | al día tras regenerar |

**Desglose de las 58 pruebas nuevas:** 40 de redacción (`tests/test_redaction.py`)
+ 18 de configuración y presupuesto (`tests/test_config_budget.py`).

Tras extender `Budget` fue necesario **regenerar el contrato exportado**
(`tools/export_contracts.py`); la prueba que comprueba su vigencia lo detectó, que
es exactamente su función.

---

## 17. Estado de las fases

| Fase | Estado |
|---|---|
| `M0` — diseño | ✅ cerrada |
| `M1` — esqueleto ejecutable | ✅ cerrada, etiquetada `m1-verified-baseline` |
| **`F1` — reproducibilidad + hardening pre-M2** | ✅ **cerrada (este documento)** |
| Pre-M2 — seguridad (redacción, config, presupuesto) | ✅ cerrada |
| **`M2` — agentes reales** | ⬜ **no iniciada** |
| `M3`–`M7` | ⬜ no iniciadas |

---

## 18. Veredicto

### `READY_FOR_MODEL_GATEWAY = YES`

**Con qué respaldo.** Las condiciones que `F1` debía dejar cumplidas se cumplen y
están verificadas:

- El proyecto sigue funcionando: 211/211 pruebas, frontend 11/11 en navegador real.
- La reproducibilidad es real, no declarada: un entorno reconstruido desde el
  lockfile, **fuera del workspace**, reproduce 211/211 con las mismas versiones.
- La versión de Python está fijada (`3.13`, verificado 3.13.14).
- `langgraph` refleja la rama realmente probada (`>=1.2,<2`).
- `mcp` sigue siendo opcional y no instalado.
- No hay ninguna clave real en el repositorio.
- Existe redacción centralizada (`security/redaction.py`), integrada con `logging`,
  y **tiene pruebas que la protegen de verdad** (8/8 mutaciones cazadas).
- `Budget` ya tiene los contadores que `M2` necesitará, sin ninguna llamada hecha.
- No se ha conectado ningún modelo, no se han escrito prompts, no existe
  `ModelGateway`.

**Con qué reserva, para no vender una seguridad que no existe.** `READY_FOR_MODEL_GATEWAY = YES`
significa «el terreno está preparado», **no** «el sistema está seguro». Al empezar
`M2` habrá que tratar como trabajo propio de esa fase, como mínimo:

1. **La redacción debe usarse, no solo existir.** Está disponible y probada, pero
   su garantía depende de que los puntos que registran prompts y respuestas la
   invoquen. En `M2` conviene que el registro de trazas pase por `sanitize()` de
   forma estructural, no por disciplina de cada llamante.
2. **La validación de configuración debe llamarse en el borde.** `require_model_credentials`
   está lista; `M2` debe invocarla justo antes de la primera llamada real, de modo
   que el fallo llegue pronto y con contexto en lugar de subir opaco desde dentro
   del cliente del modelo.
3. **El límite de coste no tiene una fuente de precio todavía.** `max_cost` existe
   como campo, pero sin una tabla de precios por modelo no hay quien lo alimente;
   decidir si `M2` lo usa o lo deja declarado sin efecto es una decisión de `M2`.
4. **Sin autenticación.** Sigue sin haberla (hallazgo de la auditoría externa). No
   es un requisito de `F1` ni bloquea `M2` en local, pero sigue abierto y afecta a
   cualquier despliegue.

**Siguiente paso:** empezar `M2` (agentes reales: conexión del modelo,
interpretación real, parches sobre worktree aislado). **No se inicia en esta
sesión.**
