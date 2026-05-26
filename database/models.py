from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    type_annotation_map = {
        list[str]: JSON,
    }


class ProductStatus(StrEnum):
    PENDING = "pending"      # parsed from channel, awaiting admin approval
    IN_STOCK = "in_stock"
    RESERVED = "reserved"
    SOLD = "sold"


class ProductCategory(StrEnum):
    BAGS = "bags"
    SHOES = "shoes"
    TOPS = "tops"            # Кофты / Футболки
    JACKETS = "jackets"      # Куртки, ветровки, пуховики, жилетки
    PANTS = "pants"          # Штаны, брюки, джинсы
    ACCESSORIES = "accessories"
    CUSTOM_ORDER = "custom_order"  # Special info-only "Под заказ" category
    OTHER = "other"
    # Legacy — kept for one phase to allow migration rollback; removed in Phase 7
    CLOTHING = "clothing"


class OrderStatus(StrEnum):
    NEW = "new"
    CONFIRMED = "confirmed"
    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class DeliveryMethod(StrEnum):
    COURIER_WARSAW = "courier_warsaw"
    EUROPE = "europe"
    WORLDWIDE = "worldwide"
    PICKUP = "pickup"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)

    brand: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[ProductCategory] = mapped_column(
        String(20),
        default=ProductCategory.CLOTHING,
        index=True,
    )

    size: Mapped[str | None] = mapped_column(String(50))
    condition: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(255))

    price_pln: Mapped[int] = mapped_column(Integer)
    price_usdt: Mapped[int | None] = mapped_column(Integer)

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

    order_items: Mapped[list[OrderItem]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )

    @property
    def is_available(self) -> bool:
        return self.status == ProductStatus.IN_STOCK

    @property
    def main_photo(self) -> str | None:
        return self.photos[0] if self.photos else None

    def __repr__(self) -> str:
        return f"<Product id={self.id} {self.brand} {self.name!r} {self.status}>"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(100))
    full_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50))

    delivery_method: Mapped[DeliveryMethod] = mapped_column(
        String(30),
        default=DeliveryMethod.COURIER_WARSAW,
    )
    delivery_address: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)

    total_pln: Mapped[int] = mapped_column(Integer, default=0)
    total_usdt: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[OrderStatus] = mapped_column(
        String(20),
        default=OrderStatus.NEW,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Order id={self.id} user={self.user_id} {self.status}>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), index=True
    )

    price_pln: Mapped[int] = mapped_column(Integer)
    price_usdt: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(
        back_populates="order_items", lazy="joined"
    )

    def __repr__(self) -> str:
        return (
            f"<OrderItem id={self.id} order={self.order_id} "
            f"product={self.product_id} x{self.quantity}>"
        )
