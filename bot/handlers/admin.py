from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.callbacks import OrderAction
from bot.keyboards import order_admin_keyboard
from bot.notifications import (
    format_order_for_admin,
    notify_client_status_change,
)
from bot.texts import STATUS_LABELS
from config import ADMIN_IDS
from database import OrderRepository, OrderStatus

logger = logging.getLogger(__name__)

router = Router(name=__name__)

# Restrict every handler in this router to admins only.
_ADMIN_SET = set(ADMIN_IDS)
router.message.filter(F.from_user.id.in_(_ADMIN_SET))
router.callback_query.filter(F.from_user.id.in_(_ADMIN_SET))


# ─────────────────────────────────────────────────────────────
# Order status change via inline button on admin notification
# ─────────────────────────────────────────────────────────────
@router.callback_query(OrderAction.filter())
async def handle_order_action(
    query: CallbackQuery,
    callback_data: OrderAction,
    session: AsyncSession,
) -> None:
    try:
        new_status = OrderStatus(callback_data.new_status)
    except ValueError:
        await query.answer("Неизвестный статус", show_alert=True)
        return

    repo = OrderRepository(session)

    try:
        order = await repo.set_status(callback_data.order_id, new_status)
    except ValueError as exc:
        await query.answer(f"Ошибка: {exc}", show_alert=True)
        return

    # Commit immediately so the customer notification reflects the actual
    # persisted state (middleware would commit on return, but we want the
    # write done before we ping the customer).
    await session.commit()

    new_text = format_order_for_admin(order)
    new_kb = order_admin_keyboard(order.id, order.status)

    try:
        if query.message:
            await query.message.edit_text(new_text, reply_markup=new_kb)
    except TelegramAPIError:
        logger.exception("Failed to edit admin order message")

    status_label = STATUS_LABELS.get(new_status, new_status)
    await query.answer(f"→ {status_label}")

    await notify_client_status_change(order)


# ─────────────────────────────────────────────────────────────
# /admin — short help
# ─────────────────────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    text = (
        "⚙️ <b>Админ-панель</b>\n\n"
        "<b>Команды:</b>\n"
        "/orders_all — последние заказы\n"
        "/stats — статистика\n\n"
        "Уведомления о новых заказах приходят сюда автоматически "
        "с inline-кнопками для смены статуса."
    )
    await message.answer(text)


# ─────────────────────────────────────────────────────────────
# /orders_all — list recent orders
# ─────────────────────────────────────────────────────────────
@router.message(Command("orders_all"))
async def cmd_orders_all(message: Message, session: AsyncSession) -> None:
    orders = await OrderRepository(session).list_recent(limit=20)

    if not orders:
        await message.answer("Заказов пока нет.")
        return

    lines = ["📑 <b>Последние 20 заказов</b>", ""]
    for o in orders:
        status = STATUS_LABELS.get(o.status, o.status)
        date = o.created_at.strftime("%d.%m %H:%M")
        username = f" @{o.username}" if o.username else ""
        name = o.full_name or "—"
        lines.append(
            f"<b>#{o.id}</b> {status}\n"
            f"   {name}{username} · {o.total_pln} zł · {date}"
        )

    await message.answer("\n\n".join([lines[0]] + lines[2:]))


# ─────────────────────────────────────────────────────────────
# /stats — revenue summary
# ─────────────────────────────────────────────────────────────
@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    repo = OrderRepository(session)

    today_n, today_pln, today_usdt = await repo.revenue_since(today_start)
    week_n, week_pln, week_usdt = await repo.revenue_since(week_ago)
    month_n, month_pln, month_usdt = await repo.revenue_since(month_ago)
    all_n, all_pln, all_usdt = await repo.revenue_since(None)
    pending = await repo.count_pending()

    def fmt(n: int, pln: int, usdt: int) -> str:
        line = f"{n} заказ(ов) · <b>{pln:,} zł</b>".replace(",", " ")
        if usdt:
            line += f" / {usdt} USDT"
        return line

    text = (
        f"📊 <b>Статистика магазина</b>\n\n"
        f"📅 Сегодня: {fmt(today_n, today_pln, today_usdt)}\n"
        f"📅 За 7 дней: {fmt(week_n, week_pln, week_usdt)}\n"
        f"📅 За 30 дней: {fmt(month_n, month_pln, month_usdt)}\n"
        f"♾ Всего: {fmt(all_n, all_pln, all_usdt)}\n\n"
        f"⏳ В работе (новые / подтверждённые / ждут оплаты): "
        f"<b>{pending}</b>"
    )
    await message.answer(text)
