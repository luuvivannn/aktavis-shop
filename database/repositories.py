from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from database.models import (
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductCategory,
    ProductStatus,
)


class ProductNotAvailableError(Exception):
    def __init__(self, product_id: int, status: ProductStatus) -> None:
        super().__init__(
            f"Product {product_id} is not available (status={status})."
        )
        self.product_id = product_id
        self.status = status


class ProductNotFoundError(Exception):
    def __init__(self, product_id: int) -> None:
        super().__init__(f"Product {product_id} not found.")
        self.product_id = product_id


@dataclass(slots=True)
class CartItem:
    product_id: int
    quantity: int = 1


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, product_id: int) -> Product | None:
        return await self.session.get(Product, product_id)

    async def get_by_channel_message_id(
        self, channel_message_id: int
    ) -> Product | None:
        stmt = select(Product).where(
            Product.channel_message_id == channel_message_id
        )
        return await self.session.scalar(stmt)

    async def delete(self, product: Product) -> None:
        await self.session.delete(product)
        await self.session.flush()

    async def get_or_raise(self, product_id: int) -> Product:
        product = await self.get(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        return product

    async def get_many(self, product_ids: Sequence[int]) -> list[Product]:
        if not product_ids:
            return []
        stmt = select(Product).where(Product.id.in_(product_ids))
        return list((await self.session.scalars(stmt)).all())

    async def list_available(
        self,
        *,
        category: ProductCategory | None = None,
        brand: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Product]:
        stmt = (
            select(Product)
            .where(Product.status == ProductStatus.IN_STOCK)
            .order_by(Product.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if category is not None:
            stmt = stmt.where(Product.category == category)
        if brand is not None:
            stmt = stmt.where(Product.brand == brand)
        return list((await self.session.scalars(stmt)).all())

    async def count_available(
        self,
        *,
        category: ProductCategory | None = None,
        brand: str | None = None,
    ) -> int:
        stmt = (
            select(func.count(Product.id))
            .where(Product.status == ProductStatus.IN_STOCK)
        )
        if category is not None:
            stmt = stmt.where(Product.category == category)
        if brand is not None:
            stmt = stmt.where(Product.brand == brand)
        return await self.session.scalar(stmt) or 0

    async def list_brands(self) -> list[str]:
        stmt = (
            select(Product.brand)
            .where(Product.status == ProductStatus.IN_STOCK)
            .group_by(Product.brand)
            .order_by(Product.brand)
        )
        return list((await self.session.scalars(stmt)).all())

    async def search(self, query: str, *, limit: int = 50) -> list[Product]:
        pattern = f"%{query.strip()}%"
        stmt = (
            select(Product)
            .where(
                Product.status == ProductStatus.IN_STOCK,
                or_(
                    Product.brand.ilike(pattern),
                    Product.name.ilike(pattern),
                    Product.description.ilike(pattern),
                ),
            )
            .order_by(Product.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.scalars(stmt)).all())

    async def create(self, **payload) -> Product:
        product = Product(**payload)
        self.session.add(product)
        await self.session.flush()
        return product

    async def set_status(
        self, product_id: int, status: ProductStatus
    ) -> Product:
        product = await self.get_or_raise(product_id)
        product.status = status
        await self.session.flush()
        return product


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, order_id: int) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items).joinedload(OrderItem.product))
        )
        return await self.session.scalar(stmt)

    async def list_by_user(
        self, user_id: int, *, limit: int = 20, offset: int = 0
    ) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
            .options(selectinload(Order.items).joinedload(OrderItem.product))
        )
        return list((await self.session.scalars(stmt)).all())

    async def list_recent(self, *, limit: int = 20, offset: int = 0) -> list[Order]:
        stmt = (
            select(Order)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
            .options(selectinload(Order.items).joinedload(OrderItem.product))
        )
        return list((await self.session.scalars(stmt)).all())

    async def revenue_since(
        self, since: datetime | None = None
    ) -> tuple[int, int, int]:
        """Return (orders_count, total_pln, total_usdt) for revenue statuses.

        Revenue counts only orders that are paid / shipped / delivered.
        """
        counted = {OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED}
        stmt = select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_pln), 0),
            func.coalesce(func.sum(Order.total_usdt), 0),
        ).where(Order.status.in_(counted))
        if since is not None:
            stmt = stmt.where(Order.created_at >= since)
        row = (await self.session.execute(stmt)).one()
        return int(row[0]), int(row[1] or 0), int(row[2] or 0)

    async def count_pending(self) -> int:
        """Orders that need attention: new / confirmed / awaiting_payment."""
        pending = {
            OrderStatus.NEW,
            OrderStatus.CONFIRMED,
            OrderStatus.AWAITING_PAYMENT,
        }
        stmt = select(func.count(Order.id)).where(Order.status.in_(pending))
        return int((await self.session.scalar(stmt)) or 0)

    async def create(
        self,
        *,
        user_id: int,
        cart: Sequence[CartItem],
        username: str | None = None,
        full_name: str | None = None,
        phone: str | None = None,
        delivery_method: DeliveryMethod = DeliveryMethod.COURIER_WARSAW,
        delivery_address: str | None = None,
        comment: str | None = None,
        reserve_products: bool = True,
    ) -> Order:
        if not cart:
            raise ValueError("Cart is empty.")

        product_ids = [item.product_id for item in cart]
        stmt = (
            select(Product)
            .where(Product.id.in_(product_ids))
            .with_for_update()
        )
        products: dict[int, Product] = {
            p.id: p for p in (await self.session.scalars(stmt)).all()
        }

        items: list[OrderItem] = []
        total_pln = 0
        total_usdt = 0

        for cart_item in cart:
            product = products.get(cart_item.product_id)
            if product is None:
                raise ProductNotFoundError(cart_item.product_id)
            if product.status != ProductStatus.IN_STOCK:
                raise ProductNotAvailableError(product.id, product.status)

            qty = max(1, cart_item.quantity)
            total_pln += product.price_pln * qty
            if product.price_usdt is not None:
                total_usdt += product.price_usdt * qty

            items.append(
                OrderItem(
                    product=product,
                    price_pln=product.price_pln,
                    price_usdt=product.price_usdt,
                    quantity=qty,
                )
            )

            if reserve_products:
                product.status = ProductStatus.RESERVED

        order = Order(
            user_id=user_id,
            username=username,
            full_name=full_name,
            phone=phone,
            delivery_method=delivery_method,
            delivery_address=delivery_address,
            comment=comment,
            total_pln=total_pln,
            total_usdt=total_usdt,
            status=OrderStatus.NEW,
            items=items,
        )
        self.session.add(order)
        await self.session.flush()
        return order

    async def set_status(self, order_id: int, status: OrderStatus) -> Order:
        order = await self.get(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found.")

        previous = order.status
        order.status = status

        if status == OrderStatus.CANCELLED and previous in {
            OrderStatus.NEW,
            OrderStatus.CONFIRMED,
            OrderStatus.AWAITING_PAYMENT,
        }:
            for item in order.items:
                if item.product.status == ProductStatus.RESERVED:
                    item.product.status = ProductStatus.IN_STOCK

        if status in {OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED}:
            for item in order.items:
                item.product.status = ProductStatus.SOLD

        await self.session.flush()
        return order
