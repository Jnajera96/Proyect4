"""El balance y sus casos limite deben conservar precision decimal."""
from decimal import Decimal
import pytest
from models.ledger import Entry, calcular_balance, summarize

def test_balance():
    entries = [Entry("1", "income", Decimal("100.25")),
               Entry("2", "expense", Decimal("25.10"))]
    assert calcular_balance(entries) == Decimal("75.15")

def test_empty_balance():
    assert calcular_balance([]) == Decimal("0")

def test_invalid_entry():
    with pytest.raises(ValueError):
        Entry("3", "unknown", Decimal("10"))

def test_summary_counts_entries():
    rows = [Entry("4", "income", Decimal("0.01"))]
    assert summarize(rows) == {"balance": "0.01", "count": 1}
