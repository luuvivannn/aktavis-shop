from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import HTTPException, status

from config import BOT_TOKEN

INIT_DATA_TTL_SECONDS = 24 * 60 * 60


@dataclass(slots=True, frozen=True)
class TelegramUser:
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    is_premium: bool = False

    @property
    def full_name(self) -> str | None:
        parts = [self.first_name, self.last_name]
        joined = " ".join(p for p in parts if p)
        return joined or None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "tma"},
    )


def verify_init_data(
    init_data: str, *, max_age_seconds: int = INIT_DATA_TTL_SECONDS
) -> TelegramUser:
    if not init_data:
        raise _unauthorized("Empty initData")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise _unauthorized("Missing hash in initData")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(parsed.items())
    )

    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise _unauthorized("Invalid initData signature")

    auth_date_raw = parsed.get("auth_date")
    if not auth_date_raw or not auth_date_raw.isdigit():
        raise _unauthorized("Missing or invalid auth_date")

    auth_date = int(auth_date_raw)
    if max_age_seconds > 0 and time.time() - auth_date > max_age_seconds:
        raise _unauthorized("initData expired")

    user_raw = parsed.get("user")
    if not user_raw:
        raise _unauthorized("initData has no user")

    try:
        user_dict = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise _unauthorized("Malformed user payload") from exc

    return TelegramUser(
        id=int(user_dict["id"]),
        first_name=user_dict.get("first_name"),
        last_name=user_dict.get("last_name"),
        username=user_dict.get("username"),
        language_code=user_dict.get("language_code"),
        is_premium=bool(user_dict.get("is_premium", False)),
    )
