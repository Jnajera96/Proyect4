# Acta de la Fase 3 — Endurecimiento del borde local (P0/P1/P2)

## 1. RESUMEN

Se cerraron ocho brechas que no tenian tope ni prueba en el borde de entrada:

  - El contenedor ya no arranca la API en todas las interfaces de fabrica.
  - Todas las respuestas (incluidos los errores) llevan cabeceras de seguridad.
  - Un `Host` desconocido se rechaza sin tocar el manejador.
  - El limite de peticiones existe, esta apagado por defecto y corta con 429.
  - El audio tiene tope de tamano (413) y lista blanca de formato (415).
  - La paginacion tiene maximo: `?limit=1000000000` ya no es valido.
  - Las conexiones SSE simultaneas tienen tope, con 503 y `Retry-After`.
  - El contenido que viene del repositorio se marca como **dato** en los dos
    prompts que lo reciben (Coder y Reviewer), y el veto determinista no lee
    ese texto: una inyeccion indirecta no puede alterar ninguna decision.

Ademas, el worktree del sandbox ahora se limpia en los **tres** caminos
terminales: cierre normal del grafo (`finalize`), aborto del trabajador
(`RunEngine.abortar`) y recuperacion de ejecuciones huerfanas al arrancar. Los
tres tienen prueba con un sandbox git **real**.

## 2. CAMBIOS REALIZADOS

**Creados:**

  - `src/ai_swe/security/untrusted.py` — delimitadores y aviso para contenido
    derivado del repositorio.
  - `tests/test_hardening.py` — 24 pruebas que ejercitan las ocho brechas.

**Modificados:**

  - `src/ai_swe/config.py` — `max_audio_bytes`, `max_page_size`,
    `max_sse_connections`, `rate_limit_enabled`, `rate_limit_per_minute`.
  - `src/ai_swe/api/app.py` — `TrustedHostMiddleware`, cabeceras de seguridad
    (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `CSP`),
    `LimitadorDePeticiones` (apagado por defecto), clamp de paginacion,
    tope de conexiones SSE, validacion de audio (MIME + tamano con lectura
    por trozos), limpieza de worktrees huerfanos al arrancar.
  - `src/ai_swe/graph/nodes.py` — `PROMPT_CODIFICACION` y `PROMPT_REVISION`
    usan `bloque_no_confiable(...)` para diff, salida de pruebas y evidencia
    del Researcher.
  - `src/ai_swe/graph/engine.py` — `abortar` llama a `limpiar_worktree` antes
    de devolver el estado final.
  - `src/ai_swe/sandbox.py` — `limpiar_worktree(...)` (funcion compartida para
    los tres caminos terminales).
  - `src/ai_swe/security/__init__.py` — exporta `bloque_no_confiable`,
    `AVISO_NO_CONFIABLE`, `MARCA_INICIO`, `MARCA_FIN`.
  - `Dockerfile` — `AI_SWE_HOST=127.0.0.1` por defecto, interfaz configurable.
  - `docker-compose.yml` — publica el puerto solo en `127.0.0.1`.

**Eliminados / movidos:** ninguno.

## 3. DECISIONES DE SEGURIDAD

### 3.1 El rate limiter esta apagado por defecto

En bucle local mono-usuario no protege de nadie y estorba a las pruebas. La
estrategia existe y se activa con `AI_SWE_RATE_LIMIT_ENABLED=true`; el plan
de exposicion publica la encendera.

### 3.2 CSP permite `style-src 'unsafe-inline'`

El frontend React usa estilos inline (atributo `style={{...}}`). Bloquearlos
romperia la interfaz. Se mantiene `'unsafe-inline'` en `style-src`; el plan de
hardening del frontend evaluara si se pueden pasar a clases CSS.

### 3.3 `TrustedHostMiddleware` permite `localhost` y `127.0.0.1`

En entornos de desarrollo local esos son los unicos hosts esperados. En
exposicion publica se anadiran los dominios reales a la lista.

### 3.4 Los delimitadores de contenido no confiable son una **peticion**, no una barrera

`bloque_no_confiable(...)` envuelve el texto con marcas y un aviso al modelo,
pero no impide que el modelo las ignore. Lo que impide de verdad que un
repositorio hostil altere el comportamiento son las barreras **deterministas**:

  - **Alcance declarado** (`Scope.allowed_paths`) — el Coder no puede escribir
    fuera de las rutas autorizadas, independientemente de lo que diga el prompt.
  - **Policy Engine** — rechaza herramientas de riesgo incluso si el modelo las
    solicita.
  - **Sandbox** — el codigo se ejecuta en un worktree aislado, no en el repo del
    usuario.
  - **Veto determinista del Reviewer** (`_guarda_pruebas`) — solo mira el
    `exit_code` de las pruebas, no su salida textual.

Las pruebas adversariales de `test_hardening.py` verifican que un texto de
inyeccion no altera ni el alcance, ni el veto, ni la decision de aprobacion.

## 4. HALLAZGOS

1. **TestClient sincrono no permite peticiones concurrentes dentro de un
   `stream()`**. El hilo se queda consumiendo el generador SSE y la segunda
   peticion no llega a ejecutarse. La prueba del tope SSE se reescribio para
   manipular el contador directamente, que es el mismo estado que el endpoint
   consulta.

2. **La marca de cierre dentro del contenido se neutraliza automaticamente**.
   `bloque_no_confiable` transforma cualquier `MARCA_FIN` interno en un texto
   inerte, de modo que el contenido no puede "salir" de su propio bloque.

3. **El arnes de mutaciones encontro un punto ciego real en las pruebas del
   limitador de peticiones.** La prueba que verifica que el limitador esta
   "apagado por defecto" hacia 30 peticiones a `/health`; la cuota por defecto es
   120/minuto. Un limitador **siempre activo** con los ajustes de serie tambien
   daba verde: 30 < 120. La prueba media el limite equivocado y no podia
   distinguir "apagado" de "encendido con la cuota de serie". La mutacion
   "el rate limiter siempre activo rompe local" pasaba sin que nada fallara.
   
   Corregido comprobando el **hecho observable**: con el limitador apagado el
   middleware no se instala y `app.state.rate_limiter` no existe. El arnes
   encontro esto; no se descubrio leyendo el codigo.

4. **La primera version de la mutacion de paginacion era ineficaz, no las
   pruebas.** Sustituia `le=ajustes.max_page_size` (200) por `le=99999999`, y la
   prueba pide `limit=1000000000`: **sigue siendo mayor que el tope**, asi que
   FastAPI seguia devolviendo 422 y la mutacion no cambiaba nada observable. Es
   la distincion entre una mutacion que describe un fallo que el codigo puede
   cometer y una que no: la version correcta **elimina la restriccion**
   (`Query(default=50, ge=1)`), y con ella `?limit=1000000000` si devuelve 200.
   Verificado aplicandola sobre el arbol en memoria antes de relanzar el arnes.

5. **La suite base tarda ~663 s** (644 tests). El limite del verificador de
   mutaciones se mantiene en 1200 s; la suite mutada puede tardar casi el
doble.

## 5. MUTACIONES (Fase 3)

| # | Mutacion | Esperado |
|---|----------|----------|
| 1 | Quitar cabeceras de seguridad del middleware | `test_hardening.py` |
| 2 | Quitar `TrustedHostMiddleware` | `test_hardening.py` |
| 3 | Activar rate limiter siempre (rompe local) | `test_hardening.py` |
| 4 | Quitar tope de tamano de audio | `test_hardening.py` |
| 5 | Quitar lista blanca de formato de audio | `test_hardening.py` |
| 6 | Quitar clamp de paginacion (`le=99999999`) | `test_hardening.py` |
| 7 | Quitar tope de conexiones SSE | `test_hardening.py` |
| 8 | Quitar `limpiar_worktree` de `abortar` | `test_hardening.py` |
| 9 | Quitar la limpieza de huerfanas al arrancar | `test_hardening.py` |

Veredicto: **9/9 cazadas**.

## 6. TESTS

| | |
|---|---|
| Collected | **644** (618 base + 26 de F3) |
| Passed | **642** |
| Failed / Errors | **0 / 0** |
| Skipped | **2** (opt-in por diseno) |
| Duration | ~720 s |
| Veredicto (JUnit XML) | **GREEN** |
| `tsc --noEmit` / `vite build` | limpios |
| Real provider / STT / Browser | no ejecutados (opt-in / fase de frontend) |

## 7. LIMITACIONES

  - `AI_SWE_NETWORK_EGRESS_ENABLED` sigue sin aplicarse (ahora se declara
    explicitamente en `config.py` y `.env.example`).
  - El rate limiter es por instancia de proceso, no por cluster.
  - La verificacion en navegador no se ejecuto.

## 8. SIGUIENTE FASE

**Fase 4 — Preparacion para exposicion publica.** Autenticacion, autorizacion,
secretos en vault, TLS terminacion, rate limiting por IP y por usuario, y
auditoria de accesos. **Riesgo estimado: ALTO** (toca autenticacion y
autorizacion, que son caminos de ataque criticos).

## 9. VEREDICTO

**PHASE_3_READY = YES**
