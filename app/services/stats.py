from __future__ import annotations

from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MembershipStatus, PaymentRequestStatus
from app.models.membership import Membership
from app.models.payment_request import PaymentRequest
from app.models.plan import Plan
from app.models.user import User
from app.utils.time import utc_now


async def get_overview(session: AsyncSession) -> dict[str, object]:
    total_users = await session.scalar(select(func.count(User.id)))
    active_memberships = await session.scalar(
        select(func.count(Membership.id)).where(
            Membership.status == MembershipStatus.ACTIVE,
            Membership.expires_at > utc_now(),
        )
    )
    pending_payments = await session.scalar(
        select(func.count(PaymentRequest.id)).where(
            PaymentRequest.status == PaymentRequestStatus.PENDING
        )
    )
    revenue = await session.scalar(
        select(func.coalesce(func.sum(PaymentRequest.amount), 0)).where(
            PaymentRequest.status == PaymentRequestStatus.APPROVED
        )
    )
    renewals = await session.scalar(
        select(func.count(PaymentRequest.id)).where(
            PaymentRequest.status == PaymentRequestStatus.APPROVED
        )
    )
    expirations = await session.scalar(
        select(func.count(Membership.id)).where(Membership.status == MembershipStatus.EXPIRED)
    )
    top_plans_result = await session.execute(
        select(Plan.name, func.count(PaymentRequest.id).label("sales"))
        .join(PaymentRequest, PaymentRequest.plan_id == Plan.id)
        .where(PaymentRequest.status == PaymentRequestStatus.APPROVED)
        .group_by(Plan.name)
        .order_by(desc("sales"))
        .limit(5)
    )
    return {
        "total_users": int(total_users or 0),
        "active_users": int(active_memberships or 0),
        "active_memberships": int(active_memberships or 0),
        "pending_payments": int(pending_payments or 0),
        "revenue": Decimal(revenue or 0),
        "renewals": int(renewals or 0),
        "expirations": int(expirations or 0),
        "top_plans": [(row[0], int(row[1])) for row in top_plans_result],
    }

