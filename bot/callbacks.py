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


class ChannelPostCategory(CallbackData, prefix="cpcat"):
    """Callback for re-assigning a pending product's category from the preview.

    ``category`` is a :class:`ProductCategory` value. Only allowed while the
    product is still PENDING (i.e. before the admin publishes it).
    """

    product_id: int
    category: str


class HiddenListAction(CallbackData, prefix="hl"):
    """Callback for the ``/hidden`` list — restore a hidden product.

    Action ``restore`` moves HIDDEN → IN_STOCK and re-renders the list.
    """

    product_id: int
    action: str


class PendingListAction(CallbackData, prefix="pnd"):
    """Callback for the ``/pending`` list — recover a stuck draft.

    A product can be stuck in PENDING with no preview ever sent if the bot
    restarted while the preview's debounce timer was still armed (the timer
    lives only in memory — see ``bot/handlers/channel.py``). ``/pending``
    surfaces those rows directly from the DB.

    Actions:
      ``publish`` — move PENDING → IN_STOCK
      ``skip``    — delete the stuck draft + its downloaded photos
    """

    product_id: int
    action: str
