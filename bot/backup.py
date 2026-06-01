"""Telegram-delivered database backups.

Sends a fresh copy of ``shop.db`` to the admin (or a configured backup
chat) as a document — both on a timer and on the ``/backup`` command.
Telegram's cloud then doubles as off-site storage, so a lost Railway
volume no longer means a lost catalog.

Restore is trivial: download the file, drop it in place of ``shop.db``
on the volume, restart.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message
from sqlalchemy import func, select

from config import ADMIN_IDS, BACKUP_CHAT_ID, BACKUP_INTERVAL_HOURS
from database import Product, async_session_factory
from database.backup import create_backup_file

logger = logging.getLogger(__name__)

router = Router(name=__name__)

# Wait a little after boot so seeding/migrations settle before the first
# scheduled snapshot, and so rapid redeploys don't each fire instantly.
_STARTUP_DELAY_SECONDS = 30


def _backup_chat_id() -> int | None:
    if BACKUP_CHAT_ID is not None:
        return BACKUP_CHAT_ID
    if ADMIN_IDS:
        return ADMIN_IDS[0]
    return None


async def _product_count() -> int:
    async with async_session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(Product))
        return int(total or 0)


async def send_backup(bot: Bot, chat_id: int) -> None:
    """Create a snapshot and send it to ``chat_id``. Cleans up the file."""
    path = await create_backup_file()
    try:
        size_kb = path.stat().st_size / 1024
        count = await _product_count()
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        caption = (
            "💾 <b>Бэкап базы AKTAVIS</b>\n"
            f"{stamp}\n"
            f"Товаров: {count} · {size_kb:.0f} КБ\n\n"
            "Восстановление: положить этот файл на место "
            "<code>shop.db</code> и перезапустить."
        )
        await bot.send_document(
            chat_id,
            FSInputFile(path, filename=path.name),
            caption=caption,
        )
    finally:
        path.unlink(missing_ok=True)


@router.message(Command("backup"))
async def cmd_backup(message: Message) -> None:
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return  # silently ignore non-admins
    notice = await message.answer("⏳ Делаю бэкап базы…")
    try:
        await send_backup(message.bot, message.chat.id)
    except Exception:
        logger.exception("Manual /backup failed")
        await message.answer(
            "⚠️ Не удалось сделать бэкап — подробности в логах."
        )
    finally:
        try:
            await notice.delete()
        except Exception:
            pass


async def backup_loop(bot: Bot) -> None:
    """Periodically DM a DB snapshot to the backup chat.

    Bullet-proof by design: it never lets an exception escape, so a backup
    hiccup can't take down the bot or the shop API (they share one
    process and are torn down together on the first unhandled error).
    """
    chat_id = _backup_chat_id()
    if chat_id is None:
        logger.warning(
            "Auto-backup disabled: no BACKUP_CHAT_ID and no ADMIN_IDS set."
        )
        return

    interval = max(1, BACKUP_INTERVAL_HOURS) * 3600
    logger.info(
        "Auto-backup enabled: every %dh to chat %s.",
        BACKUP_INTERVAL_HOURS,
        chat_id,
    )

    await asyncio.sleep(_STARTUP_DELAY_SECONDS)
    while True:
        try:
            await send_backup(bot, chat_id)
            logger.info("Scheduled DB backup sent to %s.", chat_id)
        except Exception:
            logger.exception("Scheduled backup failed; retrying next cycle.")
        await asyncio.sleep(interval)
