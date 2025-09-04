from __future__ import annotations
from typing import List, Dict

def compute_subtotal(items: List[Dict], days: int) -> float:
    return sum((float(it["daily_price"]) * int(it["qty"])) for it in items) * max(int(days), 1)

def weekend_multiplier(days: int, weekend_factor: float = 1.15) -> float:
    return weekend_factor if int(days) >= 2 else 1.0

def package_discount(total: float) -> float:
    if total >= 2000: return 0.10
    if total >= 1000: return 0.05
    return 0.0

def price_quote(items: List[Dict], days: int) -> dict:
    sub = compute_subtotal(items, days)
    sub *= weekend_multiplier(days)
    disc_rate = package_discount(sub)
    discount = sub * disc_rate
    total = sub - discount
    return {"subtotal": round(sub, 2), "discount": round(discount, 2), "total": round(total, 2)}
