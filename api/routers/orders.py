from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from api.dependencies import CurrentUser, DBSession
from api.schemas import MeOut, OrderCreateIn, OrderOut
from bot.notifications import notify_admins_new_order
from database import (
    CartItem,
    OrderRepository,
    ProductNotAvailableError,
    ProductNotFoundError,
)

router = APIRouter(tags=["orders"])


@router.get("/me", response_model=MeOut)
async def whoami(user: CurrentUser) -> MeOut:
    return MeOut(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code,
        is_premium=user.is_premium,
    )


@router.get("/orders/my", response_model=list[OrderOut])
async def my_orders(
    session: DBSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[OrderOut]:
    orders = await OrderRepository(session).list_by_user(
        user.id, limit=limit, offset=offset
    )
    return [OrderOut.model_validate(o) for o in orders]


@router.post(
    "/orders",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    payload: OrderCreateIn,
    session: DBSession,
    user: CurrentUser,
    background: BackgroundTasks,
) -> OrderOut:
    repo = OrderRepository(session)
    try:
        order = await repo.create(
            user_id=user.id,
            username=user.username,
            full_name=payload.full_name or user.full_name,
            phone=payload.phone,
            delivery_method=payload.delivery_method,
            delivery_address=payload.delivery_address,
            comment=payload.comment,
            cart=[
                CartItem(product_id=item.product_id, quantity=item.quantity)
                for item in payload.items
            ],
        )
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ProductNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    await session.commit()
    await session.refresh(order)

    background.add_task(notify_admins_new_order, order)

    return OrderOut.model_validate(order)


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int, session: DBSession, user: CurrentUser
) -> OrderOut:
    order = await OrderRepository(session).get(order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )
    return OrderOut.model_validate(order)
