from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

import uvicorn

from api.app import app as fastapi_app
from bot import create_dispatcher, get_bot, shutdown_bot
from bot.commands import set_default_commands, set_menu_button
from config import API_HOST, API_PORT
from database import dispose_engine, init_db

logger = logging.getLogger(__name__)


async def run_api() -> None:
    config = uvicorn.Config(
        fastapi_app,
        host=API_HOST,
        port=API_PORT,
        loop="asyncio",
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)
    logger.info("Starting API on %s:%s", API_HOST, API_PORT)
    await server.serve()


async def run_bot() -> None:
    bot = get_bot()
    dispatcher = create_dispatcher()

    me = await bot.get_me()
    logger.info("Bot started as @%s (id=%s)", me.username, me.id)

    await bot.delete_webhook(drop_pending_updates=True)
    await set_default_commands(bot)
    await set_menu_button(bot)
    await dispatcher.start_polling(bot, handle_signals=False)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)

    await init_db(seed=True)

    tasks: set[asyncio.Task] = {
        asyncio.create_task(run_api(), name="api"),
        asyncio.create_task(run_bot(), name="bot"),
    }

    try:
        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_EXCEPTION
        )

        for task in pending:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        for task in done:
            exc = task.exception()
            if exc is not None:
                raise exc
    finally:
        await shutdown_bot()
        await dispose_engine()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
