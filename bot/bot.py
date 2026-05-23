from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN

logger = logging.getLogger(__name__)

_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        logger.info("Bot instance created.")
    return _bot


async def shutdown_bot() -> None:
    global _bot
    if _bot is not None:
        await _bot.session.close()
        _bot = None
        logger.info("Bot session closed.")


def create_dispatcher() -> Dispatcher:
    from bot.handlers import setup_handlers
    from bot.middlewares import DbSessionMiddleware

    dp = Dispatcher(storage=MemoryStorage())

    db_mw = DbSessionMiddleware()
    dp.message.middleware(db_mw)
    dp.callback_query.middleware(db_mw)

    setup_handlers(dp)
    return dp
