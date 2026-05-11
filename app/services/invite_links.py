from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from aiogram import Bot
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.models.channel import Channel
from app.models.enums import LogAction
from app.models.generated_invite_link import GeneratedInviteLink
from app.models.group import TelegramGroup
from app.models.plan import Plan
from app.models.user import User
from app.services.logs import log_event
from app.services.plans import get_plan
from app.utils.time import utc_now


@dataclass(frozen=True)
class PlanChatOption:
    kind: str
    db_id: int
    telegram_chat_id: int
    title: str


async def chat_options_for_plan(session: AsyncSession, plan_id: int) -> list[PlanChatOption]:
    plan = await get_plan(session, plan_id)
    if plan is None:
        return []
    options = [
        PlanChatOption("channel", channel.id, channel.telegram_chat_id, channel.title)
        for channel in plan.channels
        if channel.is_active
    ]
    options.extend(
        PlanChatOption("group", group.id, group.telegram_chat_id, group.title)
        for group in plan.groups
        if group.is_active
    )
    return options


async def generate_links(
    *,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    creator: User,
    plan_id: int,
    chat_kind: str,
    chat_db_id: int,
    amount: int,
) -> list[GeneratedInviteLink]:
    if amount < 1 or amount > settings.max_invite_links_per_batch:
        raise ValueError(f"La cantidad debe estar entre 1 y {settings.max_invite_links_per_batch}.")
    plan = await get_plan(session, plan_id)
    if plan is None:
        raise ValueError("Plan no encontrado.")

    chat: Channel | TelegramGroup | None
    if chat_kind == "channel":
        chat = await session.get(Channel, chat_db_id)
        channel_id, group_id = chat_db_id, None
    elif chat_kind == "group":
        chat = await session.get(TelegramGroup, chat_db_id)
        channel_id, group_id = None, chat_db_id
    else:
        raise ValueError("Tipo de chat invalido.")
    if chat is None:
        raise ValueError("Canal o grupo no encontrado.")

    expire_at = utc_now() + timedelta(days=plan.duration_days)
    created: list[GeneratedInviteLink] = []
    for index in range(amount):
        invite = await bot.create_chat_invite_link(
            chat_id=chat.telegram_chat_id,
            name=f"{plan.slug}-{creator.telegram_id}-{index + 1}",
            expire_date=expire_at,
            member_limit=1,
            creates_join_request=False,
        )
        record = GeneratedInviteLink(
            creator_user_id=creator.id,
            plan_id=plan.id,
            channel_id=channel_id,
            group_id=group_id,
            telegram_chat_id=chat.telegram_chat_id,
            chat_title=chat.title,
            invite_link=invite.invite_link,
            expire_at=expire_at,
        )
        session.add(record)
        created.append(record)

    await log_event(
        session,
        LogAction.INVITE_LINK_CREATED,
        f"{amount} links generados para {plan.name} / {chat.title}",
        actor_user_id=creator.id,
        details={"plan_id": plan.id, "chat_id": chat.telegram_chat_id, "amount": amount},
    )
    return created


async def list_recent_links(session: AsyncSession, limit: int = 20) -> list[GeneratedInviteLink]:
    result = await session.scalars(
        select(GeneratedInviteLink)
        .options(selectinload(GeneratedInviteLink.plan))
        .order_by(GeneratedInviteLink.created_at.desc())
        .limit(limit)
    )
    return list(result)


async def revoke_link(
    *,
    bot: Bot,
    session: AsyncSession,
    link_id: int,
    actor: User,
) -> GeneratedInviteLink:
    record = await session.get(GeneratedInviteLink, link_id)
    if record is None:
        raise ValueError("Link no encontrado.")
    if record.revoked_at is None:
        await bot.revoke_chat_invite_link(record.telegram_chat_id, record.invite_link)
        record.revoked_at = utc_now()
        await log_event(
            session,
            LogAction.INVITE_LINK_REVOKED,
            f"Invite link revocado: {record.id}",
            actor_user_id=actor.id,
            details={"link_id": record.id, "chat_id": record.telegram_chat_id},
        )
    return record


async def mark_invite_used(
    session: AsyncSession,
    *,
    invite_link: str,
    user: User,
) -> GeneratedInviteLink | None:
    record = await session.scalar(
        select(GeneratedInviteLink).where(GeneratedInviteLink.invite_link == invite_link)
    )
    if record is None:
        return None
    record.is_used = True
    record.used_by_user_id = user.id
    record.used_at = utc_now()
    await log_event(
        session,
        LogAction.INVITE_LINK_USED,
        f"Invite link usado: {record.id}",
        target_user_id=user.id,
        details={"link_id": record.id},
    )
    return record


async def link_stats(session: AsyncSession) -> dict[str, int]:
    total = await session.scalar(select(func.count(GeneratedInviteLink.id)))
    used = await session.scalar(select(func.count(GeneratedInviteLink.id)).where(GeneratedInviteLink.is_used.is_(True)))
    revoked = await session.scalar(select(func.count(GeneratedInviteLink.id)).where(GeneratedInviteLink.revoked_at.is_not(None)))
    active = await session.scalar(
        select(func.count(GeneratedInviteLink.id)).where(
            GeneratedInviteLink.is_used.is_(False),
            GeneratedInviteLink.revoked_at.is_(None),
            GeneratedInviteLink.expire_at > utc_now(),
        )
    )
    return {"total": int(total or 0), "active": int(active or 0), "used": int(used or 0), "revoked": int(revoked or 0)}

