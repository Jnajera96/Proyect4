"""Comprobacion estructural de serializabilidad de los contratos.

Un contrato que debe persistirse no puede contener funciones. El problema es que
esto falla en silencio: serializar un objeto descarta sus metodos sin avisar, y
solo se descubre al intentar recuperarlo.

Esta comprobacion recorre el arbol de modelos y detecta cualquier tipo que no
sea serializable, en cualquier nivel de anidamiento.
"""

from __future__ import annotations

import types
import typing
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel

# Tipos hoja que se serializan sin problema.
_ALLOWED_LEAF: tuple[object, ...] = (
    str,
    int,
    float,
    bool,
    bytes,
    type(None),
    datetime,
    date,
    typing.Any,
    object,
)


def _check(annotation: object, path: str, seen: set[type]) -> list[str]:
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if origin is typing.Union or origin is types.UnionType:
        problems: list[str] = []
        for arg in args:
            problems.extend(_check(arg, path, seen))
        return problems

    if origin in (list, tuple, set, frozenset):
        return _check(args[0], f"{path}[]", seen) if args else []

    if origin is dict:
        problems = []
        if args:
            problems.extend(_check(args[0], f"{path}<clave>", seen))
        if len(args) > 1:
            problems.extend(_check(args[1], f"{path}<valor>", seen))
        return problems

    if annotation in _ALLOWED_LEAF:
        return []

    if isinstance(annotation, type):
        if issubclass(annotation, Enum):
            return []
        if issubclass(annotation, BaseModel):
            return find_non_serializable(annotation, seen)

    return [f"{path}: tipo no serializable {annotation!r}"]


def find_non_serializable(
    model: type[BaseModel], _seen: set[type] | None = None
) -> list[str]:
    """Devuelve la lista de campos no serializables del modelo y sus anidados.

    Una lista vacia significa que el modelo se puede persistir sin perdida.
    """
    if _seen is None:
        _seen = set()
    if model in _seen:
        return []
    _seen.add(model)

    problems: list[str] = []
    for name, field in model.model_fields.items():
        problems.extend(_check(field.annotation, f"{model.__name__}.{name}", _seen))
    return problems
