"""Daily promo broadcast.

Every day at ``PROMO_HOUR`` (Warsaw time) the bot DMs the promo post —
photo, caption and link buttons — to every subscriber: users who pressed
/start or allowed the bot to message them from the Mini App. Telegram
doesn't let a bot write to anyone else.

``/promo`` shows the admin a preview of the post plus audience stats.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot, Router
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.backup import backup_chat_id
from config import ADMIN_IDS, PROMO_ENABLED, PROMO_HOUR
from database import PromoBroadcast, SubscriberRepository, async_session_factory

logger = logging.getLogger(__name__)

router = Router(name=__name__)

PROMO_TZ = ZoneInfo("Europe/Warsaw")
PROMO_PHOTO = Path(__file__).resolve().parent / "assets" / "promo.jpg"

_ADMIN_DM = "https://t.me/aktavis_eu"

PROMO_CAPTION = (
    "💸 <b>Выкупаю ваши вещи в день обращения</b>\n\n"
    "Сразу пишите цену, состояние и размер, так отвечу быстрее\n\n"
    "📍 Варшава / Шип\n\n"
    "Chrome Hearts / Dior / Louis Vuitton / Balenciaga / Gucci / Amiri / "
    "Valentino / Moncler / Givenchy / Burberry / Palm Angels / "
    "Stone Island / Prada / C.P Company / Vetements / Palace / "
    "Maison Margiela"
)

PROMO_BUTTONS: list[tuple[str, str]] = [
    ("Заказать", _ADMIN_DM),
    ("Проверить вещь на оригинальность", _ADMIN_DM),
    ("Отзывы", "https://t.me/actavis_feedback"),
    ("TikTok", "https://www.tiktok.com/@aktaviss"),
    ("Instagram", "https://www.instagram.com/aktavis.eu"),
]

# Telegram allows a bot ~30 messages/sec overall; stay well under it.
_SEND_INTERVAL_SECONDS = 0.05
# If the bot was down at the scheduled hour (redeploy), still send once it
# is back within this window — any later and the post lands at night.
_GRACE = timedelta(hours=3)
_CHECK_INTERVAL_SECONDS = 60
_STARTUP_DELAY_SECONDS = 45

# Telegram file_id of the uploaded photo: the image is uploaded on the
# first send of a process and reused for every other recipient.
_photo_file_id: str | None = None


def promo_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, url=url)]
            for text, url in PROMO_BUTTONS
        ]
    )


async def send_promo(bot: Bot, chat_id: int) -> None:
    global _photo_file_id
    message = await bot.send_photo(
        chat_id,
        photo=_photo_file_id or FSInputFile(PROMO_PHOTO),
        caption=PROMO_CAPTION,
        reply_markup=promo_keyboard(),
    )
    if _photo_file_id is None and message.photo:
        _photo_file_id = message.photo[-1].file_id


async def _deliver(bot: Bot, user_id: int) -> str:
    """Send the promo to one user. Returns "sent", "blocked" or "failed"."""
    for _ in range(3):
        try:
            await send_promo(bot, user_id)
            return "sent"
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 1)
        except TelegramForbiddenError:
            return "blocked"  # blocked the bot or deleted the account
        except TelegramBadRequest as exc:
            if "chat not found" in str(exc).lower():
                return "blocked"
            logger.warning("Promo to %s rejected: %s", user_id, exc)
            return "failed"
        except TelegramAPIError:
            logger.exception("Promo to %s failed", user_id)
            return "failed"
    return "failed"


async def run_broadcast(bot: Bot, day: date) -> PromoBroadcast | None:
    """Send the promo for ``day`` to every active subscriber.

    Returns None if that day's broadcast already ran. The day is claimed in
    the DB before the first send, so a crash or redeploy mid-run never
    makes anyone get the post twice.
    """
    async with async_session_factory() as session:
        already = await session.scalar(
            select(PromoBroadcast.id).where(PromoBroadcast.promo_date == day)
        )
        if already is not None:
            return None
        user_ids = await SubscriberRepository(session).active_ids()
        record = PromoBroadcast(promo_date=day, recipients=len(user_ids))
        session.add(record)
        await session.commit()
        record_id = record.id

    logger.info("Promo broadcast for %s: %d recipients.", day, len(user_ids))
    sent = failed = 0
    blocked: list[int] = []
    for user_id in user_ids:
        result = await _deliver(bot, user_id)
        if result == "sent":
            sent += 1
        elif result == "blocked":
            blocked.append(user_id)
        else:
            failed += 1
        await asyncio.sleep(_SEND_INTERVAL_SECONDS)

    async with async_session_factory() as session:
        await SubscriberRepository(session).mark_blocked(blocked)
        record = await session.get(PromoBroadcast, record_id)
        record.sent = sent
        record.blocked = len(blocked)
        record.failed = failed
        record.finished_at = func.now()
        await session.commit()
        await session.refresh(record)

    logger.info(
        "Promo broadcast for %s done: %d sent, %d blocked, %d failed.",
        day, sent, len(blocked), failed,
    )
    return record


def _format_result(record: PromoBroadcast) -> str:
    line = (
        f"{record.promo_date:%d.%m}: "
        f"доставлено {record.sent} из {record.recipients}"
    )
    if record.blocked:
        line += f" · заблокировали бота: {record.blocked}"
    if record.failed:
        line += f" · ошибок: {record.failed}"
    return line


async def _report(bot: Bot, record: PromoBroadcast) -> None:
    text = f"📣 Рассылка {_format_result(record)}"
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except TelegramAPIError:
            logger.warning("Could not send promo report to %s", admin_id)


async def promo_loop(bot: Bot) -> None:
    """Send the promo once a day at PROMO_HOUR, Warsaw time.

    Never raises — like the backup loop, a failure here must not take the
    shop down with it.
    """
    if not PROMO_ENABLED:
        logger.info("Promo broadcast disabled (PROMO_ENABLED=false).")
        return

    logger.info(
        "Promo broadcast enabled: daily at %02d:00 Europe/Warsaw.", PROMO_HOUR
    )
    await asyncio.sleep(_STARTUP_DELAY_SECONDS)
    while True:
        try:
            now = datetime.now(PROMO_TZ)
            slot = now.replace(
                hour=PROMO_HOUR, minute=0, second=0, microsecond=0
            )
            if slot <= now < slot + _GRACE:
                record = await run_broadcast(bot, slot.date())
                if record is not None:
                    await _report(bot, record)
        except Exception:
            logger.exception("Promo broadcast failed; retrying next check.")
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)


@router.message(Command("promo"))
async def cmd_promo(message: Message, session: AsyncSession) -> None:
    user_id = message.from_user.id if message.from_user else None
    if user_id is None or (
        user_id not in ADMIN_IDS and user_id != backup_chat_id()
    ):
        return  # silently ignore non-admins

    await send_promo(message.bot, message.chat.id)

    active, blocked = await SubscriberRepository(session).counts()
    last = await session.scalar(
        select(PromoBroadcast).order_by(PromoBroadcast.promo_date.desc())
    )
    lines = ["👆 Так выглядит пост рассылки", ""]
    if PROMO_ENABLED:
        lines.append(f"Каждый день в {PROMO_HOUR:02d}:00 по Варшаве")
    else:
        lines.append("Рассылка выключена (PROMO_ENABLED=false)")
    subscribers = f"Подписчиков: {active}"
    if blocked:
        subscribers += f" · заблокировали бота: {blocked}"
    lines.append(subscribers)
    if last is not None:
        lines.append(f"Последняя: {_format_result(last)}")
    await message.answer("\n".join(lines))
