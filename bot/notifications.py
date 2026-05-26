"""Bot-to-admin notifications.

Currently empty except for shared utilities — order notifications were
removed when the checkout flow moved out of the Mini App. Channel-sync
admin previews live in ``bot/handlers/channel.py``.

Kept as a placeholder so future notification helpers have an obvious
home.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from config import ADMIN_IDS

logger = logging.getLogger(__name__)


def admin_ids() -> Iterable[int]:
    """Iterable of admin Telegram user IDs (from .env)."""
    return ADMIN_IDS or ()
