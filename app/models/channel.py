from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, ForeignKey, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.associations import plan_channels
from app.models.enums import ChatKind
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.plan import Plan
    from app.models.user import User


class Channel(Base, TimestampMixin):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(128), index=True)
    kind: Mapped[ChatKind] = mapped_column(
        enum_type(ChatKind, "channel_kind"),
        default=ChatKind.CHANNEL,
        server_default=ChatKind.CHANNEL.value,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False, index=True)
    require_join_approval: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )
    added_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    plans: Mapped[list["Plan"]] = relationship(
        secondary=plan_channels,
        back_populates="channels",
        lazy="selectin",
    )
    added_by: Mapped["User | None"] = relationship()
