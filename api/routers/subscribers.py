from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from api.dependencies import DBSession
from api.security import verify_init_data
from database import SubscriberRepository

router = APIRouter(tags=["subscribers"])


@router.post("/subscribe")
async def subscribe(
    session: DBSession,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    """Add the Mini App user to the daily promo audience (bot/promo.py).

    Only the flag Telegram signs into initData counts. A user who agrees to
    the Mini App's "allow messages" prompt right now still has the old flag
    in this launch's initData — the bot records them from Telegram's
    write_access_allowed service message instead.
    """
    scheme, _, init_data = (authorization or "").partition(" ")
    if scheme.lower() != "tma":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Telegram initData",
            headers={"WWW-Authenticate": "tma"},
        )
    user = verify_init_data(init_data)
    if not user.allows_write_to_pm:
        return {"subscribed": False}

    await SubscriberRepository(session).upsert(
        user.id,
        first_name=user.first_name,
        username=user.username,
        source="webapp",
    )
    return {"subscribed": True}
