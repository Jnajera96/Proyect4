"""Catalogo local con importes y categorias editables."""
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class Product:
    name: str
    price: str
    category: str = "general"
    stock: int = 0

    def __post_init__(self):
        self.name = self.name.strip()
        self.category = self.category.strip() or "general"
        value = Decimal(self.price)
        if not self.name or len(self.name) > 120:
            raise ValueError("Invalid product name")
        if not value.is_finite() or value < 0:
            raise ValueError("Invalid price")
        if self.stock < 0:
            raise ValueError("Invalid stock")
        self.price = str(value)

    def to_dict(self):
        return {"name": self.name, "price": self.price,
                "category": self.category, "stock": self.stock}
