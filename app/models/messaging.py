from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, Text, text as sa_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import DeliveryStatus
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.user import User


class OutboundMessage(Base, TimestampMixin):
    __tablename__ = "outbound_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_message_id: Mapped[int | None] = mapped_column(index=True)
    source: Mapped[str] = mapped_column(String(40), default="ADMIN_DIRECT", server_default="ADMIN_DIRECT", nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), default="text", server_default="text", nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[DeliveryStatus] = mapped_column(
        enum_type(DeliveryStatus, "delivery_status"),
        default=DeliveryStatus.PENDING,
        server_default=DeliveryStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=sa_text("'{}'"), nullable=False
    )

    target_user: Mapped["User"] = relationship(foreign_keys=[target_user_id], lazy="selectin")
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_user_id], lazy="selectin")


class InboxMessage(Base, TimestampMixin):
    __tablename__ = "inbox_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    support_thread_id: Mapped[int | None] = mapped_column(
        ForeignKey("support_threads.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    admin_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_message_id: Mapped[int | None] = mapped_column(index=True)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    file_id: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=sa_text("'{}'"), nullable=False
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id], lazy="selectin")
    admin_user: Mapped["User | None"] = relationship(foreign_keys=[admin_user_id], lazy="selectin")
