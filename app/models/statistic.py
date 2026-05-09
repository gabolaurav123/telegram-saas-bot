from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, JSON, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class Statistic(Base, TimestampMixin):
    __tablename__ = "statistics"
    __table_args__ = (UniqueConstraint("date", "metric", name="uq_statistics_date_metric"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )
