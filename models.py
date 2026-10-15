"""
models.py
---------
SQLAlchemy table definitions for DEV-X BOOK STORE.

This file has NO imports from the other project files, so it can be imported
safely from anywhere (database.py, schemas.py, main.py) without circular imports.
"""

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class every table inherits from."""


class ProductCategory(str, enum.Enum):
    """The 4 fixed store categories. The value is what is stored/returned by the API."""

    CLOTHING = "Clothing"
    STATIONERY = "Stationery"
    MUGS_AND_BOTTLES = "Mugs and bottles"
    ACCESSORIES = "Accessories"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    """One row per product in the catalog."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Main product name. Arabic or English (SQLite/Postgres store UTF-8 fine).
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    # Optional second-language name (e.g. English name for an Arabic product).
    name_en: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Stored as the plain category text, e.g. "Mugs and bottles".
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # NULL = "price not set yet" (your storefront already has unpriced products).
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # A normal https:// link to the picture (host images elsewhere, e.g. Cloudinary/Imgur).
    image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # List of {"name": "Black", "hex": "#111111"} objects stored as JSON.
    color_swatches: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
