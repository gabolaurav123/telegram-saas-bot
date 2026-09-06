from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import AutomationJobStatus
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.user import User


class AutomationRule(Base, TimestampMixin):
    __tablename__ = "automation_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    trigger: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    delay_seconds: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    conditions_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    action_payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    created_by: Mapped["User | None"] = relationship(lazy="selectin")


class AutomationJob(Base, TimestampMixin):
    __tablename__ = "automation_jobs"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_automation_jobs_dedupe_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("automation_rules.id", ondelete="SET NULL"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    trigger: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[AutomationJobStatus] = mapped_column(
        enum_type(AutomationJobStatus, "automation_job_status"),
        default=AutomationJobStatus.PENDING,
        server_default=AutomationJobStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    rule: Mapped[AutomationRule | None] = relationship(lazy="selectin")
    user: Mapped["User | None"] = relationship(lazy="selectin")
