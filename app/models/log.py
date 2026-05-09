from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import LogAction
from app.models.types import enum_type


class SystemLog(Base, TimestampMixin):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[LogAction] = mapped_column(
        enum_type(LogAction, "log_action", length=64),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(16), default="INFO", server_default="INFO", nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_user_id])
    target: Mapped["User | None"] = relationship(foreign_keys=[target_user_id])
