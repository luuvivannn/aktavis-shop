"""Admin-only catalog curation from inside the bot.

`/hidden` lists every product the admin has hidden (status HIDDEN) with a
one-tap restore button. Hiding happens from the channel-post preview
(see ``handlers/channel.py``); this is the central place to review and
undo those hides — no code edits, no redeploy.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.callbacks import HiddenListAction
from config import ADMIN_IDS
from database import Product, ProductStatus

logger = logging.getLogger(__name__)

router = Router(name=__name__)

_MAX_LISTED = 50


def _is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in ADMIN_IDS


async def _hidden_products(session: AsyncSession) -> list[Product]:
    stmt = (
        select(Product)
        .where(Product.status == ProductStatus.HIDDEN)
        .order_by(Product.brand, Product.name, Product.id)
        .limit(_MAX_LISTED)
    )
    return list((await session.scalars(stmt)).all())


def _render_hidden(products: list[Product]) -> tuple[str, InlineKeyboardMarkup | None]:
    if not products:
        return "✨ Скрытых товаров нет.", None

    lines = [f"🙈 <b>Скрытые товары ({len(products)})</b>", ""]
    rows: list[list[InlineKeyboardButton]] = []
    for p in products:
        if p.price_eur:
            price = f"{p.price_eur}€"
        elif p.price_pln:
            price = f"{p.price_pln} zł"
        else:
            price = "?"
        lines.append(f"#{p.id} · {p.brand} {p.name} · {price}")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"👁 Вернуть #{p.id} · {p.brand} {p.name}"[:64],
                    callback_data=HiddenListAction(
                        product_id=p.id, action="restore"
                    ).pack(),
                )
            ]
        )

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("hidden"))
async def cmd_hidden(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return  # silently ignore non-admins

    products = await _hidden_products(session)
    text, markup = _render_hidden(products)
    await message.answer(text, reply_markup=markup)


@router.callback_query(HiddenListAction.filter())
async def on_hidden_restore(
    query: CallbackQuery,
    callback_data: HiddenListAction,
    session: AsyncSession,
) -> None:
    if not _is_admin(query.from_user.id):
        await query.answer("Только для админов", show_alert=True)
        return

    product = await session.get(Product, callback_data.product_id)
    if product is None:
        await query.answer("Товар не найден", show_alert=True)
    elif product.status != ProductStatus.HIDDEN:
        await query.answer("Товар уже не скрыт")
    else:
        product.status = ProductStatus.IN_STOCK
        await session.commit()
        logger.info(
            "Admin %s restored product %s (%s %s) HIDDEN → IN_STOCK",
            query.from_user.id, product.id, product.brand, product.name,
        )
        await query.answer(f"Вернул #{product.id} в каталог")

    # Re-render the list so the restored item drops off immediately.
    products = await _hidden_products(session)
    text, markup = _render_hidden(products)
    if query.message:
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except TelegramAPIError:
            logger.exception("Failed to re-render /hidden list")
