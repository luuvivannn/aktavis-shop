from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from config import BOT_USERNAME, MINIAPP_SHORT_NAME, WEBAPP_URL

BTN_SHOP = "🛍 Открыть магазин"
BTN_SHOP_OPEN_PRODUCT = "🛍 Открыть в магазине"
BTN_DELIVERY = "📦 Доставка"
BTN_ABOUT = "ℹ️ О магазине"
BTN_CONTACT = "✉️ Связаться"


def miniapp_product_url(product_id: int) -> str:
    return (
        f"https://t.me/{BOT_USERNAME}/{MINIAPP_SHORT_NAME}"
        f"?startapp=p_{product_id}"
    )


def channel_post_buttons(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_SHOP_OPEN_PRODUCT,
                    url=miniapp_product_url(product_id),
                ),
            ],
        ],
    )


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
            [KeyboardButton(text=BTN_CONTACT)],
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
