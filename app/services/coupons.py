from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CouponType, LogAction
from app.models.growth import Coupon, CouponRedemption
from app.models.payment_request import PaymentRequest
from app.models.user import User
from app.services.logs import log_event
from app.utils.time import utc_now


async def validate_coupon(
    session: AsyncSession,
    *,
    code: str,
    user: User,
    plan_id: int,
    amount: Decimal,
) -> tuple[Coupon, Decimal]:
    coupon = await session.scalar(
        select(Coupon).where(Coupon.code == code.strip().upper(), Coupon.enabled.is_(True))
    )
    if coupon is None:
        raise ValueError("Cupon no encontrado.")
    now = utc_now()
    if coupon.plan_id and coupon.plan_id != plan_id:
        raise ValueError("Este cupon no aplica para el plan seleccionado.")
    if coupon.start_date and coupon.start_date > now:
        raise ValueError("Este cupon aun no esta activo.")
    if coupon.end_date and coupon.end_date < now:
        raise ValueError("Este cupon expiro.")
    total_uses = await session.scalar(
        select(func.count(CouponRedemption.id)).where(CouponRedemption.coupon_id == coupon.id)
    )
    if coupon.max_uses is not None and int(total_uses or 0) >= coupon.max_uses:
        raise ValueError("Este cupon ya alcanzo su limite de uso.")
    user_uses = await session.scalar(
        select(func.count(CouponRedemption.id)).where(
            CouponRedemption.coupon_id == coupon.id,
            CouponRedemption.user_id == user.id,
        )
    )
    if int(user_uses or 0) >= coupon.uses_per_user:
        raise ValueError("Ya usaste este cupon.")
    discount = coupon.value if coupon.coupon_type == CouponType.FIXED else amount * coupon.value / Decimal("100")
    return coupon, min(amount, discount)


async def redeem_coupon(
    session: AsyncSession,
    *,
    coupon: Coupon,
    user: User,
    payment_request: PaymentRequest,
    discount_amount: Decimal,
) -> CouponRedemption:
    redemption = CouponRedemption(
        coupon_id=coupon.id,
        user_id=user.id,
        payment_request_id=payment_request.id,
        discount_amount=discount_amount,
        redeemed_at=utc_now(),
    )
    session.add(redemption)
    await log_event(
        session,
        LogAction.COUPON_REDEEMED,
        f"Cupon redimido: {coupon.code}",
        target_user_id=user.id,
        details={
            "coupon_id": coupon.id,
            "payment_request_id": payment_request.id,
            "discount_amount": str(discount_amount),
        },
    )
    return redemption
