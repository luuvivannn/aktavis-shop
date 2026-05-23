from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import BTN_ORDERS, open_shop_inline
from bot.texts import (
    DELIVERY_LABELS,
    NO_ORDERS,
    ORDER_HEADER,
    STATUS_LABELS,
)
from database import Order, OrderRepository

router = Router(name=__name__)


def _format_order(order: Order) -> str:
    status = STATUS_LABELS.get(order.status, order.status)
    delivery = DELIVERY_LABELS.get(order.delivery_method, order.delivery_method)

    lines = [
        f"<b>Заказ #{order.id}</b> — {status}",
        f"📅 {order.created_at:%d.%m.%Y %H:%M}",
        "",
    ]
    for item in order.items:
        product = item.product
        size = f" • {product.size}" if product.size else ""
        lines.append(
            f"  • {product.brand} {product.name}{size}"
            f" — {item.price_pln} zł × {item.quantity}"
        )

    lines.append("")
    lines.append(f"💰 Итого: <b>{order.total_pln} zł</b>")
    if order.total_usdt:
        lines.append(f"     ≈ {order.total_usdt} USDT")

    lines.append(f"🚚 {delivery}")
    if order.delivery_address:
        lines.append(f"   {order.delivery_address}")
    return "\n".join(lines)


@router.message(Command("orders"))
@router.message(F.text == BTN_ORDERS)
async def my_orders(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return

    orders = await OrderRepository(session).list_by_user(
        message.from_user.id, limit=10
    )
    if not orders:
        await message.answer(NO_ORDERS, reply_markup=open_shop_inline())
        return

    await message.answer(ORDER_HEADER)
    for order in orders:
        await message.answer(_format_order(order))
