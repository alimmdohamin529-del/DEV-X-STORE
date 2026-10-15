"""
main.py
-------
DEV-X BOOK STORE - FastAPI backend.

Run locally:   uvicorn main:app --reload
Swagger UI:    http://127.0.0.1:8000/docs

Environment variables:
  ADMIN_API_KEY    (required for admin endpoints) secret token for POST/PUT/PATCH/DELETE
  ALLOWED_ORIGINS  (optional) comma-separated website origins allowed by CORS, default "*"
  DATABASE_URL     (optional) defaults to a local SQLite file
"""

import os
import secrets
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

import database
import schemas
from models import ProductCategory


# --------------------------------------------------------------------------- #
# App setup
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once when the server starts: make sure the tables exist."""
    database.init_db()
    yield


app = FastAPI(
    title="DEV-X BOOK STORE API",
    version="1.0.0",
    description=(
        "Backend for the DEV-X BOOK STORE.\n\n"
        "**Public:** anyone can read the catalog (`GET` endpoints).\n\n"
        "**Admin:** creating, editing and deleting products needs a token. "
        "Click the **Authorize** button (top right), paste your `ADMIN_API_KEY`, "
        "then use the padlock endpoints below."
    ),
    lifespan=lifespan,
    # Keeps the token filled in after you refresh the /docs page.
    swagger_ui_parameters={"persistAuthorization": True},
)

# --------------------------------------------------------------------------- #
# CORS - lets your storefront website (a different domain) call this API
# --------------------------------------------------------------------------- #
# For production set ALLOWED_ORIGINS="https://your-store.com,https://www.your-store.com"
_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,  # we use a Bearer header, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------- #
# Admin authentication (Bearer token)
# --------------------------------------------------------------------------- #
bearer_scheme = HTTPBearer(auto_error=False, description="Paste your ADMIN_API_KEY")


def require_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> None:
    """Dependency that protects admin endpoints."""
    expected = os.getenv("ADMIN_API_KEY")

    # Fail closed: if no key is configured, nobody can use admin endpoints.
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin access is disabled: ADMIN_API_KEY is not set on the server.",
        )

    # compare_digest avoids timing attacks when comparing secrets.
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


admin_only = [Depends(require_admin)]


def _get_or_404(db: Session, product_id: int):
    product = database.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found.")
    return product


# --------------------------------------------------------------------------- #
# Public endpoints
# --------------------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
def root():
    return {"service": "DEV-X BOOK STORE API", "docs": "/docs", "status": "ok"}


@app.get("/health", tags=["System"])
def health():
    """Simple uptime check (useful for Render and monitoring)."""
    return {"status": "ok"}


@app.get("/categories", response_model=List[str], tags=["Catalog"])
def get_categories():
    """The 4 allowed product categories."""
    return [c.value for c in ProductCategory]


@app.get("/products", response_model=schemas.ProductListOut, tags=["Catalog"])
def list_products(
    category: Optional[ProductCategory] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, max_length=100, description="Search name/description"),
    in_stock: bool = Query(False, description="Only products with stock > 0"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(database.get_db),
):
    """List products with optional filters and pagination."""
    items, total = database.list_products(
        db, category=category, search=search, in_stock_only=in_stock, offset=offset, limit=limit
    )
    return schemas.ProductListOut(items=items, total=total, limit=limit, offset=offset)


@app.get("/products/{product_id}", response_model=schemas.ProductOut, tags=["Catalog"])
def read_product(product_id: int, db: Session = Depends(database.get_db)):
    """Get a single product by id."""
    return _get_or_404(db, product_id)


# --------------------------------------------------------------------------- #
# Admin endpoints (Bearer token required)
# --------------------------------------------------------------------------- #
@app.post(
    "/products",
    response_model=schemas.ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=admin_only,
    tags=["Admin"],
)
def create_product(payload: schemas.ProductCreate, db: Session = Depends(database.get_db)):
    """Add a new product."""
    return database.create_product(db, payload)


@app.put(
    "/products/{product_id}",
    response_model=schemas.ProductOut,
    dependencies=admin_only,
    tags=["Admin"],
)
def replace_product(
    product_id: int, payload: schemas.ProductCreate, db: Session = Depends(database.get_db)
):
    """Replace ALL fields of a product (send the complete product)."""
    return database.replace_product(db, _get_or_404(db, product_id), payload)


@app.patch(
    "/products/{product_id}",
    response_model=schemas.ProductOut,
    dependencies=admin_only,
    tags=["Admin"],
)
def update_product(
    product_id: int, payload: schemas.ProductUpdate, db: Session = Depends(database.get_db)
):
    """Change only some fields (e.g. just `price` or `stock_quantity`)."""
    if not payload.model_fields_set:
        raise HTTPException(status_code=400, detail="Send at least one field to update.")
    return database.update_product(db, _get_or_404(db, product_id), payload)


@app.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=admin_only,
    tags=["Admin"],
)
def delete_product(product_id: int, db: Session = Depends(database.get_db)):
    """Delete a product permanently."""
    database.delete_product(db, _get_or_404(db, product_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
