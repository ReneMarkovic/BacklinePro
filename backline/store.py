from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import os
from typing import List, Dict, Any

STORE_DIR = os.environ.get("BACKLINE_STORE", ".backline_store")
os.makedirs(STORE_DIR, exist_ok=True)

@dataclass
class Quote:
    id: str
    created_at: str
    customer: str
    items: List[Dict[str, Any]]
    days: int
    subtotal: float
    discount: float
    total: float
    note: str | None = None

def _quotes_path() -> str:
    return os.path.join(STORE_DIR, "quotes.json")

def load_quotes() -> list[dict]:
    p = _quotes_path()
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_quote(q: Quote) -> None:
    data = load_quotes()
    data.append(asdict(q))
    with open(_quotes_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
