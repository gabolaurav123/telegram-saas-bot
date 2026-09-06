from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.payment_request import PaymentRequest
    from app.models.plan import Plan
    from app.models.user import User


class TelegramStarsPayment(Base, TimestampMixin):
    __tablename__ = "telegram_stars_payments"
    __table_args__ = (
        UniqueConstraint("invoice_payload", name="uq_stars_invoice_payload"),
        UniqueConstraint("telegram_payment_charge_id", name="uq_stars_charge_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    payment_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="SET NULL"),
        index=True,
    )
    invoice_payload: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    telegram_payment_charge_id: Mapped[str | None] = mapped_column(String(255), index=True)
    provider_payment_charge_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), default="INVOICE_CREATED", server_default="INVOICE_CREATED", nullable=False, index=True)
    amount_stars: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="XTR", server_default="XTR", nullable=False)
    subscription_period: Mapped[int | None] = mapped_column()
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    user: Mapped["User"] = relationship(lazy="selectin")
    plan: Mapped["Plan"] = relationship(lazy="selectin")
    payment_request: Mapped["PaymentRequest | None"] = relationship(lazy="selectin")


class ExternalPaymentSession(Base, TimestampMixin):
    __tablename__ = "external_payment_sessions"
    __table_args__ = (
        UniqueConstraint("provider", "provider_session_id", name="uq_external_payment_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    payment_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="SET NULL"),
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider_session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    checkout_url: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="CREATED", server_default="CREATED", nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    user: Mapped["User"] = relationship(lazy="selectin")
    plan: Mapped["Plan"] = relationship(lazy="selectin")
    payment_request: Mapped["PaymentRequest | None"] = relationship(lazy="selectin")


class ProviderWebhookEvent(Base, TimestampMixin):
    __tablename__ = "provider_webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_provider_webhook_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="RECEIVED", server_default="RECEIVED", nullable=False, index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    error: Mapped[str | None] = mapped_column(Text)
