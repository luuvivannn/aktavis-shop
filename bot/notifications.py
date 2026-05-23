from __future__ import annotations

import logging
from collections.abc import Iterable

from aiogram.exceptions import TelegramAPIError

from bot.bot import get_bot
from bot.keyboards import order_admin_keyboard
from bot.texts import DELIVERY_LABELS, STATUS_LABELS
from config import ADMIN_IDS
from database import Order, OrderStatus

logger = logging.getLogger(__name__)


# Human-friendly notifications sent to the customer when admin changes status.
CLIENT_STATUS_MESSAGES: dict[str, str] = {
    OrderStatus.CONFIRMED: (
        "✅ Ваш заказ <b>#{id}</b> подтверждён.\n"
        "Менеджер свяжется с вами в ближайшее время."
    ),
    OrderStatus.AWAITING_PAYMENT: (
        "💳 Заказ <b>#{id}</b> ожидает оплаты.\n"
        "Реквизиты придут отдельным сообщением."
    ),
    OrderStatus.PAID: (
        "✅ Оплата по заказу <b>#{id}</b> получена. Спасибо!"
    ),
    OrderStatus.SHIPPED: (
        "📦 Заказ <b>#{id}</b> отправлен."
    ),
    OrderStatus.DELIVERED: (
        "🏁 Заказ <b>#{id}</b> доставлен.\nСпасибо за покупку 🤍"
    ),
    OrderStatus.CANCELLED: (
        "❌ Заказ <b>#{id}</b> отменён."
    ),
}


def _admin_ids() -> Iterable[int]:
    return ADMIN_IDS or ()


def format_order_for_admin(order: Order) -> str:
    lines = [
        f"🆕 <b>Новый заказ #{order.id}</b>",
        "",
        f"👤 Покупатель: {order.full_name or '—'}",
    ]
    if order.username:
        lines.append(f"   @{order.username}")
    lines.append(f"   ID: <code>{order.user_id}</code>")
    if order.phone:
        lines.append(f"   📞 {order.phone}")

    lines.append("")
    lines.append("🛍 <b>Состав заказа:</b>")
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

    lines.append("")
    delivery_label = DELIVERY_LABELS.get(
        order.delivery_method, order.delivery_method
    )
    lines.append(f"🚚 Доставка: {delivery_label}")
    if order.delivery_address:
        lines.append(f"   {order.delivery_address}")

    if order.comment:
        lines.append("")
        lines.append(f"💬 Комментарий: {order.comment}")

    lines.append("")
    status_label = STATUS_LABELS.get(order.status, order.status)
    lines.append(f"Статус: {status_label}")

    return "\n".join(lines)


async def notify_admins_new_order(order: Order) -> None:
    admins = list(_admin_ids())
    if not admins:
        logger.warning(
            "ADMIN_IDS is empty; new order #%s notification skipped.", order.id
        )
        return

    bot = get_bot()
    text = format_order_for_admin(order)
    keyboard = order_admin_keyboard(order.id, order.status)

    for admin_id in admins:
        try:
            await bot.send_message(admin_id, text, reply_markup=keyboard)
        except TelegramAPIError:
            logger.exception("Failed to notify admin %s", admin_id)


async def notify_client_status_change(order: Order) -> None:
    """Send a short message to the customer when their order status changes."""
    template = CLIENT_STATUS_MESSAGES.get(order.status)
    if template is None:
        return

    bot = get_bot()
    text = template.format(id=order.id)
    try:
        await bot.send_message(order.user_id, text)
    except TelegramAPIError:
        logger.exception(
            "Failed to notify client %s about order #%s status %s",
            order.user_id, order.id, order.status,
        )
