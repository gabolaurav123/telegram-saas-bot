from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class Setting(Base, TimestampMixin):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
