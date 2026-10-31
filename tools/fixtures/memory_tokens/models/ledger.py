"""Movimientos contables: el balance conserva importes decimales."""
from dataclasses import dataclass
from decimal import Decimal
from utils.arithmetic import amount, total

@dataclass(frozen=True)
class Entry:
    identifier: str
    kind: str
    value: Decimal
    description: str = ""

    def __post_init__(self):
        if self.kind not in {"income", "expense"}:
            raise ValueError("Unknown entry kind")
        if amount(self.value) < 0:
            raise ValueError("Negative entry")

def calcular_balance(entries):
    income = total(entry.value for entry in entries if entry.kind == "income")
    expense = total(entry.value for entry in entries if entry.kind == "expense")
    return income - expense

def summarize(entries):
    rows = list(entries)
    return {"balance": str(calcular_balance(rows)), "count": len(rows)}
