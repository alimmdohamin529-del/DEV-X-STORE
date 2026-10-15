"""
database.py
-----------
Database connection + all CRUD (Create / Read / Update / Delete) operations.

By default it uses a local SQLite file (devx_store.db).
To use another database (e.g. a free hosted Postgres) just set the
DATABASE_URL environment variable - no code changes needed.
"""

import os
from typing import List, Optional, Tuple

from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

import schemas
from models import Base, Product, ProductCategory

# --------------------------------------------------------------------------- #
# Connection setup
# --------------------------------------------------------------------------- #
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./devx_store.db")

# Some hosts hand out "postgres://..." URLs, which SQLAlchemy 2.x no longer accepts.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    # SQLite + FastAPI: allow the connection to be used across request threads.
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # pool_pre_ping drops dead connections (important on free hosted databases).
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables if they don't exist yet (called on app startup)."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: opens a DB session per request and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# CRUD operations
# --------------------------------------------------------------------------- #
def get_product(db: Session, product_id: int) -> Optional[Product]:
    """Return one product or None."""
    return db.get(Product, product_id)


def list_products(
    db: Session,
    category: Optional[ProductCategory] = None,
    search: Optional[str] = None,
    in_stock_only: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> Tuple[List[Product], int]:
    """Return (products for this page, total number of matches)."""
    stmt = select(Product)

    if category is not None:
        stmt = stmt.where(Product.category == category.value)

    if search and search.strip():
        # Escape LIKE wildcards so a user typing "%" or "_" searches literally.
        term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{term}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(like, escape="\\"),
                Product.name_en.ilike(like, escape="\\"),
                Product.description.ilike(like, escape="\\"),
            )
        )

    if in_stock_only:
        stmt = stmt.where(Product.stock_quantity > 0)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Product.id).offset(offset).limit(limit)).all()
    return list(items), total


def create_product(db: Session, data: schemas.ProductCreate) -> Product:
    """Insert a new product."""
    # mode="json" turns the enum into its text value and swatches into plain dicts.
    product = Product(**data.model_dump(mode="json"))
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def replace_product(db: Session, product: Product, data: schemas.ProductCreate) -> Product:
    """PUT: overwrite every field of an existing product."""
    for field, value in data.model_dump(mode="json").items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product: Product, data: schemas.ProductUpdate) -> Product:
    """PATCH: change only the fields that were actually sent."""
    for field, value in data.model_dump(mode="json", exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product: Product) -> None:
    """Remove a product permanently."""
    db.delete(product)
    db.commit()
