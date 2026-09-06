from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    bot_token: str = Field(..., alias="BOT_TOKEN")
    database_url: str = Field(..., alias="DATABASE_URL")
    owner_ids: list[int] = Field(
        default_factory=list,
        validation_alias=AliasChoices("OWNER_IDS", "OWNER_ID"),
    )

    app_env: str = Field(default="production", alias="APP_ENV")
    app_timezone: str = Field(default="America/La_Paz", alias="APP_TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_to_file: bool = Field(default=True, alias="LOG_TO_FILE")

    support_url: str | None = Field(default=None, alias="SUPPORT_URL")
    faq_url: str | None = Field(default=None, alias="FAQ_URL")
    public_brand_name: str = Field(default="Premium Access", alias="PUBLIC_BRAND_NAME")

    admin_notification_chat_id: int | None = Field(
        default=None, alias="ADMIN_NOTIFICATION_CHAT_ID"
    )
    default_currency: str = Field(default="USD", alias="DEFAULT_CURRENCY")
    invite_link_ttl_minutes: int = Field(default=30, alias="INVITE_LINK_TTL_MINUTES")
    approved_invite_link_ttl_hours: int = Field(default=10, alias="APPROVED_INVITE_LINK_TTL_HOURS")

    rate_limit_window_seconds: int = Field(default=10, alias="RATE_LIMIT_WINDOW_SECONDS")
    rate_limit_max_events: int = Field(default=8, alias="RATE_LIMIT_MAX_EVENTS")

    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    expire_check_minutes: int = Field(default=15, alias="EXPIRE_CHECK_MINUTES")
    reminder_check_minutes: int = Field(default=60, alias="REMINDER_CHECK_MINUTES")
    backup_enabled: bool = Field(default=False, alias="BACKUP_ENABLED")
    backup_interval_hours: int = Field(default=24, alias="BACKUP_INTERVAL_HOURS")
    backup_dir: Path = Field(default=BASE_DIR / "backups", alias="BACKUP_DIR")
    pg_dump_path: str = Field(default="pg_dump", alias="PG_DUMP_PATH")

    broadcast_batch_size: int = Field(default=25, alias="BROADCAST_BATCH_SIZE")
    broadcast_batch_delay_seconds: float = Field(default=1.0, alias="BROADCAST_BATCH_DELAY_SECONDS")
    broadcast_max_retries: int = Field(default=2, alias="BROADCAST_MAX_RETRIES")
    max_invite_links_per_batch: int = Field(default=100, alias="MAX_INVITE_LINKS_PER_BATCH")
    expired_link_reissue_hours: int = Field(default=24, alias="EXPIRED_LINK_REISSUE_HOURS")

    receipt_max_download_mb: int = Field(default=20, alias="RECEIPT_MAX_DOWNLOAD_MB")
    ai_enabled: bool = Field(default=False, alias="AI_ENABLED")
    ocr_enabled: bool = Field(default=False, alias="OCR_ENABLED")
    smart_replies_enabled: bool = Field(default=False, alias="SMART_REPLIES_ENABLED")
    telegram_stars_enabled: bool = Field(default=True, alias="TELEGRAM_STARS_ENABLED")
    telegram_stars_default_ratio: int = Field(default=1, alias="TELEGRAM_STARS_DEFAULT_RATIO")
    external_payments_enabled: bool = Field(default=False, alias="EXTERNAL_PAYMENTS_ENABLED")
    external_payment_webhook_secret: str | None = Field(default=None, alias="EXTERNAL_PAYMENT_WEBHOOK_SECRET")
    mini_app_client_url: str | None = Field(default=None, alias="MINI_APP_CLIENT_URL")
    mini_app_admin_url: str | None = Field(default=None, alias="MINI_APP_ADMIN_URL")
    telegram_webhook_secret_token: str | None = Field(default=None, alias="TELEGRAM_WEBHOOK_SECRET_TOKEN")

    auto_create_db: bool = Field(default=False, alias="AUTO_CREATE_DB")
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")

    @field_validator("owner_ids", mode="before")
    @classmethod
    def parse_owner_ids(cls, value: Any) -> list[int]:
        if value in (None, ""):
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [int(item) for item in value]
        raise TypeError("OWNER_ID/OWNER_IDS must be a Telegram ID or comma separated list")

    @field_validator("default_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper().strip()

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return an async SQLAlchemy URL accepted by asyncpg."""

        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self._without_asyncpg_unsupported_query_params(url)

    @property
    def alembic_database_url(self) -> str:
        return self.sqlalchemy_database_url

    @property
    def safe_database_url(self) -> str:
        parts = urlsplit(self.sqlalchemy_database_url)
        username = parts.username or "user"
        host = parts.hostname or "host"
        port = f":{parts.port}" if parts.port else ""
        return f"{parts.scheme}://{username}:***@{host}{port}{parts.path}"

    @property
    def asyncpg_connect_args(self) -> dict[str, Any]:
        params = dict(parse_qsl(urlsplit(self.database_url).query, keep_blank_values=True))
        sslmode = params.get("sslmode")
        if sslmode and sslmode.lower() != "disable":
            return {"ssl": True}
        return {}

    @staticmethod
    def _without_asyncpg_unsupported_query_params(url: str) -> str:
        unsupported = {"sslmode", "channel_binding"}
        parts = urlsplit(url)
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in unsupported
        ]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
