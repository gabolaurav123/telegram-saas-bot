from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import Role
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.user import User


class Admin(Base, TimestampMixin):
    __tablename__ = "admins"
    __table_args__ = (UniqueConstraint("telegram_id", name="uq_admins_telegram_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[Role] = mapped_column(
        enum_type(Role, "admin_role"), default=Role.MODERATOR, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False, index=True)
    permissions: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )
    added_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(
        back_populates="admin_profile",
        foreign_keys=[user_id],
    )
    added_by: Mapped["User | None"] = relationship(foreign_keys=[added_by_id])
