"""Quick stats of the local shop database.

Shows total products, breakdown by status and by brand.
Helps decide what's worth syncing to Railway.

Usage:
    python scripts/show_stats.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, select  # noqa: E402

from database.db import async_session_factory  # noqa: E402
from database.models import Product, ProductStatus  # noqa: E402


async def main() -> None:
    async with async_session_factory() as session:
        total = await session.scalar(select(func.count(Product.id)))

        print("=" * 50)
        print(f"📦 Total products: {total}")
        print("=" * 50)

        print("\n📊 By status:")
        for status in ProductStatus:
            count = await session.scalar(
                select(func.count(Product.id)).where(Product.status == status)
            )
            print(f"   {status.value:20s} {count}")

        print("\n🏷  By brand (top 15):")
        result = await session.execute(
            select(Product.brand, func.count(Product.id))
            .group_by(Product.brand)
            .order_by(func.count(Product.id).desc())
            .limit(15)
        )
        for brand, count in result.all():
            print(f"   {brand:25s} {count}")

        print("\n📂 By category:")
        result = await session.execute(
            select(Product.category, func.count(Product.id))
            .group_by(Product.category)
            .order_by(func.count(Product.id).desc())
        )
        for category, count in result.all():
            print(f"   {category:20s} {count}")

        print("\n💰 Price range (all products in stock):")
        stock_query = select(Product).where(
            Product.status == ProductStatus.IN_STOCK
        )
        prices = [p.price_pln for p in (await session.scalars(stock_query)).all() if p.price_pln]
        if prices:
            print(f"   min:   {min(prices)} zł")
            print(f"   max:   {max(prices)} zł")
            print(f"   avg:   {sum(prices) // len(prices)} zł")
            print(f"   total: {sum(prices)} zł (если бы продали всё)")
        else:
            print("   (нет товаров в наличии)")

        print()


if __name__ == "__main__":
    asyncio.run(main())
