"""Pruebas de autenticacion y autorizacion por clave de API (Fase 4, `AUD-06`).

**Que protege este fichero.** Un control de acceso que se apaga o se esquivara no
produce ningun error visible: la API seguiria respondiendo igual, solo que tambien
a quien no deberia poder escribir. Las pruebas de aqui afirman por tanto sobre
**codigos de estado observables** -401, 403, 404, 200, 202, 415- y no sobre "no
da error", que es la afirmacion que un control roto tambien cumple.

Cinco propiedades:

  1. **Desactivada por defecto, y observablemente desactivada.** Sin claves
     declaradas la API se comporta como antes. La prueba comprueba hechos -el
     estado de las credenciales y una peticion sin clave que **llega** al
     manejador-: si alguien encendiera la autenticacion por defecto, esa peticion
     daria 401 y la prueba fallaria.
  2. **Activada, las puertas se cierran.** 401 sin clave o con clave invalida -con
     el mismo mensaje en ambos casos, para no permitir enumerar que claves
     existen-, y 403 cuando el rol no alcanza. La matriz endpoint x rol esta
     entera, incluidos los tres endpoints que escriben o aprueban.
  3. **La comparacion es en tiempo constante** y ningun camino -ni el de la clave
     por query- devuelve la clave ni permite distinguir una clave valida de una
     invalida por el mensaje.
  4. **La clave por query funciona solo en el flujo SSE**, y solo cuando no hay
     cabeceras: es la unica forma que tiene `EventSource` de autenticarse, y
     admitirla en el resto de la API seria un agujero.
  5. **Las claves no se filtran.** Se registran en el redactor central y la
     auditoria escribe el `clave_id` (cuatro caracteres y longitud), nunca la
     clave.

Todas las pruebas HTTP usan `TestClient`; no se abre ningun puerto de red.
"""

from __future__ import annotations

import hmac
import json
import logging
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ai_swe.api import crear_app
from ai_swe.config import Settings
from ai_swe.graph import nodes
from ai_swe.security import (
    Credenciales,
    Rol,
    clear_registered_secrets,
    credencial_de_peticion,
    redact,
)
from ai_swe.state import RunStore

# --------------------------------------------------------------- credenciales

#: Claves de fantasia. Se nombran para que sea evidente que no son reales y para
#: poder buscarlas en la salida sin equivocarse. Todas superan la longitud minima
#: de registro del redactor (6), que es tambien lo que las hace registrables.
CLAVE_ADMIN = "clave-admin-de-prueba-0001"
CLAVE_OPERARIO = "clave-operator-de-prueba-02"
CLAVE_LECTOR = "clave-reader-de-prueba-003"
CLAVE_INVALIDA = "clave-invalida-de-prueba-99"
CLAVE_CORTA = "abc"

MAPEO_DE_PRUEBA = {
    CLAVE_ADMIN: "admin",
    CLAVE_OPERARIO: "operator",
    CLAVE_LECTOR: "reader",
}


def _git(repo: Path, *args: str) -> str:
    resultado = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, shell=False
    )
    assert resultado.returncode == 0, f"git {' '.join(args)} fallo: {resultado.stderr}"
    return resultado.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repositorio git real, con un `tests/` que pasa."""
    raiz = tmp_path / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "test@localhost")
    _git(raiz, "config", "user.name", "Test")
    (raiz / "src").mkdir()
    (raiz / "src" / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (raiz / "tests").mkdir()
    (raiz / "tests" / "test_ok.py").write_text(
        "def test_pasa():\n    assert 1 == 1\n", encoding="utf-8"
    )
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "inicial")
    return raiz


@pytest.fixture(autouse=True)
def _inyeccion_limpia() -> None:
    """Deja el estado de modulo que comparten API y grafo como estaba.

    El motor de la API usa el **mismo** modulo `nodes` que las pruebas. Se limpia
    antes y despues: solo al final no basta, porque una prueba que empiece con
    basura ajena dependeria del orden de ejecucion.
    """
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    nodes.usar_modelo_reviewer(None)
    nodes.usar_workspace_root(None)
    nodes.usar_targets_permitidos(None)
    yield
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    nodes.usar_modelo_reviewer(None)
    nodes.usar_workspace_root(None)
    nodes.usar_targets_permitidos(None)


def _cliente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, claves: dict[str, str] | None):
    store = RunStore(tmp_path / "estado.db")
    try:
        if claves is None:
            # Se borra a proposito: si el entorno de desarrollo tuviera
            # `AI_SWE_API_KEYS`, la prueba del estado por defecto mediria el
            # entorno del desarrollador y no el del sistema.
            monkeypatch.delenv("AI_SWE_API_KEYS", raising=False)
        else:
            monkeypatch.setenv("AI_SWE_API_KEYS", json.dumps(claves))
        with TestClient(crear_app(store=store)) as c:
            yield c
    finally:
        store.close()


@pytest.fixture
def cliente_sin_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Cliente con la configuracion por defecto: autenticacion desactivada."""
    yield from _cliente(tmp_path, monkeypatch, None)


@pytest.fixture
def cliente_con_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Cliente con tres claves declaradas: autenticacion activada."""
    yield from _cliente(tmp_path, monkeypatch, MAPEO_DE_PRUEBA)


# ------------------------------------------------------- unidad: credenciales


def test_sin_claves_la_autenticacion_esta_desactivada() -> None:
    credenciales = Credenciales({})
    assert credenciales.activa is False
    assert credenciales.numero_de_claves == 0
    # Sin claves, **cualquier** clave es desconocida: no hay nada que identificar.
    assert credenciales.identificar(CLAVE_ADMIN) is None
    assert credenciales.identificar(CLAVE_INVALIDA) is None


def test_una_clave_valida_identifica_su_rol_y_guarda_referencia_corta() -> None:
    credenciales = Credenciales(MAPEO_DE_PRUEBA)
    assert credenciales.activa is True
    identidad = credenciales.identificar(CLAVE_ADMIN)
    assert identidad is not None
    assert identidad.rol is Rol.ADMIN
    # El `clave_id` debe bastar para la auditoria y no para reconstruir la clave.
    assert identidad.clave_id == "clav...len26"
    assert CLAVE_ADMIN not in identidad.clave_id


def test_clave_con_prefijo_comun_no_se_acepta() -> None:
    """`compare_digest` compara la cadena entera: un prefijo no basta.

    Si la comparacion fuera por prefijo -o si se cortara la clave-, una clave
    filtrada a medias seguiria dando acceso. Aqui se afirma que la clave tiene que
    coincidir completa, incluso compartiendo veintitres caracteres.
    """
    credenciales = Credenciales(MAPEO_DE_PRUEBA)
    assert credenciales.identificar(CLAVE_ADMIN + "-extension") is None
    assert credenciales.identificar(CLAVE_ADMIN[:-1]) is None


def test_la_comparacion_de_claves_usa_tiempo_constante(monkeypatch: pytest.MonkeyPatch) -> None:
    """La comparacion pasa por `hmac.compare_digest`, una vez por clave.

    **Que se afirma aqui y que no.** El tiempo constante no se puede **medir**
    en una prueba: seria una medida de ruido con falsos negativos. Lo que si se
    puede afirmar es el mecanismo -que la comparacion es `compare_digest` y no
    `==`- y que se recorre **cada** clave aunque una ya haya coincidido.

    Las dos cosas que se comprueban son fallos reales que el codigo puede
    tener:

      - `==` en lugar de `compare_digest` filtra el prefijo por temporizacion:
        el tiempo de respuesta depende de cuantos caracteres iniciales
        coinciden, y un atacante recupera la clave prefijo a prefijo, un byte
        por peticion. Es invisible en una prueba de comportamiento -el
        resultado es el mismo-, asi que se observa el mecanismo con un espia.
      - Salir en la primera coincidencia hace que el tiempo dependa de la
        posicion de la clave dentro del mapa y de si existe. Con el espia se
        ve cuantas comparaciones se hicieron: una por clave, ganara o no.
    """
    llamadas: list[tuple[str, str]] = []
    original = hmac.compare_digest

    def espia(candidata: str, recibida: str) -> bool:
        llamadas.append((candidata, recibida))
        return original(candidata, recibida)

    monkeypatch.setattr(hmac, "compare_digest", espia)
    # La clave que coincide es la **primera** del mapa: con salida temprana
    # habria una sola comparacion en lugar de dos. (Con la coincidencia en la
    # ultima posicion las dos versiones harian el mismo numero de
    # comparaciones y la prueba no distinguiria nada -se comprobo.)
    credenciales = Credenciales({CLAVE_ADMIN: "admin", CLAVE_LECTOR: "reader"})
    identidad = credenciales.identificar(CLAVE_ADMIN)
    assert identidad is not None
    assert identidad.rol is Rol.ADMIN
    assert len(llamadas) == 2, (
        f"se hicieron {len(llamadas)} comparaciones para 2 claves: "
        "la busqueda sale antes de recorrer la lista completa"
    )
    assert (CLAVE_ADMIN, CLAVE_ADMIN) in llamadas
    assert (CLAVE_LECTOR, CLAVE_ADMIN) in llamadas


def test_clave_ausente_e_clave_invalida_no_se_distinguen() -> None:
    """Las dos deben dar `None`: quien llama no puede enumerar que claves existen."""
    credenciales = Credenciales(MAPEO_DE_PRUEBA)
    assert credenciales.identificar(None) is None
    assert credenciales.identificar("") is None
    assert credenciales.identificar(CLAVE_LECTOR + "-casi") is None
    # Y ninguna devuelve Identidad con rol leido de un mapa vacio.
    assert Credenciales({}).identificar(CLAVE_LECTOR) is None


def test_la_jerarquia_de_roles_es_la_declarada() -> None:
    assert Rol.ADMIN.puede(Rol.OPERATOR) is True
    assert Rol.ADMIN.puede(Rol.READER) is True
    assert Rol.OPERATOR.puede(Rol.READER) is True
    assert Rol.OPERATOR.puede(Rol.ADMIN) is False
    assert Rol.READER.puede(Rol.OPERATOR) is False
    assert Rol.READER.puede(Rol.ADMIN) is False


def test_credencial_de_peticion_acepta_las_dos_cabeceras() -> None:
    credenciales = Credenciales(MAPEO_DE_PRUEBA)
    por_cabecera = credencial_de_peticion(credenciales, CLAVE_LECTOR, None)
    assert por_cabecera is not None and por_cabecera.rol is Rol.READER
    por_bearer = credencial_de_peticion(credenciales, None, f"Bearer {CLAVE_ADMIN}")
    assert por_bearer is not None and por_bearer.rol is Rol.ADMIN
    # El esquema no distingue mayusculas y se admiten espacios de sobra.
    minusculas = credencial_de_peticion(credenciales, None, f"bearer   {CLAVE_LECTOR}  ")
    assert minusculas is not None and minusculas.rol is Rol.READER
    con_espacios = credencial_de_peticion(credenciales, f"  {CLAVE_ADMIN}  ", None)
    assert con_espacios is not None and con_espacios.rol is Rol.ADMIN


def test_credencial_de_peticion_rechaza_esquema_ajeno_duplicado_y_vacio() -> None:
    credenciales = Credenciales(MAPEO_DE_PRUEBA)
    assert credencial_de_peticion(credenciales, None, f"Basic {CLAVE_ADMIN}") is None
    assert credencial_de_peticion(credenciales, None, "Bearer") is None
    assert credencial_de_peticion(credenciales, None, "Bearer    ") is None
    # Dos cabeceras con valores distintos: se rechaza en lugar de preferir una en
    # silencio, porque preferir daria un comportamiento que el cliente no ve.
    assert credencial_de_peticion(credenciales, CLAVE_LECTOR, f"Bearer {CLAVE_ADMIN}") is None
    # Y sin nada de nada.
    assert credencial_de_peticion(credenciales, None, None) is None
    # Con la autenticacion desactivada tampoco se identifica a nadie.
    apagadas = Credenciales({})
    assert credencial_de_peticion(apagadas, CLAVE_ADMIN, None) is None


def test_roles_de_claves_distintos_y_ordenados() -> None:
    credenciales = Credenciales({CLAVE_ADMIN: "admin", CLAVE_LECTOR: "reader", CLAVE_OPERARIO: "operator"})
    assert credenciales.roles_de_claves() == ["admin", "operator", "reader"]
    # Sin valores: la funcion es para el arranque y las pruebas, no para filtrar.
    assert CLAVE_ADMIN not in str(credenciales.roles_de_claves())


# ------------------------------------------------ unidad: configuracion y redaccion


def test_el_validador_rechaza_rol_desconocido_y_clave_vacia() -> None:
    """Un rol inventado se para **al arrancar**, no en la primera peticion.

    Si se aceptara en silencio, el fallo apareceria lejos de donde se declaro y
    con un mensaje que no explicaria nada.
    """
    with pytest.raises(ValidationError, match="rol de API no reconocido"):
        Settings(api_keys={CLAVE_ADMIN: "superadmin"})
    with pytest.raises(ValidationError, match="clave de API vacia"):
        Settings(api_keys={"   ": "admin"})


#: Variables de entorno que `registrar_secretos` tambien cuenta. Se borran en las
#: pruebas de redaccion para que el resultado mida el codigo y no el entorno de
#: la maquina: con `AI_SWE_MODEL_API_KEY` puesta, el recuento dejaria de ser el
#: de las claves de API.
SECRETOS_DEL_ENTORNO = ("AI_SWE_MODEL_API_KEY", "AI_SWE_LANGFUSE_SECRET_KEY", "AI_SWE_LANGFUSE_PUBLIC_KEY")


@pytest.fixture
def _sin_otros_secretos(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in SECRETOS_DEL_ENTORNO:
        monkeypatch.delenv(variable, raising=False)


def test_las_claves_de_api_se_registran_en_el_redactor(
    _sin_otros_secretos: None,
) -> None:
    """Una clave registrada sale `[REDACTED]` aunque acabe en un log.

    Es la segunda linea de defensa: la primera es no escribirla, y un log es
    justo donde eso se olvida.
    """
    clear_registered_secrets()
    try:
        ajustes = Settings(api_keys={CLAVE_LECTOR: "reader", CLAVE_ADMIN: "admin"})
        assert ajustes.registrar_secretos() == 2
        texto = f"peticion rechazada: la clave {CLAVE_LECTOR} no coincide"
        redactado = redact(texto)
        assert CLAVE_LECTOR not in redactado
        assert "[REDACTED]" in redactado
        # Y registrar dos veces no duplica ni rompe.
        assert ajustes.registrar_secretos() == 2
        assert ajustes.api_keys == {CLAVE_LECTOR: "reader", CLAVE_ADMIN: "admin"}
    finally:
        clear_registered_secrets()


def test_una_clave_corta_no_se_registra(_sin_otros_secretos: None) -> None:
    """El redactor tiene un minimo de longitud, y las claves cortas no lo pasan.

    Redactar cualquier cadena de tres caracteres destruiria el texto: la palabra
    "abc" aparece en demasiados sitios innocuos. La clave corta **sigue siendo
    valida** para autenticar -el minimo es del redactor, no de `Credenciales`-, lo
    que se afirma aqui es solo que no se registra.
    """
    clear_registered_secrets()
    try:
        ajustes = Settings(api_keys={CLAVE_CORTA: "reader"})
        assert ajustes.registrar_secretos() == 0
        credenciales = Credenciales(ajustes.api_keys)
        assert credenciales.identificar(CLAVE_CORTA) is not None
    finally:
        clear_registered_secrets()


# ------------------------------------------------- HTTP: autenticacion desactivada


def test_la_autenticacion_esta_desactivada_por_defecto(cliente_sin_auth) -> None:
    """El estado por defecto, comprobado por hechos observables.

    `activa is False` solo no valdria: es un detalle interno. Lo que de verdad
    distingue "desactivada" de "activada" es que una peticion **sin clave llega
    al manejador**, asi que se afirma sobre respuestas 200/202. Si alguien
    encendiera la autenticacion por defecto, estas peticiones darian 401.
    """
    assert cliente_sin_auth.app.state.credenciales.activa is False
    assert cliente_sin_auth.get("/health").status_code == 200
    assert cliente_sin_auth.get("/runs").status_code == 200
    assert cliente_sin_auth.get("/projects").status_code == 200


def test_sin_autenticacion_se_puede_crear_una_ejecucion(cliente_sin_auth, repo) -> None:
    """El comportamiento previo, intacto: crear ejecucion sin ninguna clave."""
    respuesta = cliente_sin_auth.post(
        "/runs",
        json={"instruction": "corrige f", "options": {"repo_path": str(repo)}},
    )
    assert respuesta.status_code == 202
    assert respuesta.json()["run_id"]


# ------------------------------------------------------- HTTP: autenticacion activa

#: Todos los endpoints protegidos. Si la autenticacion esta activa, una peticion
#: sin clave debe ser 401 **antes** de mirar el cuerpo: ni el formato del audio ni
#: la validez de la decision llegan a comprobarse, y por eso `/transcriptions` va
#: con un fichero de tipo rechazable a proposito -si diera 415, la autenticacion
#: se estaria saltando-.
PROTEGIDOS = [
    ("get", "/projects", {}),
    ("get", "/projects/no-existe", {}),
    ("get", "/runs", {}),
    ("get", "/runs/no-existe", {}),
    ("post", "/transcriptions", {"files": {"audio": ("a.txt", b"x", "text/plain")}}),
    ("post", "/runs", {"json": {"instruction": "corrige f"}}),
    ("post", "/runs/x/confirm-requirements", {"json": {"decision": "approved"}}),
    ("post", "/runs/x/approve", {"json": {"decision": "approved"}}),
    ("post", "/runs/x/cancel", {}),
    ("get", "/runs/x/events", {"params": {"timeout_s": 1}}),
]


@pytest.mark.parametrize(("metodo", "ruta", "kwargs"), PROTEGIDOS, ids=[fila[1] for fila in PROTEGIDOS])
def test_sin_clave_los_endpoints_protegidos_responden_401(
    cliente_con_auth, metodo: str, ruta: str, kwargs: dict
) -> None:
    respuesta = cliente_con_auth.request(metodo.upper(), ruta, **kwargs)
    assert respuesta.status_code == 401, f"{metodo.upper()} {ruta} dejo pasar sin clave"


def test_health_sigue_abierto_con_autenticacion_activada(cliente_con_auth) -> None:
    """El health check de infraestructura tiene que poder llegar sin credenciales.

    Un balanceador que recibe 401 marca el servicio caido y lo quita de rotacion:
    la autenticacion habria convertido una comprobacion de vida en un fallo.
    """
    assert cliente_con_auth.get("/health").status_code == 200
    cuerpo = cliente_con_auth.get("/health").json()
    assert cuerpo["status"] == "ok"


def test_clave_invalida_y_clave_ausente_dan_el_mismo_error(cliente_con_auth) -> None:
    """El mensaje no puede usarse para enumerar que claves existen.

    Si el 401 de "clave invalida" dijera algo distinto del de "no mandaste nada",
    un atacante sabria si una clave candidata es real solo leyendo la respuesta.
    """
    sin_clave = cliente_con_auth.get("/runs")
    con_clave_invalida = cliente_con_auth.get("/runs", headers={"X-API-Key": CLAVE_INVALIDA})
    assert sin_clave.status_code == con_clave_invalida.status_code == 401
    assert sin_clave.json()["detail"] == con_clave_invalida.json()["detail"]
    # Y ninguna de las dos respuestas repite la clave recibida.
    assert CLAVE_INVALIDA not in con_clave_invalida.text


def test_dos_cabeceras_distintas_se_rechazan(cliente_con_auth) -> None:
    """ Dos cabeceras validas pero distintas: 401, no "gana una".

    Preferir una en silencio daria un comportamiento que depende de un detalle que
    el cliente no ve, y un fallo asi es caro de depurar.
    """
    respuesta = cliente_con_auth.get(
        "/runs",
        headers={"X-API-Key": CLAVE_LECTOR, "Authorization": f"Bearer {CLAVE_ADMIN}"},
    )
    assert respuesta.status_code == 401


#: Matriz endpoint x rol. Los numeros son los estados observables, y varios son a
#: proposito **exitos parciales**: un 404 o un 415 significa que la autenticacion
#: paso y el manejador siguio -la ejecucion o el proyecto no existen, o el formato
#: del audio no vale-, que es justo la senal de que el rol alcanzo. Un 403, en
#: cambio, es el rol rechazado.
def _matriz(repo: Path):
    audio = {"files": {"audio": ("a.txt", b"x", "text/plain")}}
    return [
        ("get", "/health", {}, {"reader": 200, "operator": 200, "admin": 200}),
        ("get", "/runs", {}, {"reader": 200, "operator": 200, "admin": 200}),
        ("get", "/projects", {}, {"reader": 200, "operator": 200, "admin": 200}),
        ("get", "/runs/no-existe", {}, {"reader": 404, "operator": 404, "admin": 404}),
        ("post", "/transcriptions", audio, {"reader": 403, "operator": 415, "admin": 415}),
        (
            "post",
            "/runs",
            {"json": {"instruction": "corrige f", "options": {"repo_path": str(repo)}}},
            {"reader": 403, "operator": 202, "admin": 202},
        ),
        (
            "post",
            "/projects",
            {"json": {"name": "matriz", "repo_path": str(repo)}},
            {"reader": 403, "operator": 403, "admin": 201},
        ),
        (
            "post",
            "/runs/x/confirm-requirements",
            {"json": {"decision": "approved"}},
            {"reader": 403, "operator": 404, "admin": 404},
        ),
        (
            "post",
            "/runs/x/approve",
            {"json": {"decision": "approved"}},
            {"reader": 403, "operator": 404, "admin": 404},
        ),
        ("post", "/runs/x/cancel", {}, {"reader": 403, "operator": 404, "admin": 404}),
        (
            "get",
            "/runs/x/events",
            {"params": {"timeout_s": 1}},
            {"reader": 404, "operator": 404, "admin": 404},
        ),
    ]


CLAVES_POR_ROL = {"reader": CLAVE_LECTOR, "operator": CLAVE_OPERARIO, "admin": CLAVE_ADMIN}


def test_la_matriz_de_roles_es_la_declarada(cliente_con_auth, repo) -> None:
    """Cada endpoint acepta exactamente los roles que la matriz dice.

    Se recorren las once filas con las tres claves y se acumulan **todos** los
    fallos, no el primero: una matriz por la mitad es inutil para arreglarla.
    """
    fallos = []
    for metodo, ruta, kwargs, esperados in _matriz(repo):
        for rol, clave in CLAVES_POR_ROL.items():
            respuesta = cliente_con_auth.request(
                metodo.upper(), ruta, headers={"X-API-Key": clave}, **kwargs
            )
            if respuesta.status_code != esperados[rol]:
                fallos.append(
                    f"{rol:9} {metodo.upper():4} {ruta:35} "
                    f"-> {respuesta.status_code}, esperado {esperados[rol]}"
                )
    assert not fallos, "la matriz de roles no se cumple:/n" + "\n".join(fallos)


# ------------------------------------------------- HTTP: la clave por query en SSE


def test_la_clave_por_query_funciona_en_el_flujo_sse(cliente_con_auth) -> None:
    """La excepcion de la query es la unica forma que tiene `EventSource` de autenticarse.

    El navegador no puede enviar cabeceras por `EventSource`; si el flujo solo
    aceptara cabeceras, el dashboard -su unico consumidor real- se quedaria fuera.

    La clave valida en la query deja pasar la auth: la ejecucion no existe, asi
    que la respuesta es **404**, no 401. El 404 es la senal de que la clave se
    acepto; un 401 aqui significaria que la excepcion es codigo muerto.
    """
    respuesta = cliente_con_auth.get(
        "/runs/no-existe/events",
        params={"api_key": CLAVE_LECTOR, "timeout_s": 1},
    )
    assert respuesta.status_code == 404
    assert "no-existe" in respuesta.json()["detail"]


def test_la_clave_por_query_no_vale_fuera_del_flujo_sse(cliente_con_auth) -> None:
    """La concesion es **solo** del flujo de eventos, y se queda ahi.

    Una clave en la URL acaba en registros de acceso, historial y proxies. Abrir
    la misma excepcion al resto de la API pondria el secreto en todos esos sitios
    a cambio de nada: cualquier cliente HTTP de verdad sabe mandar cabeceras.
    """
    for ruta in ("/runs", "/projects", "/runs/no-existe"):
        respuesta = cliente_con_auth.get(ruta, params={"api_key": CLAVE_LECTOR})
        assert respuesta.status_code == 401, f"{ruta} acepto la clave por query"


def test_el_flujo_sse_no_se_abre_con_claves_que_no_valen(cliente_con_auth) -> None:
    # Clave invalida en la query: 401.
    assert (
        cliente_con_auth.get(
            "/runs/no-existe/events", params={"api_key": CLAVE_INVALIDA, "timeout_s": 1}
        ).status_code
        == 401
    )
    # Clave invalida en la query **y** cabecera invalida: tampoco. Sin cabecera
    # valida la query se evalua, y una query invalida es 401.
    assert (
        cliente_con_auth.get(
            "/runs/no-existe/events",
            params={"api_key": CLAVE_INVALIDA, "timeout_s": 1},
            headers={"X-API-Key": "otra-clave-invalida-88"},
        ).status_code
        == 401
    )
    # Sin nada de nada: 401.
    assert (
        cliente_con_auth.get(
            "/runs/no-existe/events", params={"timeout_s": 1}
        ).status_code
        == 401
    )
    # Con cabecera valida manda ella: la query invalida se ignora y el manejador
    # sigue hasta el 404 de ejecucion inexistente.
    assert (
        cliente_con_auth.get(
            "/runs/no-existe/events",
            params={"api_key": CLAVE_INVALIDA, "timeout_s": 1},
            headers={"X-API-Key": CLAVE_LECTOR},
        ).status_code
        == 404
    )


# --------------------------------------------------------------- HTTP: auditoria


def test_la_auditoria_registra_el_actor_y_nunca_la_clave(cliente_con_auth, repo, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="ai_swe.audit"):
        respuesta = cliente_con_auth.post(
            "/runs",
            json={"instruction": "corrige f", "options": {"repo_path": str(repo)}},
            headers={"X-API-Key": CLAVE_OPERARIO},
        )
    assert respuesta.status_code == 202
    run_id = respuesta.json()["run_id"]
    lineas = [m for m in caplog.messages if "accion=ejecucion.creada" in m]
    assert len(lineas) == 1, f"la auditoria no registro la creacion: {caplog.text}"
    linea = lineas[0]
    # El actor lleva el rol y el `clave_id`: cuatro caracteres y la longitud. Se
    # afirma la forma exacta -no se llama a `_identificador`, que es la funcion
    # bajo prueba- porque un `clave_id` que llevara la clave entera pasaria una
    # comparacion consigo misma.
    assert "actor=operator:clav...len27" in linea
    assert run_id in linea
    assert CLAVE_OPERARIO not in caplog.text


def test_con_autenticacion_desactivada_la_auditoria_dice_sin_autenticar(
    cliente_sin_auth, repo, caplog
) -> None:
    with caplog.at_level(logging.INFO, logger="ai_swe.audit"):
        respuesta = cliente_sin_auth.post(
            "/runs",
            json={"instruction": "corrige f", "options": {"repo_path": str(repo)}},
        )
    assert respuesta.status_code == 202
    assert any("actor=sin-autenticar" in m for m in caplog.messages)
