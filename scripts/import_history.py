"""One-time historical import of channel posts via Telethon.

Reads the full history of the configured Telegram channel using your
personal Telegram account (so the bot does NOT need to be channel admin),
parses each post with the same parser used for live updates, downloads
photos, and creates Products in the database.

Idempotent: posts that were already imported (matched by
channel_message_id) are skipped on subsequent runs.

Usage:
    python scripts/import_history.py                  # import all posts
    python scripts/import_history.py --hide-seed      # also hide non-channel
                                                      # seed products from the
                                                      # catalog by marking
                                                      # them as SOLD
    python scripts/import_history.py --limit 50       # import only N posts

On the first run Telethon will ask for your phone number and the login
code that Telegram sends to your account. The session is saved to a local
``telethon.session`` file so subsequent runs don't ask again.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text  # noqa: E402
from telethon import TelegramClient  # noqa: E402

from bot.channel_parser import parse_channel_post  # noqa: E402
from config import (  # noqa: E402
    CHANNEL_USERNAME,
    PHOTOS_DIR,
    TELEGRAM_API_HASH,
    TELEGRAM_API_ID,
)
from database import (  # noqa: E402
    Product,
    ProductRepository,
    ProductStatus,
    async_session_factory,
    init_db,
)

logger = logging.getLogger(__name__)

SESSION_PATH = PROJECT_ROOT / "telethon"


# ─────────────────────────────────────────────────────────────
# Collect channel messages and group them
# ─────────────────────────────────────────────────────────────
async def collect_posts(client: TelegramClient, limit: int | None) -> list[list]:
    print(f"📡 Reading messages from @{CHANNEL_USERNAME}...")

    groups: dict[int, list] = {}
    singles: list = []

    total = 0
    async for msg in client.iter_messages(CHANNEL_USERNAME, limit=limit):
        total += 1
        if total % 50 == 0:
            print(f"   ... {total} messages read")

        if msg.grouped_id:
            groups.setdefault(msg.grouped_id, []).append(msg)
        else:
            singles.append(msg)

    print(
        f"📦 Read {total} messages: "
        f"{len(groups)} media groups + {len(singles)} singles"
    )

    posts = list(groups.values()) + [[m] for m in singles]
    posts.sort(key=lambda p: min(m.id for m in p))  # chronological
    return posts


# ─────────────────────────────────────────────────────────────
# Process one post (1 message or a media-group of N)
# ─────────────────────────────────────────────────────────────
async def process_post(
    client: TelegramClient, messages: list
) -> tuple[bool, str]:
    sorted_msgs = sorted(messages, key=lambda m: m.id)
    first_id = sorted_msgs[0].id

    caption = ""
    for m in sorted_msgs:
        if m.text:
            caption = m.text
            break

    if not caption.strip():
        return False, "no caption"

    parsed = parse_channel_post(caption)
    if parsed is None:
        return False, "unparseable"

    if not parsed.price_pln and not parsed.is_sold:
        return False, f"no price found in '{parsed.title[:40]}...'"

    async with async_session_factory() as session:
        repo = ProductRepository(session)
        if await repo.get_by_channel_message_id(first_id):
            return False, f"already imported (msg {first_id})"

    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    photo_paths: list[str] = []
    for idx, msg in enumerate(sorted_msgs):
        if not msg.photo:
            continue
        filename = f"channel_{first_id}_{idx}.jpg"
        full_path = PHOTOS_DIR / filename
        try:
            await client.download_media(msg, file=full_path)
            photo_paths.append(f"photos/{filename}")
        except Exception as exc:
            logger.warning("Photo download failed (msg %s): %s", msg.id, exc)

    status = ProductStatus.SOLD if parsed.is_sold else ProductStatus.IN_STOCK

    async with async_session_factory() as session:
        product = Product(
            brand=parsed.brand,
            name=parsed.name,
            category=parsed.category,
            size=parsed.size,
            condition=parsed.condition,
            description=parsed.description,
            note=parsed.note,
            price_pln=parsed.price_pln or 0,
            price_usdt=parsed.price_usdt,
            photos=photo_paths,
            status=status,
            channel_message_id=first_id,
            channel_chat_id=sorted_msgs[0].chat_id,
        )
        session.add(product)
        await session.commit()

    label = "SOLD" if status == ProductStatus.SOLD else "STOCK"
    return True, f"[{label}] {parsed.brand} — {parsed.name} ({parsed.size or '—'})"


# ─────────────────────────────────────────────────────────────
# Hide pre-existing seed products
# ─────────────────────────────────────────────────────────────
async def hide_seed_products() -> int:
    async with async_session_factory() as session:
        result = await session.execute(
            text(
                "UPDATE products SET status = 'sold' "
                "WHERE channel_message_id IS NULL AND status != 'sold'"
            )
        )
        await session.commit()
        return result.rowcount or 0


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import channel history into the shop database."
    )
    parser.add_argument(
        "--hide-seed",
        action="store_true",
        help=(
            "Before importing, mark all products with no channel_message_id "
            "as SOLD so they hide from the catalog (keeps order history intact)."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Import only the latest N messages (useful for testing).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,  # less noisy by default; bumped to INFO in our code
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        print("❌ TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
        sys.exit(1)
    if not CHANNEL_USERNAME:
        print("❌ CHANNEL_USERNAME must be set in .env")
        sys.exit(1)

    print("=" * 60)
    print("🛍  AKTAVIS channel history importer")
    print(f"   Channel: @{CHANNEL_USERNAME}")
    print("=" * 60)

    await init_db(seed=False)

    print(
        "🔑 If this is the first run, Telethon will ask for your phone number "
        "and the login code that Telegram sends.\n"
    )

    client = TelegramClient(str(SESSION_PATH), TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await client.start()

    me = await client.get_me()
    username = f"@{me.username}" if me.username else f"id={me.id}"
    print(f"👤 Logged in as: {me.first_name} ({username})\n")

    # Hide seeds only AFTER successful auth, so we don't wipe the catalog
    # if the user fails the login step.
    if args.hide_seed:
        hidden = await hide_seed_products()
        print(f"🙈 Hid {hidden} pre-existing non-channel products.\n")

    posts = await collect_posts(client, limit=args.limit)
    print(f"\n⚙️  Processing {len(posts)} posts...\n")

    imported = 0
    skipped = 0
    failed = 0

    for i, messages in enumerate(posts, 1):
        first_id = min(m.id for m in messages)
        try:
            success, info = await process_post(client, messages)
            if success:
                imported += 1
                print(f"  [{i:>3}/{len(posts)}] ✓ {info}")
            else:
                skipped += 1
        except Exception:
            failed += 1
            logger.exception("Failed processing post %s", first_id)

    await client.disconnect()

    print()
    print("=" * 60)
    print(
        f"✅ Done. Imported: {imported} · Skipped: {skipped} · Failed: {failed}"
    )
    print("=" * 60)

    if imported:
        print("\n💡 New products are visible in the Mini App now.")
        print("   Refresh the catalog to see them.")
    if skipped:
        print(
            "\n   Skipped posts usually mean: no caption, no price, or "
            "already imported."
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⛔ Cancelled by user")
