from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.models.enums import LogAction, MembershipStatus
from app.models.crm import UserTag
from app.models.membership import Membership
from app.models.payment_request import PaymentRequest
from app.models.user import User
from app.services.logs import log_event
from app.utils.time import human_datetime, utc_now
from app.utils.xlsx import write_xlsx


HEADERS = [
    "telegram_id",
    "nombre",
    "username",
    "fecha_registro",
    "plan_actual",
    "fecha_expiracion",
    "estado",
    "metodo_pago",
    "total_pagos",
    "ultimo_acceso",
    "crm_status",
    "source",
    "campaign",
    "referral_code",
    "delivery_status",
    "tags",
    "vip",
]


async def export_clients(
    session: AsyncSession,
    *,
    settings: Settings,
    filter_name: str,
    actor_user_id: int | None = None,
    plan_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[Path, Path]:
    users = await _users_for_filter(
        session,
        filter_name=filter_name,
        plan_id=plan_id,
        date_from=date_from,
        date_to=date_to,
    )
    rows: list[list[object]] = []
    for user in users:
        membership = await _latest_membership(session, user.id)
        total_payments = len(user.payment_requests)
        latest_payment = max(user.payment_requests, key=lambda item: item.submitted_at, default=None)
        payment_method = latest_payment.payment_method.name if latest_payment else "-"
        tags = ", ".join(item.tag.name for item in user.tags)
        rows.append(
            [
                user.telegram_id,
                user.display_name,
                f"@{user.username}" if user.username else "",
                human_datetime(user.registered_at, settings.app_timezone),
                membership.plan.name if membership else "",
                human_datetime(membership.expires_at, settings.app_timezone) if membership else "",
                membership.status.value if membership else "SIN_SUSCRIPCION",
                payment_method,
                total_payments,
                human_datetime(user.last_seen_at, settings.app_timezone),
                user.crm_status.value,
                user.source or "",
                user.campaign or "",
                user.referral_code or "",
                user.delivery_status,
                tags,
                "SI" if user.is_vip else "NO",
            ]
        )

    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y%m%d-%H%M%S")
    csv_path = settings.backup_dir / f"clients-{filter_name}-{stamp}.csv"
    xlsx_path = settings.backup_dir / f"clients-{filter_name}-{stamp}.xlsx"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(HEADERS)
        writer.writerows(rows)
    write_xlsx(xlsx_path, HEADERS, rows)
    await log_event(
        session,
        LogAction.CLIENTS_EXPORTED,
        f"Clientes exportados: {len(rows)}",
        actor_user_id=actor_user_id,
        details={"filter": filter_name, "plan_id": plan_id, "rows": len(rows)},
    )
    return csv_path, xlsx_path


async def _users_for_filter(
    session: AsyncSession,
    *,
    filter_name: str,
    plan_id: int | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[User]:
    stmt = select(User).options(
        selectinload(User.payment_requests).selectinload(PaymentRequest.payment_method),
        selectinload(User.tags).selectinload(UserTag.tag),
    )
    active_membership = select(Membership.user_id).where(
        Membership.status == MembershipStatus.ACTIVE,
        Membership.expires_at > utc_now(),
    )
    if filter_name == "active":
        stmt = stmt.where(User.id.in_(active_membership))
    elif filter_name == "expired":
        stmt = stmt.where(
            User.id.in_(select(Membership.user_id).where(Membership.status == MembershipStatus.EXPIRED))
        )
    elif filter_name == "plan" and plan_id is not None:
        stmt = stmt.where(User.id.in_(active_membership.where(Membership.plan_id == plan_id)))
    elif filter_name == "date":
        if date_from is not None:
            stmt = stmt.where(User.registered_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(User.registered_at <= date_to)
    result = await session.scalars(stmt.order_by(User.created_at.desc()))
    return list(result)


async def _latest_membership(session: AsyncSession, user_id: int) -> Membership | None:
    return await session.scalar(
        select(Membership)
        .options(selectinload(Membership.plan))
        .where(Membership.user_id == user_id)
        .order_by(Membership.expires_at.desc())
        .limit(1)
    )
