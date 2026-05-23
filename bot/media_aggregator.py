"""Aggregate Telegram media groups.

Telegram sends a single multi-photo post as N separate updates, all sharing
the same ``media_group_id``. This helper buffers them and calls a callback
once the group looks complete (no new message arrived within a short window).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeAlias

from aiogram.types import Message

logger = logging.getLogger(__name__)

GroupCallback: TypeAlias = Callable[[list[Message]], Awaitable[None]]


class MediaGroupAggregator:
    """Debounce-based aggregator.

    Each time a message with ``media_group_id`` arrives, the flush timer
    resets. When the timer expires without a new arrival, the buffered
    messages are sorted by ``message_id`` and dispatched to the callback.

    A message without ``media_group_id`` is dispatched immediately as a
    single-element list.
    """

    def __init__(self, callback: GroupCallback, *, timeout: float = 2.0) -> None:
        self._callback = callback
        self._timeout = timeout
        self._buffers: dict[str, list[Message]] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def add(self, message: Message) -> None:
        group_id = message.media_group_id
        if not group_id:
            await self._dispatch([message])
            return

        self._buffers.setdefault(group_id, []).append(message)

        existing_task = self._tasks.get(group_id)
        if existing_task is not None:
            existing_task.cancel()

        self._tasks[group_id] = asyncio.create_task(self._flush(group_id))

    async def _flush(self, group_id: str) -> None:
        try:
            await asyncio.sleep(self._timeout)
        except asyncio.CancelledError:
            return

        messages = self._buffers.pop(group_id, [])
        self._tasks.pop(group_id, None)

        if not messages:
            return

        messages.sort(key=lambda m: m.message_id)
        await self._dispatch(messages)

    async def _dispatch(self, messages: list[Message]) -> None:
        try:
            await self._callback(messages)
        except Exception:
            logger.exception(
                "Media group callback failed for messages %s",
                [m.message_id for m in messages],
            )
