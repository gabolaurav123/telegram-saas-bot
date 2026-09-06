from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import CRMStatus, UserStatus
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.membership import Membership
    from app.models.payment_request import PaymentRequest
    from app.models.crm import CRMStateHistory, UserNote, UserTag


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(128), index=True)
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(16))
    is_bot: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        enum_type(UserStatus, "user_status"),
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
        nullable=False,
        index=True,
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    first_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    crm_status: Mapped[CRMStatus] = mapped_column(
        enum_type(CRMStatus, "crm_status"),
        default=CRMStatus.LEAD,
        server_default=CRMStatus.LEAD.value,
        nullable=False,
        index=True,
    )
    start_parameter: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(120), index=True)
    campaign: Mapped[str | None] = mapped_column(String(120), index=True)
    referral_code: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    referred_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    internal_notes: Mapped[str | None] = mapped_column(Text)
    is_vip: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False, index=True)
    delivery_status: Mapped[str] = mapped_column(default="UNKNOWN", server_default="UNKNOWN", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    admin_profile: Mapped["Admin | None"] = relationship(
        back_populates="user",
        foreign_keys="Admin.user_id",
        uselist=False,
    )
    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")
    payment_requests: Mapped[list["PaymentRequest"]] = relationship(
        back_populates="user",
        foreign_keys="PaymentRequest.user_id",
    )
    referred_by: Mapped["User | None"] = relationship(
        remote_side=[id],
        foreign_keys=[referred_by_user_id],
    )
    notes: Mapped[list["UserNote"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserNote.user_id",
    )
    tags: Mapped[list["UserTag"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserTag.user_id",
    )
    crm_history: Mapped[list["CRMStateHistory"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="CRMStateHistory.user_id",
    )

    @property
    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        full_name = " ".join(part for part in [self.first_name, self.last_name] if part)
        return full_name or str(self.telegram_id)
