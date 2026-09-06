from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import CRMStatus
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.user import User


class CRMTag(Base, TimestampMixin):
    __tablename__ = "crm_tags"
    __table_args__ = (UniqueConstraint("name", name="uq_crm_tags_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    color: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False, index=True)


class UserTag(Base, TimestampMixin):
    __tablename__ = "user_tags"
    __table_args__ = (UniqueConstraint("user_id", "tag_id", name="uq_user_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("crm_tags.id", ondelete="CASCADE"), index=True)
    added_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    user: Mapped["User"] = relationship(back_populates="tags", foreign_keys=[user_id])
    tag: Mapped[CRMTag] = relationship(lazy="selectin")
    added_by: Mapped["User | None"] = relationship(foreign_keys=[added_by_user_id], lazy="selectin")


class UserNote(Base, TimestampMixin):
    __tablename__ = "user_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)

    user: Mapped["User"] = relationship(back_populates="notes", foreign_keys=[user_id])
    author: Mapped["User | None"] = relationship(foreign_keys=[author_user_id], lazy="selectin")


class CRMStateHistory(Base, TimestampMixin):
    __tablename__ = "crm_state_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[CRMStatus | None] = mapped_column(enum_type(CRMStatus, "crm_status_from"))
    to_status: Mapped[CRMStatus] = mapped_column(enum_type(CRMStatus, "crm_status_to"), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(255))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="crm_history", foreign_keys=[user_id])
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_user_id], lazy="selectin")


class FunnelEvent(Base, TimestampMixin):
    __tablename__ = "funnel_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    event_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(String(120), index=True)
    campaign: Mapped[str | None] = mapped_column(String(120), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id", ondelete="SET NULL"), index=True)
    payment_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="SET NULL"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    user: Mapped["User | None"] = relationship(foreign_keys=[user_id], lazy="selectin")
