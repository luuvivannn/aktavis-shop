from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.commands import ensure_admin_commands
from bot.keyboards import main_menu, open_shop_inline
from bot.texts import WELCOME
from config import ADMIN_IDS

router = Router(name=__name__)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
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
