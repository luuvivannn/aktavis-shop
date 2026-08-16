from __future__ import annotations

from aiogram import Dispatcher

from bot.handlers import accounting, admin, channel, info, start


def setup_handlers(dp: Dispatcher) -> None:
    # Channel router first — handles channel_post / edited_channel_post
    # and its own admin-only ChannelPostAction callbacks.
    dp.include_router(channel.router)
    # Accounting's message handlers are state-filtered (only fire while an
    # admin is mid-dialog), so registering it before admin/start/info just
    # means a stray /cancel or /hidden typed mid-dialog is captured here
    # first — acceptable for the beta.
    dp.include_router(accounting.router)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(info.router)
