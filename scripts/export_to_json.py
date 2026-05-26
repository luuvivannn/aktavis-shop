"""Export imported channel products from the local DB into a JSON snapshot.

The snapshot only contains products that originate from the Telegram channel
(those with non-NULL ``channel_message_id``) — built-in seed products are
skipped because they're already defined in ``database/db.py``.

The JSON file is read on Railway startup by ``seed_products()`` to merge
these products into the production DB.

Usage:
    python scripts/export_to_json.py
"""

from __future__ import annotations

import asyncio
import json
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
from database.models import Product  # noqa: E402

OUTPUT_PATH = PROJECT_ROOT / "seed_data.json"


def _product_to_dict(p: Product) -> dict:
    return {
        "brand": p.brand,
        "name": p.name,
        "category": str(p.category),
        "size": p.size,
        "condition": p.condition,
        "description": p.description,
        "note": p.note,
        "price_pln": p.price_pln,
        "price_usdt": p.price_usdt,
        "photos": list(p.photos or []),
        "status": str(p.status),
        "channel_message_id": p.channel_message_id,
        "channel_chat_id": p.channel_chat_id,
    }


async def main() -> None:
    async with async_session_factory() as session:
        stmt = (
            select(Product)
            .where(Product.channel_message_id.is_not(None))
            .order_by(Product.channel_message_id)
        )
        products = list((await session.scalars(stmt)).all())

    data = [_product_to_dict(p) for p in products]

    OUTPUT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"✓ Exported {len(data)} products to {OUTPUT_PATH.name}")

    if not data:
        return

    in_stock = sum(1 for d in data if d["status"] == "in_stock")
    sold = sum(1 for d in data if d["status"] == "sold")
    print(f"   {in_stock} in stock, {sold} sold")

    # Quick sanity check: confirm all referenced photos exist locally
    photos_dir = PROJECT_ROOT / "photos"
    missing = []
    seen = set()
    for d in data:
        for photo_path in d["photos"]:
            name = Path(photo_path).name
            if name in seen:
                continue
            seen.add(name)
            if not (photos_dir / name).exists():
                missing.append(name)

    if missing:
        print(f"\n⚠️  {len(missing)} photo files are referenced but missing:")
        for m in missing[:10]:
            print(f"      {m}")
        if len(missing) > 10:
            print(f"      ... and {len(missing) - 10} more")
    else:
        print(f"   {len(seen)} unique photo files all present in photos/")


if __name__ == "__main__":
    asyncio.run(main())
