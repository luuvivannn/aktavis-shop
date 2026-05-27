"""Channel sync handlers.

Listens to posts (and edits) in the configured channel, parses them and
either drafts a new product (pending admin confirmation) or marks an
existing product as sold.
"""

from __future__ import annotations

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
from bot.callbacks import ChannelPostAction
from bot.channel_parser import ParsedProduct, parse_channel_post
from bot.keyboards import channel_post_buttons
from bot.media_aggregator import MediaGroupAggregator
from config import ADMIN_IDS, CHANNEL_ID, CHANNEL_USERNAME, PHOTOS_DIR
from database import (
    Product,
    ProductRepository,
    ProductStatus,
    async_session_factory,
)

logger = logging.getLogger(__name__)

router = Router(name=__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


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


def _format_preview(product: Product, parsed: ParsedProduct) -> str:
    lines = [
        "📥 <b>Новый пост из канала</b>",
        "",
        f"<b>Бренд:</b> {product.brand}",
        f"<b>Название:</b> {product.name}",
        f"<b>Категория:</b> {product.category}",
    ]
    if product.size:
        lines.append(f"<b>Размер:</b> {product.size}")
    if product.condition:
        lines.append(f"<b>Состояние:</b> {product.condition}")

    price = f"{product.price_pln} zł" if product.price_pln else "?"
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
    if not product.price_pln:
        warnings.append("⚠️ Цена не извлечена")
    if not product.size:
        warnings.append("⚠️ Размер не найден")
    if parsed.is_sold:
        warnings.append("⚠️ Пост помечен #продано")

    if warnings:
        lines.extend(warnings)
        lines.append("")

    lines.append("Опубликовать в магазин?")
    return "\n".join(lines)


def _preview_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=ChannelPostAction(
                        product_id=product_id, action="publish"
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Пропустить",
                    callback_data=ChannelPostAction(
                        product_id=product_id, action="skip"
                    ).pack(),
                ),
            ],
        ]
    )


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


async def _attach_shop_button(product: Product) -> None:
    """Add the «Открыть в магазине» inline button to the original channel post.

    Requires the bot to be a channel admin with edit-messages permission.
    Failures are logged but never abort publishing — the product stays
    IN_STOCK either way.
    """
    if not (product.channel_chat_id and product.channel_message_id):
        return

    bot = get_bot()
    try:
        await bot.edit_message_reply_markup(
            chat_id=product.channel_chat_id,
            message_id=product.channel_message_id,
            reply_markup=channel_post_buttons(product.id),
        )
    except TelegramAPIError:
        logger.exception(
            "Failed to attach shop button to channel post chat=%s msg=%s (product=%s)",
            product.channel_chat_id,
            product.channel_message_id,
            product.id,
        )


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
            photos=photo_paths,
            status=ProductStatus.PENDING,
            channel_message_id=first.message_id,
            channel_chat_id=first.chat.id,
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        product_id = product.id
        preview_text = _format_preview(product, parsed)

    await _send_preview_to_admins(product_id, preview_text, photo_paths)
    logger.info("Created PENDING product %s from channel post %s", product_id, first.message_id)


async def _send_preview_to_admins(
    product_id: int, preview_text: str, photo_paths: list[str]
) -> None:
    if not ADMIN_IDS:
        logger.warning("ADMIN_IDS empty — cannot send channel preview")
        return

    bot = get_bot()
    keyboard = _preview_keyboard(product_id)

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
# Aiogram routes
# ─────────────────────────────────────────────────────────────
_aggregator = MediaGroupAggregator(callback=_process_post, timeout=2.5)


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

    caption = (message.caption or message.text or "").lower()

    async with async_session_factory() as session:
        repo = ProductRepository(session)
        product = await repo.get_by_channel_message_id(message.message_id)
        if product is None:
            return

        if "#продано" in caption and product.status != ProductStatus.SOLD:
            product.status = ProductStatus.SOLD
            await session.commit()
            logger.info(
                "Product %s marked SOLD via channel edit (msg=%s)",
                product.id, message.message_id,
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

    if callback_data.action == "publish":
        if product.status == ProductStatus.PENDING:
            product.status = ProductStatus.IN_STOCK
            await session.commit()

        await _attach_shop_button(product)

        outcome = (
            f"✅ <b>Опубликован</b>\n"
            f"#{product.id} {product.brand} {product.name}"
        )
        await query.answer("Опубликован")

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
            await query.message.edit_text(outcome)
        except TelegramAPIError:
            logger.exception("Failed to edit preview message")
