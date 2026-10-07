"""Redaccion centralizada de secretos (`RNF-S3`).

**Por que un componente y no una funcion por modulo.** Si cada modulo improvisa su
propia redaccion, la garantia deja de ser una garantia: basta que uno se olvide
para que una clave acabe en un log. Aqui hay un unico sitio que decide que es un
secreto y como se sustituye, y el resto del sistema lo usa.

**Que protege.** El objetivo declarado es que ningun secreto conocido aparezca en:

  - registros de log;
  - mensajes de error y excepciones serializadas;
  - eventos persistidos;
  - trazas y mensajes de observabilidad;
  - salida de depuracion;
  - representaciones de configuracion (`repr`, `model_dump`).

**Como lo protege, en tres capas.**

  1. **Valores registrados.** `register_secret()` aprende el valor literal de una
     clave. Es la unica forma fiable de redactar una clave **corta** o con formato
     raro, que ninguna heuristica reconoceria.
  2. **Patrones conocidos.** Claves con prefijo identificable (`sk-`, `ghp_`,
     `AKIA`...), cabeceras `Authorization` y tokens `Bearer`, y pares
     `clave=valor`/`"api_key": "valor"` en texto.
  3. **Marcadores.** Todo lo que el llamante marque explicitamente como secreto.

**Lo que NO hace, y es deliberado.** No intenta adivinar si una cadena cualquiera
"parece" un secreto. Una heuristica agresiva destruye informacion legitima —por
ejemplo, un identificador de 32 caracteres hexadecimales es indistinguible de un
token para una expresion regular— y un sistema de trazabilidad que redacta de mas
es tan inutil como uno que redacta de menos. Se prefiere una garantia estrecha y
verdadera a una amplia y falsa.

Uso:

    from ai_swe.security import redact, redact_deep, register_secret

    register_secret(settings.model_api_key)      # al arrancar, si existe
    log.info("respuesta del modelo: %s", redact(cuerpo))
    eventos.append(redact_deep(payload))         # estructuras anidadas
"""

from __future__ import annotations

import re
import threading
from typing import Any

# --------------------------------------------------------------------- constante

REDACTADO = "[REDACTED]"

# Longitud minima para registrar un valor literal como secreto. Por debajo de
# esto, el valor es tan corto que redactarlo en texto libre destruiria el idioma
# (por ejemplo, la palabra "es" o un numero). Los patrones con prefijo siguen
# funcionando para valores cortos con formato reconocible.
LONGITUD_MINIMA_SECRETO = 6

# --------------------------------------------------------------------- patrones

# Claves con prefijo o forma reconocible. Se ancla en un limite de palabra para no
# partir identificadores que contienen la subcadena por casualidad.
_PATRONES_PREFIJO: tuple[re.Pattern[str], ...] = (
    # OpenAI / Anthropic / OpenRouter: sk-..., sk-ant-..., sk-or-v1-...
    re.compile(r"\bsk-(?:ant-|or-|proj-|live-|test-)?[A-Za-z0-9_\-]{16,}"),
    # GitHub
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    # AWS
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Google
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    # Hugging Face
    re.compile(r"\bhf_[A-Za-z0-9]{30,}"),
    # Stripe
    re.compile(r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{16,}"),
    # Slack
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"),
)

# Cabeceras de autorizacion. Se consume TODO el valor tras `:`/`=`, incluido un
# esquema opcional (`Bearer`, `Basic`), para no dejar el token huerfano detras.
# El esquema se conserva: el diagnostico sigue viendo que se envio un Bearer.
_PATRON_AUTORIZACION = re.compile(
    r"(?i)\b(authorization|proxy-authorization)\b(\s*[:=]\s*)"
    r"((?:bearer|basic)\s+)?(\S+)"
)
_PATRON_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+([A-Za-z0-9._\-+/=]{8,})")

# Palabras que son el *esquema* de una cabecera de autorizacion, no el secreto.
# El barrido de `clave=valor` no debe borrarlas: `Authorization: Bearer` deja el
# token fuera de ese par, y lo trata la capa especifica de cabeceras.
_ESQUEMAS_AUTORIZACION = frozenset({"bearer", "basic"})

# Nombres de cabecera que gestiona la capa DEDICADA de autorizacion. El barrido
# generico de `clave=valor` debe apartarse de ellos: si tambien los capturara, una
# mutacion que rompiera la capa dedicada quedaria enmascarada por la generica y
# ninguna prueba la cazaria. Se comprobo por mutacion, y por eso existe esta
# separacion explicita. Cada capa, una responsabilidad.
_CABECERAS_DELEGADAS = frozenset({"authorization", "proxy_authorization"})

# Claves cuyo VALOR se redacta siempre, sea cual sea su forma. Es la parte que
# hace que la redaccion de estructuras no dependa de que el valor "parezca" un
# secreto. Fuente unica de verdad: la usan tanto el escaneo de texto (`redact`)
# como el recorrido de estructuras (`redact_deep`).
CLAVES_QUE_REDACTAN_VALOR: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "access_key",
        "secret_key",
        "secretkey",
        "client_secret",
        "private_key",
        "auth_token",
        "access_token",
        "refresh_token",
        "password",
        "passwd",
        "contrasena",
        "contraseña",
        "secret",
        "token",
        "credential",
        "credentials",
        "authorization",
        "proxy_authorization",
        "model_api_key",
        "langfuse_secret_key",
        "langfuse_public_key",
    }
)

# Pares clave=valor en texto. La clave puede venir con prefijo (`model_api_key`,
# `AI_SWE_MODEL_API_KEY`, `openai-secret-key`, `db.password`). Se captura el
# identificador completo y se delimita por ambos lados; la decision de "es
# sensible" se toma despues, en Python (`_nombre_es_sensible`), porque exigir en
# la expresion regular que el nombre *termine* en la palabra sensible es fragil.
# El valor puede ir entre comillas o suelto; el patron de valor suelto excluye
# `[` para no tragarse un `[REDACTED]` ya aplicado por una capa anterior.
_PATRON_CLAVE_VALOR = re.compile(
    r"(?i)([\"']?[A-Za-z_][A-Za-z0-9_.\-]{1,64}[\"']?)(\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^\s,;}\]&\[]+)"
)


def _nombre_es_sensible(nombre: str) -> bool:
    """Decide si un nombre de clave delata un secreto.

    Se acepta tanto el nombre exacto (`api_key`) como con prefijo o sufijo
    (`model_api_key`, `openai_secret_key`, `db.password`). La normalizacion pasa
    `-` y `.` a `_` para tratar las tres convenciones por igual.
    """
    normalizado = (
        nombre.strip().strip("\"'").lower().replace("-", "_").replace(".", "_")
    )
    if normalizado in CLAVES_QUE_REDACTAN_VALOR:
        return True
    partes = [p for p in normalizado.split("_") if p]
    # Palabras sueltas: `openai_secret`, `db_password`.
    if any(parte in CLAVES_QUE_REDACTAN_VALOR for parte in partes):
        return True
    # Nombres compuestos por varias partes: `AI_SWE_MODEL_API_KEY` contiene
    # `api_key`, que no aparece como palabra suelta. Se prueba cada union de
    # partes contiguas de dos en dos.
    return any(
        "_".join(partes[i : i + 2]) in CLAVES_QUE_REDACTAN_VALOR
        for i in range(len(partes) - 1)
    )

# URL con credenciales incrustadas: https://usuario:clave@host
_PATRON_URL_CON_CREDENCIALES = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)[^/\s:@]+:[^/\s:@]+@")

# ------------------------------------------------------------------ estado global

_registro_lock = threading.Lock()
_secretos_registrados: set[str] = set()


def register_secret(valor: str | None) -> bool:
    """Registra el valor literal de un secreto para que se redacte siempre.

    Devuelve `True` si se registro. Es la via fiable para valores cortos o con
    formato impredecible, que ningun patron reconoceria.

    El valor **no** se guarda en claro mas alla de este conjunto en memoria, y el
    conjunto nunca se expone ni se serializa.
    """
    if not valor or not isinstance(valor, str):
        return False
    limpio = valor.strip()
    if len(limpio) < LONGITUD_MINIMA_SECRETO:
        return False
    with _registro_lock:
        _secretos_registrados.add(limpio)
    return True


def secrets_registrados() -> int:
    """Cuantos secretos hay registrados. **Nunca** devuelve los valores.

    Se expone para poder comprobar en pruebas que el registro ocurre, sin abrir
    una via para leer los secretos.
    """
    with _registro_lock:
        return len(_secretos_registrados)


def clear_registered_secrets() -> None:
    """Olvida los secretos registrados. Uso previsto: aislamiento entre pruebas."""
    with _registro_lock:
        _secretos_registrados.clear()


# ------------------------------------------------------------------- redaccion


def redact(texto: Any) -> str:
    """Redacta secretos en una cadena de texto.

    Nunca lanza: si algo falla, devuelve la entrada convertida a texto. Una funcion
    de seguridad que rompe el registro es peor que una que redacta de menos, porque
    empuja al llamante a saltarsela.
    """
    if texto is None:
        return ""
    if not isinstance(texto, str):
        try:
            texto = str(texto)
        except Exception:  # noqa: BLE001 - nunca propagar desde aqui
            return REDACTADO
    if not texto:
        return texto

    salida = texto

    # 1. Valores registrados. Se ordena de mas largo a mas corto para que una clave
    #    que contiene a otra no deje un resto visible.
    with _registro_lock:
        conocidos = sorted(_secretos_registrados, key=len, reverse=True)
    for secreto in conocidos:
        if secreto in salida:
            salida = salida.replace(secreto, REDACTADO)

    # 2. Patrones con prefijo reconocible.
    for patron in _PATRONES_PREFIJO:
        salida = patron.sub(REDACTADO, salida)

    # 3. Pares clave=valor: se conserva el nombre de la clave, se borra el valor.
    #    Va ANTES que las cabeceras de autorizacion para que `Authorization: Bearer
    #    <token>` lo resuelva la capa especifica, que sabe conservar el esquema; si
    #    corriera despues, esta capa borraria el propio `Bearer`.
    #    Si el valor ya es el marcador (lo puso una capa anterior), no se toca: la
    #    redaccion debe ser idempotente, o el texto acabaria con dos marcas.
    salida = _PATRON_CLAVE_VALOR.sub(
        lambda m: (
            m.group(0)
            if not _nombre_es_sensible(m.group(1))
            or _nombre_delegado(m.group(1))
            or m.group(3).strip("\"'") == REDACTADO
            or m.group(3).strip("\"'").lower() in _ESQUEMAS_AUTORIZACION
            else f"{m.group(1)}{m.group(2)}{REDACTADO}"
        ),
        salida,
    )

    # 4. Cabeceras de autorizacion: se conserva el nombre de la cabecera y el
    #    esquema (`Bearer`/`Basic`), se elimina el token.
    salida = _PATRON_AUTORIZACION.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3) or ''}{REDACTADO}", salida
    )
    salida = _PATRON_BEARER.sub(lambda m: f"{m.group(1)} {REDACTADO}", salida)

    # 5. URL con credenciales incrustadas.
    salida = _PATRON_URL_CON_CREDENCIALES.sub(lambda m: f"{m.group(1)}{REDACTADO}@", salida)
    return salida


# Claves cuyo VALOR se redacta siempre, sea cual sea su forma. Es la parte que
# hace que la redaccion de estructuras no dependa de que el valor "parezca" un
# secreto.
def _clave_sensible(clave: str) -> bool:
    """Version de `_nombre_es_sensible` para claves de estructuras.

    Se mantiene como envoltorio con nombre propio porque el uso difiere: aqui la
    clave ya viene aislada de un `dict`, y no hay valor que redactar en texto.
    """
    return _nombre_es_sensible(clave)


def _nombre_delegado(nombre: str) -> bool:
    """Indica si el nombre corresponde a una capa que lo trata por separado.

    Aplica a las cabeceras de autorizacion: tienen su propio patron, que conserva
    el esquema (`Bearer`/`Basic`) y borra solo el token. El barrido generico de
    `clave=valor` debe apartarse para no dejar sin cobertura real a la capa
    dedicada.
    """
    normalizado = nombre.strip().strip("\"'").lower().replace("-", "_")
    return normalizado in _CABECERAS_DELEGADAS


def redact_deep(objeto: Any, *, _profundidad: int = 0) -> Any:
    """Redacta secretos en estructuras anidadas: `dict`, `list`, `tuple`, `set`.

    Devuelve una **copia** de la misma forma, con los valores sensibles sustituidos
    por `[REDACTED]`. No modifica la entrada.

    Se protege contra referencias circulares y contra profundidades absurdas: una
    funcion que se cuelga o desborda la pila en el camino de los errores es
    exactamente lo que no se quiere en una herramienta de seguridad.
    """
    if _profundidad > 12:
        return REDACTADO

    if isinstance(objeto, dict):
        salida: dict[Any, Any] = {}
        for clave, valor in objeto.items():
            if isinstance(clave, str) and _clave_sensible(clave):
                salida[clave] = REDACTADO
            else:
                salida[clave] = redact_deep(valor, _profundidad=_profundidad + 1)
        return salida

    if isinstance(objeto, (list, tuple, set, frozenset)):
        redactados = [redact_deep(v, _profundidad=_profundidad + 1) for v in objeto]
        if isinstance(objeto, tuple):
            return tuple(redactados)
        if isinstance(objeto, frozenset):
            return frozenset(redactados)
        if isinstance(objeto, set):
            # Un elemento redactado puede dejar de ser hashable (un dict anidado
            # se convierte en dict). En ese caso se degrada a lista: conservar la
            # forma no justifica perder la redaccion.
            try:
                return set(redactados)
            except TypeError:
                return redactados
        return redactados

    if isinstance(objeto, str):
        return redact(objeto)

    # Bytes: se redactan como cadena para que un cuerpo de peticion en binario no
    # esquive la redaccion.
    if isinstance(objeto, (bytes, bytearray)):
        return redact(bytes(objeto).decode("utf-8", errors="replace"))

    return objeto


def sanitize(objeto: Any) -> Any:
    """Aplica `redact_deep` y, si es un modelo Pydantic, parte de su `model_dump`.

    Punto de entrada unico para "quiero registrar esto sin filtrar nada". Reconoce
    modelos Pydantic sin importarlos en tiempo de importacion del modulo, para no
    acoplar la capa de seguridad a Pydantic.
    """
    volcado = getattr(objeto, "model_dump", None)
    if callable(volcado):
        try:
            return redact_deep(volcado())
        except Exception:  # noqa: BLE001 - si el volcado falla, se redacta el repr
            return redact(repr(objeto))
    if isinstance(objeto, BaseException):
        return redact(f"{type(objeto).__name__}: {objeto}")
    return redact_deep(objeto)
