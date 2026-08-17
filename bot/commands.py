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
# КОМАНДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ (видны в синем меню «/»)
# ─────────────────────────────────────────────────────────────
USER_COMMANDS: list[BotCommand] = [
    BotCommand(command="start", description="🥤 Главное меню"),
    BotCommand(command="delivery", description="📦 Условия доставки"),
    BotCommand(command="about", description="ℹ️ О магазине"),
    BotCommand(command="contact", description="✉️ Связаться"),
]


# Admins get the user set plus catalog-curation commands. These are
# registered per-admin-chat scope, so regular users never see them.
ADMIN_COMMANDS: list[BotCommand] = [
    *USER_COMMANDS,
    BotCommand(command="hidden", description="🙈 Скрытые товары"),
    BotCommand(command="pending", description="⏳ Зависшие черновики"),
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
    """Register admin commands for a specific admin chat (idempotent).

    With admin commands collapsed into the user list, this is mostly a
    no-op these days — kept for compatibility with the /start handler.
    """
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
