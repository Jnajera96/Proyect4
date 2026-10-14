# Acta de la Fase 4 — Preparacion para exposicion publica (AUD-06)

## 1. RESUMEN

La API no tenia ninguna capa de autenticacion: cualquiera que alcanzara el puerto
podia lanzar una ejecucion -que escribe codigo y ejecuta pruebas en un worktree- y
podia usar `POST /runs/{id}/approve`, que promueve el parche al repositorio del
usuario. Con el sistema local mono-usuario eso era un riesgo teorico; abrirlo lo
convierte en real. Esta fase anade la capa que faltaba:

  - **Autenticacion por clave de API, desactivada por defecto.** Sin claves
    declaradas la API se comporta exactamente como en las fases anteriores.
  - **Autorizacion por rol, con la clave.** `reader` / `operator` / `admin`, en
    jerarquia, aplicada a los once endpoints en una unica matriz.
  - **La excepcion del flujo SSE** (`?api_key=`), que existia en el codigo pero
    era **inalcanzable**: la dependencia de ruta rechazaba la peticion antes de
    que el manejador viera la query. Encontrada por las pruebas de esta fase,
    documentada en el hallazgo 1.
  - **Auditoria** de las acciones que cambian estado, en un logger dedicado, con
    el `clave_id` y nunca la clave.
  - **Las claves se registran en el redactor central**, asi que una fuga en un
    log sale `[REDACTED]`.
  - **La plantilla de entorno documenta `AI_SWE_API_KEYS`** y una prueba nueva
    carga el archivo entero para que un valor invalido falle en la suite y no en
    el arranque de quien lo copie.

## 2. CAMBIOS REALIZADOS

**Creados:**

  - `src/ai_swe/security/auth.py` — `Rol` (enumeracion cerrada con jerarquia),
    `Identidad` (rol + `clave_id`), `Credenciales` (mapa clave->rol con busqueda
    en tiempo constante), `credencial_de_peticion` (cabeceras) y `credenciales_de`
    (desde los ajustes validados).
  - `tests/test_auth.py` — pruebas de unidad del modulo de credenciales y de
    integracion de la matriz completa endpoint x rol.

**Modificados:**

  - `src/ai_swe/config.py` — campo `api_keys: dict[str, str]` con validador de
    rol (enumeracion cerrada) y de clave no vacia; `registrar_secretos()` ahora
    registra tambien cada clave de API.
  - `src/ai_swe/security/__init__.py` — exporta `Credenciales`, `Identidad`,
    `Rol`, `credencial_de_peticion`, `credenciales_de`, `ROLES_VALIDOS`.
  - `src/ai_swe/api/app.py` — identidad por cabecera, dependencias `_exige(rol)`,
    matriz de roles en un solo sitio, auditoria de las acciones que escriben, y
    la correccion de la autenticacion del flujo SSE (hallazgo 1).
  - `.env.example` — seccion de autenticacion con `AI_SWE_API_KEYS`.
  - `tests/test_config_budget.py` — prueba de que la plantilla de entorno
    completa carga sin error.
  - `frontend/src/lib/auth.ts`, `frontend/src/lib/api.ts`,
    `frontend/src/hooks/useEventosRun.ts`, `frontend/src/App.tsx` — la clave se
    guarda en `localStorage`, viaja en cada `fetch` (cabecera) y en la query del
    `EventSource`, y la interfaz tiene una seccion para guardarla u olvidarla.

**Hechos al verificar (no al implementar):**

  - `src/ai_swe/security/auth.py` — `identificar` recorre la lista **completa**
    sin salir en la coincidencia. El docstring de `Credenciales` ya afirmaba
    "el tiempo es el mismo"; con la salida temprana eso era falso -el tiempo
    dependia de la posicion de la clave-. Ahora el codigo hace cierto lo que
    dice, y un espia sobre `compare_digest` lo protege.
  - `tests/test_auth.py` — `test_la_comparacion_de_claves_usa_tiempo_constante`
    (33 pruebas en el fichero).
  - `tools/verify_frontend.py` — modo `--auth` y **reconstruccion de `dist`
    antes de servir** (ver seccion 6: sin ella, las mutaciones del frontend
    habrian sido invisibles para el navegador).
  - `tools/mutation_check.py` — las 16 mutaciones de la fase y la reparacion de
    las cuatro mutaciones del frontend que llevaban muertas desde F11.

## 3. DECISIONES DE SEGURIDAD

### 3.1 Desactivada por defecto, y la prueba puede fallar si alguien la enciende

Sin claves declaradas la API no cambia: el desarrollo local y las pruebas
existentes siguen funcionando. La prueba del estado por defecto no afirma "no da
error" -eso lo cumple tambien un control roto- sino hechos observables: el estado
de las credenciales y peticiones **sin clave que llegan al manejador** (200/202).
Si alguien encendiera la autenticacion por defecto, esas peticiones darian 401 y
la prueba fallaria. Es la leccion del punto ciego del rate limiter (Fase 3,
hallazgo 3) aplicada a un control nuevo.

### 3.2 Clave en cabecera, no en cookie

No hay sesion que mantener: hay claves. Se acepta `X-API-Key` y
`Authorization: Bearer`. Si llegan **las dos con valores distintos** se rechaza
(401): preferir una en silencio daria un comportamiento que depende de un detalle
que el cliente no ve.

### 3.3 El rol viaja con la clave

No hay usuarios, hay claves; cada clave declara su rol. Una clave filtrada
concede lo minimo y revocarla es borrarla del mapa. `admin` queda para registrar
proyectos, porque un proyecto fija el `repo_path` contra el que se ejecutara, y
con alcance amplio eso es elegir sobre que repositorio se escribe.

### 3.4 Comparacion en tiempo constante

`hmac.compare_digest`, no `==`. Con `==` el tiempo de respuesta depende de
cuantos caracteres iniciales coinciden, y eso convierte el endpoint en un oraculo
con el que recuperar la clave prefijo a prefijo. `Credenciales` recorre la lista
completa comparando cada clave, de modo que el tiempo no depende de la posicion
ni de que haya coincidencia.

Las pruebas afirman lo que se puede afirmar de forma estable: que una clave con
prefijo comun **no** se acepta y que ausente e invalida no se distinguen. El
tiempo de ejecucion no se mide -una prueba de temporizacion en una maquina de
desarrollo es fluctuante y daria falsos verdes-, pero el **mecanismo** si se
afirma: `test_la_comparacion_de_claves_usa_tiempo_constante` pone un espia
sobre `hmac.compare_digest` y comprueba que la comparacion pasa por ahi (y que
se recorre cada clave, no solo hasta la coincidencia). No prueba que el tiempo
sea constante -eso no se puede probar en una prueba-; prueba que el primitivo
que lo garantiza esta en el camino, que es lo unico observable. La mutation
`PH4: la comparacion de claves pasa a ser directa` la caza.

### 3.5 `/health` queda sin autenticacion

Un health check de infraestructura tiene que poder llegar sin credenciales, o el
balanceador marca el servicio caido y lo quita de rotacion. Se afirma con
prueba: con la autenticacion activada, `/health` responde 200.

### 3.6 La clave por query es solo del flujo SSE, y vive en el manejador

`EventSource` no puede enviar cabeceras; un endpoint de solo cabeceras dejaria el
streaming fuera del dashboard, que es su unico consumidor real. Se acepta
`?api_key=` **solo ahi** y solo cuando no viene ninguna cabecera. La concesion
tiene un precio declarado: una clave en la URL acaba en registros de acceso,
historial y proxies. Por eso esta pensada para una clave de lectura, y por eso
antes de una exposicion real hay que sustituirla por un vale de un solo uso
emitido por un endpoint autenticado.

La comprobacion vive **en el manejador**, no en una dependencia de ruta. Con la
dependencia puesta, la excepcion era codigo muerto (hallazgo 1).

### 3.7 Auditoria en logger dedicado, sin la clave

`ai_swe.audit`, separado del log de aplicacion: la auditoria se consume de otra
forma -se retiene, se busca, se compara-. Se registra el `clave_id` (cuatro
caracteres y longitud), nunca la clave. Con la autenticacion desactivada el actor
es `sin-autenticar`, que es la verdad de ese modo.

**Limitacion declarada:** hoy escribe en el flujo de log. Antes de una exposicion
real hace falta un sumidero persistente (fichero rotado o el almacen), porque un
log que nadie retiene no es un registro de auditoria.

## 4. MATRIZ DE ROLES

| Endpoint | reader | operator | admin |
|---|---|---|---|
| `GET /health` | si | si | si (sin auth, a proposito) |
| `GET /projects`, `GET /projects/{id}` | si | si | si |
| `POST /projects` | no | no | si |
| `GET /runs`, `GET /runs/{id}` | si | si | si |
| `GET /runs/{id}/events` | si (cabecera o `?api_key=`) | si | si |
| `POST /transcriptions` | no | si | si |
| `POST /runs` | no | si | si |
| `POST /runs/{id}/confirm-requirements` | no | si | si |
| `POST /runs/{id}/approve` | no | si | si |
| `POST /runs/{id}/cancel` | no | si | si |

`approve` es la accion mas sensible de la API: promueve el parche al repositorio
del usuario. `operator` como minimo, y se audita con el `run_id`, el veredicto y
los comentarios.

## 5. HALLAZGOS

1. **La excepcion de la clave por query en el flujo SSE era codigo muerto.** El
   endpoint llevaba `dependencies=[LEER]`, y la dependencia solo lee cabeceras.
   FastAPI resuelve las dependencias **antes** del manejador, asi que una
   peticion con `?api_key=` valida -la unica forma que tiene `EventSource` de
   autenticarse- recibia 401 sin que el manejador llegara a ejecutar nada. La
   prueba `test_la_clave_por_query_funciona_en_el_flujo_sse` lo encontro
   afirmando un hecho observable: con clave valida la respuesta debe ser **404**
   (la ejecucion no existe), no 401.

   Corregido moviendo la comprobacion al manejador, con precedencia explicita:
   si viene cualquier cabecera manda ella; si no, se admite la query; sin ninguna
   de las dos cosas, 401. De paso se cerro el hueco que la mudanza habria
   destapado -con query **y** cabecera presentes, el codigo viejo no comprobaba
   nada-: ahora `?api_key=invalida` + cabecera invalida sigue siendo 401, y hay
   prueba para ello.

2. **`AI_SWE_API_KEYS=[]` en la plantilla rompe el arranque.** El campo es un
   diccionario; `[]` es la forma natural de escribir "vacio" y `Settings` la
   rechaza con `Input should be a valid dictionary`. Quien copiara
   `.env.example` a `.env` habria visto el servicio morir por una linea de
   documentacion. Corregido a `{}` y anadida
   `test_la_plantilla_de_entorno_completa_es_valida`, que carga el archivo
   entero; verificada reintroduciendo el fallo a proposito.

3. **Dos pruebas mias estaban mal escritas, no el codigo.** Un `GET` a
   `/runs/x/approve` devuelve **405** (ruta solo POST) y una ruta inexistente
   devuelve **404**: en ambos casos el enrutado responde antes que la
   autenticacion. Las dos filas se quitaron de la barrida de 401, que ahora solo
   contiene endpoints que de verdad existen y aceptan el metodo usado.

4. **Cuatro mutaciones del frontend llevaban muertas desde F11.** Apuntaban al
   `index.html` de la version previa a React; al reescribirse como Vite los
   patrones dejaron de existir y salian "NO APLICADA". Ademas,
   `verify_frontend.py` servia `dist` sin reconstruirlo: con las mutaciones
   atacando `src/`, el navegador habria visto el bundle anterior y las cinco
   nuevas habrian salido "NO CAZADA" sin que nada fallara -un punto ciego
   fabricado por el instrumento-. Ambas cosas se corrigieron (ver seccion 6) y
   la verificacion del frontend ahora reconstruye antes de servir.

5. **La comprobacion de la linea de tiempo era casi vacia.** Contaba filas
   (`FILAS_TIMELINE`), y la linea de tiempo pinta los cuatro hitos canonicos
   **siempre** -alcanzados o pendientes-, asi que la comprobacion pasaba
   tambien con una interfaz que nunca recibia un evento. Lo encontro la
   mutacion "deja de pintar los eventos" al reescribirla: la version que
   compilaba no era vista por el verificador. Se anadio `HITOS_ALCANZADOS`
   (filas con marca de secuencia). Mismo patron que AUD-17.

6. **El docstring de `Credenciales` afirmaba un recorrido que el codigo no
   hacia.** "Se recorre la lista completa comparando cada clave, de modo que el
   tiempo es el mismo": con la salida en la primera coincidencia, el tiempo
   dependia de la posicion de la clave dentro del mapa. No es el oraculo
   peligroso -eso lo cierra `compare_digest`-, pero era una afirmacion falsa
   sobre una propiedad de seguridad. Se hizo el recorrido completo y un espia
   sobre `compare_digest` lo protege con dos mutaciones.

## 6. MUTACIONES (Fase 4)

Arnes `tools/mutation_check.py`. Dos corridas filtradas, las dos con linea base
verde y arbol restaurado en verde:

  - filtro `PH4`: **16/16 cazadas** (38,5 min). Catorce atacan el backend y se
    comprueban con `tests/test_auth.py`; dos atacan el frontend y se comprueban
    en un navegador real (`verify_frontend.py --auth`).
  - filtro `frontend`: **5/5 cazadas** (32,8 min). Las tres mutaciones
    estructurales reparadas mas las dos de la clave, que corren en los dos
    filtros. En total, 19 mutaciones distintas.

| Mutacion | Defecto que describe | Quien la caza |
|---|---|---|
| `PH4: /projects deja de exigir admin` | un `reader` fija el `repo_path` de un proyecto | matriz de roles |
| `PH4: /approve deja de exigir operator` | cualquiera promueve el parche al repo del usuario | matriz de roles |
| `PH4: la comprobacion de rol deja de distinguir niveles` | `_exige` no compara: pasan todos | matriz de roles |
| `PH4: la jerarquia de roles se invierte` | `reader` haria lo de `admin` y al reves | prueba de jerarquia |
| `PH4: la autenticacion se enciende siempre` | con el mapa vacio ni el local arranca | estado por defecto (hechos observables) |
| `PH4: el 401 distingue clave ausente de invalida` | el mensaje se vuelve oraculo de enumeracion | mismo-error |
| `PH4: /health pasa a exigir clave` | el balanceador marca el servicio caido | health abierto |
| `PH4: dos cabeceras distintas se aceptan` | gana una en silencio | dos-cabeceras |
| `PH4: la comparacion de claves pasa a ser directa` | `==` filtra el prefijo por temporizacion | espia de `compare_digest` |
| `PH4: la busqueda sale en la primera coincidencia` | el tiempo depende de la posicion | espia de `compare_digest` |
| `PH4: la auditoria registra la clave entera` | el secreto escrito en el registro | `clave_id` corto |
| `PH4: las claves de API no se registran en el redactor` | una fuga saldria en claro | redactor |
| `PH4: el flujo SSE pierde la clave por query` | la excepcion vuelve a ser codigo muerto (hallazgo 1) | query-en-SSE |
| `PH4: la query manda por encima de la cabecera` | precedencia invertida | SSE con claves que no valen |
| `PH4: el frontend deja de mandar la clave en las peticiones` | toda la interfaz en 401 | navegador, modo `--auth` |
| `PH4: el flujo SSE del frontend viaja sin la clave` | ningun evento llega | navegador, modo `--auth` |
| `el frontend pierde la suscripcion a los eventos` | se suscribe a un flujo que no existe | navegador (`EVENTOS=0`) |
| `el frontend deja de mostrar el run_id` | la interfaz no expone la ejecucion | navegador (`RUN_ID`) |
| `el frontend deja de pintar los eventos` | el conjunto de hitos queda vacio | navegador (`HITOS_ALCANZADOS=0`) |

**La prueba nueva tambien se muto.** La pareja del tiempo constante necesitaba
un test que no existia (ver 3.4). La primera version del espia ponia la clave
coincidente la **ultima** del mapa: con esa posicion, salir en la primera
coincidencia y recorrer la lista completa hacen exactamente dos comparaciones,
asi que la mutacion de la salida temprana pasaba en verde. La encontro el
pre-vuelo manual -aplicar la mutacion a lo recien escrito, antes de lanzar el
arnes-, no el arnes. Con la coincidencia en la primera posicion, las dos
mutaciones caen. Es la misma leccion de F7 ("verificar que la verificacion
funciona") aplicada a un test de esta fase.

**Una mutacion candidata se retiro con evidencia, no con suposicion.** La rama
`if not identidad.puede(Rol.READER)` del flujo SSE es defensiva: la enumeracion
de roles es cerrada y los tres valores validos quedan todos en `reader` o por
encima, de modo que la rama no puede ejecutarse. Se aplico la mutacion al
arbol y se corrio la suite entera: **verde con ella y sin ella** (33/33). Una
mutacion sobre codigo inalcanzable no verifica nada; se retiro y queda aqui el
rastro.

**Cuatro mutaciones del frontend llevaban muertas desde F11.** Apuntaban al
`index.html` de la version previa a React, que era la aplicacion entera en un
fichero; cuando F11 la reescribio como Vite los patrones dejaron de existir y
las cuatro salian "NO APLICABLE" -que es peor que no tenerlas, porque aparenta
verificar algo-. Se reescribieron contra las fuentes actuales
(`useEventosRun.ts`, `App.tsx`). Una quinta, "el frontend deja de cargar los
contratos", **se retira**: el cliente actual importa `contracts.json` en
compilacion (los tipos se derivan de ahi), no hay ninguna carga por red que
romper, y la propiedad que quedaba -que el JSON corresponde al backend- la
protege `tests/test_contracts.py`.

**Las dos primeras versiones de las mutaciones reparadas las cazaba el
compilador, no el navegador -y eso tambien era un defecto del arnes.** La
version inicial de "pierde la suscripcion" ponia `if (true)` en el guardia, y
sin guardia `runId` ya no se estrecha a `string`: `encodeURIComponent(runId)`
no compila. La de "deja de pintar los eventos" devolvia `return []` directo, y
con `noUnusedLocals` el parametro y el conjunto quedaban sin usar. Las dos
funcionaban -el typechecker las rechazaba-, pero en diez segundos y sin llegar
al navegador: no se sabria si la comprobacion del navegador sirve. Y el arnes
las anotaba **NO CONCLUYENTE** porque la herramienta salia por `SystemExit` sin
el marcador `RESULTADO:` -un fallo de compilacion es un veredicto, no una caida
del verificador-. Ahora `_reconstruir` emite el marcador en el fallo de
compilacion (y no lo emite si `npm` no existe o hay un corte de tiempo, que ahi
si que no se ha comprobado nada).

**Reescribir la de los hitos destapo que la comprobacion de la linea de tiempo
era casi vacia.** Con el conjunto de hitos vacio, la suscripion seguia
funcionando y la verificacion **pasaba**: la linea de tiempo pinta los cuatro
hitos canonicos **siempre**, alcanzados o pendientes, y `FILAS_TIMELINE` contaba
filas -no hitos alcanzados-. Una interfaz que nunca recibiera un evento habria
pasado esa comprobacion. Se anadio `HITOS_ALCANZADOS` (filas con marca de
secuencia, no pendientes) y la mutacion cae. Es el mismo patron que AUD-17: la
prueba que no puede distinguir "apagado" de "encendido".

**Y el instrumento tenia un punto ciego fabricado.** `verify_frontend.py`
servia `dist` tal como estuviera en disco: con las mutaciones atacando `src/`,
el navegador habria seguido viendo el bundle anterior y las cinco habrian
salido "NO CAZADA" sin que nada hubiera fallado. Desde esta fase la herramienta
**reconstruye `dist` antes de verificar** -que un cambio sin compilar se note,
no que se verde sobre el arbol viejo-.

## 7. TESTS

Suite completa (`python -m pytest -q --junitxml=_fase4_final.xml`):
**678 pruebas, 0 fallos, 0 errores, 2 skips**. El veredicto sale del informe
XML: el codigo de salida es 1 porque el interceptor de borrados del entorno
mata la limpieza de temporales **despues** de escribir el informe -la trampa ya
conocida, la misma que motivo la regla del veredicto por XML-. Las dos skips
son las opt-in por diseno (proveedor real y STT real), igual que en fases
anteriores.

La cuenta cuadra: 644 al cerrar la Fase 3 + 33 de `tests/test_auth.py` + 1 de
`tests/test_config_budget.py` = 678. De las 33 de la fase, 32 son de
implementacion y una -el espia de la comparacion- se anadio al verificar,
porque sin ella dos mutaciones reales no se veian.

Frontend, en navegador real (`tools/verify_frontend.py`): 16 comprobaciones en
modo sin autenticacion y 18 en modo autenticado, todas en verde, con la
aplicacion **reconstruida desde el fuente** en cada corrida.

## 8. LIMITACIONES

  - **TLS no esta terminado en ningun sitio**: el servicio habla HTTP. La
    terminacion TLS es de quien expone (proxy inverso o balanceador), y hay que
    declararlo antes de abrir.
  - **Los secretos siguen en variables de entorno**, no en un vault. Para el
    bucle local es la forma practica; para una exposicion real hace falta un
    gestor.
  - **El rate limiter sigue apagado por defecto** (Fase 3). Encenderlo es parte
    de la operacion de exposicion, junto con `AI_SWE_TRUSTED_HOSTS` con los
    dominios reales.
  - **La auditoria escribe en el flujo de log**, sin sumidero persistente.
  - **Una clave por query en la URL** sigue siendo la concesion del flujo SSE;
    su sustitucion por un vale de un solo uso esta declarada, no implementada.
  - **La CSP del frontend no se ha revisado** en esta fase: el alcance original
    lo pediamos y quedo fuera. Es trabajo de la fase de exposicion.

## 9. VEREDICTO

**La Fase 4 queda cerrada.** La autenticacion por clave de API (opt-in,
desactivada por defecto) y la autorizacion por rol existen, estan aplicadas en
una sola matriz, auditadas y con las claves registradas en el redactor. La
excepcion del flujo SSE -que era codigo muerto- funciona y tiene prueba; su
precedencia respecto a la cabecera esta declarada y cubierta.

Verificacion:

  - Suite completa: **678 pruebas, 0 fallos, 0 errores, 2 skips** (XML).
  - Mutaciones de la fase: **16/16** con el filtro `PH4`; **5/5** con el filtro
    `frontend` (19 distintas en total; las dos de la clave corren en los dos).
  - Dos mutaciones candidatas se retiraron **con evidencia**, no con suposicion:
    la rama defensiva de rol del SSE (verde con y sin la mutacion: la
    enumeracion cerrada la hace inalcanzable) y la de los contratos del frontend
    (el cliente ya no los carga por red).
  - La verificacion encontro, ademas de los tres hallazgos de implementacion,
    tres defectos del propio proceso: cuatro mutaciones muertas desde F11, una
    comprobacion del navegador casi vacia y un punto ciego fabricado por servir
    `dist` sin reconstruir. Los tres estan corregidos y documentados.

Lo que **no** se hizo, y es condicion para exponer el servicio de verdad:
terminacion TLS, claves en un gestor de secretos, rate limiter encendido,
sumidero persistente para la auditoria, vale de un solo uso para la clave por
query del SSE y revision de la CSP del frontend. Estan en la seccion 8 y en
TD-02 del snapshot. Con esos seis puntos abiertos, el servicio sigue siendo de
exposicion local.
