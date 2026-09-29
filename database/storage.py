"""Keeps the photo volume from filling up.

Photos share the Railway volume with ``shop.db``, and nothing used to remove
them — once the volume is full SQLite can't write either and the whole shop
stops. One cleanup run:

1. keeps only the main photo of SOLD products — they never return to the
   catalog, and the full set still lives in the channel post;
2. deletes files no product references (raw channel-export leftovers,
   extra photos of sold items, orphans);
3. shrinks anything larger than ``MAX_PHOTO_SIDE`` to a phone-sized JPEG.

Idempotent — safe to run on every boot and on a timer.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy import select

from config import PHOTOS_DIR
from database.db import (
    async_session_factory,
    bundled_photos_dir,
    referenced_photo_names,
)
from database.models import Product, ProductStatus

logger = logging.getLogger(__name__)

# Longest side a stored photo may have. Telegram keeps originals up to
# 2560px; a phone screen never needs more than this.
MAX_PHOTO_SIDE = 1280
JPEG_QUALITY = 82

# Photos are downloaded before their product row is written, so a fresh
# unreferenced file may belong to a post that is still being processed.
_MIN_AGE_SECONDS = 3600

_lock = asyncio.Lock()


@dataclass
class CleanupReport:
    skipped: bool = False
    sold_trimmed: int = 0  # products left with just the main photo
    deleted: int = 0
    shrunk: int = 0
    freed_bytes: int = 0


def _on_volume() -> bool:
    # Locally PHOTOS_DIR *is* the repo's photos/ folder — never delete or
    # re-encode tracked files there.
    return PHOTOS_DIR.resolve() != bundled_photos_dir().resolve()


def disk_usage() -> tuple[int, int]:
    """(used, total) bytes of the filesystem holding the photos — on Railway
    that's the volume, shared with shop.db."""
    usage = shutil.disk_usage(PHOTOS_DIR)
    return usage.used, usage.total


async def run_storage_cleanup() -> CleanupReport:
    report = CleanupReport()
    if not _on_volume():
        report.skipped = True
        return report

    async with _lock:
        report.sold_trimmed = await _trim_sold_photos()
        referenced = await referenced_photo_names()
        if referenced:  # an empty set means a broken/empty DB — delete nothing
            await asyncio.to_thread(_delete_unreferenced, referenced, report)
        await asyncio.to_thread(_shrink_oversized, report)

    logger.info(
        "Storage cleanup: sold trimmed=%d, deleted=%d, shrunk=%d, freed=%.1f MB",
        report.sold_trimmed, report.deleted, report.shrunk,
        report.freed_bytes / 1048576,
    )
    return report


async def _trim_sold_photos() -> int:
    trimmed = 0
    async with async_session_factory() as session:
        stmt = select(Product).where(Product.status == ProductStatus.SOLD)
        for product in (await session.scalars(stmt)).all():
            photos = list(product.photos or [])
            if len(photos) > 1:
                product.photos = photos[:1]
                trimmed += 1
        if trimmed:
            await session.commit()
    return trimmed


def _delete_unreferenced(referenced: set[str], report: CleanupReport) -> None:
    cutoff = time.time() - _MIN_AGE_SECONDS
    for path in PHOTOS_DIR.iterdir():
        if not path.is_file() or path.name in referenced:
            continue
        try:
            st = path.stat()
            if st.st_mtime > cutoff:
                continue
            path.unlink()
        except OSError:
            logger.exception("Failed to delete unreferenced photo %s", path)
            continue
        report.deleted += 1
        report.freed_bytes += st.st_size


def _shrink_oversized(report: CleanupReport) -> None:
    cutoff = time.time() - _MIN_AGE_SECONDS
    for path in PHOTOS_DIR.iterdir():
        if path.suffix.lower() not in {".jpg", ".jpeg"} or not path.is_file():
            continue
        tmp = path.with_name(path.name + ".tmp")
        try:
            st = path.stat()
            if st.st_mtime > cutoff:
                continue
            with Image.open(path) as im:
                if max(im.size) <= MAX_PHOTO_SIDE:
                    continue
                im = ImageOps.exif_transpose(im)
                im.thumbnail((MAX_PHOTO_SIDE, MAX_PHOTO_SIDE), Image.LANCZOS)
                im.convert("RGB").save(
                    tmp, "JPEG",
                    quality=JPEG_QUALITY, optimize=True, progressive=True,
                )
            # Atomic swap: the API may be serving this file right now.
            os.replace(tmp, path)
        except Exception:
            logger.exception("Failed to shrink photo %s", path)
            tmp.unlink(missing_ok=True)
            continue
        report.shrunk += 1
        report.freed_bytes += st.st_size - path.stat().st_size
