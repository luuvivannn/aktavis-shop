from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    MenuButtonWebApp,
    WebAppInfo,
)

from config import ADMIN_IDS, WEBAPP_URL

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# КОМАНДЫ ДЛЯ ОБЫЧНЫХ ПОЛЬЗОВАТЕЛЕЙ
# Это то, что видно всем в синем меню «/».
# Чтобы добавить новую команду:
#   1. Создай хендлер в bot/handlers/<файл>.py
#   2. Добавь сюда строку BotCommand(command="...", description="...")
# Длина description — до 256 символов, но лучше держать коротко.
# ─────────────────────────────────────────────────────────────
USER_COMMANDS: list[BotCommand] = [
    BotCommand(command="start", description="🥤 Главное меню"),
    BotCommand(command="orders", description="📋 Мои заказы"),
    BotCommand(command="delivery", description="📦 Условия доставки"),
    BotCommand(command="about", description="ℹ️ О магазине"),
    BotCommand(command="contact", description="✉️ Связаться"),
]


# ─────────────────────────────────────────────────────────────
# КОМАНДЫ ДЛЯ АДМИНОВ (видны только тем, кто в ADMIN_IDS)
# Сейчас тут заготовки — допишем хендлеры позже.
# Пока что Telegram покажет эти команды только админам,
# но при нажатии бот ответит дефолтным «Не понимаю команду».
# ─────────────────────────────────────────────────────────────
ADMIN_COMMANDS: list[BotCommand] = USER_COMMANDS + [
    BotCommand(command="admin", description="⚙️ Админ-панель"),
    BotCommand(command="addproduct", description="➕ Добавить товар"),
    BotCommand(command="orders_all", description="📑 Все заказы"),
    BotCommand(command="stats", description="📊 Статистика"),
]


async def set_default_commands(bot: Bot) -> None:
    """Register bot commands shown in Telegram's blue menu button."""
    try:
        await bot.set_my_commands(
            USER_COMMANDS,
            scope=BotCommandScopeAllPrivateChats(),
        )
        logger.info("Registered %d user commands.", len(USER_COMMANDS))
    except TelegramAPIError:
        logger.exception("Failed to set user commands")

    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(
                ADMIN_COMMANDS,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
            logger.info(
                "Registered %d admin commands for %s",
                len(ADMIN_COMMANDS),
                admin_id,
            )
        except TelegramBadRequest as exc:
            if "chat not found" in str(exc).lower():
                logger.warning(
                    "Admin %s has not started a chat with the bot yet — "
                    "admin commands will be set automatically on first /start.",
                    admin_id,
                )
            else:
                logger.exception("Failed to set admin commands for %s", admin_id)
        except TelegramAPIError:
            logger.exception("Failed to set admin commands for %s", admin_id)


async def set_menu_button(bot: Bot) -> None:
    """Pin a WebApp button to the bot's chat menu (left of message input).

    This is the most reliable way to launch a Mini App on every platform —
    initData arrives correctly on iOS, Android, Desktop and Web.
    """
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🛍 Магазин",
                web_app=WebAppInfo(url=WEBAPP_URL),
            ),
        )
        logger.info("Chat menu button set to Mini App (%s)", WEBAPP_URL)
    except TelegramAPIError:
        logger.exception("Failed to set chat menu button")


async def ensure_admin_commands(bot: Bot, admin_id: int) -> None:
    """Register admin commands for a specific admin chat (idempotent)."""
    if admin_id not in ADMIN_IDS:
        return
    try:
        await bot.set_my_commands(
            ADMIN_COMMANDS,
            scope=BotCommandScopeChat(chat_id=admin_id),
        )
        logger.info("Admin commands registered for %s on demand.", admin_id)
    except TelegramAPIError:
        logger.exception("Failed to lazily set admin commands for %s", admin_id)


async def reset_commands(bot: Bot) -> None:
    """Wipe all registered commands (useful while debugging)."""
    try:
        await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
        for admin_id in ADMIN_IDS:
            await bot.delete_my_commands(
                scope=BotCommandScopeChat(chat_id=admin_id)
            )
        logger.info("All bot commands cleared.")
    except TelegramAPIError:
        logger.exception("Failed to reset commands")
