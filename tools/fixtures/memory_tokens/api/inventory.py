"""Respuestas JSON de inventario mediante el helper compartido."""
from fastapi import APIRouter
from api.responses import response_ok, response_error
from models.catalog import Product

router = APIRouter()
products = {}

@router.get("")
def list_products(category=None):
    rows = [p.to_dict() for p in products.values()
            if category is None or p.category == category]
    return response_ok(sorted(rows, key=lambda row: row["name"]))

@router.post("")
def add_product(name: str, price: str, category: str = "general"):
    product = Product(name=name, price=price, category=category)
    if name in products:
        return response_error("Product already exists", code="duplicate")
    products[name] = product
    return response_ok(product.to_dict())

@router.delete("/{name}")
def remove_product(name: str):
    if name not in products:
        return response_error("Product not found", code="not_found")
    products.pop(name)
    return response_ok({"removed": name})
