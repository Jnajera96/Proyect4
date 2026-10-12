"""Pruebas de la capa HTTP.

Dos pruebas son las que sostienen el diseno con navegador de por medio:

  - `test_crear_responde_antes_de_ejecutar`: `POST /runs` devuelve el `run_id`
    **antes** de que la ejecucion ocurra. Sin eso el cliente no puede suscribirse
    al progreso, y el flujo SSE solo puede reproducir.
  - `test_una_instruccion_de_voz_sin_confirmar_es_rechazada`: demuestra que `RF-03`
    —el audio crudo nunca llega al Supervisor— se hace cumplir **en el contrato**,
    no en un `if` del manejador que alguien puede borrar sin que nada lo note.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from ai_swe.api import crear_app
from ai_swe.state import RunStore
from ai_swe.stt import FakeAdapter

AUDIO = b"\x1a\x45\xdf\xa3" + b"\x00" * 512
TERMINALES = {"completed", "failed", "needs_human", "cancelled"}


def esperar(cliente: TestClient, run_id: str, timeout: float = 20.0) -> dict:
    """Espera a que la ejecucion termine **por el flujo de eventos**.

    No se sondea el estado: la senal de fin del contrato es el evento `run.done`.
    Sondear el estado tenia dos problemas reales. El primero, que el punto de
    control puede ser terminal antes de que el indice se sincronice, asi que una
    consulta inmediata veia datos obsoletos. El segundo, mas grave: el flujo SSE
    cerraba al ver el indice en terminal, que se sincroniza **antes** de escribir
    los eventos, de modo que el cliente perdia `run.status`, `run.report` y
    `run.done`. Esperar al evento es lo que hace un navegador de verdad.
    """
    with cliente.stream(
        "GET", f"/runs/{run_id}/events", params={"timeout_s": timeout}
    ) as flujo:
        for linea in flujo.iter_lines():
            if linea.strip() == "event: run.done":
                break
    return cliente.get(f"/runs/{run_id}").json()


@pytest.fixture
def cliente(tmp_path):
    store = RunStore(tmp_path / "estado.db")
    app = crear_app(store=store, stt=FakeAdapter(texto="corrige el error de parseo"))
    try:
        with TestClient(app) as c:
            yield c
    finally:
        store.close()


# ------------------------------------------------------------- puertas humanas


def _esperar_estado(cliente: TestClient, run_id: str, objetivo: str, timeout: float) -> dict:
    limite = time.perf_counter() + timeout
    cuerpo = cliente.get(f"/runs/{run_id}").json()
    while time.perf_counter() < limite:
        cuerpo = cliente.get(f"/runs/{run_id}").json()
        if cuerpo["status"] == objetivo:
            return cuerpo
        time.sleep(0.02)
    raise AssertionError(f"{run_id} no llego a '{objetivo}': se quedo en '{cuerpo['status']}'")


def _esperar_reposo(
    cliente: TestClient, run_id: str, *, excluir: str | None = None, timeout: float = 20.0
) -> dict:
    """Espera a un estado de reposo: terminal o una puerta humana.

    `excluir` descarta un estado de reposo concreto. Hace falta porque el trabajador
    reanuda de forma **asincrona**: justo despues de `POST /approve` el estado sigue
    siendo el de la puerta que se acaba de responder, y sin excluirlo la espera
    devolveria ese mismo estado sin que la reanudacion hubiera ocurrido.
    """
    limite = time.perf_counter() + timeout
    cuerpo = cliente.get(f"/runs/{run_id}").json()
    while time.perf_counter() < limite:
        cuerpo = cliente.get(f"/runs/{run_id}").json()
        estado = cuerpo["status"]
        en_reposo = estado in TERMINALES or estado.startswith("awaiting_")
        if en_reposo and estado != excluir:
            return cuerpo
        time.sleep(0.02)
    raise AssertionError(f"{run_id} no llego a un estado de reposo: '{cuerpo['status']}'")


def confirmar_requisitos(cliente: TestClient, run_id: str, timeout: float = 20.0) -> dict:
    """Confirma la puerta de requisitos (M2, item 3) y espera al siguiente reposo.

    **Por que sondea el estado y no el flujo de eventos.** Una ejecucion de M2 tiene
    **dos** altos humanos, y el flujo SSE replaya los eventos desde el principio
    cuando no recibe `Last-Event-ID`: esperar `run.done` a secas devolveria el
    primero de ellos otra vez. El estado es la fuente autoritativa de "donde esta
    ahora", y es lo que hace falta para encadenar dos esperas.

    Se usa el endpoint de requisitos, que es distinto del de aprobacion final.
    Aunque para el cliente ambas puertas son "hay una decision pendiente", el
    contrato HTTP las separa para evitar que se responda a la puerta equivocada.
    """
    pausa = "awaiting_human_requirements_confirmation"
    _esperar_estado(cliente, run_id, pausa, timeout)
    respuesta = cliente.post(
        f"/runs/{run_id}/confirm-requirements", json={"decision": "approved"}
    )
    assert respuesta.status_code == 200, respuesta.text
    return _esperar_reposo(cliente, run_id, excluir=pausa, timeout=timeout)


# -------------------------------------------------------------------- salud


def test_health_responde(cliente) -> None:
    r = cliente.get("/health")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["fase"] == "M3"
    assert cuerpo["stt"] is True


# -------------------------------------------------------------- transcripcion


def test_transcribir_devuelve_texto_con_metadatos(cliente) -> None:
    r = cliente.post("/transcriptions", files={"audio": ("i.webm", AUDIO, "audio/webm")})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["text"]
    assert cuerpo["language"] == "es"
    assert 0.0 <= cuerpo["confidence"] <= 1.0
    assert cuerpo["duration_s"] > 0
    assert cuerpo["provider"].startswith("fake:")


def test_transcribir_no_crea_ninguna_ejecucion(cliente) -> None:
    """`RF-02`: la transcripcion es un paso previo, no una ejecucion."""
    antes = cliente.get("/runs").json()
    cliente.post("/transcriptions", files={"audio": ("i.webm", AUDIO, "audio/webm")})
    assert cliente.get("/runs").json() == antes


def test_audio_vacio_es_rechazado(cliente) -> None:
    r = cliente.post("/transcriptions", files={"audio": ("i.webm", b"", "audio/webm")})
    assert r.status_code == 422


# --------------------------------------------------------------- asincronia


def test_crear_responde_antes_de_ejecutar(cliente) -> None:
    """El cliente recibe el `run_id` de inmediato, no cuando la ejecucion termina.

    Es la condicion que hace posible el progreso en vivo: sin el identificador
    antes de tiempo, no hay nada a lo que suscribirse.
    """
    t0 = time.perf_counter()
    r = cliente.post("/runs", json={"instruction": "Analiza el proyecto y corrige el error."})
    transcurrido = time.perf_counter() - t0

    assert r.status_code == 202
    assert r.json()["run_id"]
    assert transcurrido < 1.0, f"la creacion bloqueo {transcurrido:.2f}s"
    # El estado devuelto es el inicial, no el final: la ejecucion aun no ocurrio.
    assert r.json()["status"] == "planned"
    assert r.json()["final_report"] is None


class WorkerQueNoEjecuta:
    """Trabajador de prueba que registra el encargo y no ejecuta nada.

    Permite comprobar de forma **determinista** que la API delega en lugar de
    ejecutar. Sin esto, la unica forma de detectarlo seria medir el tiempo, y un
    umbral de tiempo o es tan flojo que no caza la regresion, o es tan ajustado que
    falla solo en una maquina cargada.
    """

    def __init__(self) -> None:
        self.encargos: list[str] = []

    def submit(self, run_id: str) -> None:
        self.encargos.append(run_id)

    def submit_resume(self, run_id: str, decision) -> None:
        self.encargos.append(run_id)

    def shutdown(self, wait: bool = True) -> None:
        pass


def test_la_api_delega_la_ejecucion_en_el_trabajador(tmp_path) -> None:
    """La API **encola**, no ejecuta. Es la decision `DEC-11` comprobada."""
    store = RunStore(tmp_path / "estado.db")
    try:
        trabajador = WorkerQueNoEjecuta()
        app = crear_app(store=store, worker=trabajador)
        with TestClient(app) as c:
            r = c.post("/runs", json={"instruction": "Analiza el proyecto"})
            assert r.status_code == 202
            run_id = r.json()["run_id"]

            assert trabajador.encargos == [run_id], "la API no encargo la ejecucion"
            # Y no se ejecuto: sigue en `planned`, sin punto de control.
            assert c.get(f"/runs/{run_id}").json()["status"] == "planned"
            assert c.get(f"/runs/{run_id}").json()["interpretation"] is None
    finally:
        store.close()


def test_el_progreso_se_emite_por_nodo(cliente) -> None:
    """Los eventos describen el avance real, nodo a nodo, no solo el resultado.

    Desde F11 (AUD-11) el avance por nodo se expresa con **hitos nombrados**
    (`requirements.completed`, ...) y no con el generico `run.step`, que se retiro.
    Un nodo sin hito propio (como `researcher`) no emite evento: su avance queda en
    el punto de control y en `GET /runs/{id}`.
    """
    creada = cliente.post("/runs", json={"instruction": "Analiza el proyecto y corrige el error."})
    run_id = creada.json()["run_id"]

    with cliente.stream("GET", f"/runs/{run_id}/events") as s:
        tipos = [
            linea.split(":", 1)[1].strip()
            for linea in s.iter_lines()
            if linea.startswith("event:")
        ]

    assert tipos[0] == "run.created"
    assert "run.started" in tipos
    # El progreso por nodo llega como hitos nombrados, no como `run.step`.
    assert "requirements.completed" in tipos, f"no se emitio el hito de requisitos: {tipos}"
    assert "run.step" not in tipos, f"volvio el evento heredado run.step: {tipos}"
    assert tipos[-1] == "run.done"


def test_los_pasos_nombran_el_nodo_ejecutado(cliente) -> None:
    creada = cliente.post("/runs", json={"instruction": "¿Dónde se valida el token?"})
    run_id = creada.json()["run_id"]
    confirmar_requisitos(cliente, run_id)
    with cliente.stream("GET", f"/runs/{run_id}/events") as s:
        cuerpo = "".join(s.iter_lines())

    compacto = cuerpo.replace(" ", "")
    # Los hitos por nodo llevan el nombre del nodo en `data.node`.
    assert '"node":"interpret"' in compacto
    # `plan` no tiene hito si la instruccion es una pregunta (no planifica substeps
    # de codigo); el hito que si se emite siempre tras interpretar es el de
    # requisitos, que ya se comprueba arriba. Aqui se verifica que el `data` del
    # hito lleva el nodo, que es lo que permite mapear evento -> nodo.
    assert "requirements.completed" in cuerpo


def test_last_event_id_reanuda_solo_lo_que_falta(cliente) -> None:
    """Reconexion de un navegador: no repite lo ya visto ni pierde lo nuevo."""
    creada = cliente.post("/runs", json={"instruction": "Analiza el proyecto y corrige el error."})
    run_id = creada.json()["run_id"]
    esperar(cliente, run_id)

    with cliente.stream("GET", f"/runs/{run_id}/events") as s:
        todos = [l.split(":", 1)[1].strip() for l in s.iter_lines() if l.startswith("id:")]
    assert len(todos) >= 3

    corte = todos[2]
    with cliente.stream("GET", f"/runs/{run_id}/events", headers={"Last-Event-ID": corte}) as s:
        restantes = [l.split(":", 1)[1].strip() for l in s.iter_lines() if l.startswith("id:")]

    assert restantes == todos[3:], "la reanudacion no devolvio exactamente lo que faltaba"


def test_varias_ejecuciones_a_la_vez_no_se_pisan(cliente) -> None:
    """Cada ejecucion tiene su propio flujo de estado.

    Con una sola conexion SQLite compartida entre el hilo de la peticion y los
    trabajadores, esto fallaba con `SystemError: error return without exception
    set` en el `commit`.
    """
    ids = [
        cliente.post("/runs", json={"instruction": f"Analiza el módulo {i}"}).json()["run_id"]
        for i in range(6)
    ]
    estados = [confirmar_requisitos(cliente, run_id)["status"] for run_id in ids]
    assert estados == ["completed"] * 6

    # Y cada uno conserva su propia instruccion.
    textos = {cliente.get(f"/runs/{r}").json()["instruction"]["text"] for r in ids}
    assert len(textos) == 6


# -------------------------------------------------------------- ejecuciones


def test_crear_ejecucion_de_texto(cliente) -> None:
    creada = cliente.post("/runs", json={"instruction": "¿Dónde se valida el token de sesión?"})
    assert creada.status_code == 202
    final = confirmar_requisitos(cliente, creada.json()["run_id"])
    assert final["status"] == "completed"
    assert final["interpretation"]["intent"] == "question"
    assert final["final_report"] is not None


def test_una_instruccion_de_voz_sin_confirmar_es_rechazada(cliente) -> None:
    """`RF-03`, el invariante central: el audio crudo no llega al Supervisor.

    Se envia `source=voice` sin metadatos de transcripcion. El contrato
    `Instruction` lo rechaza, y el rechazo llega como 422, no como 500.
    """
    r = cliente.post("/runs", json={"instruction": "corrige el parser", "source": "voice"})
    assert r.status_code == 422
    assert "transcript_meta" in str(r.json())


def test_una_instruccion_de_voz_confirmada_se_acepta(cliente) -> None:
    r = cliente.post(
        "/runs",
        json={
            "instruction": "corrige el error de parseo",
            "source": "voice",
            "transcript_meta": {
                "provider": "fake:deterministic",
                "language": "es",
                "confidence": 0.93,
                "duration_s": 3.2,
            },
        },
    )
    assert r.status_code == 202
    cuerpo = r.json()
    assert cuerpo["instruction"]["source"] == "voice"
    assert cuerpo["instruction"]["transcript_meta"]["confidence"] == pytest.approx(0.93)


def test_instruccion_vacia_es_rechazada(cliente) -> None:
    assert cliente.post("/runs", json={"instruction": ""}).status_code == 422


def _esperar_listado(cliente: TestClient, run_ids: list[str], timeout: float = 20.0) -> list[dict]:
    """Espera a que **el listado** refleje el estado terminal de esas ejecuciones.

    `GET /runs` lee el **indice**, que se sincroniza **despues** del punto de
    control: `_persistir` llama a `store.sync` y luego escribe los eventos. Esperar
    al punto de control (`GET /runs/{id}`) y leer el indice acto seguido es una
    carrera real -el indice puede ir un instante por detras- y hacia fallar esta
    afirmacion de forma intermitente.

    Se espera a la vista que se va a afirmar, no a otra distinta.
    """
    limite = time.perf_counter() + timeout
    listado = cliente.get("/runs").json()
    while time.perf_counter() < limite:
        listado = cliente.get("/runs").json()
        por_id = {r["run_id"]: r for r in listado}
        if all(por_id.get(rid, {}).get("status") == "completed" for rid in run_ids):
            return listado
        time.sleep(0.02)
    raise AssertionError(f"el listado no reflejo el estado terminal: {listado}")


def test_listar_ejecuciones(cliente) -> None:
    creadas = [
        cliente.post("/runs", json={"instruction": "Analiza el módulo de autenticación"}).json(),
        cliente.post("/runs", json={"instruction": "¿Dónde se valida el token?"}).json(),
    ]
    for creada in creadas:
        confirmar_requisitos(cliente, creada["run_id"])

    listado = _esperar_listado(cliente, [c["run_id"] for c in creadas])
    assert len(listado) == 2
    assert {r["intent"] for r in listado} == {"inspect", "question"}
    assert all(r["status"] == "completed" for r in listado)


def test_obtener_una_ejecucion(cliente) -> None:
    creada = cliente.post("/runs", json={"instruction": "Analiza el módulo de autenticación"}).json()
    esperar(cliente, creada["run_id"])
    r = cliente.get(f"/runs/{creada['run_id']}")
    assert r.status_code == 200
    assert r.json()["run_id"] == creada["run_id"]


def test_obtener_una_ejecucion_inexistente_da_404(cliente) -> None:
    assert cliente.get("/runs/run-fantasma").status_code == 404


# ------------------------------------------------------------------ eventos


def test_los_eventos_de_una_ejecucion_inexistente_dan_404(cliente) -> None:
    assert cliente.get("/runs/run-fantasma/events").status_code == 404


def test_el_flujo_de_eventos_cierra_al_terminar(cliente) -> None:
    """Sin cierre, el navegador dejaria una conexion abierta para siempre."""
    creada = cliente.post("/runs", json={"instruction": "¿Dónde se valida el token?"}).json()
    esperar(cliente, creada["run_id"])
    with cliente.stream("GET", f"/runs/{creada['run_id']}/events") as s:
        cuerpo = "".join(s.iter_lines())
    assert "run.done" in cuerpo


# --------------------------------------------------------------- aprobacion


def test_aprobar_una_ejecucion_que_no_espera_da_409(cliente) -> None:
    creada = cliente.post("/runs", json={"instruction": "¿Dónde se valida el token?"}).json()
    # Se confirma la puerta de requisitos para que la ejecucion llegue a su fin: si
    # se dejara pausada, `approve` seria legitimo y no habria 409 que comprobar.
    confirmar_requisitos(cliente, creada["run_id"])
    r = cliente.post(f"/runs/{creada['run_id']}/approve", json={"decision": "approved"})
    assert r.status_code == 409
    assert "no esta esperando aprobacion" in r.json()["detail"]


def test_aprobar_una_ejecucion_inexistente_da_404(cliente) -> None:
    r = cliente.post("/runs/run-fantasma/approve", json={"decision": "approved"})
    assert r.status_code == 404


# ---------------------------------------------------------- frontend y CORS


def test_el_frontend_se_sirve_desde_el_mismo_origen(cliente) -> None:
    """Mismo origen significa que el frontend no necesita CORS.

    Es lo que evita una clase entera de fallos de integracion entre navegador y
    backend: preflight, credenciales y el origen `null` de `file://`.

    **Desde F11 se sirve la construccion de Vite (`frontend/dist`), no el fuente.**
    Si la construccion no existe, la aplicacion **no monta** `/app` -montar el
    directorio fuente serviria un `index.html` que apunta a `/src/main.tsx`, que el
    navegador no puede ejecutar, y el fallo apareceria como una pagina en blanco sin
    explicacion-. El no montar es deliberado, asi que esta prueba acepta dos
    resultados **explicables** y ninguno de ellos es un 200 mudo:

      - con construccion: ``/app/`` responde 200 con `text/html` (lo que se afirma);
      - sin construccion: ``/app/`` responde 404, que es la senal de que falta
        `npm run build`, y la prueba lo **dice** en lugar de darlo por bueno.

    Una prueba que pasara en los dos casos sin distinguirlos no comprobaria nada.
    """
    from ai_swe.api.app import FRONTEND_DIST

    r = cliente.get("/app/")
    if FRONTEND_DIST.is_dir():
        assert r.status_code == 200, r.text
        assert "text/html" in r.headers["content-type"]
        # El punto de entrada construido tiene que ser el de React, no un stub.
        assert '<div id="root">' in r.text or "id=\"root\"" in r.text
    else:
        assert r.status_code == 404, (
            "sin construccion en frontend/dist, /app/ debe dar 404 (falta "
            f"`npm run build`); respondio {r.status_code}"
        )


def test_sin_origenes_configurados_no_hay_cabeceras_cors(cliente) -> None:
    r = cliente.get("/health", headers={"Origin": "http://malicioso.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_los_origenes_permitidos_se_pueden_configurar(tmp_path) -> None:
    store = RunStore(tmp_path / "estado.db")
    try:
        app = crear_app(store=store, cors_origins=["http://localhost:5173"])
        with TestClient(app) as c:
            r = c.get("/health", headers={"Origin": "http://localhost:5173"})
            assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    finally:
        store.close()


# ----------------------------------------------------------------- cancelar


def test_cancelar_no_esta_implementado_y_lo_dice(cliente) -> None:
    """Devolver 501 con el motivo es mejor que un endpoint a medias que parece
    funcionar."""
    creada = cliente.post("/runs", json={"instruction": "Analiza el módulo de auth"}).json()
    r = cliente.post(f"/runs/{creada['run_id']}/cancel")
    assert r.status_code == 501
    assert "RF-16" in r.json()["detail"]


def test_cancelar_una_ejecucion_inexistente_da_404(cliente) -> None:
    assert cliente.post("/runs/run-fantasma/cancel").status_code == 404
