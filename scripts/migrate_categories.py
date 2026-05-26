"""Migrate existing 'clothing' products into new categories.

Reads all ``Product`` rows with ``category='clothing'``, classifies each
based on keywords in the ``name`` field, prints a summary table, then
applies updates only if invoked with ``--apply``.

By default this script is a **dry-run** — it shows what would change
without writing to the database. Re-run with ``--apply`` to commit.

Usage:
    python scripts/migrate_categories.py           # dry-run (preview)
    python scripts/migrate_categories.py --apply   # commit changes
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Make sure we can print emoji on Windows consoles (cp1250/cp1252).
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from database.db import async_session_factory  # noqa: E402
from database.models import Product, ProductCategory  # noqa: E402


# Keyword classifiers. Each category list mixes Russian and English
# terms because imported channel posts use both (e.g. "**Худи" vs
# "** Hoodie", "Кроссовки" vs "Runner").
#
# Order matters: SHOES is checked BEFORE clothing categories because some
# sneaker model names (Replica, Runner, B22) might otherwise be ambiguous.
SHOES_KEYWORDS = (
    "тапочк", "trainer", "skate", "sneak", "loaf", "крос", "shoe",
    "обув", "сандал", "босонож", "ботин", "мокас", "runner", "replica",
    " b22", " b25", " b27", " b30", " trio",
)
JACKETS_KEYWORDS = (
    "куртк", "ветровк", "пуховик", "пальто", "плащ", "жилет",
    "пиджак", "бомбер", "парк", "анорак", "шуб",
    "jacket", "coat", "vest", "windbreaker", "down jacket",
)
TOPS_KEYWORDS = (
    "худи", "кофт", "свитшот", "лонгслив", "футболк", "майк",
    "поло", "толстовк", "свитер", "джемпер", "пуловер", "рубашк",
    "hoodie", "t-shirt", "tshirt", "tee", "longsleeve", "long sleeve",
    "sweatshirt", "sweater", "polo", "shirt",
)
BAGS_KEYWORDS = (
    "сумк", "клатч", "рюкзак", "backpack", "tote", "пояс", " bag",
)
ACCESSORIES_KEYWORDS = (
    "часы", "кольц", "очки", "ремень", "кошел", "шапк", "перчатк",
    "watch", "scarf", "шарф", "брелок", "браслет", "кепк", "панам",
    "sunglasses", "glasses", "belt", "cap",
)
# We don't have a Pants category in the Mini App — these fall to OTHER
# unless we add one. Track them so the report flags them clearly.
PANTS_KEYWORDS = ("штан", "брюк", "джинс", "pants", "trousers", "jeans")


def classify(name: str, description: str = "") -> ProductCategory:
    """Classify a product into a category based on name + description.

    The description is included because imported channel posts sometimes
    have model-codes in the name ('B22', '** Trio') and the actual
    product type only appears in the body of the post.
    """
    text = (name + " " + description).lower()

    # Order matters: SHOES first (catches sneaker model codes), then
    # outerwear (jackets), then pants, then tops, then bags/accessories.
    if any(kw in text for kw in SHOES_KEYWORDS):
        return ProductCategory.SHOES
    if any(kw in text for kw in JACKETS_KEYWORDS):
        return ProductCategory.JACKETS
    if any(kw in text for kw in PANTS_KEYWORDS):
        return ProductCategory.PANTS
    if any(kw in text for kw in TOPS_KEYWORDS):
        return ProductCategory.TOPS
    if any(kw in text for kw in BAGS_KEYWORDS):
        return ProductCategory.BAGS
    if any(kw in text for kw in ACCESSORIES_KEYWORDS):
        return ProductCategory.ACCESSORIES
    return ProductCategory.OTHER


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the changes. Without this flag the script is dry-run.",
    )
    args = parser.parse_args()

    async with async_session_factory() as session:
        stmt = (
            select(Product)
            .where(Product.category == ProductCategory.CLOTHING)
            .order_by(Product.id)
        )
        products = list((await session.scalars(stmt)).all())

    if not products:
        print("No products with category='clothing' found. Nothing to migrate.")
        return

    print()
    print("=" * 90)
    print(f"📦 Found {len(products)} products with category='clothing'")
    print("=" * 90)
    print()
    print(f"  {'ID':>4}  {'Brand':22}  {'Name':35}  →  {'New category'}")
    print("  " + "─" * 86)

    decisions: list[tuple[Product, ProductCategory]] = []
    for product in products:
        new_cat = classify(product.name, product.description or "")
        decisions.append((product, new_cat))
        marker = "⚠️" if new_cat == ProductCategory.OTHER else "  "
        brand = product.brand[:22]
        name = product.name[:35]
        print(
            f"{marker}{product.id:>4}  {brand:22}  {name:35}  →  {new_cat.value}"
        )

    print()
    print("Summary:")
    by_cat: dict[ProductCategory, int] = {}
    for _, cat in decisions:
        by_cat[cat] = by_cat.get(cat, 0) + 1
    for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat.value:12}  {count}")

    other_count = by_cat.get(ProductCategory.OTHER, 0)
    if other_count:
        print(
            f"\n⚠️  {other_count} product(s) fell back to 'other' — "
            f"review and adjust keywords or fix manually after migration."
        )

    # Detect junk rows: no price, no photos, no size — these are channel
    # info posts mis-imported as products (e.g., welcome message, rules).
    junk_rows = [
        p for p, _ in decisions
        if (p.price_pln or 0) == 0 and not p.photos and not p.size
    ]
    if junk_rows:
        print()
        print(
            f"🗑️  Found {len(junk_rows)} junk row(s) (no price + no photos "
            f"+ no size — channel info posts mis-imported as products):"
        )
        for p in junk_rows:
            print(f"     id={p.id}  {p.name[:60]}...")
        print("     → will be DELETED with --apply")

    if not args.apply:
        print()
        print("─" * 90)
        print("Dry-run only. Nothing was changed.")
        print("Re-run with --apply to commit these changes.")
        print("─" * 90)
        return

    # Apply
    print()
    print("⚙️  Applying changes...")
    async with async_session_factory() as session:
        for product, new_cat in decisions:
            # Skip junk rows — they get deleted below
            if product in junk_rows:
                continue
            db_product = await session.get(Product, product.id)
            if db_product is None:
                continue
            db_product.category = new_cat
        # Delete junk rows
        for junk in junk_rows:
            db_junk = await session.get(Product, junk.id)
            if db_junk is not None:
                await session.delete(db_junk)
        await session.commit()

    deleted = len(junk_rows)
    updated = len(decisions) - deleted
    print(f"✓ Committed {updated} category updates, {deleted} junk rows deleted.")


if __name__ == "__main__":
    asyncio.run(main())
