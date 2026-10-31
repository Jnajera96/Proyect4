"""Calculo decimal: conversion de importes y sumas sin redondeo intermedio."""
from decimal import Decimal, InvalidOperation

def amount(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not an amount")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid amount") from exc
    if not result.is_finite():
        raise ValueError("Non finite amount")
    return result

def total(values):
    return sum((amount(value) for value in values), Decimal("0"))

def display_amount(value):
    return format(amount(value).quantize(Decimal("0.01")), "f")

def split_amount(value, portions):
    if not isinstance(portions, int) or portions < 1:
        raise ValueError("Invalid portions")
    return amount(value) / portions
