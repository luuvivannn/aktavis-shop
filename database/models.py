from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    type_annotation_map = {
        list[str]: JSON,
    }


class ProductStatus(StrEnum):
    PENDING = "pending"          # parsed from channel, awaiting admin approval
    IN_STOCK = "in_stock"
    RESERVED = "reserved"
    SOLD = "sold"
    DUPLICATED = "duplicated"    # soft-deleted by _collapse_duplicates (machine)
    HIDDEN = "hidden"            # manually hidden by the admin from the bot


class ProductCategory(StrEnum):
    BAGS = "bags"
    SHOES = "shoes"
    TOPS = "tops"            # Худи / Футболки
    JACKETS = "jackets"      # Куртки, ветровки, пуховики, жилетки
    PANTS = "pants"          # Шорты, штаны, брюки, джинсы
    ACCESSORIES = "accessories"
    CUSTOM_ORDER = "custom_order"  # Special info-only "Под заказ" category
    OTHER = "other"


class SortBy(StrEnum):
    """Sort order for catalog listings."""
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)

    brand: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[ProductCategory] = mapped_column(
        String(20),
        default=ProductCategory.OTHER,
        index=True,
    )

    size: Mapped[str | None] = mapped_column(String(50))
    condition: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(255))

    price_pln: Mapped[int] = mapped_column(Integer)
    price_usdt: Mapped[int | None] = mapped_column(Integer)
    price_eur: Mapped[int | None] = mapped_column(Integer)
    price_eur_original: Mapped[int | None] = mapped_column(Integer, default=None)
    price_pln_original: Mapped[int | None] = mapped_column(Integer, default=None)

    photos: Mapped[list[str]] = mapped_column(JSON, default=list)

    status: Mapped[ProductStatus] = mapped_column(
        String(20),
        default=ProductStatus.IN_STOCK,
        index=True,
    )

    # If the product originated from a Telegram channel post, store its
    # identity here so we can react to edits (e.g., #продано → mark sold).
    channel_message_id: Mapped[int | None] = mapped_column(
        Integer, index=True, default=None
    )
    channel_chat_id: Mapped[int | None] = mapped_column(
        BigInteger, default=None
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def is_available(self) -> bool:
        return self.status == ProductStatus.IN_STOCK

    @property
    def main_photo(self) -> str | None:
        return self.photos[0] if self.photos else None

    def __repr__(self) -> str:
        return f"<Product id={self.id} {self.brand} {self.name!r} {self.status}>"


class Sale(Base):
    """Accounting record: purchase/sale price captured from the admin after
    a product is marked #продано. One row per product (see
    ``SaleRepository.exists_for_product``)."""

    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), index=True
    )

    purchase_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    purchase_currency: Mapped[str] = mapped_column(String(10))
    sale_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    sale_currency: Mapped[str] = mapped_column(String(10))
    # Only set when purchase_currency == sale_currency — no FX conversion.
    profit: Mapped[float | None] = mapped_column(Numeric(10, 2), default=None)

    recorded_by_admin_id: Mapped[int] = mapped_column(BigInteger)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<Sale id={self.id} product_id={self.product_id} "
            f"{self.purchase_amount} {self.purchase_currency} → "
            f"{self.sale_amount} {self.sale_currency}>"
        )
