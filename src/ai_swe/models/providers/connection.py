"""Bounded provider catalog checks without inference or credential persistence."""

import json
import time
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ai_swe.config import is_local_model_endpoint

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
REMOTE_HOSTS = {
    "router.huggingface.co", "generativelanguage.googleapis.com",
    "openrouter.ai", "api.openai.com",
}


def local_endpoint(url: str) -> bool:
    return is_local_model_endpoint(url)


def validate_endpoint(url: str) -> str:
    parsed = urlsplit(url.strip())
    local = parsed.hostname in LOCAL_HOSTS
    if (
        not parsed.hostname or parsed.username or parsed.password
        or parsed.query or parsed.fragment
        or parsed.scheme not in ({"http", "https"} if local else {"https"})
    ):
        raise ValueError("Usa HTTPS remoto o HTTP local, sin credenciales, parámetros ni fragmentos en la URL")
    return url.strip().rstrip("/")


class ConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_base_url: str = Field(max_length=2048)
    model_name: str = Field(default="", max_length=120)
    reviewer_model: str = Field(default="", max_length=120)
    hf_token: SecretStr | None = None


def resolve_catalog_model(requested: str, catalog: list[str]) -> str | None:
    """Resolve aliases without selecting an ambiguous model, except the local combo."""
    name = requested.strip().casefold()
    for model in catalog:
        if model.casefold() == name:
            return model
    if name == "omniroute-combo":
        excluded = ("embedding", "tts", "image", "audio", "transcribe", "vision-only")
        return next((model for model in catalog
                     if not any(word in model.casefold() for word in excluded)), None)

    def parts(value: str, strip_tag: bool) -> set[str]:
        value = value.casefold()
        if strip_tag:
            value = value.split(":", 1)[0]
        return {value, value.split("/", 1)[-1], value.rsplit("/", 1)[-1]}

    for strip_tag in (False, True):
        requested_parts = parts(name, strip_tag)
        matches = [model for model in catalog if requested_parts & parts(model, strip_tag)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None
    return None


def check_connection(body: ConnectionRequest, previous: dict) -> dict:
    endpoint = validate_endpoint(body.model_base_url)
    local = local_endpoint(endpoint)
    if not local and urlsplit(endpoint).hostname not in REMOTE_HOSTS:
        return {"ok": False, "message": "La prueba remota admite Gemini, Hugging Face, OpenRouter y OpenAI.", "models": []}
    token = body.hf_token.get_secret_value().strip() if body.hf_token else ""
    if body.hf_token is None and endpoint == previous.get("model_base_url", "").rstrip("/"):
        token = previous.get("hf_token", "").strip()
    headers = {}
    if not local:
        if not token or token.lower() in {"local", "none", "null"}:
            return {"ok": False, "message": "Ingresa la clave del proveedor seleccionado.", "models": []}
        headers["Authorization"] = f"Bearer {token}"
    try:
        deadline = time.monotonic() + 5
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
            with client.stream("GET", endpoint + "/models", headers=headers) as response:
                if response.status_code in {401, 403}:
                    return {"ok": False, "message": "Clave no aceptada. Revisa la credencial de este proveedor.", "models": []}
                if response.status_code != 200:
                    return {"ok": False, "message": f"El catálogo respondió HTTP {response.status_code}. Revisa el endpoint.", "models": []}
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 1_000_000 or time.monotonic() > deadline:
                        raise ValueError("Catálogo demasiado grande")
                payload = json.loads(content)
        catalog = sorted({item["id"] for item in payload.get("data", [])
                         if isinstance(item, dict) and isinstance(item.get("id"), str)
                         and 0 < len(item["id"]) <= 120})
        models = catalog[:500]
        if not models:
            message = (
                "Ollama está activo pero no tiene modelos descargados. Ejecuta 'ollama run qwen2.5-coder' en tu terminal."
                if local and urlsplit(endpoint).port == 11434
                else "El servidor está activo pero su catálogo está vacío. Puedes guardar un identificador personalizado."
            )
            return {"ok": False, "message": message, "models": [],
                    "resolved_coder_model": None, "resolved_reviewer_model": None}
        coder = resolve_catalog_model(body.model_name, catalog) if body.model_name else models[0]
        reviewer = resolve_catalog_model(body.reviewer_model, catalog) if body.reviewer_model else coder
        # Hugging Face's suffix chooses the inference provider, not a different model.
        if urlsplit(endpoint).hostname == "router.huggingface.co":
            if coder and ":" in body.model_name:
                coder = coder.split(":", 1)[0] + ":" + body.model_name.rsplit(":", 1)[1]
            if reviewer and ":" in body.reviewer_model:
                reviewer = reviewer.split(":", 1)[0] + ":" + body.reviewer_model.rsplit(":", 1)[1]
            elif not body.reviewer_model:
                reviewer = coder
        resolved = {"resolved_coder_model": coder, "resolved_reviewer_model": reviewer}
        missing = (body.model_name and coder is None) or (body.reviewer_model and reviewer is None)
        if missing:
            return {"ok": False, "message": "El identificador no figura en el catálogo. Puedes seleccionar uno disponible o guardar tu modelo personalizado.", "models": models, **resolved}
        return {"ok": True, "message": "Conexión y catálogo comprobados. La generación se validará al ejecutar.", "models": models, **resolved}
    except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError):
        return {"ok": False, "message": "No se pudo consultar el catálogo. Comprueba que el servidor esté activo y la URL sea correcta.", "models": []}
