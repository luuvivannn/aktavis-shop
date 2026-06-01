from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class ChannelPostAction(CallbackData, prefix="cp"):
    """Callback for the admin preview of a parsed channel post.

    Actions:
      ``publish`` — move PENDING → IN_STOCK
      ``skip``    — delete the pending product + its downloaded photos
      ``hide``    — move IN_STOCK → HIDDEN (drop it from the catalog)
      ``show``    — move HIDDEN → IN_STOCK (bring it back)
    """

    product_id: int
    action: str


class HiddenListAction(CallbackData, prefix="hl"):
    """Callback for the ``/hidden`` list — restore a hidden product.

    Action ``restore`` moves HIDDEN → IN_STOCK and re-renders the list.
    """

    product_id: int
    action: str
