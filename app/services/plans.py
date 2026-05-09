from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.channel import Channel
from app.models.enums import LogAction
from app.models.group import TelegramGroup
from app.models.payment_method import PaymentMethod
from app.models.plan import Plan, PlanPaymentMessage
from app.models.user import User
from app.services.logs import log_event
from app.services.payment_methods import list_payment_methods
from app.utils.text import DEFAULT_PAYMENT_TEMPLATE, slugify


async def list_plans(session: AsyncSession, *, only_active: bool = False) -> list[Plan]:
    stmt = (
        select(Plan)
        .options(
            selectinload(Plan.channels),
            selectinload(Plan.groups),
            selectinload(Plan.payment_methods),
            selectinload(Plan.payment_messages),
        )
        .order_by(Plan.sort_order, Plan.price, Plan.name)
    )
    if only_active:
        stmt = stmt.where(Plan.is_active.is_(True))
    result = await session.scalars(stmt)
    return list(result)


async def get_plan(session: AsyncSession, plan_id: int) -> Plan | None:
    return await session.scalar(
        select(Plan)
        .options(
            selectinload(Plan.channels),
            selectinload(Plan.groups),
            selectinload(Plan.payment_methods),
            selectinload(Plan.payment_messages).selectinload(PlanPaymentMessage.payment_method),
        )
        .where(Plan.id == plan_id)
    )


async def _unique_slug(session: AsyncSession, name: str) -> str:
    base = slugify(name)
    slug = base
    counter = 2
    while await session.scalar(select(Plan.id).where(Plan.slug == slug)):
        slug = f"{base}-{counter}"
        counter += 1
    return slug


async def create_plan(
    session: AsyncSession,
    *,
    name: str,
    description: str | None,
    price: Decimal,
    duration_days: int,
    currency: str,
    actor: User | None = None,
) -> Plan:
    active_methods = await list_payment_methods(session, only_active=True)
    plan = Plan(
        slug=await _unique_slug(session, name),
        name=name.strip(),
        description=description.strip() if description else None,
        price=price,
        duration_days=duration_days,
        currency=currency.upper().strip(),
        is_active=True,
    )
    plan.payment_methods.extend(active_methods)
    session.add(plan)
    await session.flush()

    for method in active_methods:
        session.add(
            PlanPaymentMessage(
                plan_id=plan.id,
                payment_method_id=method.id,
                message_template=DEFAULT_PAYMENT_TEMPLATE,
            )
        )

    await log_event(
        session,
        LogAction.PLAN_CREATED,
        f"Plan creado: {plan.name}",
        actor_user_id=actor.id if actor else None,
        details={"plan_id": plan.id, "price": str(plan.price), "currency": plan.currency},
    )
    return plan


async def toggle_plan(session: AsyncSession, plan_id: int, *, actor: User | None = None) -> Plan:
    plan = await get_plan(session, plan_id)
    if plan is None:
        raise ValueError("Plan no encontrado.")
    plan.is_active = not plan.is_active
    await log_event(
        session,
        LogAction.PLAN_UPDATED,
        f"Plan {plan.name} {'activado' if plan.is_active else 'desactivado'}",
        actor_user_id=actor.id if actor else None,
        details={"plan_id": plan.id, "is_active": plan.is_active},
    )
    return plan


async def delete_plan(session: AsyncSession, plan_id: int, *, actor: User | None = None) -> None:
    plan = await get_plan(session, plan_id)
    if plan is None:
        raise ValueError("Plan no encontrado.")
    plan.is_active = False
    await log_event(
        session,
        LogAction.PLAN_UPDATED,
        f"Plan {plan.name} marcado como inactivo",
        actor_user_id=actor.id if actor else None,
        details={"plan_id": plan.id, "soft_delete": True},
    )


async def set_plan_payment_message(
    session: AsyncSession,
    *,
    plan_id: int,
    payment_method_id: int,
    template: str,
    actor: User | None = None,
) -> PlanPaymentMessage:
    plan = await get_plan(session, plan_id)
    if plan is None:
        raise ValueError("Plan no encontrado.")
    method = await session.get(PaymentMethod, payment_method_id)
    if method is None:
        raise ValueError("Metodo de pago no encontrado.")

    message = await session.scalar(
        select(PlanPaymentMessage).where(
            PlanPaymentMessage.plan_id == plan_id,
            PlanPaymentMessage.payment_method_id == payment_method_id,
        )
    )
    if message is None:
        message = PlanPaymentMessage(
            plan_id=plan_id,
            payment_method_id=payment_method_id,
            message_template=template,
        )
        session.add(message)
    else:
        message.message_template = template

    if method not in plan.payment_methods:
        plan.payment_methods.append(method)

    await log_event(
        session,
        LogAction.PLAN_UPDATED,
        f"Mensaje de pago actualizado para {plan.name} / {method.name}",
        actor_user_id=actor.id if actor else None,
        details={"plan_id": plan_id, "payment_method_id": payment_method_id},
    )
    return message


async def link_channel_to_plan(
    session: AsyncSession,
    *,
    plan_id: int,
    channel_id: int,
    actor: User | None = None,
) -> Plan:
    plan = await get_plan(session, plan_id)
    channel = await session.get(Channel, channel_id)
    if plan is None or channel is None:
        raise ValueError("Plan o canal no encontrado.")
    if channel not in plan.channels:
        plan.channels.append(channel)
    await log_event(
        session,
        LogAction.PLAN_UPDATED,
        f"Canal vinculado a plan {plan.name}",
        actor_user_id=actor.id if actor else None,
        details={"plan_id": plan_id, "channel_id": channel_id},
    )
    return plan


async def link_group_to_plan(
    session: AsyncSession,
    *,
    plan_id: int,
    group_id: int,
    actor: User | None = None,
) -> Plan:
    plan = await get_plan(session, plan_id)
    group = await session.get(TelegramGroup, group_id)
    if plan is None or group is None:
        raise ValueError("Plan o grupo no encontrado.")
    if group not in plan.groups:
        plan.groups.append(group)
    await log_event(
        session,
        LogAction.PLAN_UPDATED,
        f"Grupo vinculado a plan {plan.name}",
        actor_user_id=actor.id if actor else None,
        details={"plan_id": plan_id, "group_id": group_id},
    )
    return plan


async def count_active_plans(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count(Plan.id)).where(Plan.is_active.is_(True))) or 0)

