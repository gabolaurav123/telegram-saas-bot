from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.models.access_event import MembershipAccessEvent
from app.models.enums import AccessEventKind, CRMStatus, LogAction, MembershipStatus, PaymentRequestStatus
from app.models.log import SystemLog
from app.models.membership import Membership
from app.models.payment_request import PaymentRequest
from app.models.plan import Plan
from app.models.user import User
from app.utils.time import utc_now


async def get_overview(session: AsyncSession, settings: Settings | None = None) -> dict[str, object]:
    total_users = await session.scalar(select(func.count(User.id)))
    active_today = await session.scalar(
        select(func.count(User.id)).where(
            User.last_seen_at >= utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        )
    )
    active_week = await session.scalar(
        select(func.count(User.id)).where(User.last_seen_at >= utc_now() - timedelta(days=7))
    )
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
    revenue, unconverted_currencies = await _approved_revenue_usd(session, settings)
    renewals = await session.scalar(
        select(func.count(PaymentRequest.id)).where(
            PaymentRequest.status == PaymentRequestStatus.APPROVED
        )
    )
    expirations = await session.scalar(
        select(func.count(Membership.id)).where(Membership.status == MembershipStatus.EXPIRED)
    )
    successful_joins = await session.scalar(
        select(func.count(MembershipAccessEvent.id)).where(
            MembershipAccessEvent.event_kind == AccessEventKind.JOIN,
            MembershipAccessEvent.join_confirmed.is_(True),
        )
    )
    renewal_requested = await session.scalar(
        select(func.count(SystemLog.id)).where(SystemLog.action == LogAction.MEMBERSHIP_RENEWAL_REQUESTED)
    )
    renewal_approved = await session.scalar(
        select(func.count(SystemLog.id)).where(SystemLog.action == LogAction.MEMBERSHIP_RENEWAL_APPROVED)
    )
    renewal_rejected = await session.scalar(
        select(func.count(SystemLog.id)).where(SystemLog.action == LogAction.MEMBERSHIP_RENEWAL_REJECTED)
    )
    approved_payments = await session.scalar(
        select(func.count(PaymentRequest.id)).where(
            PaymentRequest.status == PaymentRequestStatus.APPROVED
        )
    )
    leads = await session.scalar(select(func.count(User.id)).where(User.crm_status == CRMStatus.LEAD))
    interested = await session.scalar(select(func.count(User.id)).where(User.crm_status == CRMStatus.INTERESTED))
    payment_pending = await session.scalar(
        select(func.count(User.id)).where(User.crm_status == CRMStatus.PAYMENT_PENDING)
    )
    recovered = await session.scalar(select(func.count(User.id)).where(User.crm_status == CRMStatus.RECOVERED))
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
        "active_today": int(active_today or 0),
        "active_week": int(active_week or 0),
        "active_memberships": int(active_memberships or 0),
        "pending_payments": int(pending_payments or 0),
        "leads": int(leads or 0),
        "interested": int(interested or 0),
        "payment_pending": int(payment_pending or 0),
        "recovered": int(recovered or 0),
        "revenue": Decimal(revenue or 0),
        "revenue_currency": "USD",
        "unconverted_currencies": unconverted_currencies,
        "renewals": int(renewals or 0),
        "renewal_requested": int(renewal_requested or 0),
        "renewal_approved": int(renewal_approved or 0),
        "renewal_rejected": int(renewal_rejected or 0),
        "expirations": int(expirations or 0),
        "successful_joins": int(successful_joins or 0),
        "conversion_rate": (
            round((int(approved_payments or 0) / int(total_users or 1)) * 100, 2)
            if int(total_users or 0)
            else 0
        ),
        "top_plans": [(row[0], int(row[1])) for row in top_plans_result],
    }


async def _approved_revenue_usd(
    session: AsyncSession,
    settings: Settings | None,
) -> tuple[Decimal, list[str]]:
    if settings is None:
        raw_total = await session.scalar(
            select(func.coalesce(func.sum(PaymentRequest.amount), 0)).where(
                PaymentRequest.status == PaymentRequestStatus.APPROVED
            )
        )
        return Decimal(raw_total or 0), []
    rows = await session.execute(
        select(
            PaymentRequest.currency,
            func.coalesce(func.sum(PaymentRequest.amount), 0),
        )
        .where(
            PaymentRequest.status == PaymentRequestStatus.APPROVED,
            PaymentRequest.currency != "XTR",
        )
        .group_by(PaymentRequest.currency)
    )
    totals = [(str(currency).upper(), Decimal(amount or 0)) for currency, amount in rows]
    total_usd = Decimal("0")
    missing: list[str] = []
    for currency, amount in totals:
        rate = settings.currency_usd_rates.get(currency)
        if rate is None:
            missing.append(currency)
            continue
        total_usd += amount * rate

    stars_rows = await session.execute(
        select(PaymentRequest.amount, PaymentRequest.metadata_json).where(
            PaymentRequest.status == PaymentRequestStatus.APPROVED,
            PaymentRequest.currency == "XTR",
        )
    )
    for amount, metadata in stars_rows:
        historical_usd = (metadata or {}).get("usd_amount")
        if historical_usd not in (None, ""):
            total_usd += Decimal(str(historical_usd))
        else:
            total_usd += Decimal(amount or 0) / settings.effective_stars_per_usd
    return total_usd.quantize(Decimal("0.01")), sorted(set(missing))
