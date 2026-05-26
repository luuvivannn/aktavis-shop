from __future__ import annotations

import json
import logging
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import DATABASE_URL, PHOTOS_DIR
from database.models import Base, Product, ProductCategory, ProductStatus

logger = logging.getLogger(__name__)

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db(*, seed: bool = True) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created.")

    await _run_migrations()

    if seed:
        _copy_bundled_photos()
        await seed_products()

    await _auto_reclassify_clothing()


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


# ──────────────────────────────────────────────────────────────────────
# Auto-migration of legacy `clothing` category → new sub-categories.
# This runs on every startup but is a no-op once all rows are migrated,
# so it's safe to leave in place during the redesign transition.
# ──────────────────────────────────────────────────────────────────────
_SHOES_KEYWORDS = (
    "тапочк", "trainer", "skate", "sneak", "loaf", "крос", "shoe",
    "обув", "сандал", "босонож", "ботин", "мокас", "runner", "replica",
    " b22", " b25", " b27", " b30", " trio",
)
_JACKETS_KEYWORDS = (
    "куртк", "ветровк", "пуховик", "пальто", "плащ", "жилет",
    "пиджак", "бомбер", "парк", "анорак", "шуб",
    "jacket", "coat", "vest", "windbreaker",
)
_PANTS_KEYWORDS = (
    "штан", "брюк", "джинс", "pants", "trousers", "jeans",
)
_TOPS_KEYWORDS = (
    "худи", "кофт", "свитшот", "лонгслив", "футболк", "майк",
    "поло", "толстовк", "свитер", "джемпер", "пуловер", "рубашк",
    "hoodie", "t-shirt", "tshirt", "tee", "longsleeve", "long sleeve",
    "sweatshirt", "sweater", "polo", "shirt",
)
_BAGS_KEYWORDS = (
    "сумк", "клатч", "рюкзак", "backpack", "tote", "пояс", " bag",
)
_ACCESSORIES_KEYWORDS = (
    "часы", "кольц", "очки", "ремень", "кошел", "шапк", "перчатк",
    "watch", "scarf", "шарф", "брелок", "браслет", "кепк", "панам",
    "sunglasses", "glasses", "belt", "cap",
)


def _classify_legacy_clothing(name: str, description: str) -> ProductCategory:
    text = (name + " " + (description or "")).lower()
    if any(kw in text for kw in _SHOES_KEYWORDS):
        return ProductCategory.SHOES
    if any(kw in text for kw in _JACKETS_KEYWORDS):
        return ProductCategory.JACKETS
    if any(kw in text for kw in _PANTS_KEYWORDS):
        return ProductCategory.PANTS
    if any(kw in text for kw in _TOPS_KEYWORDS):
        return ProductCategory.TOPS
    if any(kw in text for kw in _BAGS_KEYWORDS):
        return ProductCategory.BAGS
    if any(kw in text for kw in _ACCESSORIES_KEYWORDS):
        return ProductCategory.ACCESSORIES
    return ProductCategory.OTHER


async def _auto_reclassify_clothing() -> None:
    """Idempotent: reclassify any product still marked 'clothing' on startup.

    Also deletes obviously-junk rows (Unknown brand + name >100 chars, which
    are typically channel info posts mis-imported as products).
    """
    async with async_session_factory() as session:
        stmt = select(Product).where(Product.category == ProductCategory.CLOTHING)
        products = list((await session.scalars(stmt)).all())

    if not products:
        return

    reclassified = 0
    deleted = 0

    async with async_session_factory() as session:
        for product in products:
            # Junk row: no price, no photos, no size — channel info post.
            is_junk = (
                (product.price_pln or 0) == 0
                and not product.photos
                and not product.size
            )
            if is_junk:
                db_obj = await session.get(Product, product.id)
                if db_obj is not None:
                    await session.delete(db_obj)
                    deleted += 1
                continue

            new_cat = _classify_legacy_clothing(
                product.name, product.description or ""
            )
            db_obj = await session.get(Product, product.id)
            if db_obj is not None:
                db_obj.category = new_cat
                reclassified += 1

        await session.commit()

    logger.info(
        "Auto-migration: %d products reclassified, %d junk rows deleted.",
        reclassified, deleted,
    )


def _copy_bundled_photos() -> None:
    """Copy photos bundled with the code into PHOTOS_DIR if they aren't there.

    Useful for first-time deploys on Railway: the volume at /data is empty,
    but the repository ships with photos that the seeded products reference.
    Runs locally too as a no-op when bundled_dir == PHOTOS_DIR.
    """
    project_root = Path(__file__).resolve().parent.parent
    bundled_dir = project_root / "photos"

    if not bundled_dir.exists():
        return
    if bundled_dir.resolve() == PHOTOS_DIR.resolve():
        return

    copied = 0
    for src in bundled_dir.iterdir():
        if src.suffix.lower() not in _IMAGE_EXTS:
            continue
        dest = PHOTOS_DIR / src.name
        if dest.exists():
            continue
        try:
            shutil.copy(src, dest)
            copied += 1
        except Exception:
            logger.exception("Failed to copy bundled photo %s", src)

    if copied:
        logger.info("Copied %d bundled photos into %s", copied, PHOTOS_DIR)


async def _run_migrations() -> None:
    """Apply additive schema changes that ``create_all`` cannot do
    on already-existing SQLite tables.

    Each statement runs in its own transaction so one failing statement
    doesn't poison the rest.
    """
    statements = [
        "ALTER TABLE products ADD COLUMN channel_message_id INTEGER",
        "ALTER TABLE products ADD COLUMN channel_chat_id INTEGER",
        (
            "CREATE INDEX IF NOT EXISTS ix_products_channel_message_id "
            "ON products(channel_message_id)"
        ),
    ]
    for stmt in statements:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
                logger.info("Migration applied: %s", stmt)
        except Exception as exc:
            msg = str(exc).lower()
            if "duplicate column" in msg or "already exists" in msg:
                logger.debug("Migration already applied: %s", stmt)
            else:
                logger.warning("Migration failed: %s — %s", stmt, exc)


async def dispose_engine() -> None:
    await engine.dispose()


SEED_PRODUCTS: list[dict] = [
    {
        "brand": "C.P. Company",
        "name": "Ветровка",
        "category": ProductCategory.JACKETS,
        "size": "L",
        "condition": "Идеальное состояние",
        "description": (
            "Ветровка C.P. Company\n"
            "Размер : L\n"
            "- Идеальное состояние\n"
            "Цена : 999 zł / 275 USDT"
        ),
        "price_pln": 999,
        "price_usdt": 275,
        "photos": [
            "photos/photo_2@15-01-2026_22-31-15.jpg",
            "photos/photo_3@15-01-2026_22-31-15.jpg",
            "photos/photo_4@15-01-2026_22-31-15.jpg",
            "photos/photo_5@15-01-2026_22-31-15.jpg",
            "photos/photo_6@15-01-2026_22-31-15.jpg",
        ],
        "status": ProductStatus.IN_STOCK,
    },
    {
        "brand": "Maison Margiela",
        "name": "Худи",
        "category": ProductCategory.TOPS,
        "size": "XS (факт M-L)",
        "condition": "Идеальное состояние",
        "description": (
            "Худи Maison Margiela\n"
            "Размер : XS (факт M-L)\n"
            "- Идеальное состояние\n"
            "Цена : 1050 zł / 300 USDT"
        ),
        "price_pln": 1050,
        "price_usdt": 300,
        "photos": [
            "photos/photo_12@15-01-2026_22-42-05.jpg",
            "photos/photo_13@15-01-2026_22-42-05.jpg",
            "photos/photo_14@15-01-2026_22-42-05.jpg",
            "photos/photo_15@15-01-2026_22-42-05.jpg",
            "photos/photo_16@15-01-2026_22-42-05.jpg",
        ],
        "status": ProductStatus.IN_STOCK,
    },
    {
        "brand": "Moncler",
        "name": "Жилетка",
        "category": ProductCategory.JACKETS,
        "size": "5 (L-XL)",
        "condition": "Идеальное состояние",
        "description": (
            "Жилетка Moncler\n"
            "Размер : 5 (L-XL)\n"
            "- Идеальное состояние\n"
            "Цена : 1450 zł / 400 USDT"
        ),
        "note": "У жилетки два капюшона, второй можно увидеть на 5-ом фото.",
        "price_pln": 1450,
        "price_usdt": 400,
        "photos": [
            "photos/photo_17@15-01-2026_22-56-26.jpg",
            "photos/photo_18@15-01-2026_22-56-26.jpg",
            "photos/photo_19@15-01-2026_22-56-26.jpg",
            "photos/photo_20@15-01-2026_22-56-26.jpg",
            "photos/photo_21@15-01-2026_22-56-26.jpg",
        ],
        "status": ProductStatus.IN_STOCK,
    },
    {
        "brand": "Celine",
        "name": "Худи",
        "category": ProductCategory.TOPS,
        "size": "L",
        "condition": "Идеальное состояние",
        "description": (
            "Худи Celine\n"
            "Размер : L\n"
            "- Идеальное состояние\n"
            "Цена : 1450 zł / 400 USDT"
        ),
        "price_pln": 1450,
        "price_usdt": 400,
        "photos": [
            "photos/photo_22@16-01-2026_16-45-26.jpg",
            "photos/photo_23@16-01-2026_16-45-26.jpg",
            "photos/photo_24@16-01-2026_16-45-26.jpg",
            "photos/photo_25@16-01-2026_16-45-26.jpg",
            "photos/photo_26@16-01-2026_16-45-26.jpg",
        ],
        "status": ProductStatus.IN_STOCK,
    },
    {
        "brand": "Stone Island",
        "name": "Зип-худи",
        "category": ProductCategory.TOPS,
        "size": "M (факт M-L)",
        "condition": "Идеальное состояние",
        "description": (
            "Зип-худи Stone Island\n"
            "Размер : M (факт M-L)\n"
            "- Идеальное состояние\n"
            "Цена : 900 zł / 250 USDT"
        ),
        "price_pln": 900,
        "price_usdt": 250,
        "photos": [
            "photos/photo_27@16-01-2026_16-52-24.jpg",
            "photos/photo_28@16-01-2026_16-52-24.jpg",
            "photos/photo_29@16-01-2026_16-52-24.jpg",
            "photos/photo_30@16-01-2026_16-52-24.jpg",
            "photos/photo_31@16-01-2026_16-52-24.jpg",
        ],
        "status": ProductStatus.IN_STOCK,
    },
    {
        "brand": "Gucci",
        "name": "Тапочки",
        "category": ProductCategory.SHOES,
        "size": "42",
        "condition": "Состояние новых (пару носок)",
        "description": (
            "Тапочки Gucci\n"
            "Размер : 42\n"
            "- Состояние новых (пару носок)\n"
            "Цена : 900 zł / 250 USDT"
        ),
        "price_pln": 900,
        "price_usdt": 250,
        "photos": [
            "photos/photo_32@16-01-2026_16-57-08.jpg",
            "photos/photo_33@16-01-2026_16-57-08.jpg",
            "photos/photo_34@16-01-2026_16-57-08.jpg",
            "photos/photo_35@16-01-2026_16-57-08.jpg",
        ],
        "status": ProductStatus.IN_STOCK,
    },
    {
        "brand": "Stone Island x Supreme",
        "name": "Пуховик",
        "category": ProductCategory.JACKETS,
        "size": "M",
        "condition": "Новый (одна примерка)",
        "description": (
            "Пуховик Stone Island x Supreme\n"
            "Размер : M\n"
            "- Новый (одна примерка)\n"
            "Цена : 4500 zł / 1250 USDT\n\n"
            "🔊 VERY RARE 🔊"
        ),
        "note": "VERY RARE",
        "price_pln": 4500,
        "price_usdt": 1250,
        "photos": [
            "photos/photo_36@16-01-2026_17-02-36.jpg",
            "photos/photo_37@16-01-2026_17-02-36.jpg",
            "photos/photo_38@16-01-2026_17-02-36.jpg",
            "photos/photo_39@16-01-2026_17-02-36.jpg",
            "photos/photo_40@16-01-2026_17-02-36.jpg",
        ],
        "status": ProductStatus.IN_STOCK,
    },
]


async def seed_products() -> None:
    """Seed the database from two sources, both idempotent.

    1. Built-in ``SEED_PRODUCTS`` — added only if the DB is empty.
    2. ``seed_data.json`` snapshot of imported channel history —
       merged in by ``channel_message_id`` (skipping rows that already
       exist), so it's safe to run repeatedly.
    """
    async with async_session_factory() as session:
        existing = await session.scalar(select(Product).limit(1))
        if existing is None:
            session.add_all([Product(**payload) for payload in SEED_PRODUCTS])
            await session.commit()
            logger.info("Seeded %d built-in products.", len(SEED_PRODUCTS))
        else:
            logger.info(
                "Products already present, skipping built-in seed."
            )

    await _merge_json_snapshot()


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


async def _merge_json_snapshot() -> None:
    """Add products from ``seed_data.json`` whose channel_message_id
    isn't already in the DB. No-op if the file is missing.
    """
    snapshot_path = _project_root() / "seed_data.json"
    if not snapshot_path.exists():
        return

    try:
        items = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read seed_data.json: %s", exc)
        return

    if not items:
        return

    added = 0
    skipped = 0

    async with async_session_factory() as session:
        for item in items:
            channel_msg_id = item.get("channel_message_id")
            if channel_msg_id is None:
                # Only merge channel-sourced entries; built-ins live in code.
                continue

            existing = await session.scalar(
                select(Product).where(
                    Product.channel_message_id == channel_msg_id
                )
            )
            if existing is not None:
                skipped += 1
                continue

            payload = dict(item)
            # Coerce string enum back to the typed values
            if "status" in payload and payload["status"]:
                payload["status"] = ProductStatus(payload["status"])
            if "category" in payload and payload["category"]:
                payload["category"] = ProductCategory(payload["category"])

            try:
                session.add(Product(**payload))
                added += 1
            except Exception:
                logger.exception(
                    "Failed to add product from snapshot (msg %s)",
                    channel_msg_id,
                )

        if added:
            await session.commit()

    logger.info(
        "Snapshot merge: %d added, %d skipped (already present).",
        added, skipped,
    )
