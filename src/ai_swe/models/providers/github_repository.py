"""GitHub HTTP adapter. Separate from domain logic and from paid model inference."""

import re

import httpx

from ai_swe.security import register_secret


def create_repository(name: str, token: str, private: bool) -> str:
    register_secret(token)
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            response = client.post(
                "https://api.github.com/user/repos",
                headers={
                    "Authorization": "Bearer " + token,
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2026-03-10",
                },
                json={"name": name, "private": private, "auto_init": False},
            )
    except httpx.HTTPError:
        raise ValueError(
            "No se pudo contactar con GitHub. Revisa la conexión e intenta otra vez."
        ) from None
    if response.status_code != 201:
        raise ValueError("GitHub no creó el repositorio. Revisa permisos, nombre y conexión.")
    try:
        owner = response.json().get("owner", {}).get("login", "")
    except (ValueError, AttributeError):
        raise ValueError("GitHub devolvió una respuesta no válida.") from None
    if not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", owner):
        raise ValueError("GitHub devolvió un propietario no válido.")
    return f"https://github.com/{owner}/{name}.git"
