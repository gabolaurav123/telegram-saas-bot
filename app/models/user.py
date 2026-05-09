from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import UserStatus
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.membership import Membership
    from app.models.payment_request import PaymentRequest


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
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
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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

    @property
    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        full_name = " ".join(part for part in [self.first_name, self.last_name] if part)
        return full_name or str(self.telegram_id)
