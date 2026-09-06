from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class QuickReply(Base, TimestampMixin):
    __tablename__ = "quick_replies"
    __table_args__ = (UniqueConstraint("command", name="uq_quick_replies_command"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    command: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=100, server_default="100", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    created_by = relationship("User", lazy="selectin")
