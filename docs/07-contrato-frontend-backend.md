# Contrato entre frontend y backend

> **Estado (2026-10-06): VIGENTE.** El contrato descrito aquí está implementado y
> verificado en un motor de render real (11/11 comprobaciones). Los 15 contratos
> exportados a `frontend/contracts.json` siguen siendo correctos.

> **Propuesta de diseño adicional [PROP].** Este documento existe porque la interfaz
> principal del sistema es un navegador, y con un navegador de por medio la
> coordinación entre las dos partes deja de ser un detalle de implementación y pasa
> a ser una decisión de arquitectura.

---

## 1. El problema que este documento resuelve

La primera versión de M1 ejecutaba la tarea **dentro de la petición HTTP**. Eso
tenía una consecuencia que no era evidente hasta poner un navegador delante:

```
POST /runs ─────────────────────────────────► 202/201 con la ejecución YA TERMINADA
            (bloquea 166 ms, y con un modelo serían 40 s)
```

El cliente recibía el `run_id` **cuando la ejecución ya había acabado**. Por tanto:

- No podía suscribirse al progreso de una ejecución que aún no conocía.
- El flujo SSE solo podía **reproducir** eventos ya ocurridos, nunca emitirlos en vivo.
- Una ejecución de 40 segundos dejaría la interfaz congelada 40 segundos, sin señal
  alguna, y con un `fetch` que un proxy podría cortar por inactividad.

**Con un navegador como interfaz principal, esto no es una limitación: es un fallo de
diseño.** Se midió y se corrigió antes de escribir el frontend.

### 1.1 La corrección, en una línea

```
POST /runs ──► 202 + run_id ──► (el cliente se suscribe) ──► el trabajador ejecuta
   (5 ms)                        GET /runs/{id}/events
```

`POST /runs` pasó de 166 ms bloqueando a **5 ms devolviendo el identificador**. La
ejecución se movió a un trabajador, y el progreso pasó a ser un flujo de eventos.

---

## 2. Los cinco puntos de coordinación

Cada uno resuelve una forma concreta de que las dos partes se desincronicen.

### 2.1 Un solo origen de verdad para los tipos

**Problema:** el frontend no comparte el sistema de tipos del backend. Sin un
artefacto común, los dos lados divergen y los fallos aparecen en el navegador, en
tiempo de ejecución, como un `undefined` en algún sitio.

**Solución:** los contratos son modelos Pydantic, y `tools/export_contracts.py` los
exporta a `frontend/contracts.json` como JSON Schema. Una prueba comprueba que el
fichero **está al día**, de modo que no puede quedarse obsoleto en silencio.

```json
{
  "schemas": {
    "RunStatus": { "enum": ["planned", "running", "awaiting_approval", "completed",
                            "failed", "needs_human", "cancelled"] },
    "EventKind": { "enum": ["run.created", "run.started", "run.step", "run.status",
                            "run.awaiting_approval", "run.report", "run.error", "run.done"] }
  },
  "endpoints": { "POST /runs": { "cuerpo": "RunRequest", "respuesta": "RunState", "codigo": 202 } }
}
```

**Lo que esto compra:** las enumeraciones son un **conjunto cerrado**. El frontend
puede hacer un `switch` exhaustivo sobre los tipos de evento, y un tipo nuevo no se
cuela sin que alguien lo note. Además, el frontend no tiene que adivinar la forma de
la respuesta.

**Lo que todavía NO compra, y conviene decirlo:** el frontend **no valida** las
respuestas contra el esquema en tiempo de ejecución. Consume las enumeraciones y lee
los campos que necesita. Una validación real en el cliente sería el siguiente paso,
y hoy no existe.

### 2.2 El ciclo de vida, y quién cambia cada estado

**Problema:** con dos procesos (API y trabajador) tocando el mismo estado, «quién
escribió qué» deja de ser obvio.

**Regla:** un estado, un dueño.

| Estado | Quién lo escribe | Significado para el navegador |
|---|---|---|
| `planned` | La API, al crear | Aceptada, aún no empezó. **El cliente ya tiene el `run_id`.** |
| `running` | El Supervisor, en el primer nodo | Hay progreso que mostrar |
| `awaiting_approval` | El nodo `mark_awaiting` | **Hay que mostrar la puerta de aprobación** |
| `completed` | El nodo `finalize` | Hay informe final |
| `needs_human` | Cualquier escalada | Hay errores que mostrar y nada más que esperar |
| `failed` / `cancelled` | Red de seguridad / cancelación | Terminal sin informe |

**Regla de oro para el frontend:** `awaiting_approval` **no es terminal**. Es una
espera legítima y la interfaz debe seguir conectada. Confundirla con un final deja al
usuario mirando una pantalla que ya no se actualiza mientras el sistema espera su
decisión.

**Segunda regla de oro, y esta se aprendió de un fallo real:** la señal de fin de una
ejecución es **el evento `run.done`**, no un estado consultado. La primera versión del
flujo cerraba cuando el índice decía «terminal», y el índice se sincroniza **antes** de
escribir los eventos. Resultado: el flujo se cerraba y el cliente **perdía
`run.status`, `run.report` y `run.done`** sin ningún error visible. Cerrar por evento
elimina la carrera de raíz, porque el evento *es* la señal.

### 2.3 Los eventos: el canal por el que el navegador se entera

**Problema:** el progreso tiene que llegar al navegador sin que este pregunte en
bucle, y sin perderse si la conexión se corta.

**Solución:** Server-Sent Events sobre un registro **persistente**. Tres campos por
evento:

```
id: 7
event: run.step
data: {"seq":7,"at":"2026-10-06T17:20:31Z","kind":"run.step","data":{"node":"researcher"}}
```

- **`id`** es el número de secuencia. El navegador lo reenvía como `Last-Event-ID` al
  reconectar, y el servidor devuelve **solo lo que falta**. Verificado: con
  `Last-Event-ID: 3` sobre 10 eventos, el cliente recibe exactamente los ids 4 a 10.
- **`event`** es el tipo, de un conjunto cerrado. Permite `addEventListener` por tipo
  en lugar de un `switch` sobre el contenido.
- **`data`** es un `RunEvent` completo y **estructurado**. El frontend lo consume
  directamente; no hay que parsear texto libre.

**Por qué el registro es una tabla y no una cola en memoria:** una cola en memoria se
pierde al reiniciar y no permite reconectar. Una tabla hace que «recargar la página a
mitad de una ejecución» sea un caso resuelto, no un caso perdido.

**`ping` cada 10 segundos:** un proxy cierra una conexión inactiva. Sin latido, una
ejecución larga se corta en silencio y el usuario ve una interfaz congelada sin
ningún error.

### 2.4 La aprobación humana

**Problema:** la decisión del usuario llega por una petición distinta, minutos después
de que el grafo se pausara. Y el grafo debe reanudarse **desde donde estaba**, no
desde el principio.

**Solución:**

```
1. El grafo se pausa y persiste el estado          → evento run.awaiting_approval
2. El frontend muestra la pregunta y el diff        → el usuario decide
3. POST /runs/{id}/approve {decision}               → 200 inmediato
4. La reanudación vuelve al trabajador              → el cliente recibe eventos
```

Detalles que importan:

- La aprobación **no espera** a que el grafo termine: responde 200 y el progreso
  sigue llegando por el flujo.
- El frontend **vuelve a suscribirse** tras aprobar, porque el flujo anterior se
  cerró al pausarse. Es barato y correcto gracias a `Last-Event-ID`.
- `409` si la ejecución no está esperando nada; `404` si no existe. **Son respuestas
  distintas y el cliente las distingue.** La primera versión devolvía 409 para una
  ejecución inexistente, lo que impedía distinguir «no existe» de «no toca».

### 2.5 Mismo origen: el prototipo no necesita CORS

**Problema:** CORS es una fuente inagotable de fallos de integración —*preflight*,
credenciales, y el origen `null` que produce `file://`.

**Solución:** el backend sirve el frontend en `/app`. **Mismo origen, sin CORS.**
Verificado: sin orígenes configurados no aparece ninguna cabecera
`Access-Control-Allow-Origin`.

La lista de orígenes permitidos existe y es configurable, pero **vacía por defecto**,
para el caso de desarrollar el frontend con un servidor aparte. Un origen no
declarado no recibe permiso.

---

## 3. Cuando algo va mal

Un contrato entre dos partes no está completo hasta que dice qué pasa en los fallos.

| Situación | Qué ocurre | Por qué |
|---|---|---|
| El navegador se recarga a mitad de ejecución | Reconecta con `Last-Event-ID` y recupera lo perdido | El registro es persistente, no una cola en memoria |
| Se corta la red | `EventSource` reconecta solo; el servidor completa lo que falta | Comportamiento nativo de SSE + `id` por evento |
| El servidor se reinicia con ejecuciones abiertas | Se marcan como `needs_human` y se emite `run.error` con `ORPHANED_RUN` | Dejarlas en `running` sería la terminación anómala que `MET-13` prohíbe, y el navegador esperaría para siempre |
| El trabajador lanza una excepción | Se registra un error tipado y la ejecución queda en `needs_human` | Una excepción sin capturar deja la ejecución colgada |
| La petición no pasa el contrato | `422` con el motivo, campo por campo | El frontend muestra qué corregir |
| Se pide aprobar algo que no espera | `409` con explicación | Distinto de «no existe» (`404`) |
| La ejecución tarda más que el tiempo de espera del flujo | Evento final y cierre | Una conexión abierta para siempre es una fuga |

**Decisión de diseño:** el servidor **siempre** deja la ejecución en un estado
terminal o en `awaiting_approval`. El frontend puede asumir que, si el flujo se
cierra sin `run.done`, algo se rompió — y no quedarse esperando indefinidamente.

---

## 4. Verificación

No basta con que el contrato esté escrito. `tools/verify_frontend.py` arranca el
servidor, abre la página en **Chrome headless real** (no un shim de DOM), **pulsa el
botón** y lee lo que pasó desde la propia página.

Resultado de la última ejecución:

| Comprobación | Valor observado |
|---|---|
| Errores y avisos de consola | 0 |
| Contratos cargados | 15 |
| Enumeraciones de evento | 8 |
| Filas en la línea de tiempo | 8 |
| Tipos de evento recibidos | `run.created, run.started, run.step×3, run.status, run.report, run.done` |
| Estado final mostrado | `completada` |
| `run_id` recibido por el cliente | `run-2a299238143d` |
| Desbordamiento horizontal | ninguno |

**Y la verificación se verifica.** Una comprobación que nunca ha fallado no demuestra
nada, así que se introdujeron cuatro defectos a propósito en el frontend y se
comprobó que se detectan:

| Mutación | ¿Cazada? |
|---|---|
| Se elimina la suscripción SSE | ✅ |
| No se cargan los contratos | ✅ |
| El `run_id` no se muestra | ✅ |
| Se rompe el render de eventos | ✅ |

Las cuatro están incorporadas en `tools/mutation_check.py`, de modo que se comprueban
en cada ejecución.

#### Y una cosa que salió mal, que importa más que la tabla anterior

Al principio, **tres de esas cuatro mutaciones se reportaron como cazadas sin que la
comprobación llegara a ejecutarse.** La verificación del navegador moría a los 1,3 s
porque el entorno le bloqueaba un borrado de fichero, y el verificador interpretaba
«código de salida distinto de cero» como «mutación cazada».

Un verificador que se cae **no ha comprobado nada**. Ahora una herramienta de
verificación debe **emitir un veredicto explícito**; si no lo emite, el resultado se
marca como **NO CONCLUYENTE**, no cuenta como cazada, y hace que el verificador termine
en rojo. Es el fallo más peligroso de los encontrados en esta fase: un verificador que
deja el árbol modificado produce fallos que no existen, y eso se nota. Uno que cuenta
como comprobado lo que no llegó a comprobar produce una confianza sin respaldo, y eso
**no se nota nunca**.

---

## 5. Lo que NO está resuelto todavía

Se declara porque un contrato que solo describe lo que funciona no es un contrato.

| Hueco | Consecuencia | Cuándo se cierra |
|---|---|---|
| **No hay autenticación ni sesión** | Cualquier navegador ve **todas** las ejecuciones de `GET /runs`. Aceptable en un prototipo de una máquina; **inaceptable en cuanto haya dos usuarios.** | Antes de cualquier despliegue compartido |
| **El frontend no valida contra el esquema** | Consume las enumeraciones, pero no comprueba las respuestas. Un campo que cambie de nombre falla en el navegador | Siguiente iteración del contrato |
| **`RF-16` (cancelar) devuelve 501** | El usuario no puede detener una ejecución en curso | Con el modelo conectado (M2) |
| **El flujo SSE consulta la base cada 50 ms por cliente** | Con 100 pestañas abiertas son ~2 000 consultas por segundo. **Es el primer cuello de botella del frontend**, y no es el que uno espera | Con un bus de eventos en proceso, o `LISTEN/NOTIFY` al migrar a PostgreSQL |
| **El trabajador son hilos, no procesos** | Una ejecución que consuma CPU afecta a las demás. Suficiente porque el trabajo es espera de red | Con el contenedor por ejecución (M3) |
| **Sin límite de tasa** | Nada impide que un cliente envíe 10 000 ejecuciones | Con cuotas por usuario |

**El cuello de botella del SSE es el hallazgo más útil de esta sección.** No aparece
al construir una interfaz de demostración; aparece al abrir la pestaña número veinte.
Se declara ahora para que no sorprenda después.

---

## 6. Trazabilidad

| Decisión | Dónde vive |
|---|---|
| Ejecución fuera de la petición | `DEC-11` (nueva), `src/ai_swe/graph/worker.py` |
| Progreso por eventos persistentes | `src/ai_swe/state/store.py`, `api/app.py` |
| Contrato exportado | `tools/export_contracts.py`, `frontend/contracts.json` |
| Mismo origen | `api/app.py` (`/app`), `RNF-E1` |
| Estados y su dueño | `01-arquitectura.md` §14.2, `contracts/state.py` |
| Aprobación sin bloquear | `RF-11`, `RF-12`, `api/app.py` |
| Recuperación de huérfanas | `RunStore.orphan_open_runs`, `MET-13` |

### `DEC-11` — La ejecución no ocurre dentro de la petición

| | |
|---|---|
| **Alternativa descartada** | Ejecutar dentro de la petición y devolver el resultado completo. Más simple, sin trabajador, sin eventos. |
| **Motivo del descarte** | El cliente no puede suscribirse a una ejecución cuyo identificador aún no tiene, y una tarea de decenas de segundos deja la interfaz congelada. Con un navegador como interfaz principal, es un fallo de diseño, no una limitación. |
| **Coste aceptado** | Un componente más (el trabajador), un estado más que gestionar (`planned`), y la necesidad de recuperar ejecuciones huérfanas al arrancar. |
| **Condición de revisión** | Si el trabajador se convierte en el cuello de botella, se sustituyen los hilos por procesos con el contenedor por ejecución. La interfaz no cambia: el contrato HTTP y el flujo de eventos ya están separados del mecanismo de ejecución. |

## Extensión G: configuración del proveedor

GET `/health` conserva su respuesta 200 y añade `provider_configuration`, con
`status` (`not_configured`, `offline`, `configured`), `remote_enabled`,
`missing_fields`, `message`, `credential_validated` e `inference_verified`.
Los dos últimos son false en este diagnóstico sin red. No contiene secretos ni
confirma saldo/conectividad. La vista general muestra el mensaje si falta configurar.

POST `/runs` puede responder 503 si hay roles remotos habilitados y falta la
configuración necesaria. El rechazo ocurre antes de guardar/encolar la ejecución.
No bloquea GET de salud, proyectos o historial. Con roles remotos desactivados,
continúa disponible la ejecución determinista local.
Véase `INSTALLED-CONFIGURATION-WINDOWS.md` para rutas y precedencia.
