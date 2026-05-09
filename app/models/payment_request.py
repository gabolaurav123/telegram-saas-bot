from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import PaymentRequestStatus, ProofKind
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.payment_method import PaymentMethod
    from app.models.plan import Plan
    from app.models.user import User


class PaymentRequest(Base, TimestampMixin):
    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="RESTRICT"),
        index=True,
    )
    status: Mapped[PaymentRequestStatus] = mapped_column(
        enum_type(PaymentRequestStatus, "payment_request_status"),
        default=PaymentRequestStatus.PENDING,
        server_default=PaymentRequestStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    proof_kind: Mapped[ProofKind | None] = mapped_column(enum_type(ProofKind, "proof_kind"))
    proof_file_id: Mapped[str | None] = mapped_column(String(255))
    proof_file_unique_id: Mapped[str | None] = mapped_column(String(255))
    proof_message_id: Mapped[int | None] = mapped_column()
    admin_note: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    user: Mapped["User"] = relationship(
        back_populates="payment_requests",
        foreign_keys=[user_id],
    )
    reviewed_by: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by_id])
    plan: Mapped["Plan"] = relationship(lazy="selectin")
    payment_method: Mapped["PaymentMethod"] = relationship(lazy="selectin")
    membership: Mapped["Membership | None"] = relationship(
        back_populates="payment_request",
        uselist=False,
    )
