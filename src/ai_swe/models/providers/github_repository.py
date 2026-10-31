"""GitHub HTTP adapter. Separate from domain logic and from paid model inference."""

import re

import httpx

from ai_swe.security import register_secret


def _headers(token: str) -> dict:
    register_secret(token)
    return {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
    }


def validate_token(token: str) -> str:
    try:
        with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
            response = client.get("https://api.github.com/user", headers=_headers(token))
    except httpx.HTTPError:
        raise ValueError("No se pudo contactar con GitHub para validar el token.") from None
    if response.status_code == 401:
        raise ValueError("GitHub rechazó el token. Revisa que sea válido y no haya vencido.")
    if response.status_code != 200:
        raise ValueError("GitHub no pudo validar los permisos del token.")
    # Fine-grained permissions cannot be proven from X-OAuth-Scopes; fail closed.
    scopes = {s.strip() for s in response.headers.get("X-OAuth-Scopes", "").split(",")}
    if "repo" not in scopes:
        raise ValueError("Usa un PAT clásico de GitHub con el permiso repo para esta publicación.")
    try:
        login = response.json()["login"]
    except (ValueError, KeyError, TypeError):
        raise ValueError("GitHub devolvió una identidad no válida.") from None
    if not isinstance(login, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
        raise ValueError("GitHub devolvió una identidad no válida.")
    return login


def create_repository(name: str, token: str, private: bool, organization: str = "") -> str:
    register_secret(token)
    try:
        with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
            response = client.post(
                f"https://api.github.com/orgs/{organization}/repos"
                if organization
                else "https://api.github.com/user/repos",
                headers=_headers(token),
                json={"name": name, "private": private, "auto_init": False},
            )
    except httpx.HTTPError:
        raise ValueError(
            "No se pudo contactar con GitHub. Revisa la conexión e intenta otra vez."
        ) from None
    if response.status_code != 201:
        if response.status_code == 422:
            raise ValueError("El nombre ya existe o no es válido. Elige otro nombre en GitHub.")
        if response.status_code == 401:
            raise ValueError("GitHub rechazó el token. Vuelve a configurarlo.")
        raise ValueError("GitHub no creó el repositorio. Revisa permisos, nombre y conexión.")
    try:
        owner = response.json().get("owner", {}).get("login", "")
    except (ValueError, AttributeError):
        raise ValueError("GitHub devolvió una respuesta no válida.") from None
    if not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", owner):
        raise ValueError("GitHub devolvió un propietario no válido.")
    return f"https://github.com/{owner}/{name}.git"
