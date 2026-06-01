"""Consistent SQLite snapshots for off-site backup.

The whole shop — catalog, prices, statuses, hide flags — lives in a single
``shop.db`` file on the Railway volume. This module produces a clean,
consistent copy of it using SQLite's online backup API, which is safe to
run while the app is reading and writing (no locking the shop out).

The copy is handed to ``bot.backup``, which DMs it to the admin so there's
always an off-site restore point in Telegram's cloud.
"""

from __future__ import annotations

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from database import engine

logger = logging.getLogger(__name__)


def _source_db_path() -> Path:
    """Resolve the on-disk path of the live SQLite database."""
    db = engine.url.database
    if not db:
        raise RuntimeError(
            "Engine is not backed by a file database — cannot back up."
        )
    return Path(db)


async def create_backup_file() -> Path:
    """Write a consistent snapshot of the live DB to a temp file.

    Returns the path to the snapshot. The caller is responsible for
    deleting it once it's been sent.
    """
    src_path = _source_db_path()
    if not src_path.exists():
        raise FileNotFoundError(f"Database file not found: {src_path}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = Path(tempfile.gettempdir()) / f"aktavis-backup-{ts}.db"

    # Online backup API: copies committed pages page-by-page, restarting
    # automatically if the source is written to mid-copy. Guarantees a
    # non-corrupt snapshot even under concurrent writes.
    async with (
        aiosqlite.connect(src_path) as src,
        aiosqlite.connect(dest) as dst,
    ):
        await src.backup(dst)

    logger.info("Created DB snapshot: %s (%d bytes)", dest, dest.stat().st_size)
    return dest
