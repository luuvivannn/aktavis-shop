from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Product,
    ProductCategory,
    ProductStatus,
    SortBy,
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

    async def find_in_stock_by_brand_name(
        self, brand: str, name: str
    ) -> Product | None:
        """Fallback lookup for products without channel_message_id.

        Returns the single IN_STOCK match for brand+name, or None if there
        are zero or multiple matches (ambiguous).
        """
        stmt = (
            select(Product)
            .where(
                Product.brand == brand,
                Product.name == name,
                Product.status == ProductStatus.IN_STOCK,
            )
            .order_by(Product.id.desc())
        )
        rows = list((await self.session.scalars(stmt)).all())
        return rows[0] if len(rows) == 1 else None

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
        size: str | None = None,
        sort_by: SortBy = SortBy.NEWEST,
        price_min: int | None = None,
        price_max: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Product]:
        stmt = select(Product).where(Product.status == ProductStatus.IN_STOCK)
        stmt = self._apply_catalog_filters(
            stmt,
            category=category,
            size=size,
            price_min=price_min,
            price_max=price_max,
        )
        stmt = self._apply_catalog_sort(stmt, sort_by)
        stmt = stmt.limit(limit).offset(offset)
        return list((await self.session.scalars(stmt)).all())

    async def count_available(
        self,
        *,
        category: ProductCategory | None = None,
        size: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
    ) -> int:
        stmt = (
            select(func.count(Product.id))
            .where(Product.status == ProductStatus.IN_STOCK)
        )
        stmt = self._apply_catalog_filters(
            stmt,
            category=category,
            size=size,
            price_min=price_min,
            price_max=price_max,
        )
        return await self.session.scalar(stmt) or 0

    @staticmethod
    def _apply_catalog_filters(
        stmt,
        *,
        category: ProductCategory | None,
        size: str | None,
        price_min: int | None,
        price_max: int | None,
    ):
        if category is not None:
            stmt = stmt.where(Product.category == category)
        if size is not None and size.strip():
            # Substring match: filter "M" finds "M", "M (факт M-L)", etc.
            stmt = stmt.where(Product.size.ilike(f"%{size.strip()}%"))
        # EUR is the active currency; fall back to PLN for legacy zł-only
        # products so they still sort and filter sensibly.
        price_expr = func.coalesce(Product.price_eur, Product.price_pln)
        if price_min is not None:
            stmt = stmt.where(price_expr >= price_min)
        if price_max is not None:
            stmt = stmt.where(price_expr <= price_max)
        return stmt

    @staticmethod
    def _apply_catalog_sort(stmt, sort_by: SortBy):
        price_expr = func.coalesce(Product.price_eur, Product.price_pln)
        if sort_by == SortBy.PRICE_ASC:
            return stmt.order_by(price_expr.asc(), Product.id.desc())
        if sort_by == SortBy.PRICE_DESC:
            return stmt.order_by(price_expr.desc(), Product.id.desc())
        # NEWEST (default)
        return stmt.order_by(Product.created_at.desc(), Product.id.desc())

    async def get_new_product_ids(self) -> set[int]:
        """Return IDs of the top-3 most recent IN_STOCK products per category.

        These are shown with a NEW badge in the catalog. Uses a single
        window-function query for efficiency.
        """
        rn = (
            func.row_number()
            .over(
                partition_by=Product.category,
                order_by=(Product.created_at.desc(), Product.id.desc()),
            )
            .label("rn")
        )
        inner = (
            select(Product.id.label("id"), rn)
            .where(Product.status == ProductStatus.IN_STOCK)
            .subquery()
        )
        stmt = select(inner.c.id).where(inner.c.rn <= 3)
        return set((await self.session.scalars(stmt)).all())

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
