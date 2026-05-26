from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class ChannelPostAction(CallbackData, prefix="cp"):
    """Callback for admin preview of a parsed channel post.

    Actions: ``publish`` (move PENDING → IN_STOCK) or
    ``skip`` (delete pending product + its downloaded photos).
    """

    product_id: int
    action: str
