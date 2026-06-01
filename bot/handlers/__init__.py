from __future__ import annotations

from aiogram import Dispatcher

from bot.handlers import admin, channel, info, start


def setup_handlers(dp: Dispatcher) -> None:
    # Channel router first — handles channel_post / edited_channel_post
    # and its own admin-only ChannelPostAction callbacks.
    dp.include_router(channel.router)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(info.router)
