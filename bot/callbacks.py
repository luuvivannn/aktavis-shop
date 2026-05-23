from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class OrderAction(CallbackData, prefix="oa"):
    """Callback for admin → change order status.

    Prefix is intentionally short ('oa') because Telegram limits callback_data
    to 64 bytes total.
    """

    order_id: int
    new_status: str


class ChannelPostAction(CallbackData, prefix="cp"):
    """Callback for admin preview of a parsed channel post.

    Actions: ``publish`` (move PENDING → IN_STOCK) or
    ``skip`` (delete pending product + its downloaded photos).
    """

    product_id: int
    action: str
