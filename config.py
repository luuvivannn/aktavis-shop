from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    bot_token: str = Field(alias="BOT_TOKEN")
    bot_username: str = Field(alias="BOT_USERNAME", default="aktaviuseu_bot")
    miniapp_short_name: str = Field(alias="MINIAPP_SHORT_NAME", default="shop")
    webapp_url: str = Field(alias="WEBAPP_URL", default="https://example.com/")
    admin_ids: list[int] = Field(alias="ADMIN_IDS", default_factory=list)

    channel_username: str = Field(alias="CHANNEL_USERNAME", default="")
    channel_id: int | None = Field(alias="CHANNEL_ID", default=None)

    # Database backup: the bot DMs a fresh copy of shop.db to this chat
    # on a timer and on /backup. Falls back to the first admin if unset.
    backup_chat_id: int | None = Field(alias="BACKUP_CHAT_ID", default=None)
    backup_interval_hours: int = Field(
        alias="BACKUP_INTERVAL_HOURS", default=24
    )

    telegram_api_id: int | None = Field(alias="TELEGRAM_API_ID", default=None)
    telegram_api_hash: str = Field(alias="TELEGRAM_API_HASH", default="")

    # Where persistent data lives (database file + downloaded photos).
    # On Railway / VPS this is a mounted volume like /data.
    # Locally it defaults to the project folder.
    data_dir: str = Field(alias="DATA_DIR", default=str(PROJECT_ROOT))

    database_url: str = Field(alias="DATABASE_URL", default="")
    api_host: str = Field(alias="API_HOST", default="0.0.0.0")
    # Railway sets PORT automatically — honour it if present, fall back to API_PORT.
    api_port: int = Field(alias="PORT", default=8000)

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_admin_ids(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                import json

                return json.loads(value)
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        return value


settings = Settings()  # type: ignore[call-arg]

BOT_TOKEN: str = settings.bot_token
BOT_USERNAME: str = settings.bot_username.lstrip("@")
MINIAPP_SHORT_NAME: str = settings.miniapp_short_name
WEBAPP_URL: str = settings.webapp_url
ADMIN_IDS: list[int] = settings.admin_ids
CHANNEL_USERNAME: str = settings.channel_username.lstrip("@")
CHANNEL_ID: int | None = settings.channel_id
BACKUP_CHAT_ID: int | None = settings.backup_chat_id
BACKUP_INTERVAL_HOURS: int = settings.backup_interval_hours
TELEGRAM_API_ID: int | None = settings.telegram_api_id
TELEGRAM_API_HASH: str = settings.telegram_api_hash

from pathlib import Path as _Path  # noqa: E402

DATA_DIR: _Path = _Path(settings.data_dir).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
PHOTOS_DIR: _Path = DATA_DIR / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL: str = (
    settings.database_url
    or f"sqlite+aiosqlite:///{DATA_DIR / 'shop.db'}"
)
API_HOST: str = settings.api_host
API_PORT: int = settings.api_port
