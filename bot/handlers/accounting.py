"""Sales accounting (beta): captures purchase/sale price from the admin
right after a channel post is marked #продано, and logs it to the `sales`
table + a Google Sheet (see bot/sheets.py).

The dialog is bot-initiated (triggered from bot/handlers/channel.py, not
by an incoming admin message), so it drives FSM state directly via a
StorageKey rather than relying on aiogram to inject it from an update.
"""

from __future__ import annotations

import asyncio
import logging
import re
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.bot import get_bot, get_storage
from bot.sheets import append_sale_row
from config import ACCOUNTING_ADMIN_IDS
from database import Product, SaleRepository

logger = logging.getLogger(__name__)

router = Router(name=__name__)

_AMOUNT_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([A-Za-z]+)\s*$")


class AccountingStates(StatesGroup):
    awaiting_purchase = State()
    awaiting_sale = State()


def _parse_amount(text: str) -> tuple[Decimal, str] | None:
    match = _AMOUNT_RE.match(text or "")
    if not match:
        return None
    try:
        amount = Decimal(match.group(1).replace(",", "."))
    except InvalidOperation:
        return None
    return amount, match.group(2).upper()


async def start_accounting_dialog(product: Product, session: AsyncSession) -> None:
    """Kick off the purchase/sale price DM dialog for a freshly-SOLD product.

    Called from on_edited_channel_post right after the SOLD commit, while
    that function's session is still open.
    """
    if not ACCOUNTING_ADMIN_IDS:
        return

    if await SaleRepository(session).exists_for_product(product.id):
        return

    bot = get_bot()
    storage = get_storage()
    prompt = (
        f"💰 Продано: {product.brand} {product.name}\n"
        "Закупочная цена? (напр. <code>120 EUR</code>)"
    )

    for admin_id in ACCOUNTING_ADMIN_IDS:
        key = StorageKey(bot_id=bot.id, chat_id=admin_id, user_id=admin_id)
        state = FSMContext(storage=storage, key=key)
        await state.set_state(AccountingStates.awaiting_purchase)
        await state.update_data(product_id=product.id)
        try:
            await bot.send_message(admin_id, prompt)
        except TelegramAPIError:
            logger.exception(
                "Failed to send accounting prompt to admin %s", admin_id
            )


@router.message(Command("cancel"), AccountingStates)
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.")


@router.message(AccountingStates.awaiting_purchase, F.text)
async def on_purchase_amount(message: Message, state: FSMContext) -> None:
    parsed = _parse_amount(message.text or "")
    if parsed is None:
        await message.answer(
            "Не понял формат. Напиши сумму и валюту, напр. <code>120 EUR</code>"
        )
        return

    amount, currency = parsed
    await state.update_data(purchase_amount=str(amount), purchase_currency=currency)
    await state.set_state(AccountingStates.awaiting_sale)
    await message.answer("Цена продажи? (напр. <code>300 PLN</code>)")


@router.message(AccountingStates.awaiting_sale, F.text)
async def on_sale_amount(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    parsed = _parse_amount(message.text or "")
    if parsed is None:
        await message.answer(
            "Не понял формат. Напиши сумму и валюту, напр. <code>300 PLN</code>"
        )
        return

    sale_amount, sale_currency = parsed
    data = await state.get_data()
    product_id = data["product_id"]
    purchase_amount = Decimal(data["purchase_amount"])
    purchase_currency = data["purchase_currency"]
    await state.clear()

    repo = SaleRepository(session)
    if await repo.exists_for_product(product_id):
        await message.answer("Уже внесено ранее — не дублирую.")
        return

    product = await session.get(Product, product_id)
    if product is None:
        await message.answer("Товар не найден в базе — не записал.")
        return

    profit = (
        sale_amount - purchase_amount
        if purchase_currency == sale_currency
        else None
    )
    admin_user = message.from_user
    await repo.create(
        product_id=product_id,
        purchase_amount=purchase_amount,
        purchase_currency=purchase_currency,
        sale_amount=sale_amount,
        sale_currency=sale_currency,
        profit=profit,
        recorded_by_admin_id=admin_user.id if admin_user else 0,
    )
    await session.commit()

    admin_username = (
        f"@{admin_user.username}" if admin_user and admin_user.username else str(
            admin_user.id if admin_user else "?"
        )
    )
    try:
        await asyncio.to_thread(
            append_sale_row,
            brand=product.brand,
            name=product.name,
            purchase_amount=purchase_amount,
            purchase_currency=purchase_currency,
            sale_amount=sale_amount,
            sale_currency=sale_currency,
            profit=profit,
            admin_username=admin_username,
        )
    except Exception:
        logger.exception("Failed to sync sale (product_id=%s) to Google Sheets", product_id)
        await message.answer("Записано в базу ✅, но в таблицу не ушло — гляну позже.")
        return

    await message.answer("Записано ✅")
