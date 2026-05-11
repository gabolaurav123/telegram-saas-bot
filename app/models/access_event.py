from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import AccessEventKind
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.generated_invite_link import GeneratedInviteLink
    from app.models.membership import Membership
    from app.models.plan import Plan
    from app.models.user import User


class MembershipAccessEvent(Base, TimestampMixin):
    __tablename__ = "membership_access_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[int | None] = mapped_column(ForeignKey("memberships.id", ondelete="SET NULL"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id", ondelete="SET NULL"), index=True)
    generated_invite_link_id: Mapped[int | None] = mapped_column(
        ForeignKey("generated_invite_links.id", ondelete="SET NULL"), index=True
    )
    event_kind: Mapped[AccessEventKind] = mapped_column(
        enum_type(AccessEventKind, "access_event_kind"),
        nullable=False,
        index=True,
    )
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_title: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), index=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    join_confirmed: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    kick_result: Mapped[str | None] = mapped_column(String(80))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id], lazy="selectin")
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_user_id], lazy="selectin")
    membership: Mapped["Membership | None"] = relationship(lazy="selectin")
    plan: Mapped["Plan | None"] = relationship(lazy="selectin")
    generated_invite_link: Mapped["GeneratedInviteLink | None"] = relationship(lazy="selectin")
