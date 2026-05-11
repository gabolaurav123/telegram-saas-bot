from __future__ import annotations

import logging
from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Chat
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.models.channel import Channel
from app.models.enums import ChatKind, LogAction
from app.models.generated_invite_link import GeneratedInviteLink
from app.models.group import TelegramGroup
from app.models.membership import Membership
from app.models.payment_request import PaymentRequest
from app.models.plan import Plan
from app.models.user import User
from app.services.logs import log_event
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


def _chat_kind(chat_type: str) -> ChatKind:
    if chat_type == "channel":
        return ChatKind.CHANNEL
    if chat_type == "group":
        return ChatKind.GROUP
    return ChatKind.SUPERGROUP


async def register_managed_chat(
    session: AsyncSession,
    *,
    chat: Chat,
    actor: User | None = None,
) -> Channel | TelegramGroup:
    kind = _chat_kind(chat.type)
    if kind == ChatKind.CHANNEL:
        item = await session.scalar(select(Channel).where(Channel.telegram_chat_id == chat.id))
        if item is None:
            item = Channel(
                telegram_chat_id=chat.id,
                title=chat.title or str(chat.id),
                username=chat.username,
                kind=ChatKind.CHANNEL,
                added_by_id=actor.id if actor else None,
            )
            session.add(item)
        else:
            item.title = chat.title or item.title
            item.username = chat.username
            item.is_active = True
    else:
        item = await session.scalar(
            select(TelegramGroup).where(TelegramGroup.telegram_chat_id == chat.id)
        )
        if item is None:
            item = TelegramGroup(
                telegram_chat_id=chat.id,
                title=chat.title or str(chat.id),
                username=chat.username,
                kind=kind,
                added_by_id=actor.id if actor else None,
            )
            session.add(item)
        else:
            item.title = chat.title or item.title
            item.username = chat.username
            item.kind = kind
            item.is_active = True

    await log_event(
        session,
        LogAction.CHAT_REGISTERED,
        f"Chat registrado: {chat.title or chat.id}",
        actor_user_id=actor.id if actor else None,
        details={"chat_id": chat.id, "type": chat.type},
    )
    await session.flush()
    return item


async def list_channels(session: AsyncSession, *, only_active: bool = False) -> list[Channel]:
    stmt = select(Channel).order_by(Channel.title)
    if only_active:
        stmt = stmt.where(Channel.is_active.is_(True))
    result = await session.scalars(stmt)
    return list(result)


async def list_groups(session: AsyncSession, *, only_active: bool = False) -> list[TelegramGroup]:
    stmt = select(TelegramGroup).order_by(TelegramGroup.title)
    if only_active:
        stmt = stmt.where(TelegramGroup.is_active.is_(True))
    result = await session.scalars(stmt)
    return list(result)


async def create_invite_links_for_plan(
    *,
    bot: Bot,
    session: AsyncSession,
    plan: Plan,
    user: User,
    membership: Membership,
    payment_request: PaymentRequest,
    approved_by: User,
    settings: Settings,
) -> list[tuple[str, str]]:
    expire_date = utc_now() + timedelta(hours=max(10, settings.approved_invite_link_ttl_hours))
    links: list[tuple[str, str]] = []

    managed_chats: list[tuple[str, int, int | None, int | None]] = [
        (channel.title, channel.telegram_chat_id, channel.id, None)
        for channel in plan.channels
        if channel.is_active
    ]
    managed_chats.extend(
        (group.title, group.telegram_chat_id, None, group.id)
        for group in plan.groups
        if group.is_active
    )

    for title, chat_id, channel_id, group_id in managed_chats:
        try:
            invite = await bot.create_chat_invite_link(
                chat_id=chat_id,
                name=f"{plan.slug}-{user.telegram_id}-{membership.id}",
                expire_date=expire_date,
                member_limit=1,
                creates_join_request=False,
            )
        except TelegramAPIError:
            logger.exception("Could not create invite link for chat %s", chat_id)
            continue
        record = GeneratedInviteLink(
            creator_user_id=approved_by.id,
            approved_by_user_id=approved_by.id,
            plan_id=plan.id,
            membership_id=membership.id,
            payment_request_id=payment_request.id,
            channel_id=channel_id,
            group_id=group_id,
            telegram_chat_id=chat_id,
            chat_title=title,
            invite_link=invite.invite_link,
            expire_at=expire_date,
        )
        session.add(record)
        links.append((title, invite.invite_link))
    await session.flush()
    return links


async def revoke_user_from_plan_chats(
    *,
    bot: Bot,
    plan: Plan,
    user_telegram_id: int,
) -> list[dict[str, object]]:
    revoked: list[dict[str, object]] = []
    managed_chats: list[tuple[str, int, int | None, int | None]] = [
        (channel.title, channel.telegram_chat_id, channel.id, None)
        for channel in plan.channels
        if channel.is_active
    ]
    managed_chats.extend(
        (group.title, group.telegram_chat_id, None, group.id)
        for group in plan.groups
        if group.is_active
    )

    for title, chat_id, channel_id, group_id in managed_chats:
        try:
            await bot.ban_chat_member(
                chat_id=chat_id,
                user_id=user_telegram_id,
                revoke_messages=False,
            )
            await bot.unban_chat_member(
                chat_id=chat_id,
                user_id=user_telegram_id,
                only_if_banned=True,
            )
            revoked.append(
                {
                    "title": title,
                    "chat_id": chat_id,
                    "channel_id": channel_id,
                    "group_id": group_id,
                    "result": "KICKED",
                }
            )
        except TelegramAPIError as exc:
            logger.exception("Could not revoke user %s from chat %s", user_telegram_id, chat_id)
            revoked.append(
                {
                    "title": title,
                    "chat_id": chat_id,
                    "channel_id": channel_id,
                    "group_id": group_id,
                    "result": "FAILED",
                    "error": str(exc),
                }
            )
    return revoked
