from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, JSON, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import MembershipStatus
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.payment_request import PaymentRequest
    from app.models.plan import Plan
    from app.models.user import User


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    payment_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="SET NULL"),
        unique=True,
        index=True,
    )
    status: Mapped[MembershipStatus] = mapped_column(
        enum_type(MembershipStatus, "membership_status"),
        default=MembershipStatus.ACTIVE,
        server_default=MembershipStatus.ACTIVE.value,
        nullable=False,
        index=True,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    reminder_3d_sent: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    reminder_1d_sent: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    expired_notified: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    access_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="memberships")
    plan: Mapped["Plan"] = relationship(lazy="selectin")
    payment_request: Mapped["PaymentRequest | None"] = relationship(back_populates="membership")
