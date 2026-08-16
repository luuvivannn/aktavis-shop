from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN

logger = logging.getLogger(__name__)

_bot: Bot | None = None
_storage: MemoryStorage | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        logger.info("Bot instance created.")
    return _bot


def get_storage() -> MemoryStorage:
    """Shared FSM storage, same instance the Dispatcher uses.

    Exposed so handlers can drive another user's FSM state from outside
    that user's own update (e.g. bot-initiated dialogs like the sales
    accounting flow in bot/handlers/accounting.py).
    """
    global _storage
    if _storage is None:
        _storage = MemoryStorage()
    return _storage


async def shutdown_bot() -> None:
    global _bot
    if _bot is not None:
        await _bot.session.close()
        _bot = None
        logger.info("Bot session closed.")


def create_dispatcher() -> Dispatcher:
    from bot import backup
    from bot.handlers import setup_handlers
    from bot.middlewares import DbSessionMiddleware

    dp = Dispatcher(storage=get_storage())

    db_mw = DbSessionMiddleware()
    dp.message.middleware(db_mw)
    dp.callback_query.middleware(db_mw)

    setup_handlers(dp)
    dp.include_router(backup.router)
    return dp
