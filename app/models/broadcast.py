from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.plan import Plan
    from app.models.user import User


class BroadcastJob(Base, TimestampMixin):
    __tablename__ = "broadcast_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    target: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", server_default="PENDING", nullable=False)
    source_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_message_id: Mapped[int] = mapped_column(nullable=False)
    total: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    sent: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    failed: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    blocked: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    plan: Mapped["Plan | None"] = relationship(lazy="selectin")
    recipients: Mapped[list["BroadcastRecipient"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class BroadcastRecipient(Base, TimestampMixin):
    __tablename__ = "broadcast_recipients"
    __table_args__ = (UniqueConstraint("job_id", "user_id", name="uq_broadcast_recipient_job_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("broadcast_jobs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", server_default="PENDING", nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped["BroadcastJob"] = relationship(back_populates="recipients")
    user: Mapped["User"] = relationship(lazy="selectin")
