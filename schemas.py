"""
schemas.py
----------
Pydantic models (v2) that validate incoming requests and shape API responses.
These are also what Swagger UI (/docs) uses to build its input forms.
"""

import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models import ProductCategory

# Accepts #RGB or #RRGGBB
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class ColorSwatch(BaseModel):
    """A single color option for a product."""

    name: str = Field(..., min_length=1, max_length=50, examples=["ماروني"])
    hex: str = Field(..., examples=["#7A0F22"], description="Color code like #7A0F22")

    @field_validator("hex")
    @classmethod
    def validate_hex(cls, value: str) -> str:
        value = value.strip()
        if not _HEX_RE.match(value):
            raise ValueError("hex must look like #RGB or #RRGGBB (e.g. #7A0F22)")
        return value.upper()


class ProductBase(BaseModel):
    """Fields shared by create and response models."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=200, examples=["تيشيرت Dev-X ماروني"])
    name_en: Optional[str] = Field(None, max_length=200, examples=["Dev-X Maroon T-Shirt"])
    description: Optional[str] = Field(None, max_length=5000)
    category: ProductCategory
    price: Optional[float] = Field(
        None, ge=0, description="Price in EGP. Leave empty if not decided yet."
    )
    stock_quantity: int = Field(0, ge=0)
    image_url: Optional[str] = Field(None, max_length=1000, examples=["https://example.com/img.jpg"])
    color_swatches: List[ColorSwatch] = Field(default_factory=list, max_length=20)


class ProductCreate(ProductBase):
    """Body for POST /products and PUT /products/{id} (full replace)."""


class ProductUpdate(BaseModel):
    """
    Body for PATCH /products/{id}.
    Every field is optional: only the fields you send are changed.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    name_en: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    category: Optional[ProductCategory] = None
    price: Optional[float] = Field(None, ge=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    image_url: Optional[str] = Field(None, max_length=1000)
    color_swatches: Optional[List[ColorSwatch]] = Field(None, max_length=20)

    # These columns can never be NULL, so reject an explicit null for them.
    # (Validators only run when the field is actually sent in the request.)
    @field_validator("name", "category", "stock_quantity", "color_swatches")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("this field cannot be null")
        return value


class ProductOut(ProductBase):
    """What the API returns for a product."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ProductListOut(BaseModel):
    """Paginated list response."""

    items: List[ProductOut]
    total: int
    limit: int
    offset: int
