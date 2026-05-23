"""Restore visibility of seeded products that were hidden by ``--hide-seed``.

Sets status back to ``in_stock`` for every product that has no
``channel_message_id`` (i.e. the original seed items, not channel-imported
ones) and whose current status is ``sold``.

Usage:
    python scripts/restore_seeds.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text  # noqa: E402

from database import async_session_factory  # noqa: E402


async def main() -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            text(
                "UPDATE products SET status = 'in_stock' "
                "WHERE channel_message_id IS NULL AND status = 'sold'"
            )
        )
        await session.commit()
        count = result.rowcount or 0

    if count:
        print(f"✓ Restored {count} seed products to in_stock.")
    else:
        print("Nothing to restore (no seed products were hidden).")


if __name__ == "__main__":
    asyncio.run(main())
