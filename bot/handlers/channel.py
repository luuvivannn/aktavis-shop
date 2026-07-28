"""Channel sync handlers.

Listens to posts (and edits) in the configured channel, parses them and
either drafts a new product (pending admin confirmation) or marks an
existing product as sold.

Also collects extra product photos that the admin drops into the post's
comment thread (the channel's linked discussion group): the channel post's
preview is debounced so all comment photos can be gathered into a single
preview/album before the admin is pinged. Requires the bot to be an admin
of the discussion group so it receives those messages.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.bot import get_bot
from bot.callbacks import ChannelPostAction, ChannelPostCategory
from bot.channel_parser import parse_channel_post
from bot.media_aggregator import MediaGroupAggregator
from config import ADMIN_IDS, CHANNEL_ID, CHANNEL_USERNAME, PHOTOS_DIR
from database import (
    Product,
    ProductCategory,
    ProductRepository,
    ProductStatus,
    async_session_factory,
)

logger = logging.getLogger(__name__)

router = Router(name=__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Human-readable category labels (RU) for the preview text and picker.
CATEGORY_LABELS: dict[ProductCategory, str] = {
    ProductCategory.BAGS: "👜 Сумки",
    ProductCategory.SHOES: "👟 Обувь",
    ProductCategory.TOPS: "👕 Верх",
    ProductCategory.JACKETS: "🧥 Куртки",
    ProductCategory.PANTS: "👖 Шорты/Штаны",
    ProductCategory.ACCESSORIES: "🧢 Аксессуары",
    ProductCategory.OTHER: "📦 Другое",
}

# Order + membership of the category picker shown under a pending preview.
# CUSTOM_ORDER is an info-only pseudo-category and intentionally excluded.
CATEGORY_PICKER: tuple[ProductCategory, ...] = (
    ProductCategory.BAGS,
    ProductCategory.SHOES,
    ProductCategory.TOPS,
    ProductCategory.JACKETS,
    ProductCategory.PANTS,
    ProductCategory.ACCESSORIES,
    ProductCategory.OTHER,
)


def _category_label(category: ProductCategory) -> str:
    return CATEGORY_LABELS.get(category, str(category))


# ─────────────────────────────────────────────────────────────
# Comment-photo collection (linked discussion group)
# ─────────────────────────────────────────────────────────────
# After a channel post lands we wait a bit for the admin to drop extra
# photos into its comment thread, then send ONE preview with the full album.
#
#   GRACE  — how long to wait after the post for the first comment photo
#            (also the max delay before the preview goes out for a post that
#            never gets comments).
#   SETTLE — after each comment photo, how long to keep waiting for more
#            before firing the preview.
PREVIEW_GRACE_SECONDS = 60.0
PREVIEW_SETTLE_SECONDS = 10.0

# In-memory maps (single-instance bot; cleared on restart, which is fine —
# they only matter for the short window between a post and its comments).
#   _thread_to_post   discussion-group thread root msg id -> channel post id
#   _preview_tasks    channel post id -> pending debounced-preview timer task
#   _preview_sent     channel post ids whose preview has already been sent
_thread_to_post: dict[int, int] = {}
_preview_tasks: dict[int, asyncio.Task] = {}
_preview_sent: set[int] = set()
# Serialises the read-modify-write of product.photos when several comment
# photos for the same post arrive back-to-back.
_comment_append_lock = asyncio.Lock()


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _matches_channel(message: Message) -> bool:
    if not message.chat:
        return False

    # Match by chat ID (works for both public and private channels)
    if CHANNEL_ID is not None and message.chat.id == CHANNEL_ID:
        return True

    # Fallback: match by public @username (only public channels have one)
    if (
        CHANNEL_USERNAME
        and (message.chat.username or "").lower() == CHANNEL_USERNAME.lower()
    ):
        return True

    return False


def _format_preview(product: Product) -> str:
    lines = [
        "📥 <b>Новый пост из канала</b>",
        "",
        f"<b>Бренд:</b> {product.brand}",
        f"<b>Название:</b> {product.name}",
        f"<b>Категория:</b> {_category_label(product.category)}",
    ]
    if product.size:
        lines.append(f"<b>Размер:</b> {product.size}")
    if product.condition:
        lines.append(f"<b>Состояние:</b> {product.condition}")

    # EUR is the active currency; show it first, keep zł/USDT as legacy extras.
    if product.price_eur:
        price = f"{product.price_eur}€"
        if product.price_pln:
            price += f" / {product.price_pln} zł"
    elif product.price_pln:
        price = f"{product.price_pln} zł"
    else:
        price = "?"
    if product.price_usdt:
        price += f" / {product.price_usdt} USDT"
    lines.append(f"<b>Цена:</b> {price}")

    if product.note:
        lines.append(f"<b>Примечание:</b> {product.note}")

    lines.append(f"<b>Фото:</b> {len(product.photos)} шт.")
    lines.append("")

    warnings = []
    if product.brand == "Unknown":
        warnings.append("⚠️ Бренд не распознан")
    if not (product.price_eur or product.price_pln):
        warnings.append("⚠️ Цена не извлечена")
    if not product.size:
        warnings.append("⚠️ Размер не найден")
    if product.category == ProductCategory.OTHER:
        warnings.append("⚠️ Категория не распознана — выбери ниже")

    if warnings:
        lines.extend(warnings)
        lines.append("")

    lines.append("Категория ниже — поправь если нужно, потом публикуй 👇")
    return "\n".join(lines)


def _preview_keyboard(product: Product) -> InlineKeyboardMarkup:
    """Pending-preview keyboard: a category picker + publish/skip row.

    The currently-assigned category is marked with a ✅ so the admin can
    re-tap another one to fix mis-detected categories before publishing.
    """
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for cat in CATEGORY_PICKER:
        label = CATEGORY_LABELS[cat]
        text = f"✅ {label}" if cat == product.category else label
        row.append(
            InlineKeyboardButton(
                text=text,
                callback_data=ChannelPostCategory(
                    product_id=product.id, category=cat.value
                ).pack(),
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text="🟢 Опубликовать",
                callback_data=ChannelPostAction(
                    product_id=product.id, action="publish"
                ).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Пропустить",
                callback_data=ChannelPostAction(
                    product_id=product.id, action="skip"
                ).pack(),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _published_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Shown after publish — lets the admin hide a live product later."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🙈 Скрыть из каталога",
                    callback_data=ChannelPostAction(
                        product_id=product_id, action="hide"
                    ).pack(),
                ),
            ],
        ]
    )


def _hidden_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Shown after hide — lets the admin bring the product back."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👁 Вернуть в каталог",
                    callback_data=ChannelPostAction(
                        product_id=product_id, action="show"
                    ).pack(),
                ),
            ],
        ]
    )


def _published_text(product: Product) -> str:
    return f"✅ <b>В каталоге</b>\n#{product.id} {product.brand} {product.name}"


def _hidden_text(product: Product) -> str:
    return f"🙈 <b>Скрыт</b>\n#{product.id} {product.brand} {product.name}"


async def _download_photos(messages: list[Message]) -> list[str]:
    """Download largest photo from each message; return list of relative paths."""
    bot = get_bot()

    paths: list[str] = []
    first_id = messages[0].message_id
    for idx, msg in enumerate(messages):
        if not msg.photo:
            continue
        largest = msg.photo[-1]
        filename = f"channel_{first_id}_{idx}.jpg"
        relative = f"photos/{filename}"
        full_path = PHOTOS_DIR / filename
        try:
            await bot.download(largest, destination=full_path)
            paths.append(relative)
        except TelegramAPIError:
            logger.exception(
                "Failed to download photo %s for channel post %s",
                largest.file_id, first_id,
            )
    return paths


def _cleanup_photos(photos: list[str]) -> None:
    for path in photos:
        # photos paths look like "photos/<file>", strip the prefix and use
        # the configured PHOTOS_DIR so this works on Railway volumes too.
        name = Path(path).name
        full = PHOTOS_DIR / name
        try:
            full.unlink(missing_ok=True)
        except Exception:
            logger.exception("Failed to delete photo %s", full)


# ─────────────────────────────────────────────────────────────
# Process aggregated post → save as PENDING product, ping admins
# ─────────────────────────────────────────────────────────────
async def _process_post(messages: list[Message]) -> None:
    first = messages[0]
    caption = first.caption or first.text or ""

    parsed = parse_channel_post(caption)
    if parsed is None or not caption.strip():
        logger.info(
            "Skipping channel post %s — empty or unparseable", first.message_id
        )
        return

    # Idempotency: if we already created a Product for this post, skip.
    async with async_session_factory() as session:
        repo = ProductRepository(session)
        existing = await repo.get_by_channel_message_id(first.message_id)
        if existing is not None:
            logger.info(
                "Channel post %s already linked to product %s — skipping",
                first.message_id, existing.id,
            )
            return

    # If the post is already marked sold (e.g. someone reposts an old sold
    # item), no point creating a pending product.
    if parsed.is_sold:
        logger.info(
            "Channel post %s is marked #продано — not creating product",
            first.message_id,
        )
        return

    photo_paths = await _download_photos(messages)

    async with async_session_factory() as session:
        product = Product(
            brand=parsed.brand,
            name=parsed.name,
            category=parsed.category,
            size=parsed.size,
            condition=parsed.condition,
            description=parsed.description,
            note=parsed.note,
            price_pln=parsed.price_pln or 0,
            price_usdt=parsed.price_usdt,
            price_eur=parsed.price_eur,
            photos=photo_paths,
            status=ProductStatus.PENDING,
            channel_message_id=first.message_id,
            channel_chat_id=first.chat.id,
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        product_id = product.id

    # Don't ping the admin yet — give them a window to drop extra photos into
    # the post's comment thread, then send one preview with the full album.
    _schedule_preview(first.message_id, PREVIEW_GRACE_SECONDS)
    logger.info(
        "Created PENDING product %s from channel post %s — preview scheduled "
        "in %.0fs (waiting for comment photos)",
        product_id, first.message_id, PREVIEW_GRACE_SECONDS,
    )


async def _send_preview_to_admins(
    product: Product, preview_text: str, photo_paths: list[str]
) -> None:
    if not ADMIN_IDS:
        logger.warning("ADMIN_IDS empty — cannot send channel preview")
        return

    bot = get_bot()
    keyboard = _preview_keyboard(product)

    for admin_id in ADMIN_IDS:
        try:
            if photo_paths:
                media = [
                    InputMediaPhoto(
                        media=FSInputFile(PHOTOS_DIR / Path(p).name)
                    )
                    for p in photo_paths[:10]  # Telegram cap for media groups
                ]
                await bot.send_media_group(admin_id, media)
            await bot.send_message(admin_id, preview_text, reply_markup=keyboard)
        except TelegramAPIError:
            logger.exception(
                "Failed to send channel preview to admin %s", admin_id
            )


# ─────────────────────────────────────────────────────────────
# Debounced preview send (after comment photos are collected)
# ─────────────────────────────────────────────────────────────
def _schedule_preview(channel_message_id: int, delay: float) -> None:
    """(Re)arm the debounce timer that sends the preview for a post.

    Called once when the post lands (``GRACE``) and again after each comment
    photo (``SETTLE``); the latest call wins, so the preview fires only once
    the album has stopped growing.
    """
    existing = _preview_tasks.get(channel_message_id)
    if existing is not None:
        existing.cancel()
    _preview_tasks[channel_message_id] = asyncio.create_task(
        _preview_timer(channel_message_id, delay)
    )


async def _preview_timer(channel_message_id: int, delay: float) -> None:
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return
    _preview_tasks.pop(channel_message_id, None)
    # Guard against a late re-schedule racing with an in-flight send.
    if channel_message_id in _preview_sent:
        return
    try:
        sent = await _send_preview_for(channel_message_id)
        if sent:
            _preview_sent.add(channel_message_id)
    except Exception:
        logger.exception(
            "Failed to send debounced preview for post %s", channel_message_id
        )


async def _send_preview_for(channel_message_id: int) -> bool:
    """Load the pending product for a post and send its preview. Returns
    True if a preview was actually sent."""
    async with async_session_factory() as session:
        repo = ProductRepository(session)
        product = await repo.get_by_channel_message_id(channel_message_id)
        if product is None or product.status != ProductStatus.PENDING:
            return False
        preview_text = _format_preview(product)
        photos = list(product.photos or [])
        photo_count = len(photos)
        product_id = product.id

    await _send_preview_to_admins(product, preview_text, photos)
    logger.info(
        "Sent preview for product %s (post %s) with %d photo(s)",
        product_id, channel_message_id, photo_count,
    )
    return True


# ─────────────────────────────────────────────────────────────
# Comment-photo ingestion (linked discussion group)
# ─────────────────────────────────────────────────────────────
def _is_from_admin(message: Message) -> bool:
    """True if the comment was authored by an admin.

    An admin can post in the discussion group in three ways:
      • as their own account          -> from_user.id in ADMIN_IDS
      • as the channel                -> sender_chat == the channel
      • anonymously as a group admin  -> sender_chat == the discussion group
        (Telegram sets from_user to GroupAnonymousBot in this case)

    Only chat admins can post "as a chat", so any non-None ``sender_chat`` on
    a comment is itself an admin signal. Regular user comments have
    ``sender_chat is None`` and a non-admin ``from_user``, so they're excluded.
    """
    if message.from_user and message.from_user.id in ADMIN_IDS:
        return True
    if message.sender_chat is not None:
        return True
    return False


def _resolve_post_id(message: Message) -> int | None:
    """Map a comment message back to its original channel post id."""
    thread_id = message.message_thread_id
    if thread_id is not None and thread_id in _thread_to_post:
        return _thread_to_post[thread_id]
    # Fallback: a top-level comment replies to the auto-forwarded post, which
    # carries the original channel message id.
    root = message.reply_to_message
    root_post_id = getattr(root, "forward_from_message_id", None) if root else None
    if root_post_id:
        if thread_id is not None:
            _thread_to_post[thread_id] = root_post_id
        return root_post_id
    return None


async def _download_comment_photo(post_id: int, message: Message) -> str | None:
    bot = get_bot()
    largest = message.photo[-1]
    filename = f"channel_{post_id}_c{message.message_id}.jpg"
    relative = f"photos/{filename}"
    full_path = PHOTOS_DIR / filename
    try:
        await bot.download(largest, destination=full_path)
        return relative
    except TelegramAPIError:
        logger.exception(
            "Failed to download comment photo (post %s, msg %s)",
            post_id, message.message_id,
        )
        return None


async def _notify_extra_photos(product_id: int, added: int, total: int) -> None:
    """Ping admins when photos land after the preview was already sent."""
    if not ADMIN_IDS:
        return
    bot = get_bot()
    text = (
        f"📎 К #{product_id} добавлено ещё {added} фото из комментариев "
        f"(всего {total})."
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except TelegramAPIError:
            logger.exception("Failed to notify admin %s of extra photos", admin_id)


async def _process_comment_photos(messages: list[Message]) -> None:
    """Attach admin-posted comment photos to the pending product and either
    (re)arm the preview debounce or, if the preview already went out, notify
    the admin of the late additions."""
    first = messages[0]
    post_id = _resolve_post_id(first)
    if post_id is None:
        logger.info(
            "Comment photos in thread %s not linked to any post — ignoring",
            first.message_thread_id,
        )
        return

    photo_msgs = [m for m in messages if m.photo and _is_from_admin(m)]
    if not photo_msgs:
        logger.info(
            "Comment photos for post %s ignored — not from an admin", post_id
        )
        return

    # Download outside the lock (network I/O), then do a quick guarded update.
    downloaded: list[str] = []
    for msg in photo_msgs:
        path = await _download_comment_photo(post_id, msg)
        if path:
            downloaded.append(path)
    if not downloaded:
        return

    async with _comment_append_lock:
        async with async_session_factory() as session:
            repo = ProductRepository(session)
            product = await repo.get_by_channel_message_id(post_id)
            if product is None or product.status != ProductStatus.PENDING:
                logger.info(
                    "Comment photos for post %s dropped — product missing or "
                    "no longer pending",
                    post_id,
                )
                return
            # Reassign (not .append) so SQLAlchemy persists the JSON change.
            product.photos = list(product.photos or []) + downloaded
            await session.commit()
            total = len(product.photos)
            product_id = product.id

    logger.info(
        "Attached %d comment photo(s) to product %s (post %s, total %d)",
        len(downloaded), product_id, post_id, total,
    )

    if post_id in _preview_sent:
        await _notify_extra_photos(product_id, len(downloaded), total)
    else:
        _schedule_preview(post_id, PREVIEW_SETTLE_SECONDS)


# ─────────────────────────────────────────────────────────────
# Aiogram routes
# ─────────────────────────────────────────────────────────────
_aggregator = MediaGroupAggregator(callback=_process_post, timeout=2.5)
_comment_aggregator = MediaGroupAggregator(
    callback=_process_comment_photos, timeout=2.5
)


@router.channel_post()
async def on_channel_post(message: Message) -> None:
    # Always log so we can see the channel's identity even when the filter rejects.
    chat = message.chat
    logger.info(
        "📥 channel_post: chat_id=%s username=%s title=%r msg_id=%s photo=%s text=%s",
        chat.id if chat else "?",
        (chat.username if chat else "?") or "<private>",
        (chat.title if chat else "?"),
        message.message_id,
        bool(message.photo),
        bool(message.caption or message.text),
    )

    if not _matches_channel(message):
        logger.warning(
            "Channel post ignored — chat_id=%s username=%s does not match "
            "CHANNEL_ID=%s / CHANNEL_USERNAME=%s",
            chat.id if chat else "?",
            (chat.username if chat else "?") or "<private>",
            CHANNEL_ID,
            CHANNEL_USERNAME or "(empty)",
        )
        return

    await _aggregator.add(message)


@router.message(F.is_automatic_forward)
async def on_discussion_autoforward(message: Message) -> None:
    """The linked discussion group auto-forwards every channel post.

    We use that forward to learn the mapping
    ``group thread root id -> original channel post id`` so comment photos
    in the thread can later be attached to the right product.
    """
    sender = message.sender_chat
    if CHANNEL_ID is not None and (sender is None or sender.id != CHANNEL_ID):
        return  # an auto-forward from some other channel — not ours

    post_id = getattr(message, "forward_from_message_id", None)
    if post_id is None and message.forward_origin is not None:
        post_id = getattr(message.forward_origin, "message_id", None)
    if post_id is None:
        return

    _thread_to_post[message.message_id] = post_id
    logger.info(
        "Linked discussion thread %s -> channel post %s (group %s)",
        message.message_id, post_id, message.chat.id,
    )


@router.message(F.photo, F.message_thread_id, ~F.is_automatic_forward)
async def on_discussion_comment_photo(message: Message) -> None:
    """A photo posted as a comment under a channel post. Buffer it through the
    media-group aggregator so albums are attached in one batch."""
    await _comment_aggregator.add(message)


@router.edited_channel_post()
async def on_edited_channel_post(message: Message) -> None:
    chat = message.chat
    logger.info(
        "✏️  edited_channel_post: chat_id=%s username=%s msg_id=%s",
        chat.id if chat else "?",
        (chat.username if chat else "?") or "<private>",
        message.message_id,
    )

    if not _matches_channel(message):
        return

    raw_caption = message.caption or message.text or ""
    caption_lower = raw_caption.lower()

    async with async_session_factory() as session:
        repo = ProductRepository(session)
        product = await repo.get_by_channel_message_id(message.message_id)
        if product is None:
            # Fallback for legacy products that pre-date channel_message_id
            # tracking: if the edit adds #продано, try to find the product by
            # brand + name so we can still mark it sold.
            if "#продано" not in caption_lower:
                return
            parsed_for_sold = parse_channel_post(raw_caption)
            if (
                parsed_for_sold is None
                or not parsed_for_sold.brand
                or parsed_for_sold.brand == "Unknown"
                or not parsed_for_sold.name
            ):
                return
            product = await repo.find_in_stock_by_brand_name(
                parsed_for_sold.brand, parsed_for_sold.name
            )
            if product is None:
                logger.info(
                    "Sold fallback: no unique IN_STOCK match for %r %r (msg=%s)",
                    parsed_for_sold.brand, parsed_for_sold.name, message.message_id,
                )
                return

        # Skip DUPLICATED rows — they represent stale re-posts and shouldn't
        # be transitioned to SOLD or refreshed just because the original
        # post got edited.
        if product.status == ProductStatus.DUPLICATED:
            return

        # 1) #продано → mark as SOLD and stop. Once it's gone it's gone;
        # no point refreshing fields on a product that's leaving the catalog.
        if "#продано" in caption_lower and product.status != ProductStatus.SOLD:
            product.status = ProductStatus.SOLD
            await session.commit()
            logger.info(
                "Product %s marked SOLD via channel edit (msg=%s)",
                product.id, message.message_id,
            )
            return

        # Already-sold products: skip — they don't appear in the catalog.
        if product.status == ProductStatus.SOLD:
            return

        # 2) Re-parse the edited caption and sync editable fields back into
        # the existing product row. Photos, status and channel-anchor fields
        # are intentionally left untouched.
        parsed = parse_channel_post(raw_caption)
        if parsed is None:
            return

        # Guard against the parser losing the identity fields on the new
        # caption — better to skip the update than corrupt the row.
        if not parsed.brand or parsed.brand == "Unknown" or not parsed.name:
            logger.info(
                "Edit ignored — parser could not extract brand/name for "
                "product %s (msg=%s)",
                product.id, message.message_id,
            )
            return

        changes: list[str] = []

        def _apply(field: str, new_value, *, skip_none: bool = True) -> None:
            """Overwrite product.<field> with new_value when it differs.

            Optional fields (size, note, etc.) keep their existing value if
            the parser couldn't extract anything from the new caption — we
            never want a small format change in the post to silently wipe
            data out of the catalog.
            """
            if new_value is None and skip_none:
                return
            old_value = getattr(product, field)
            if old_value != new_value:
                setattr(product, field, new_value)
                changes.append(f"{field}: {old_value!r} → {new_value!r}")

        _apply("brand", parsed.brand, skip_none=False)
        _apply("name", parsed.name, skip_none=False)
        _apply("category", parsed.category, skip_none=False)
        _apply("size", parsed.size)
        _apply("condition", parsed.condition)
        _apply("description", parsed.description)
        _apply("note", parsed.note)
        # Sale-price tracking: when the price drops, save the old value as
        # the "original" (strikethrough) price shown in the Mini App.
        # If the price is later raised back to or above the original, clear it.
        if parsed.price_eur is not None and product.price_eur is not None:
            if parsed.price_eur < product.price_eur:
                if product.price_eur_original is None:
                    product.price_eur_original = product.price_eur
                    changes.append(f"price_eur_original: None → {product.price_eur!r}")
            elif (
                product.price_eur_original is not None
                and parsed.price_eur >= product.price_eur_original
            ):
                product.price_eur_original = None
                changes.append("price_eur_original: cleared")

        if parsed.price_pln is not None and product.price_pln is not None:
            if parsed.price_pln < product.price_pln:
                if product.price_pln_original is None:
                    product.price_pln_original = product.price_pln
                    changes.append(f"price_pln_original: None → {product.price_pln!r}")
            elif (
                product.price_pln_original is not None
                and parsed.price_pln >= product.price_pln_original
            ):
                product.price_pln_original = None
                changes.append("price_pln_original: cleared")

        _apply("price_pln", parsed.price_pln)
        _apply("price_usdt", parsed.price_usdt)
        _apply("price_eur", parsed.price_eur)

        if changes:
            await session.commit()
            logger.info(
                "Product %s refreshed from channel edit (msg=%s): %s",
                product.id, message.message_id, "; ".join(changes),
            )


# ─────────────────────────────────────────────────────────────
# Admin preview callback
# ─────────────────────────────────────────────────────────────
@router.callback_query(ChannelPostAction.filter())
async def on_preview_action(
    query: CallbackQuery,
    callback_data: ChannelPostAction,
    session: AsyncSession,
) -> None:
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Только для админов", show_alert=True)
        return

    repo = ProductRepository(session)
    product = await repo.get(callback_data.product_id)
    if product is None:
        await query.answer("Товар не найден", show_alert=True)
        if query.message:
            try:
                await query.message.edit_text("❓ Товар уже удалён.")
            except TelegramAPIError:
                pass
        return

    outcome = ""
    markup: InlineKeyboardMarkup | None = None

    if callback_data.action == "publish":
        if product.status == ProductStatus.PENDING:
            product.status = ProductStatus.IN_STOCK
            await session.commit()
        outcome = _published_text(product)
        markup = _published_keyboard(product.id)
        await query.answer("В каталоге")

    elif callback_data.action == "hide":
        if product.status == ProductStatus.HIDDEN:
            await query.answer("Уже скрыт")
            return
        product.status = ProductStatus.HIDDEN
        await session.commit()
        outcome = _hidden_text(product)
        markup = _hidden_keyboard(product.id)
        await query.answer("Скрыт из каталога")

    elif callback_data.action == "show":
        product.status = ProductStatus.IN_STOCK
        await session.commit()
        outcome = _published_text(product)
        markup = _published_keyboard(product.id)
        await query.answer("Вернул в каталог")

    elif callback_data.action == "skip":
        if product.status != ProductStatus.PENDING:
            await query.answer(
                f"Нельзя — товар уже {product.status}", show_alert=True
            )
            return

        photos = list(product.photos or [])
        await repo.delete(product)
        await session.commit()
        _cleanup_photos(photos)

        outcome = f"❌ <b>Пропущено</b> (#{callback_data.product_id})"
        await query.answer("Пропущено")
    else:
        await query.answer("Неизвестное действие", show_alert=True)
        return

    if query.message:
        try:
            await query.message.edit_text(outcome, reply_markup=markup)
        except TelegramAPIError:
            logger.exception("Failed to edit preview message")


# ─────────────────────────────────────────────────────────────
# Admin preview — change category before publishing
# ─────────────────────────────────────────────────────────────
@router.callback_query(ChannelPostCategory.filter())
async def on_category_change(
    query: CallbackQuery,
    callback_data: ChannelPostCategory,
    session: AsyncSession,
) -> None:
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Только для админов", show_alert=True)
        return

    try:
        new_category = ProductCategory(callback_data.category)
    except ValueError:
        await query.answer("Неизвестная категория", show_alert=True)
        return

    repo = ProductRepository(session)
    product = await repo.get(callback_data.product_id)
    if product is None:
        await query.answer("Товар не найден", show_alert=True)
        return

    # Category is only editable while the product is still a pending draft.
    if product.status != ProductStatus.PENDING:
        await query.answer(
            "Категорию можно менять только до публикации", show_alert=True
        )
        return

    if product.category == new_category:
        await query.answer("Уже выбрана")
        return

    product.category = new_category
    await session.commit()
    await session.refresh(product)

    await query.answer(f"Категория: {_category_label(new_category)}")
    if query.message:
        try:
            await query.message.edit_text(
                _format_preview(product),
                reply_markup=_preview_keyboard(product),
            )
        except TelegramAPIError:
            logger.exception(
                "Failed to refresh preview after category change (product %s)",
                product.id,
            )
