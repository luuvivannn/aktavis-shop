from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message, User
from sqlalchemy.ext.asyncio import AsyncSession

from bot.commands import ensure_admin_commands
from bot.keyboards import main_menu, open_shop_inline
from bot.texts import WELCOME
from config import ADMIN_IDS
from database import SubscriberRepository

router = Router(name=__name__)


async def _subscribe(session: AsyncSession, user: User, source: str) -> None:
    """Add the user to the daily promo audience (bot/promo.py)."""
    await SubscriberRepository(session).upsert(
        user.id,
        first_name=user.first_name,
        username=user.username,
        source=source,
    )


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    if message.from_user and message.chat.type == "private":
        await _subscribe(session, message.from_user, "start")

    # First message: reply keyboard for text-based navigation.
    await message.answer(WELCOME, reply_markup=main_menu())

    # Second message: inline WebApp button.
    # Inline WebApp buttons pass initData reliably on every Telegram client,
    # unlike reply-keyboard WebApp buttons (broken on Android).
    await message.answer(
        "👇 Открыть магазин",
        reply_markup=open_shop_inline(),
    )

    if message.from_user and message.from_user.id in ADMIN_IDS:
        await ensure_admin_commands(message.bot, message.from_user.id)


@router.message(F.write_access_allowed)
async def on_write_access_allowed(
    message: Message, session: AsyncSession
) -> None:
    # Telegram's service message for "allow the bot to message you" — from
    # the Mini App prompt or the checkbox when opening it from a link.
    if message.from_user:
        await _subscribe(session, message.from_user, "write_access")
