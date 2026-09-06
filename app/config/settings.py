from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    default_language: str = Field(default="es", alias="DEFAULT_LANGUAGE")
    supported_languages: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["es", "en"],
        alias="SUPPORTED_LANGUAGES",
    )

    admin_notification_chat_id: int | None = Field(
        default=None, alias="ADMIN_NOTIFICATION_CHAT_ID"
    )
    default_currency: str = Field(default="USD", alias="DEFAULT_CURRENCY")
    currency_usd_rates: Annotated[dict[str, Decimal], NoDecode] = Field(
        default_factory=lambda: {"USD": Decimal("1")},
        alias="CURRENCY_USD_RATES",
    )
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
    telegram_stars_default_ratio: Decimal = Field(
        default=Decimal("44.11764706"),
        alias="TELEGRAM_STARS_DEFAULT_RATIO",
    )
    telegram_stars_per_usd: Decimal | None = Field(default=None, alias="TELEGRAM_STARS_PER_USD")
    external_payments_enabled: bool = Field(default=False, alias="EXTERNAL_PAYMENTS_ENABLED")
    external_payment_webhook_secret: str | None = Field(default=None, alias="EXTERNAL_PAYMENT_WEBHOOK_SECRET")
    mini_app_client_url: str | None = Field(default=None, alias="MINI_APP_CLIENT_URL")
    mini_app_admin_url: str | None = Field(default=None, alias="MINI_APP_ADMIN_URL")
    telegram_webhook_secret_token: str | None = Field(default=None, alias="TELEGRAM_WEBHOOK_SECRET_TOKEN")

    web_enabled: bool = Field(default=True, alias="WEB_ENABLED")
    web_host: str = Field(default="0.0.0.0", alias="WEB_HOST")
    port: int = Field(default=8000, alias="PORT", ge=1, le=65535)
    telegram_webapp_max_age_seconds: int = Field(
        default=86400,
        alias="TELEGRAM_WEBAPP_MAX_AGE_SECONDS",
        ge=60,
    )

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

    @field_validator("default_language")
    @classmethod
    def normalize_default_language(cls, value: str) -> str:
        normalized = value.lower().strip()
        return normalized or "es"

    @field_validator("supported_languages", mode="before")
    @classmethod
    def parse_supported_languages(cls, value: Any) -> list[str]:
        if value in (None, ""):
            return ["es", "en"]
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                value = json.loads(stripped)
            else:
                return [item.lower().strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).lower().strip() for item in value if str(item).strip()]
        raise TypeError("SUPPORTED_LANGUAGES must be a comma separated list")

    @field_validator("currency_usd_rates", mode="before")
    @classmethod
    def parse_currency_usd_rates(cls, value: Any) -> dict[str, Decimal]:
        if value in (None, ""):
            return {"USD": Decimal("1")}
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return {"USD": Decimal("1")}
            if stripped.startswith("{"):
                value = json.loads(stripped)
            else:
                pairs: dict[str, Decimal] = {}
                for item in stripped.split(","):
                    if not item.strip():
                        continue
                    if "=" not in item:
                        raise ValueError("CURRENCY_USD_RATES must use JSON or CODE=RATE pairs")
                    code, rate = item.split("=", 1)
                    pairs[code.upper().strip()] = Decimal(rate.strip())
                pairs.setdefault("USD", Decimal("1"))
                return pairs
        if isinstance(value, dict):
            rates = {
                str(code).upper().strip(): Decimal(str(rate))
                for code, rate in value.items()
                if str(code).strip()
            }
            rates.setdefault("USD", Decimal("1"))
            return rates
        raise TypeError("CURRENCY_USD_RATES must be JSON or CODE=RATE pairs")

    @field_validator("telegram_stars_default_ratio", "telegram_stars_per_usd", mode="before")
    @classmethod
    def parse_positive_decimal(cls, value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        parsed = Decimal(str(value))
        if parsed <= 0:
            raise ValueError("Stars conversion values must be greater than zero")
        return parsed

    @property
    def effective_stars_per_usd(self) -> Decimal:
        if self.telegram_stars_per_usd:
            return self.telegram_stars_per_usd
        if not self.telegram_stars_default_ratio or self.telegram_stars_default_ratio <= Decimal("1"):
            return Decimal("44.11764706")
        return self.telegram_stars_default_ratio

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
