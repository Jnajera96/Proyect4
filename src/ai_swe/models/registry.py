"""Registro explicito de proveedores.

**Por que un diccionario y no import dinamico.** Seria tentador resolver el
proveedor con `importlib.import_module(f"ai_swe.models.providers.{nombre}")` usando
el nombre que venga de la configuracion. Eso convierte un valor de configuracion en
una via de ejecucion de codigo arbitrario. Aqui el nombre solo puede resolver a una
fabrica **ya registrada**; cualquier otra cosa lanza `UnknownProviderError`.

Anadir un proveedor es anadir una entrada, no tocar el gateway.
"""

from __future__ import annotations

from collections.abc import Callable

from ai_swe.config import Settings
from ai_swe.models.contracts import ProviderConfig
from ai_swe.models.errors import ModelConfigurationError, UnknownProviderError
from ai_swe.models.providers.base import ProviderAdapter
from ai_swe.models.providers.fake import FakeModelAdapter
from ai_swe.models.providers.openai_compatible import OpenAICompatibleAdapter

AdapterFactory = Callable[[ProviderConfig], ProviderAdapter]

# Proveedores que no necesitan credencial. `fake` no toca la red; `ollama` y
# `vllm` son endpoints locales.
#
# Relacion con `config.PROVEEDORES_CON_CLAVE`: aquel responde a «¿la configuracion
# global trae clave para este proveedor?» y se usa como comprobacion previa sobre
# `Settings`. Este responde a «¿puedo construir un adapter usable sin clave?» y es
# la comprobacion autoritativa en el borde, porque conoce el adapter concreto.
# `fake` no aparece en el conjunto de configuracion porque no es un proveedor de
# usuario; por eso la comprobacion del gateway no puede delegar en aquella.
PROVEEDORES_SIN_CREDENCIALES: frozenset[str] = frozenset({"fake", "ollama", "vllm"})


def _fabrica_fake(config: ProviderConfig) -> ProviderAdapter:
    return FakeModelAdapter(name=config.name, model=config.model)


def _fabrica_openai_compatible(config: ProviderConfig) -> ProviderAdapter:
    return OpenAICompatibleAdapter(
        name=config.name,
        model=config.model,
        api_key=config.api_key.get_secret_value(),
        base_url=config.base_url,
        timeout_s=config.timeout_s,
    )


# Registro explicito. Las claves son los nombres aceptados en `AI_SWE_MODEL_PROVIDER`.
_REGISTRO: dict[str, AdapterFactory] = {
    "fake": _fabrica_fake,
    # Nombre canonico del adapter generico...
    "openai_compatible": _fabrica_openai_compatible,
    # ...y alias de endpoints conocidos que hablan el mismo protocolo. Se registran
    # para que el nombre del proveedor en la configuracion sea el que aparece en la
    # observabilidad, sin duplicar el adapter.
    "openai": _fabrica_openai_compatible,
    "ollama": _fabrica_openai_compatible,
    "vllm": _fabrica_openai_compatible,
}


def register_provider(name: str, factory: AdapterFactory) -> None:
    """Registra (o sustituye) una fabrica de adapter.

    Sustituir es deliberado: permite que una prueba inyecte un doble sin tocar el
    resto del sistema, y que un despliegue cambie un proveedor sin recompilar el
    gateway.
    """
    clave = name.strip().lower()
    if not clave:
        raise ValueError("el nombre del proveedor no puede estar vacio")
    _REGISTRO[clave] = factory


def registered_providers() -> tuple[str, ...]:
    """Nombres registrados, ordenados. Util para un mensaje de error accionable."""
    return tuple(sorted(_REGISTRO))


def requires_credentials(name: str) -> bool:
    """Si un adapter con ese nombre necesita credencial para ser usable."""
    return name.strip().lower() not in PROVEEDORES_SIN_CREDENCIALES


def build_adapter(config: ProviderConfig) -> ProviderAdapter:
    """Construye el adapter del proveedor indicado.

    Lanza `UnknownProviderError` si el nombre no esta registrado, con la lista de
    los que si lo estan: un error que no dice que se puede usar obliga a leer el
    codigo.
    """
    clave = config.name.strip().lower()
    fabrica = _REGISTRO.get(clave)
    if fabrica is None:
        raise UnknownProviderError(
            f"proveedor no registrado: {config.name!r}",
            detail=f"registrados: {', '.join(registered_providers())}",
        )
    return fabrica(config)


def provider_config_from_settings(settings: Settings) -> ProviderConfig:
    """Traduce la configuracion global a la configuracion de un adapter.

    Es el unico punto que conoce los nombres de los campos de `Settings`; el
    gateway trabaja con `ProviderConfig` y no con el entorno. Asi cambiar de donde
    viene la configuracion no toca al gateway.

    Si el proveedor exige credencial y no hay modelo configurado, **falla aqui**,
    en el borde, con un mensaje que nombra el campo. Rellenar con un valor por
    defecto silencioso mandaria una peticion a un modelo que nadie pidio.
    """
    nombre = settings.model_provider
    modelo = settings.model_name.strip()
    if not modelo:
        if requires_credentials(nombre):
            raise ModelConfigurationError(
                "falta AI_SWE_MODEL_NAME: el proveedor configurado exige un modelo",
                provider=nombre,
            )
        # Proveedores locales y el falso no necesitan un nombre concreto.
        modelo = "default"

    return ProviderConfig(
        name=nombre,
        model=modelo,
        api_key=settings.model_api_key,
        base_url=settings.model_base_url,
    )
