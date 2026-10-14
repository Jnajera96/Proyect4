"""Autenticacion y autorizacion por clave de API (Fase 4, `AUD-06`).

**El problema.** La API no tiene ninguna capa de autenticacion: cualquiera que
alcance el puerto puede lanzar una ejecucion, y una ejecucion **escribe codigo y
ejecuta pruebas** en un worktree. Peor: `POST /runs/{id}/approve` promueve el
parche al repositorio del usuario, asi que un cliente anonimo podria -en el peor
caso- intentar que el sistema escriba en el repositorio de otro. Mientras el
sistema es local mono-usuario eso es un riesgo teorico; en el momento de abrirlo
deja de serlo.

**Como se apaga y se enciende.** La autenticacion esta **desactivada por
defecto**: sin claves declaradas, la API se comporta exactamente como antes y el
desarrollo local no cambia. Declarar al menos una clave en `AI_SWE_API_KEYS` la
enciende para toda la API, menos `/health` (los health checks de infraestructura
tienen que poder llegar sin credenciales, o el balanceador marca el servicio como
caido).

**El diseno, y lo que deliberadamente NO es.**

  - **Clave en cabecera, no en cookie.** No hay navegador de por medio salvo el
    dashboard propio; una cookie hablaria de sesiones y de CSRF, y aqui no hay
    sesion que mantener. Se acepta `X-API-Key: <clave>` y
    `Authorization: Bearer <clave>`.
  - **Rol con la clave, no con el usuario.** No hay usuarios: hay claves. Cada
    clave declara el rol que le corresponde, asi una clave filtrada concede lo
    minimo y revocarla es borrarla del mapa.
  - **Comparacion en tiempo constante.** `hmac.compare_digest`, no `==`. Con
    `==` el tiempo de respuesta depende de cuantos caracteres iniciales coinciden,
    y eso convierte la pantalla de login en un oraculo: un atacante recupera la
    clave prefijo a prefijo, un byte por peticion. Es el defecte clasico y es
    gratis de evitar.
  - **Nunca se devuelve la clave.** Ni en el 401 ni en el 403 ni en un log. El
    mensaje dice que falta o que no vale, nunca cual era. Y como las claves se
    registran en el redactor central, si alguna acaba en un log sale `[REDACTED]`.

**Que autoriza cada rol.** `admin` todo. `operator` el ciclo de vida de
ejecuciones, que incluye aprobar -la accion mas sensible-. `reader` solo lectura.
Registrar un proyecto es `admin`: un proyecto fija el `repo_path` contra el que se
ejecutara, y con el alcance amplio eso es elegir sobre que repositorio se escribe.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from fastapi import Header

#: Roles reconocidos. Cerrada a proposito: un rol inventado se aceptaria en
#: silencio y fallaria despues, lejos de donde se declaro.
ROLES_VALIDOS = frozenset({"admin", "operator", "reader"})

#: Orden de poder. Un rol puede hacer lo suyo y lo de los anteriores.
_JERARQUIA = {"reader": 0, "operator": 1, "admin": 2}


class Rol(str, Enum):
    """Rol de una clave de API."""

    ADMIN = "admin"
    OPERATOR = "operator"
    READER = "reader"

    @property
    def nivel(self) -> int:
        return _JERARQUIA[self.value]

    def puede(self, minimo: "Rol") -> bool:
        """`True` si este rol alcanza o supera `minimo`."""
        return self.nivel >= minimo.nivel


@dataclass(frozen=True)
class Identidad:
    """Quien hace la peticion. Se propaga a los manejadores y a la auditoria.

    `clave_id` es los **primeros caracteres** de la clave, no la clave: basta para
    saber que clave actuo en un registro de auditoria sin dejar el secreto
    escrito. La clave completa no se guarda en ningun sitio de este modulo.
    """

    rol: Rol
    clave_id: str

    def puede(self, minimo: Rol) -> bool:
        return self.rol.puede(minimo)


class Credenciales:
    """Mapa clave -> rol, con busqueda en tiempo constante.

    **Por que esta clase y no un dict.** Un `dict` busca por hash: el tiempo que
    tarda en fallar una clave depende de cuantas colisiones recorrio, y sobre todo
    `clave in diccionario` seguido de indexar es patronal. Aqui se recorre la
    lista completa comparando **cada** clave con `compare_digest`, de modo que el
    tiempo es el mismo haya o no coincidencia, y no depende de la posicion. Con
    pocas claves -que es el caso previsto- el coste es irrelevante.
    """

    def __init__(self, claves: Mapping[str, str]) -> None:
        self._pares: tuple[tuple[str, Rol], ...] = tuple(
            (clave, Rol(rol)) for clave, rol in claves.items()
        )
        # `True` si no hay ni una clave: la autenticacion esta desactivada.
        self._activa = bool(self._pares)

    @property
    def activa(self) -> bool:
        return self._activa

    @property
    def numero_de_claves(self) -> int:
        return len(self._pares)

    def identificar(self, clave: str | None) -> Identidad | None:
        """Devuelve la identidad de `clave`, o `None` si no es valida.

        `None` tambien es la respuesta para una clave ausente, y a proposito: quien
        llama no puede distinguir "no mandaste nada" de "esto no existe", que es
        justo lo que evita enumerar que claves son validas.
        """
        if not clave or not self._pares:
            return None
        # Se recorre la lista **completa** sin salir en la coincidencia, y es a
        # proposito: es lo unico que hace cierto el "el tiempo es el mismo" del
        # docstring de la clase. Con una salida temprana, una clave que coincida
        # pronto responde antes que una que no coincida, y esa diferencia -aunque
        # pequena- tambien es informacion. Con pocas claves, que es el caso
        # previsto, el coste de no salir es irrelevante.
        identidad: Identidad | None = None
        for candidata, rol in self._pares:
            if hmac.compare_digest(candidata, clave):
                identidad = Identidad(rol=rol, clave_id=_identificador(candidata))
        return identidad

    def roles_de_claves(self) -> list[str]:
        """Roles distintos declarados. Para el arranque y las pruebas, sin valores."""
        return sorted({rol.value for _, rol in self._pares})


def _identificador(clave: str) -> str:
    """Referencia corta y estable de una clave, para auditoria.

    Los cuatro primeros caracteres mas la longitud: suficiente para saber **que**
    clave actuo (y distinguir dos claves que comparten prefijo), insuficiente para
    reconstruirla. La clave entera no sale de `Credenciales`.
    """
    if len(clave) <= 4:
        return f"len{len(clave)}"
    return f"{clave[:4]}...len{len(clave)}"


def credenciales_de(settings) -> Credenciales:
    """Construye las credenciales desde los ajustes validados."""
    return Credenciales(settings.api_keys)


def credencial_de_peticion(
    credenciales: Credenciales,
    x_api_key: str | None,
    authorization: str | None,
) -> Identidad | None:
    """Extrae la clave de las dos cabeceras admitidas y la identifica.

    Se acepta `X-API-Key` y `Authorization: Bearer`. Si llegan las dos con valores
    distintos se rechaza: preferir una en silencio daria un comportamiento que
    depende de un detalle que el cliente no ve, y un fallo asi es caro de depurar.
    """
    if x_api_key and authorization:
        return None
    if x_api_key:
        return credenciales.identificar(x_api_key.strip())
    if authorization:
        esquema, _, resto = authorization.partition(" ")
        if esquema.lower() != "bearer" or not resto.strip():
            return None
        return credenciales.identificar(resto.strip())
    return None
