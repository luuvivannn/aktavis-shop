from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from bot.callbacks import OrderAction
from config import WEBAPP_URL
from database import OrderStatus

BTN_SHOP = "🛍 Открыть магазин"
BTN_DELIVERY = "📦 Доставка"
BTN_ABOUT = "ℹ️ О магазине"
BTN_ORDERS = "📋 Мои заказы"
BTN_CONTACT = "✉️ Связаться"


# Per-status transition map for the admin order keyboard.
# Each row is a list of (button_label, target_status) tuples.
_ADMIN_ORDER_ACTIONS: dict[str, list[list[tuple[str, OrderStatus]]]] = {
    OrderStatus.NEW: [
        [("✅ Подтвердить", OrderStatus.CONFIRMED), ("❌ Отменить", OrderStatus.CANCELLED)],
    ],
    OrderStatus.CONFIRMED: [
        [("💳 Ждёт оплаты", OrderStatus.AWAITING_PAYMENT)],
        [("✅ Оплачен", OrderStatus.PAID), ("❌ Отменить", OrderStatus.CANCELLED)],
    ],
    OrderStatus.AWAITING_PAYMENT: [
        [("✅ Оплачен", OrderStatus.PAID), ("❌ Отменить", OrderStatus.CANCELLED)],
    ],
    OrderStatus.PAID: [
        [("📦 Отправлен", OrderStatus.SHIPPED)],
        [("❌ Отменить", OrderStatus.CANCELLED)],
    ],
    OrderStatus.SHIPPED: [
        [("🏁 Доставлен", OrderStatus.DELIVERED)],
    ],
    OrderStatus.DELIVERED: [],
    OrderStatus.CANCELLED: [],
}


def main_menu() -> ReplyKeyboardMarkup:
    # WebApp button is intentionally NOT placed on the reply keyboard:
    # on Android Telegram it sometimes fails to pass initData.
    # Use Bot Menu Button (left of input) or inline buttons instead.
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=BTN_DELIVERY),
                KeyboardButton(text=BTN_ABOUT),
            ],
            [
                KeyboardButton(text=BTN_ORDERS),
                KeyboardButton(text=BTN_CONTACT),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел или откройте магазин слева ↙",
    )


def open_shop_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_SHOP,
                    web_app=WebAppInfo(url=WEBAPP_URL),
                ),
            ],
        ],
    )


def order_admin_keyboard(order_id: int, status: str) -> InlineKeyboardMarkup | None:
    """Inline keyboard for admin to change order status.

    Returns None for terminal statuses (delivered / cancelled) — Telegram will
    render the message without any keyboard.
    """
    rows = _ADMIN_ORDER_ACTIONS.get(status, [])
    if not rows:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=OrderAction(
                        order_id=order_id,
                        new_status=target,
                    ).pack(),
                )
                for label, target in row
            ]
            for row in rows
        ]
    )
