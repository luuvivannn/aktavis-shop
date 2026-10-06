"""Hourly product cards.

Every in-stock product gets a weekday, and on that day the bot DMs its
card — photo, name, size, condition, price and an «Заказать» button — to
every subscriber of the promo. One card an hour from CARDS_START_HOUR
(Warsaw time) until the day's products run out; the daily promo keeps its
own hour.

Days are kept even: a new product joins the lightest day, a sold one drops
out, and when a day falls two behind the heaviest day hands one over. Once
today's first card is out nothing joins or leaves today, so the day is
always one unbroken run of hours.

Nothing new lands on the volume: a card's photo is the product's main
photo, uploaded on the first send, and every later send reuses Telegram's
file_id saved on the product. ``/cards`` shows the admin the next card and
the week's schedule.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlsplit

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.backup import backup_chat_id
from bot.promo import PROMO_TZ, SELLER_URL, broadcast
from config import (
    ADMIN_IDS,
    CARDS_ENABLED,
    CARDS_END_HOUR,
    CARDS_SILENT,
    CARDS_START_HOUR,
    PHOTOS_DIR,
    PROMO_ENABLED,
    PROMO_HOUR,
    WEBAPP_URL,
)
from database import (
    CardSend,
    Product,
    ProductCategory,
    ProductStatus,
    SubscriberRepository,
    async_session_factory,
)

logger = logging.getLogger(__name__)

router = Router(name=__name__)

WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

_CHECK_INTERVAL_SECONDS = 60
_STARTUP_DELAY_SECONDS = 50
# The send log only matters for today; keep a month for /cards and debugging.
_KEEP_LOG_DAYS = 30
_MESSAGE_LIMIT = 4000
_NAME_WIDTH = 40


def slot_hours() -> list[int]:
    """Hours a card may go out, in order. The promo hour is left to the
    promo so subscribers still get one message an hour."""
    return [
        hour
        for hour in range(CARDS_START_HOUR, CARDS_END_HOUR)
        if not (PROMO_ENABLED and hour == PROMO_HOUR)
    ]


# ─────────────────────────────────────────────────────────────
# The card
# ─────────────────────────────────────────────────────────────


def product_label(p: Product) -> str:
    # "Unknown" is the parser's sentinel for an unrecognised brand — the
    # Mini App hides it too.
    brand = "" if (p.brand or "").strip().lower() == "unknown" else p.brand
    return " ".join(part for part in (brand, p.name) if part)


def _tidy(text: str) -> str:
    """'Идеальное состояние , полный комплект ( до 10 носок)' →
    'Идеальное состояние, полный комплект (до 10 носок)'."""
    text = re.sub(r"\s+([,.)])", r"\1", text.strip())
    text = re.sub(r"\(\s+", "(", text)
    return text[:1].upper() + text[1:]


def _price(p: Product) -> str:
    if p.price_eur:
        price, original, unit = p.price_eur, p.price_eur_original, "{}€"
    elif p.price_pln:
        price, original, unit = p.price_pln, p.price_pln_original, "{} zł"
    else:
        return "по запросу"
    text = unit.format(price)
    if original and original > price:
        text = f"<s>{unit.format(original)}</s> {text}"
    return text


def card_caption(p: Product) -> str:
    lines = [f"<b>{html.escape(product_label(p))}</b>"]
    if p.size:
        lines.append(f"Размер: {html.escape(p.size)}")
    if p.condition:
        lines.append(html.escape(_tidy(p.condition)))
    lines.append(f"Цена: {_price(p)}")
    return "\n".join(lines)


def _public_photo_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    base = urlsplit(WEBAPP_URL)
    return f"{base.scheme}://{base.netloc}/{path.lstrip('/')}"


def order_url(p: Product) -> str:
    """Opens a chat with the seller with the order already typed — the
    same message as the Mini App's button, plus where the buyer came from.
    Telegram previews the photo link, so the seller sees the item."""
    lines = [
        f"Привет! Хочу купить {product_label(p)}, "
        f"размер {p.size or '—'} (из рассылки)"
    ]
    photo_url = _public_photo_url(p.main_photo)
    if photo_url:
        lines.append(photo_url)
    return f"{SELLER_URL}?text={quote(chr(10).join(lines), safe='')}"


def _photo_file(path: str) -> Path:
    # Photo paths look like "photos/<file>"; the files live in PHOTOS_DIR.
    return PHOTOS_DIR / Path(path).name


def _cached_file_id(p: Product) -> str | None:
    if p.card_file_id and p.card_file_path == p.main_photo:
        return p.card_file_id
    return None


class Card:
    """One product's card. The photo is uploaded on the first send and
    every later send reuses Telegram's file_id."""

    def __init__(self, product: Product) -> None:
        self.product_id = product.id
        self.label = product_label(product)
        self.photo = product.main_photo
        self.file_id = _cached_file_id(product)
        self.caption = card_caption(product)
        self.keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Заказать", url=order_url(product))]
            ]
        )
        self._uploaded = False

    async def send(
        self, bot: Bot, chat_id: int, *, silent: bool = CARDS_SILENT
    ) -> None:
        message = await bot.send_photo(
            chat_id,
            photo=self.file_id or FSInputFile(_photo_file(self.photo)),
            caption=self.caption,
            reply_markup=self.keyboard,
            disable_notification=silent,
        )
        if self.file_id is None and message.photo:
            self.file_id = message.photo[-1].file_id
            self._uploaded = True

    async def save_file_id(self, session: AsyncSession) -> None:
        if not self._uploaded:
            return
        await session.execute(
            update(Product)
            .where(Product.id == self.product_id)
            .values(card_file_id=self.file_id, card_file_path=self.photo)
        )


# ─────────────────────────────────────────────────────────────
# The week
# ─────────────────────────────────────────────────────────────


@dataclass
class Week:
    today: date
    weekday: int
    days: list[list[Product]]  # by weekday, in send order
    sends: list[CardSend]      # today's, by hour

    @property
    def queue(self) -> list[Product]:
        """Today's products that haven't gone out yet."""
        sent = {s.product_id for s in self.sends}
        return [p for p in self.days[self.weekday] if p.id not in sent]

    def next_product(self) -> Product | None:
        if self.queue:
            return self.queue[0]
        for offset in range(1, 8):
            day = self.days[(self.weekday + offset) % 7]
            if day:
                return day[0]
        return None


async def _rotation(session: AsyncSession) -> list[Product]:
    """In-stock products that get a card, oldest first."""
    stmt = (
        select(Product)
        .where(
            Product.status == ProductStatus.IN_STOCK,
            Product.category != ProductCategory.CUSTOM_ORDER,
        )
        .order_by(Product.id)
    )
    return [
        p
        for p in await session.scalars(stmt)
        if p.main_photo
        and (_cached_file_id(p) or _photo_file(p.main_photo).is_file())
    ]


def _arrange(products: list[Product], today: int, started: bool) -> bool:
    """Give every product a weekday and keep the days within one card of
    each other. Returns True if any product changed day.

    Ties go to the day coming up soonest, so a new product goes out
    quickly. Once today's first card is out (``started``) today is closed:
    nothing joins or leaves it.
    """
    days = [(today + offset) % 7 for offset in range(7)]
    if started:
        days.remove(today)
    count = Counter(p.card_weekday for p in products)
    changed = False

    for p in products:
        if p.card_weekday not in range(7):
            day = min(days, key=count.__getitem__)
            p.card_weekday = day
            count[day] += 1
            changed = True

    while True:
        light = min(days, key=count.__getitem__)
        heavy = max(days, key=count.__getitem__)
        if count[heavy] - count[light] < 2:
            return changed
        # The heaviest day hands over its last card.
        mover = max(
            (p for p in products if p.card_weekday == heavy),
            key=lambda p: p.id,
        )
        mover.card_weekday = light
        count[heavy] -= 1
        count[light] += 1
        changed = True


async def load_week(session: AsyncSession, now: datetime) -> Week:
    """The week's schedule, with new and sold products already sorted out."""
    today = now.date()
    sends = list(
        await session.scalars(
            select(CardSend)
            .where(CardSend.send_date == today)
            .order_by(CardSend.slot_hour)
        )
    )
    products = await _rotation(session)
    if _arrange(products, now.weekday(), started=bool(sends)):
        await session.commit()

    days: list[list[Product]] = [[] for _ in range(7)]
    for p in products:
        days[p.card_weekday].append(p)
    return Week(today=today, weekday=now.weekday(), days=days, sends=sends)


# ─────────────────────────────────────────────────────────────
# Sending
# ─────────────────────────────────────────────────────────────


async def _send_due_card(bot: Bot, now: datetime) -> None:
    """Send this hour's card if the hour is a slot and still has none."""
    async with async_session_factory() as session:
        week = await load_week(session, now)
        if now.hour not in slot_hours():
            return
        if any(s.slot_hour == now.hour for s in week.sends):
            return
        if not week.queue:
            return  # today's products are all out

        product = week.queue[0]
        if not week.sends:
            await session.execute(
                delete(CardSend).where(
                    CardSend.send_date
                    < week.today - timedelta(days=_KEEP_LOG_DAYS)
                )
            )
        user_ids = await SubscriberRepository(session).active_ids()
        # Claim the hour before the first send, so a crash or redeploy
        # mid-run never sends a second card this hour.
        record = CardSend(
            send_date=week.today,
            slot_hour=now.hour,
            product_id=product.id,
            recipients=len(user_ids),
        )
        session.add(record)
        await session.commit()
        record_id = record.id
        card = Card(product)

    logger.info(
        "Card %02d:00: product %s (%s) to %d subscribers.",
        now.hour, card.product_id, card.label, len(user_ids),
    )
    sent, blocked, failed = await broadcast(
        lambda chat_id: card.send(bot, chat_id), user_ids
    )

    async with async_session_factory() as session:
        await session.execute(
            update(CardSend)
            .where(CardSend.id == record_id)
            .values(sent=sent, blocked=blocked, failed=failed)
        )
        await card.save_file_id(session)
        await session.commit()
    logger.info(
        "Card %02d:00 done: %d sent, %d blocked, %d failed.",
        now.hour, sent, blocked, failed,
    )


async def cards_loop(bot: Bot) -> None:
    """Check every minute whether a card is due. Never raises — like the
    promo loop, a failure here must not take the shop down with it."""
    if not CARDS_ENABLED:
        logger.info("Product cards disabled (CARDS_ENABLED=false).")
        return

    logger.info(
        "Product cards enabled: hourly from %02d:00 Europe/Warsaw.",
        CARDS_START_HOUR,
    )
    await asyncio.sleep(_STARTUP_DELAY_SECONDS)
    while True:
        try:
            await _send_due_card(bot, datetime.now(PROMO_TZ))
        except Exception:
            logger.exception("Product card failed; retrying next check.")
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)


# ─────────────────────────────────────────────────────────────
# /cards
# ─────────────────────────────────────────────────────────────


def _short(p: Product) -> str:
    label = product_label(p)
    if len(label) > _NAME_WIDTH:
        label = label[: _NAME_WIDTH - 1] + "…"
    text = html.escape(label)
    if p.size:
        text += f" · {html.escape(p.size)}"
    return text


def _day_block(week: Week, day: int, now: datetime) -> str:
    slots = slot_hours()
    products = week.days[day]
    if day == week.weekday:
        queue = week.queue
        used = {s.slot_hour for s in week.sends}
        times = [h for h in slots if h >= now.hour and h not in used]
        late = "сегодня не успеет"
        lines = [
            f"<b>{WEEKDAYS[day]} · сегодня</b> · "
            f"отправлено {len(week.sends)}, осталось {len(queue)}"
        ]
    else:
        queue = products
        times = slots
        late = "не влезает в день"
        lines = [f"<b>{WEEKDAYS[day]}</b> · {len(products)} шт"]

    if not queue:
        lines.append("—")
    for i, p in enumerate(queue):
        when = f"{times[i]:02d}:00" if i < len(times) else late
        lines.append(f"{when} {_short(p)}")
    return "\n".join(lines)


def _schedule_text(week: Week, now: datetime) -> list[str]:
    total = sum(len(day) for day in week.days)
    header = ["🗂 <b>Карточки товаров</b>"]
    if CARDS_ENABLED:
        rule = f"Каждый день с {CARDS_START_HOUR:02d}:00, раз в час"
        if CARDS_SILENT:
            rule += ", без звука"
        if PROMO_ENABLED and CARDS_START_HOUR <= PROMO_HOUR < CARDS_END_HOUR:
            rule += f" · {PROMO_HOUR:02d}:00 — промо"
        header.append(rule)
    else:
        header.append("Карточки выключены (CARDS_ENABLED=false)")
    header.append(f"В ротации: {total} шт")
    if week.sends:
        delivered = sum(s.sent for s in week.sends)
        blocked = sum(s.blocked for s in week.sends)
        line = f"Сегодня доставлено: {delivered}"
        if blocked:
            line += f" · заблокировали бота: {blocked}"
        header.append(line)

    blocks = ["\n".join(header)]
    blocks += [
        _day_block(week, (week.weekday + offset) % 7, now)
        for offset in range(7)
    ]

    messages: list[str] = []
    for block in blocks:
        if messages and len(messages[-1]) + len(block) + 2 <= _MESSAGE_LIMIT:
            messages[-1] += "\n\n" + block
        else:
            messages.append(block)
    return messages


@router.message(Command("cards"))
async def cmd_cards(message: Message, session: AsyncSession) -> None:
    user_id = message.from_user.id if message.from_user else None
    if user_id is None or (
        user_id not in ADMIN_IDS and user_id != backup_chat_id()
    ):
        return  # silently ignore non-admins

    now = datetime.now(PROMO_TZ)
    week = await load_week(session, now)

    product = week.next_product()
    if product is not None:
        card = Card(product)
        await card.send(message.bot, message.chat.id, silent=False)
        await card.save_file_id(session)
        await message.answer("👆 Так выглядит карточка — это следующая по очереди")

    for text in _schedule_text(week, now):
        await message.answer(text)
