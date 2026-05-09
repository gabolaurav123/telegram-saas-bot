from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import LogAction, MembershipStatus
from app.models.membership import Membership
from app.models.payment_request import PaymentRequest
from app.models.plan import Plan
from app.models.user import User
from app.services.logs import log_event
from app.utils.time import add_days, utc_now


async def get_active_memberships(session: AsyncSession, user_id: int) -> list[Membership]:
    result = await session.scalars(
        select(Membership)
        .options(selectinload(Membership.plan))
        .where(
            Membership.user_id == user_id,
            Membership.status == MembershipStatus.ACTIVE,
            Membership.expires_at > utc_now(),
        )
        .order_by(Membership.expires_at.desc())
    )
    return list(result)


async def activate_membership(
    session: AsyncSession,
    *,
    user: User,
    plan: Plan,
    payment_request: PaymentRequest,
    access_payload: dict | None = None,
) -> Membership:
    current_same_plan = await session.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.plan_id == plan.id,
            Membership.status == MembershipStatus.ACTIVE,
            Membership.expires_at > utc_now(),
        )
    )
    start = utc_now()
    base = start
    if current_same_plan is not None:
        base = max(current_same_plan.expires_at, start)
        current_same_plan.status = MembershipStatus.CANCELLED
        current_same_plan.cancelled_at = start
        current_same_plan.revoke_reason = "Renewed by approved payment request"

    membership = Membership(
        user_id=user.id,
        plan_id=plan.id,
        payment_request_id=payment_request.id,
        starts_at=start,
        expires_at=add_days(plan.duration_days, base),
        status=MembershipStatus.ACTIVE,
        access_payload=access_payload or {},
    )
    session.add(membership)
    await session.flush()
    await log_event(
        session,
        LogAction.MEMBERSHIP_ACTIVATED,
        f"Membresia activada para {user.telegram_id}",
        target_user_id=user.id,
        details={"membership_id": membership.id, "plan_id": plan.id},
    )
    return membership


async def memberships_due_to_expire(session: AsyncSession) -> list[Membership]:
    result = await session.scalars(
        select(Membership)
        .options(
            selectinload(Membership.user),
            selectinload(Membership.plan).selectinload(Plan.channels),
            selectinload(Membership.plan).selectinload(Plan.groups),
        )
        .where(
            Membership.status == MembershipStatus.ACTIVE,
            Membership.expires_at <= utc_now(),
        )
        .order_by(Membership.expires_at)
    )
    return list(result)


async def memberships_for_reminder(session: AsyncSession, days_before: int) -> list[Membership]:
    now = utc_now()
    upper = now + timedelta(days=days_before)
    flag = Membership.reminder_3d_sent if days_before == 3 else Membership.reminder_1d_sent
    result = await session.scalars(
        select(Membership)
        .options(selectinload(Membership.user), selectinload(Membership.plan))
        .where(
            Membership.status == MembershipStatus.ACTIVE,
            Membership.expires_at > now,
            Membership.expires_at <= upper,
            flag.is_(False),
        )
        .order_by(Membership.expires_at)
    )
    return list(result)


async def expire_membership(session: AsyncSession, membership: Membership) -> None:
    membership.status = MembershipStatus.EXPIRED
    membership.expired_notified = True
    await log_event(
        session,
        LogAction.MEMBERSHIP_EXPIRED,
        f"Membresia vencida: {membership.id}",
        target_user_id=membership.user_id,
        details={"membership_id": membership.id, "plan_id": membership.plan_id},
    )

