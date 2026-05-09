from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, JSON, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.associations import plan_channels, plan_groups, plan_payment_methods

if TYPE_CHECKING:
    from app.models.channel import Channel
    from app.models.group import TelegramGroup
    from app.models.payment_method import PaymentMethod


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", server_default="USD", nullable=False)
    duration_days: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(default=100, server_default="100", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    channels: Mapped[list["Channel"]] = relationship(
        secondary=plan_channels,
        back_populates="plans",
        lazy="selectin",
    )
    groups: Mapped[list["TelegramGroup"]] = relationship(
        secondary=plan_groups,
        back_populates="plans",
        lazy="selectin",
    )
    payment_methods: Mapped[list["PaymentMethod"]] = relationship(
        secondary=plan_payment_methods,
        back_populates="plans",
        lazy="selectin",
    )
    payment_messages: Mapped[list["PlanPaymentMessage"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PlanPaymentMessage(Base, TimestampMixin):
    __tablename__ = "plan_payment_messages"
    __table_args__ = (
        UniqueConstraint("plan_id", "payment_method_id", name="uq_plan_payment_message_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="CASCADE"), index=True
    )
    message_template: Mapped[str] = mapped_column(Text, nullable=False)

    plan: Mapped["Plan"] = relationship(back_populates="payment_messages")
    payment_method: Mapped["PaymentMethod"] = relationship(back_populates="plan_messages")
