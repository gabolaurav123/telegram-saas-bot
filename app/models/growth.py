from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import CouponType
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.payment_request import PaymentRequest
    from app.models.plan import Plan
    from app.models.user import User


class Coupon(Base, TimestampMixin):
    __tablename__ = "coupons"
    __table_args__ = (UniqueConstraint("code", name="uq_coupons_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    coupon_type: Mapped[CouponType] = mapped_column(
        enum_type(CouponType, "coupon_type"),
        nullable=False,
        index=True,
    )
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id", ondelete="SET NULL"), index=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    max_uses: Mapped[int | None] = mapped_column()
    uses_per_user: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    new_users_only: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    expired_users_only: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    plan: Mapped["Plan | None"] = relationship(lazy="selectin")


class CouponRedemption(Base, TimestampMixin):
    __tablename__ = "coupon_redemptions"
    __table_args__ = (
        UniqueConstraint("coupon_id", "user_id", "payment_request_id", name="uq_coupon_redemption_payment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    payment_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="SET NULL"),
        index=True,
    )
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    coupon: Mapped[Coupon] = relationship(lazy="selectin")
    user: Mapped["User"] = relationship(lazy="selectin")
    payment_request: Mapped["PaymentRequest | None"] = relationship(lazy="selectin")


class Referral(Base, TimestampMixin):
    __tablename__ = "referrals"
    __table_args__ = (UniqueConstraint("referrer_user_id", "referred_user_id", name="uq_referral_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    referred_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    first_payment_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="SET NULL"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="PENDING", server_default="PENDING", nullable=False, index=True)
    revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default="0", nullable=False)
    reward_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    referrer: Mapped["User"] = relationship(foreign_keys=[referrer_user_id], lazy="selectin")
    referred: Mapped["User"] = relationship(foreign_keys=[referred_user_id], lazy="selectin")
    first_payment_request: Mapped["PaymentRequest | None"] = relationship(lazy="selectin")


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"
    __table_args__ = (UniqueConstraint("start_parameter", name="uq_campaigns_start_parameter"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str | None] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    start_parameter: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )
