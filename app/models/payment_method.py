from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.associations import plan_payment_methods
from app.models.enums import PaymentProvider
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.plan import Plan, PlanPaymentMessage


class PaymentMethod(Base, TimestampMixin):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    provider: Mapped[PaymentProvider] = mapped_column(
        enum_type(PaymentProvider, "payment_provider"),
        default=PaymentProvider.CUSTOM,
        server_default=PaymentProvider.CUSTOM.value,
        nullable=False,
        index=True,
    )
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    qr_file_id: Mapped[str | None] = mapped_column(String(255))
    account_data: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(default=100, server_default="100", nullable=False)

    plans: Mapped[list["Plan"]] = relationship(
        secondary=plan_payment_methods,
        back_populates="payment_methods",
        lazy="selectin",
    )
    plan_messages: Mapped[list["PlanPaymentMessage"]] = relationship(
        back_populates="payment_method",
        cascade="all, delete-orphan",
    )
