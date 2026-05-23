from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from api.security import TelegramUser, verify_init_data, _unauthorized
from database import async_session_factory


async def db_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DBSession = Annotated[AsyncSession, Depends(db_session)]


async def current_telegram_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> TelegramUser:
    if not authorization:
        raise _unauthorized("Missing Authorization header")

    scheme, _, init_data = authorization.partition(" ")
    if scheme.lower() != "tma" or not init_data:
        raise _unauthorized("Expected 'Authorization: tma <initData>'")

    return verify_init_data(init_data)


CurrentUser = Annotated[TelegramUser, Depends(current_telegram_user)]
