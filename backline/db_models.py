# backline/db_models.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field, Relationship


# ---------------------------
# Core catalog
# ---------------------------

class Category(SQLModel, table=True):
    __tablename__ = "category"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, nullable=False)

    # 1 -> many Gear
    gear: List["Gear"] = Relationship(back_populates="category")


class Gear(SQLModel, table=True):
    __tablename__ = "gear"
    __table_args__ = (UniqueConstraint("brand", "model", name="uq_gear_brand_model"),)

    id: Optional[int] = Field(default=None, primary_key=True)

    category_id: int = Field(foreign_key="category.id", nullable=False, index=True)

    brand: str = Field(nullable=False, index=True)
    model: str = Field(nullable=False, index=True)
    daily_price: float = Field(ge=0, nullable=False)

    # many -> 1 Category
    category: Optional[Category] = Relationship(back_populates="gear")

    # 1 -> many StockLot
    stock_lots: List["StockLot"] = Relationship(back_populates="gear")


class StockLot(SQLModel, table=True):
    """
    Optional batches of stock to track quantities per gear.
    If you don't need batches, you can ignore this table and
    keep qty in an operational table.
    """
    __tablename__ = "stock_lot"

    id: Optional[int] = Field(default=None, primary_key=True)

    gear_id: int = Field(foreign_key="gear.id", nullable=False, index=True)
    qty: int = Field(ge=0, nullable=False)
    note: Optional[str] = None

    gear: Optional[Gear] = Relationship(back_populates="stock_lots")


# ---------------------------
# Parties
# ---------------------------

class Customer(SQLModel, table=True):
    __tablename__ = "customer"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, index=True)
    email: Optional[str] = Field(default=None, index=True)
    phone: Optional[str] = None

    # 1 -> many Offers / Bookings (relationships not strictly needed here)


# ---------------------------
# Offers (quotes) before booking
# ---------------------------

class Offer(SQLModel, table=True):
    __tablename__ = "offer"

    id: Optional[int] = Field(default=None, primary_key=True)

    customer_id: int = Field(foreign_key="customer.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    days: int = Field(ge=1, nullable=False)

    subtotal: float = Field(ge=0, nullable=False)
    discount: float = Field(ge=0, nullable=False)
    total: float = Field(ge=0, nullable=False)

    note: Optional[str] = None

    # 1 -> many OfferItem
    items: List["OfferItem"] = Relationship(back_populates="offer")


class OfferItem(SQLModel, table=True):
    __tablename__ = "offer_item"

    id: Optional[int] = Field(default=None, primary_key=True)

    offer_id: int = Field(foreign_key="offer.id", nullable=False, index=True)
    gear_id: int = Field(foreign_key="gear.id", nullable=False, index=True)

    qty: int = Field(ge=1, nullable=False)
    unit_price: float = Field(ge=0, nullable=False)

    # many -> 1 Offer
    offer: Optional[Offer] = Relationship(back_populates="items")
    # (Optionally add a relationship to Gear if you need object access)
    gear: Optional[Gear] = Relationship()


# ---------------------------
# Bookings (confirmed rentals)
# ---------------------------

class Booking(SQLModel, table=True):
    __tablename__ = "booking"

    id: Optional[int] = Field(default=None, primary_key=True)

    customer_id: int = Field(foreign_key="customer.id", nullable=False, index=True)
    status: str = Field(default="CONFIRMED", nullable=False, index=True)  # CONFIRMED/CANCELLED/RETURNED

    start_ts: datetime = Field(nullable=False, index=True)
    end_ts: datetime = Field(nullable=False, index=True)

    # 1 -> many BookingItem
    items: List["BookingItem"] = Relationship(back_populates="booking")


class BookingItem(SQLModel, table=True):
    __tablename__ = "booking_item"

    id: Optional[int] = Field(default=None, primary_key=True)

    booking_id: int = Field(foreign_key="booking.id", nullable=False, index=True)
    gear_id: int = Field(foreign_key="gear.id", nullable=False, index=True)

    qty: int = Field(ge=1, nullable=False)
    daily_price: float = Field(ge=0, nullable=False)

    # many -> 1 Booking
    booking: Optional[Booking] = Relationship(back_populates="items")
    # (Optionally add a relationship to Gear if you need object access)
    gear: Optional[Gear] = Relationship()
