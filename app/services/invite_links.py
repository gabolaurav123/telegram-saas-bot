from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.models.channel import Channel
from app.models.access_event import MembershipAccessEvent
from app.models.enums import AccessEventKind, LogAction
from app.models.generated_invite_link import GeneratedInviteLink
from app.models.group import TelegramGroup
from app.models.plan import Plan
from app.models.user import User
from app.services.logs import log_event
from app.services.notifications import send_admin_log
from app.utils.text import h
from app.services.plans import get_plan
from app.utils.time import human_datetime
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
    await session.flush()

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
        record.revoked_reason = "admin_revoke"
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


async def confirm_invite_join(
    *,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    invite_link: str,
    user: User,
    chat_title: str,
    telegram_chat_id: int,
) -> GeneratedInviteLink | None:
    record = await session.scalar(
        select(GeneratedInviteLink)
        .options(
            selectinload(GeneratedInviteLink.plan),
            selectinload(GeneratedInviteLink.membership),
            selectinload(GeneratedInviteLink.approved_by),
        )
        .where(GeneratedInviteLink.invite_link == invite_link)
    )
    now = utc_now()
    if record is None:
        await log_event(
            session,
            LogAction.USER_JOINED_CHAT,
            f"Join detectado con link no registrado: {telegram_chat_id}",
            target_user_id=user.id,
            details={"invite_link": invite_link, "chat_id": telegram_chat_id, "chat_title": chat_title},
        )
        return None
    if record.join_confirmed:
        await log_event(
            session,
            LogAction.USER_JOINED_CHAT,
            f"Join duplicado ignorado para link {record.id}",
            target_user_id=user.id,
            details={"link_id": record.id, "already_confirmed": True},
        )
        return record

    record.is_used = True
    record.used_by_user_id = user.id
    record.used_at = now
    record.joined_at = now
    record.join_confirmed = True
    event = MembershipAccessEvent(
        user_id=user.id,
        membership_id=record.membership_id,
        plan_id=record.plan_id,
        generated_invite_link_id=record.id,
        event_kind=AccessEventKind.JOIN,
        telegram_chat_id=telegram_chat_id,
        chat_title=chat_title or record.chat_title,
        channel_id=record.channel_id,
        group_id=record.group_id,
        approved_by_user_id=record.approved_by_user_id,
        join_confirmed=True,
        event_at=now,
        metadata_json={"invite_link_id": record.id},
    )
    session.add(event)

    try:
        await bot.revoke_chat_invite_link(record.telegram_chat_id, record.invite_link)
        record.revoked_at = now
        record.revoked_reason = "joined"
    except TelegramAPIError as exc:
        await log_event(
            session,
            LogAction.ERROR,
            f"No se pudo revocar invite link tras join: {record.id}",
            target_user_id=user.id,
            severity="ERROR",
            details={"link_id": record.id, "error": str(exc)},
        )

    await log_event(
        session,
        LogAction.USER_JOINED_CHAT,
        f"Usuario unido correctamente: {user.telegram_id}",
        target_user_id=user.id,
        details={"link_id": record.id, "plan_id": record.plan_id, "chat_id": telegram_chat_id},
    )
    await send_admin_log(
        bot=bot,
        session=session,
        settings=settings,
        title="✅ Usuario unido correctamente",
        lines=[
            f"👤 Nombre: {h(user.display_name)}",
            f"🔗 Username: {h('@' + user.username)}" if user.username else "🔗 Username: -",
            f"🆔 ID: <code>{user.telegram_id}</code>",
            f"📦 Plan: {h(record.plan.name if record.plan else '-')}",
            f"📍 Canal: {h(chat_title or record.chat_title)}",
            f"🔗 Invite ID: INV-{record.id}",
            f"🕒 Fecha ingreso: {human_datetime(now, settings.app_timezone)}",
        ],
    )
    return record


async def reissue_expired_link(
    *,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    link_id: int,
    actor: User | None,
) -> GeneratedInviteLink:
    old = await session.scalar(
        select(GeneratedInviteLink)
        .options(selectinload(GeneratedInviteLink.plan))
        .where(GeneratedInviteLink.id == link_id)
    )
    if old is None:
        raise ValueError("Link no encontrado.")
    if old.join_confirmed:
        raise ValueError("El usuario ya uso este link.")
    expire_at = utc_now() + timedelta(hours=max(10, settings.approved_invite_link_ttl_hours))
    if old.revoked_at is None:
        try:
            await bot.revoke_chat_invite_link(old.telegram_chat_id, old.invite_link)
        except TelegramAPIError:
            pass
    invite = await bot.create_chat_invite_link(
        chat_id=old.telegram_chat_id,
        name=f"reissue-{old.id}-{old.reissue_count + 1}",
        expire_date=expire_at,
        member_limit=1,
        creates_join_request=False,
    )
    old.last_reissued_at = utc_now()
    old.reissue_count += 1
    old.revoked_at = utc_now()
    old.revoked_reason = "reissued"
    new = GeneratedInviteLink(
        creator_user_id=actor.id if actor else old.creator_user_id,
        approved_by_user_id=old.approved_by_user_id,
        plan_id=old.plan_id,
        membership_id=old.membership_id,
        payment_request_id=old.payment_request_id,
        channel_id=old.channel_id,
        group_id=old.group_id,
        telegram_chat_id=old.telegram_chat_id,
        chat_title=old.chat_title,
        invite_link=invite.invite_link,
        expire_at=expire_at,
        metadata_json={"reissued_from": old.id},
    )
    session.add(new)
    await session.flush()
    await log_event(
        session,
        LogAction.INVITE_LINK_REISSUED,
        f"Invite link reemitido: {old.id}",
        actor_user_id=actor.id if actor else None,
        details={"old_link_id": old.id, "new_link_id": new.id},
    )
    return new


async def link_stats(session: AsyncSession) -> dict[str, int]:
    total = await session.scalar(select(func.count(GeneratedInviteLink.id)))
    used = await session.scalar(select(func.count(GeneratedInviteLink.id)).where(GeneratedInviteLink.is_used.is_(True)))
    revoked = await session.scalar(select(func.count(GeneratedInviteLink.id)).where(GeneratedInviteLink.revoked_at.is_not(None)))
    joined = await session.scalar(
        select(func.count(GeneratedInviteLink.id)).where(GeneratedInviteLink.join_confirmed.is_(True))
    )
    expired_unused = await session.scalar(
        select(func.count(GeneratedInviteLink.id)).where(
            GeneratedInviteLink.join_confirmed.is_(False),
            GeneratedInviteLink.expire_at <= utc_now(),
        )
    )
    active = await session.scalar(
        select(func.count(GeneratedInviteLink.id)).where(
            GeneratedInviteLink.is_used.is_(False),
            GeneratedInviteLink.revoked_at.is_(None),
            GeneratedInviteLink.expire_at > utc_now(),
        )
    )
    return {
        "total": int(total or 0),
        "active": int(active or 0),
        "used": int(used or 0),
        "revoked": int(revoked or 0),
        "joined": int(joined or 0),
        "expired_unused": int(expired_unused or 0),
    }
