from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    title: str
    category: str
    price: float
    price_excl_tax: float
    in_stock: int
    rating: int  # 0–5
    reviews: int
    upc: str
    description: str
    url: str
    image_url: str
