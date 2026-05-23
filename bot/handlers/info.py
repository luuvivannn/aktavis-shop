from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards import (
    BTN_ABOUT,
    BTN_CONTACT,
    BTN_DELIVERY,
    open_shop_inline,
)
from bot.texts import ABOUT, CONTACT, DELIVERY

router = Router(name=__name__)


@router.message(Command("delivery"))
@router.message(F.text == BTN_DELIVERY)
async def show_delivery(message: Message) -> None:
    await message.answer(
        DELIVERY,
        reply_markup=open_shop_inline(),
        disable_web_page_preview=True,
    )


@router.message(Command("about", "info"))
@router.message(F.text == BTN_ABOUT)
async def show_about(message: Message) -> None:
    await message.answer(
        ABOUT,
        reply_markup=open_shop_inline(),
        disable_web_page_preview=True,
    )


@router.message(Command("contact", "contacts"))
@router.message(F.text == BTN_CONTACT)
async def show_contact(message: Message) -> None:
    await message.answer(CONTACT, disable_web_page_preview=True)
