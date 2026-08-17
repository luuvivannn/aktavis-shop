"""Admin-only catalog curation from inside the bot.

`/hidden` lists every product the admin has hidden (status HIDDEN) with a
one-tap restore button. Hiding happens from the channel-post preview
(see ``handlers/channel.py``); this is the central place to review and
undo those hides — no code edits, no redeploy.

`/pending` lists products stuck in PENDING with no preview ever sent — the
debounced preview timer in ``handlers/channel.py`` lives only in memory, so
a bot restart between a channel post landing and its preview firing loses
the timer forever, leaving an invisible draft in the DB. This is the
recovery path: publish or discard those drafts by hand.
"""

from __future__ import annotations

import logging
from pathlib import Path

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

from bot.callbacks import HiddenListAction, PendingListAction
from config import ADMIN_IDS, PHOTOS_DIR
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
        lines.append(f"#{p.id} · {p.brand} {p.name} · {_format_price(p)}")
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


def _format_price(p: Product) -> str:
    if p.price_eur:
        return f"{p.price_eur}€"
    if p.price_pln:
        return f"{p.price_pln} zł"
    return "?"


async def _pending_products(session: AsyncSession) -> list[Product]:
    stmt = (
        select(Product)
        .where(Product.status == ProductStatus.PENDING)
        .order_by(Product.id)
        .limit(_MAX_LISTED)
    )
    return list((await session.scalars(stmt)).all())


def _render_pending(products: list[Product]) -> tuple[str, InlineKeyboardMarkup | None]:
    if not products:
        return "✨ Зависших черновиков нет.", None

    lines = [f"⏳ <b>Зависшие черновики ({len(products)})</b>", ""]
    rows: list[list[InlineKeyboardButton]] = []
    for p in products:
        lines.append(f"#{p.id} · {p.brand} {p.name} · {_format_price(p)}")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🟢 #{p.id} · {p.brand} {p.name}"[:64],
                    callback_data=PendingListAction(
                        product_id=p.id, action="publish"
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text=f"❌ #{p.id}",
                    callback_data=PendingListAction(
                        product_id=p.id, action="skip"
                    ).pack(),
                ),
            ]
        )

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _cleanup_photo_files(photos: list[str]) -> None:
    for path in photos:
        name = Path(path).name
        full = PHOTOS_DIR / name
        try:
            full.unlink(missing_ok=True)
        except Exception:
            logger.exception("Failed to delete photo %s", full)


@router.message(Command("pending"))
async def cmd_pending(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return  # silently ignore non-admins

    products = await _pending_products(session)
    text, markup = _render_pending(products)
    await message.answer(text, reply_markup=markup)


@router.callback_query(PendingListAction.filter())
async def on_pending_action(
    query: CallbackQuery,
    callback_data: PendingListAction,
    session: AsyncSession,
) -> None:
    if not _is_admin(query.from_user.id):
        await query.answer("Только для админов", show_alert=True)
        return

    product = await session.get(Product, callback_data.product_id)
    if product is None:
        await query.answer("Товар не найден", show_alert=True)
    elif product.status != ProductStatus.PENDING:
        await query.answer("Уже не в ожидании")
    elif callback_data.action == "publish":
        product.status = ProductStatus.IN_STOCK
        await session.commit()
        logger.info(
            "Admin %s published stuck pending product %s (%s %s) via /pending",
            query.from_user.id, product.id, product.brand, product.name,
        )
        await query.answer(f"Опубликовал #{product.id}")
    elif callback_data.action == "skip":
        photos = list(product.photos or [])
        product_id = product.id
        await session.delete(product)
        await session.commit()
        _cleanup_photo_files(photos)
        logger.info(
            "Admin %s deleted stuck pending product %s via /pending",
            query.from_user.id, product_id,
        )
        await query.answer("Удалено")
    else:
        await query.answer("Неизвестное действие", show_alert=True)
        return

    products = await _pending_products(session)
    text, markup = _render_pending(products)
    if query.message:
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except TelegramAPIError:
            logger.exception("Failed to re-render /pending list")
