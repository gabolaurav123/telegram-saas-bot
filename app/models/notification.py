from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import NotificationKind
from app.models.types import enum_type


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[int | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="CASCADE"),
        index=True,
    )
    kind: Mapped[NotificationKind] = mapped_column(
        enum_type(NotificationKind, "notification_kind"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), default="PENDING", server_default="PENDING", nullable=False, index=True
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    user: Mapped["User"] = relationship()
    membership: Mapped["Membership | None"] = relationship()
