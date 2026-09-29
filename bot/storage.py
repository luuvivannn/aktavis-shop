"""Photo-volume housekeeping: a cleanup on boot + daily, and ``/cleanup``.

What a run removes is described in ``database.storage``. The owner (the
backup chat) gets a DM when a run frees a lot of space or the volume is
still nearly full — ordinary days stay silent.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import Message

from bot.backup import backup_chat_id
from config import ADMIN_IDS
from database.storage import CleanupReport, disk_usage, run_storage_cleanup

logger = logging.getLogger(__name__)

router = Router(name=__name__)

# Let the API come up and pass Railway's healthcheck before the first
# (CPU-heavy on a fresh volume) run.
_STARTUP_DELAY_SECONDS = 60
_INTERVAL_SECONDS = 24 * 3600

_NOTIFY_FREED_BYTES = 50 * 1024 * 1024
_ALERT_USAGE = 0.85


def _mb(n: int) -> str:
    return f"{n / 1048576:.0f} МБ"


def _volume_nearly_full() -> bool:
    used, total = disk_usage()
    return total > 0 and used / total >= _ALERT_USAGE


def _format_report(report: CleanupReport) -> str:
    used, total = disk_usage()
    lines = ["🧹 <b>Чистка фото</b>"]
    if report.sold_trimmed:
        lines.append(
            f"Проданные: оставлено по 1 фото у {report.sold_trimmed} шт."
        )
    lines += [
        f"Удалено файлов: {report.deleted}",
        f"Пережато: {report.shrunk}",
        f"Освобождено: {_mb(report.freed_bytes)}",
        f"Диск: {_mb(used)} из {_mb(total)} ({used / total:.0%})",
    ]
    if _volume_nearly_full():
        lines.append("\n⚠️ Volume почти заполнен — нужно больше места.")
    return "\n".join(lines)


@router.message(Command("cleanup"))
async def cmd_cleanup(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if user_id is None or (
        user_id not in ADMIN_IDS and user_id != backup_chat_id()
    ):
        return  # silently ignore non-admins
    notice = await message.answer("⏳ Чищу фото…")
    try:
        report = await run_storage_cleanup()
        if report.skipped:
            await message.answer("Локальный запуск — чистка отключена.")
        else:
            await message.answer(_format_report(report))
    except Exception:
        logger.exception("Manual /cleanup failed")
        await message.answer("⚠️ Чистка не удалась — подробности в логах.")
    finally:
        try:
            await notice.delete()
        except Exception:
            pass


async def storage_loop(bot: Bot) -> None:
    """Run the cleanup shortly after boot, then daily.

    Never lets an exception escape, for the same reason as ``backup_loop``:
    the bot and the shop API share one process.
    """
    await asyncio.sleep(_STARTUP_DELAY_SECONDS)
    while True:
        try:
            report = await run_storage_cleanup()
            if not report.skipped and (
                report.freed_bytes >= _NOTIFY_FREED_BYTES
                or _volume_nearly_full()
            ):
                await _notify_owner(bot, _format_report(report))
        except Exception:
            logger.exception("Storage cleanup failed; retrying next cycle.")
        await asyncio.sleep(_INTERVAL_SECONDS)


async def _notify_owner(bot: Bot, text: str) -> None:
    chat_id = backup_chat_id()
    if chat_id is None:
        return
    try:
        await bot.send_message(chat_id, text)
    except TelegramAPIError:
        logger.exception("Failed to send cleanup report to %s", chat_id)
