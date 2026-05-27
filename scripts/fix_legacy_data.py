"""One-off data fixes for issues spotted after Phase 4 launch:

1. Products with ``price_usdt = NULL`` whose ``description`` clearly
   contains a "<N> USDT" hint — those were imported before the channel
   parser learned to tolerate Markdown leftovers like
   ``Цена :1450 zł** **/ 400 USDT``. We re-parse them now.

2. Louis Vuitton ``Trio`` (a messenger bag) was miscategorised as SHOES
   by the original migrate_categories.py because ``" trio"`` was added
   to the shoe-keywords list (intended to catch sneaker model codes).
   Move it to BAGS.

3. Same fix applied to ``seed_data.json`` so fresh deploys to an empty
   database get the correct category from the start.

Dry-run by default. Re-run with ``--apply`` to commit.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from database.db import async_session_factory  # noqa: E402
from database.models import Product, ProductCategory, ProductStatus  # noqa: E402

USDT_RE = re.compile(r"(\d[\d\s]*)\s*USDT", re.IGNORECASE)
SEED_PATH = PROJECT_ROOT / "seed_data.json"


def _looks_like_trio_bag(brand: str, name: str) -> bool:
    """Louis Vuitton 'Trio' Messenger Bag — miscategorised as shoes."""
    return brand.lower() == "louis vuitton" and "trio" in name.lower()


async def _fix_db(*, apply: bool) -> tuple[int, int]:
    """Returns (usdt_recovered, category_fixed) counts."""
    usdt_recovered = 0
    cat_fixed = 0

    async with async_session_factory() as session:
        # 1. Re-parse USDT from descriptions
        stmt = select(Product).where(
            Product.status == ProductStatus.IN_STOCK,
            Product.price_usdt.is_(None),
        )
        for product in (await session.scalars(stmt)).all():
            desc = product.description or ""
            m = USDT_RE.search(desc)
            if not m:
                continue
            try:
                usdt = int(re.sub(r"\s", "", m.group(1)))
            except ValueError:
                continue
            print(
                f"  USDT  id={product.id:>3}  {product.brand[:20]:20}  "
                f"{product.name[:30]:30}  → {usdt} USDT"
            )
            if apply:
                product.price_usdt = usdt
            usdt_recovered += 1

        # 2. Fix LV Trio: SHOES → BAGS
        stmt = select(Product).where(
            Product.category == ProductCategory.SHOES,
        )
        for product in (await session.scalars(stmt)).all():
            if not _looks_like_trio_bag(product.brand, product.name):
                continue
            print(
                f"  CAT   id={product.id:>3}  {product.brand[:20]:20}  "
                f"{product.name[:30]:30}  shoes → bags"
            )
            if apply:
                product.category = ProductCategory.BAGS
            cat_fixed += 1

        if apply:
            await session.commit()

    return usdt_recovered, cat_fixed


def _fix_seed_json(*, apply: bool) -> int:
    """Patch seed_data.json so fresh deploys get correct categories."""
    if not SEED_PATH.exists():
        return 0
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    fixed = 0
    for item in data:
        if not _looks_like_trio_bag(item.get("brand", ""), item.get("name", "")):
            continue
        if item.get("category") == "bags":
            continue
        print(
            f"  SEED  {item.get('brand'):20}  {item.get('name'):30}  "
            f"{item.get('category')} → bags"
        )
        item["category"] = "bags"
        fixed += 1
    if apply and fixed:
        SEED_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return fixed


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit changes. Without this flag the script is dry-run.",
    )
    args = parser.parse_args()

    print()
    print("=" * 70)
    print("Fixing legacy data ({} mode)".format("APPLY" if args.apply else "DRY-RUN"))
    print("=" * 70)

    usdt, cat = await _fix_db(apply=args.apply)
    seed = _fix_seed_json(apply=args.apply)

    print()
    print("Summary:")
    print(f"  USDT prices recovered : {usdt}")
    print(f"  Category fixes (Trio) : {cat}")
    print(f"  seed_data.json patches: {seed}")

    if not args.apply:
        print()
        print("Dry-run only. Re-run with --apply to commit.")


if __name__ == "__main__":
    asyncio.run(main())
