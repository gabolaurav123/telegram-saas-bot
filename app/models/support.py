from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class SupportThread(Base, TimestampMixin):
    __tablename__ = "support_threads"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    status: Mapped[str] = mapped_column(default="OPEN", server_default="OPEN", nullable=False, index=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped["User"] = relationship(lazy="selectin")


class SupportReplyMap(Base, TimestampMixin):
    __tablename__ = "support_reply_maps"
    __table_args__ = (
        UniqueConstraint("admin_chat_id", "admin_message_id", name="uq_support_reply_admin_message"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("support_threads.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    admin_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    admin_message_id: Mapped[int] = mapped_column(index=True)
    user_message_id: Mapped[int | None] = mapped_column()
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    thread: Mapped["SupportThread"] = relationship(lazy="selectin")
    user: Mapped["User"] = relationship(lazy="selectin")

