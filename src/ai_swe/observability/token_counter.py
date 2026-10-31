"""Local reference-encoding counts, never provider billing or model identification."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path

DATA = Path(__file__).with_name("tokenizer_data")
ENCODINGS = ("cl100k_base", "o200k_base")


class TokenizerUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class TokenCount:
    tokens: int
    exact: bool
    encoding: str
    method: str


@lru_cache(maxsize=2)
def _encoder(encoding: str):
    import tiktoken

    definitions = json.loads((DATA / "encodings.json").read_text(encoding="utf-8"))
    definition = definitions["encodings"][encoding]
    raw = (DATA / f"{encoding}.tiktoken").read_bytes()
    if hashlib.sha256(raw).hexdigest() != definition["sha256"]:
        raise ValueError("El vocabulario local no coincide con su SHA-256")
    ranks = {
        base64.b64decode(token, validate=True): int(rank)
        for token, rank in (line.split() for line in raw.splitlines())
    }
    return tiktoken.Encoding(
        name=encoding,
        pat_str=definition["pat_str"],
        mergeable_ranks=ranks,
        special_tokens=definition["special_tokens"],
    )


def count_tokens(
    text: str, encoding: str = "o200k_base", *, require_exact: bool = False
) -> TokenCount:
    """Count ordinary text. No network/cache loaders or hidden encoding substitutions."""
    if encoding not in ENCODINGS:
        raise ValueError("Encoding no soportado")
    try:
        encoder = _encoder(encoding)
    except (ImportError, OSError) as exc:
        if require_exact:
            raise TokenizerUnavailable(
                "Instala el extra token-metrics y conserva los vocabularios locales"
            ) from exc
        # shortcut: bytes/4 is only a deterministic estimate, never a billing/budget bound.
        return TokenCount(
            (len(text.encode("utf-8")) + 3) // 4, False, encoding, "utf8_bytes_div4_ceiling"
        )
    return TokenCount(
        len(encoder.encode_ordinary(text)), True, encoding, "tiktoken-" + version("tiktoken")
    )
