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
BTN_CATALOG = "🛍 Каталог"
BTN_DELIVERY = "📦 Доставка"
BTN_ABOUT = "ℹ️ О магазине"
BTN_CONTACT = "✉️ Связаться"


def miniapp_home_url() -> str:
    """Direct Link to the Mini App catalog landing screen."""
    return f"https://t.me/{BOT_USERNAME}/{MINIAPP_SHORT_NAME}"


def channel_post_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_CATALOG,
                    url=miniapp_home_url(),
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
