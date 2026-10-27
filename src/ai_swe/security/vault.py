"""Versioned password-wrapped AES-GCM envelopes; no machine-bound keys."""

from __future__ import annotations

import base64
import hashlib
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = 1
MAX_VAULT_BYTES = 1024 * 1024
MAX_ENVELOPE_BYTES = 256 * 1024 * 1024 + 1024 * 1024


class VaultError(ValueError):
    """Authentication or format failure, deliberately without sensitive details."""


def seal(key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    if len(plaintext) > MAX_ENVELOPE_BYTES:
        raise VaultError("Contenido demasiado grande")
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def open_sealed(key: bytes, envelope: bytes, aad: bytes) -> bytes:
    if not 28 <= len(envelope) <= MAX_ENVELOPE_BYTES + 28:
        raise VaultError("Sobre invalido")
    try:
        return AESGCM(key).decrypt(envelope[:12], envelope[12:], aad)
    except (InvalidTag, ValueError):
        raise VaultError("Contraseña incorrecta o datos alterados") from None


def _encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _decode(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def _aad(owner: str, purpose: str) -> bytes:
    return f"ai-swe:{VERSION}:{owner}:{purpose}".encode()


def _derive(password: str, salt: bytes) -> bytes:
    if not 12 <= len(password) <= 1024 or len(salt) != 16:
        raise VaultError("Contraseña incorrecta o datos alterados")
    return hashlib.scrypt(
        password.encode(), salt=salt, n=32768, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024
    )


def wrap_key(owner: str, password: str, key: bytes) -> dict:
    salt = os.urandom(16)
    return {
        "version": VERSION,
        "owner": owner,
        "salt": _encode(salt),
        "wrapped_key": _encode(seal(_derive(password, salt), key, _aad(owner, "key"))),
    }


def unwrap_key(owner: str, password: str, header: dict) -> bytes:
    try:
        if header["version"] != VERSION or header["owner"] != owner:
            raise VaultError("Sobre invalido")
        key = open_sealed(
            _derive(password, _decode(header["salt"])),
            _decode(header["wrapped_key"]),
            _aad(owner, "key"),
        )
        if len(key) != 32:
            raise VaultError("Sobre invalido")
        return key
    except (KeyError, TypeError, ValueError):
        raise VaultError("Contraseña incorrecta o datos alterados") from None


def save_vault(owner: str, key: bytes, header: dict, data: dict) -> dict:
    plaintext = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
    if len(plaintext) > MAX_VAULT_BYTES:
        raise VaultError("Boveda demasiado grande")
    return {"header": header, "data": _encode(seal(key, plaintext, _aad(owner, "vault")))}


def create_vault(owner: str, password: str, data: dict) -> tuple[dict, bytes]:
    key = os.urandom(32)
    header = wrap_key(owner, password, key)
    return save_vault(owner, key, header, data), key


def unlock_vault(owner: str, password: str, envelope: dict) -> tuple[bytes, dict]:
    try:
        if len(json.dumps(envelope)) > MAX_VAULT_BYTES * 2:
            raise VaultError("Boveda demasiado grande")
        key = unwrap_key(owner, password, envelope["header"])
        data = json.loads(open_sealed(key, _decode(envelope["data"]), _aad(owner, "vault")))
        if not isinstance(data, dict):
            raise VaultError("Boveda invalida")
        return key, data
    except (KeyError, TypeError, ValueError):
        raise VaultError("Contraseña incorrecta o datos alterados") from None
