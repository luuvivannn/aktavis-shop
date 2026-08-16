"""Google Sheets sync for sales accounting (bot/handlers/accounting.py).

Best-effort: if GOOGLE_SHEET_ID / GOOGLE_SERVICE_ACCOUNT_JSON aren't
configured, or the API call fails, the caller falls back to "saved in DB,
not synced" rather than losing the accounting entry.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal

import gspread

from config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEET_ID

logger = logging.getLogger(__name__)

_client: gspread.Client | None = None


def _get_worksheet() -> gspread.Worksheet | None:
    global _client
    if not GOOGLE_SERVICE_ACCOUNT_JSON or not GOOGLE_SHEET_ID:
        return None

    if _client is None:
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        _client = gspread.service_account_from_dict(info)

    return _client.open_by_key(GOOGLE_SHEET_ID).sheet1


def append_sale_row(
    *,
    brand: str,
    name: str,
    purchase_amount: Decimal,
    purchase_currency: str,
    sale_amount: Decimal,
    sale_currency: str,
    profit: Decimal | None,
    admin_username: str,
) -> None:
    """Blocking network call — run via asyncio.to_thread from handlers."""
    worksheet = _get_worksheet()
    if worksheet is None:
        logger.info("Google Sheets not configured — skipping sales sync")
        return

    worksheet.append_row(
        [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            brand,
            name,
            str(purchase_amount),
            purchase_currency,
            str(sale_amount),
            sale_currency,
            str(profit) if profit is not None else "",
            admin_username,
        ]
    )
