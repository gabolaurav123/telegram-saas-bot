from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.channel import Channel
    from app.models.group import TelegramGroup
    from app.models.plan import Plan
    from app.models.user import User


class GeneratedInviteLink(Base, TimestampMixin):
    __tablename__ = "generated_invite_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_title: Mapped[str] = mapped_column(String(255), nullable=False)
    invite_link: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_used: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False, index=True)
    used_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    creator: Mapped["User | None"] = relationship(foreign_keys=[creator_user_id])
    used_by: Mapped["User | None"] = relationship(foreign_keys=[used_by_user_id])
    plan: Mapped["Plan"] = relationship(lazy="selectin")
    channel: Mapped["Channel | None"] = relationship(lazy="selectin")
    group: Mapped["TelegramGroup | None"] = relationship(lazy="selectin")
