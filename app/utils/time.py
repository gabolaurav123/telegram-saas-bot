from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(UTC)


def add_days(days: int, base: datetime | None = None) -> datetime:
    return (base or utc_now()) + timedelta(days=days)


def human_datetime(value: datetime | None, timezone_name: str = "America/La_Paz") -> str:
    if value is None:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    local_value = value.astimezone(ZoneInfo(timezone_name))
    return local_value.strftime("%Y-%m-%d %H:%M")


def remaining_days(expires_at: datetime) -> int:
    delta = expires_at - utc_now()
    return max(0, delta.days)

