"""Pruebas de la redaccion centralizada de secretos (`RNF-S3`).

**Que se comprueba y por que asi.** No basta con afirmar que `redact("api_key=x")`
devuelve `[REDACTED]`. Los modos de fallo reales de un redactor son otros:

  - que el secreto pase por un camino que nadie probo (una cabecera, una URL, un
    traceback, un `repr` de configuracion);
  - que redacte de mas y destruya informacion legitima;
  - que aplicar la redaccion dos veces deje el texto peor que aplicarla una;
  - que una excepcion dentro del propio redactor lo convierta en un punto de
    fallo del sistema.

Cada prueba intenta cubrir uno de esos modos. Las claves usadas son de fantasia:
**no hay ninguna credencial real en este fichero**, y no debe haberla nunca.
"""

from __future__ import annotations

import io
import json
import logging

import pytest
from pydantic import BaseModel, SecretStr

from ai_swe.security import (
    REDACTADO,
    clear_registered_secrets,
    install_redacting_filter,
    redact,
    redact_deep,
    register_secret,
    sanitize,
    secrets_registrados,
)

# Cadenas de fantasia. Se nombran para que sea evidente que no son reales y para
# poder buscarlas en la salida sin equivocarse.
CLAVE_FALSA = "clave-falsa-para-pruebas"
CLAVE_FALSA_CORTA = "abc123XYZ"
CLAVE_OPENAI_FALSA = "sk-proj-" + "A" * 40
CLAVE_GITHUB_FALSA = "ghp_" + "B" * 36
CLAVE_AWS_FALSA = "AKIA" + "C" * 16
BEARER_FALSO = "eyJhbGciOiJIUzI1NiJ9." + "D" * 24 + ".firma"


@pytest.fixture(autouse=True)
def _aislar_registro() -> None:
    """Cada prueba empieza sin secretos registrados.

    El registro es estado global de proceso. Sin aislarlo, una prueba que registra
    una clave dejaria a las siguientes con una redaccion que no pidieron, y el
    orden de ejecucion cambiaria el resultado.
    """
    clear_registered_secrets()
    yield
    clear_registered_secrets()


# --------------------------------------------------------------- capa 1: registro


def test_valor_registrado_se_redacta() -> None:
    assert register_secret(CLAVE_FALSA_CORTA) is True
    assert secrets_registrados() == 1
    assert redact(f"usando {CLAVE_FALSA_CORTA} ahora") == f"usando {REDACTADO} ahora"


def test_registro_rechaza_cadenas_demasiado_cortas() -> None:
    """Una cadena de 2 caracteres es indistinguible del idioma: no se registra."""
    assert register_secret("ab") is False
    assert secrets_registrados() == 0


def test_registro_rechaza_none_y_vacio() -> None:
    assert register_secret(None) is False
    assert register_secret("") is False
    assert secrets_registrados() == 0


def test_secrets_registrados_nunca_expone_valores() -> None:
    """La unica salida del registro es un contador, jamas los valores.

    Se comprueba el tipo y no el contenido: si el registro devolviera las claves,
    cualquier volcado de diagnostico se convertiria en una fuga.
    """
    register_secret(CLAVE_FALSA)
    resultado = secrets_registrados()
    assert isinstance(resultado, int)
    assert resultado == 1


# ------------------------------------------------- capa 2: patrones con prefijo


@pytest.mark.parametrize(
    "texto_con_secreto",
    [
        f"la clave es {CLAVE_OPENAI_FALSA}",
        f"token={CLAVE_GITHUB_FALSA}",
        f"AWS_ACCESS_KEY_ID={CLAVE_AWS_FALSA}",
        "google=AIza" + "E" * 35,
        "hf_" + "F" * 32,
    ],
)
def test_patrones_de_prefijo_conocido(texto_con_secreto: str) -> None:
    resultado = redact(texto_con_secreto)
    assert REDACTADO in resultado
    for fragmento in ("sk-proj-", "ghp_", "AKIA", "AIza", "hf_"):
        assert fragmento not in resultado


# ------------------------------------------------------- capa 3: clave = valor


@pytest.mark.parametrize(
    "texto",
    [
        "model_api_key=secreto123",
        'model_api_key="secreto123"',
        "model_api_key: secreto123",
        "AI_SWE_MODEL_API_KEY=secreto123",
        "{'model_api_key': 'secreto123'}",
        '{"model_api_key": "secreto123"}',
        "langfuse_secret_key=secreto123",
        "db_password=secreto123",
        "api_key=secreto123",
    ],
)
def test_pares_clave_valor(texto: str) -> None:
    """El nombre sensible puede llevar prefijo y venir citado (JSON/YAML)."""
    resultado = redact(texto)
    assert "secreto123" not in resultado
    assert REDACTADO in resultado


def test_par_clave_valor_conserva_el_nombre() -> None:
    """Se borra el valor, no la clave: el diagnostico debe seguir diciendo que era."""
    assert redact("model_api_key=secreto123") == f"model_api_key={REDACTADO}"


# ---------------------------------------------------- capa 4: cabeceras HTTP


def test_cabecera_authorization_conserva_el_esquema() -> None:
    """Se conserva `Bearer` para saber que esquema se uso; se borra el token."""
    resultado = redact(f"Authorization: Bearer {BEARER_FALSO}")
    assert BEARER_FALSO not in resultado
    assert resultado == f"Authorization: Bearer {REDACTADO}"


def test_cabecera_authorization_sin_esquema_ni_igual() -> None:
    """Prueba que AISLA la capa de cabeceras de autorizacion.

    Sin esto, la capa `Bearer` suelta y la capa `clave=valor` tapan el fallo: una
    mutacion que rompa solo la capa de cabeceras no hace caer ninguna prueba. Aqui
    el token no lleva esquema (la capa `Bearer` no puede dispararse) y va tras `:`
    (la capa `clave=valor` tampoco), de modo que **solo** la capa de cabeceras
    puede redactarlo. Verificado por mutacion: si se desactiva esa capa, esta
    prueba falla.
    """
    resultado = redact("Authorization: XyZ123tokenSinEsquemaNiIgual")
    assert "XyZ123tokenSinEsquemaNiIgual" not in resultado
    assert resultado == f"Authorization: {REDACTADO}"


def test_cabecera_basic() -> None:
    resultado = redact("Authorization: Basic dXNlcjpwYXNz")
    assert "dXNlcjpwYXNz" not in resultado
    assert resultado == f"Authorization: Basic {REDACTADO}"


def test_bearer_suelto_sin_cabecera() -> None:
    resultado = redact(f"Bearer {BEARER_FALSO}")
    assert BEARER_FALSO not in resultado


# ------------------------------------------------------ capa 5: URL con credenciales


def test_url_con_credenciales() -> None:
    resultado = redact("https://usuario:contrasena@api.example.com/v1")
    assert "contrasena" not in resultado
    assert "usuario:" not in resultado
    assert "api.example.com" in resultado


# ------------------------------------------------------------ estructuras anidadas


def test_redact_deep_dict_anidado() -> None:
    entrada = {
        "model_api_key": "secreto123",
        "nivel": {"password": "otro456", "visible": "sin-secreto"},
        "lista": ["normal", f"Bearer {BEARER_FALSO}"],
    }
    salida = redact_deep(entrada)
    assert salida["model_api_key"] == REDACTADO
    assert salida["nivel"]["password"] == REDACTADO
    assert salida["nivel"]["visible"] == "sin-secreto"
    assert salida["lista"][0] == "normal"
    assert BEARER_FALSO not in json.dumps(salida)


def test_redact_deep_no_modifica_la_entrada() -> None:
    """Devuelve una copia: redactar no puede tener efectos sobre el original."""
    entrada = {"model_api_key": "secreto123"}
    redact_deep(entrada)
    assert entrada["model_api_key"] == "secreto123"


def test_redact_deep_tuplas_y_conjuntos() -> None:
    assert redact_deep(("a", "password=x")) == ("a", f"password={REDACTADO}")
    assert redact_deep({"api_key=z"}) == {f"api_key={REDACTADO}"}


def test_redact_deep_bytes() -> None:
    salida = redact_deep({"cuerpo": b"Authorization: Bearer " + BEARER_FALSO.encode()})
    assert BEARER_FALSO not in salida["cuerpo"]


def test_redact_deep_sobrevive_a_referencia_circular() -> None:
    """Una estructura ciclica no puede colgar el redactor.

    Una funcion de seguridad que se cuelga en el camino de los errores es peor que
    una que no existe, porque empuja al llamante a saltarsela.
    """
    entrada: dict = {"model_api_key": "secreto123"}
    entrada["yo"] = entrada
    salida = redact_deep(entrada)
    assert salida["model_api_key"] == REDACTADO


# ------------------------------------------------------------ excepciones y config


def test_sanitize_excepcion() -> None:
    error = RuntimeError(f"fallo con token={CLAVE_FALSA}")
    texto = sanitize(error)
    assert CLAVE_FALSA not in texto
    assert "RuntimeError" in texto


def test_sanitize_modelo_pydantic() -> None:
    class Ajustes(BaseModel):
        model_api_key: SecretStr
        otro: str = "visible"

    salida = sanitize(Ajustes(model_api_key=SecretStr(CLAVE_FALSA)))
    assert CLAVE_FALSA not in str(salida)
    assert salida["otro"] == "visible"


def test_repr_de_configuracion_no_filtra() -> None:
    """`repr` de un modelo con `SecretStr` no debe contener el valor real."""
    from ai_swe.config import Settings

    ajustes = Settings(model_api_key=SecretStr(CLAVE_FALSA), langfuse_secret_key=SecretStr("lf-falso"))
    assert CLAVE_FALSA not in repr(ajustes)
    assert CLAVE_FALSA not in str(ajustes.model_dump())


def test_load_settings_registra_los_secretos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Al cargar la configuracion, sus secretos quedan protegidos por el redactor."""
    from ai_swe.config import load_settings

    monkeypatch.setenv("AI_SWE_MODEL_API_KEY", CLAVE_FALSA)
    monkeypatch.setenv("AI_SWE_LANGFUSE_SECRET_KEY", "lf-secreto-falso")
    ajustes = load_settings()
    # `Settings` lee `.env` si existe; se comprueba sobre los valores efectivos.
    registrados = secrets_registrados()
    assert registrados >= 1
    assert redact(f"Authorization: Bearer {ajustes.model_api_key.get_secret_value()}") == (
        f"Authorization: Bearer {REDACTADO}"
    )


# ------------------------------------------------------------- integracion logging


def _logger_con_captura() -> tuple[logging.Logger, io.StringIO]:
    flujo = io.StringIO()
    manejador = logging.StreamHandler(flujo)
    logger = logging.getLogger("prueba.redaccion")
    logger.handlers = [manejador]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    install_redacting_filter(logger)
    return logger, flujo


def test_filtro_redacta_mensaje_con_argumentos() -> None:
    """El caso que mas se olvida: `log.info("%s", clave)`.

    La clave no esta en la plantilla, esta en el argumento. El filtro tiene que
    redactar el mensaje ya formateado, no solo la plantilla.
    """
    logger, flujo = _logger_con_captura()
    register_secret(CLAVE_FALSA)
    logger.info("llamando con clave %s", CLAVE_FALSA)
    assert CLAVE_FALSA not in flujo.getvalue()
    assert REDACTADO in flujo.getvalue()


def test_filtro_redacta_dentro_de_un_traceback() -> None:
    """Un traceback arrastra valores de variables locales hasta el log."""
    logger, flujo = _logger_con_captura()
    register_secret(CLAVE_FALSA)
    try:
        raise RuntimeError(f"fallo con {CLAVE_FALSA}")
    except RuntimeError:
        logger.exception("error al llamar")
    assert CLAVE_FALSA not in flujo.getvalue()


def test_filtro_redacta_cabeceras_y_pares() -> None:
    logger, flujo = _logger_con_captura()
    logger.warning("Authorization: Bearer %s", BEARER_FALSO)
    logger.warning("api_key=otraclavefalsa123")
    salida = flujo.getvalue()
    assert BEARER_FALSO not in salida
    assert "otraclavefalsa123" not in salida


def test_instalar_filtro_es_idempotente() -> None:
    logger = logging.getLogger("prueba.idempotente")
    logger.filters = []
    primero = install_redacting_filter(logger)
    segundo = install_redacting_filter(logger)
    assert primero is segundo
    assert sum(isinstance(f, type(primero)) for f in logger.filters) == 1


# --------------------------------------------------------- garantias del redactor


def test_redaccion_es_idempotente() -> None:
    """Aplicar la redaccion dos veces no debe degradar el texto."""
    register_secret(CLAVE_FALSA)
    muestras = [
        f"Authorization: Bearer {BEARER_FALSO}",
        "model_api_key=secreto123",
        f"usando {CLAVE_FALSA}",
        CLAVE_OPENAI_FALSA,
        "https://u:c@host/x",
    ]
    for muestra in muestras:
        una_vez = redact(muestra)
        dos_veces = redact(una_vez)
        assert una_vez == dos_veces, f"no idempotente en {muestra!r}"


def test_no_redacta_texto_normal() -> None:
    """Redactar de mas destruye el diagnostico: el texto legitimo debe sobrevivir."""
    legitimos = [
        "ruta normal /var/log/app.log",
        "el nivel de log es INFO",
        "run_id=abc-123-def-456",
        "password del usuario no debe cambiar",
        "Authorization del sistema",
        "el token expiro",
        "42 pruebas en verde",
    ]
    for texto in legitimos:
        assert redact(texto) == texto, f"se redactó de más: {texto!r}"


def test_redact_nunca_lanza() -> None:
    """Un lanzamiento desde el redactor lo convertiria en un punto de fallo."""
    for valor in (None, 123, object(), b"bytes", ["lista"]):
        resultado = redact(valor)
        assert isinstance(resultado, str)
