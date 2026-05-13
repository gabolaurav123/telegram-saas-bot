from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import Channel
from app.models.group import TelegramGroup


@dataclass(frozen=True)
class ChatPermissionHealth:
    kind: str
    db_id: int
    telegram_chat_id: int
    title: str
    status: str
    can_invite_users: bool | None
    can_restrict_members: bool | None
    can_post_messages: bool | None
    error: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.status in {"administrator", "creator"}

    @property
    def invite_links_ok(self) -> bool:
        return self.is_admin and self.can_invite_users is True

    @property
    def kicks_ok(self) -> bool:
        return self.is_admin and self.can_restrict_members is True

    @property
    def messages_ok(self) -> bool:
        if self.kind == "channel":
            return self.is_admin and self.can_post_messages is True
        return self.is_admin

    @property
    def operational_ok(self) -> bool:
        return self.invite_links_ok and self.kicks_ok and self.messages_ok


async def audit_managed_chat_permissions(
    *,
    bot: Bot,
    session: AsyncSession,
    bot_id: int,
) -> list[ChatPermissionHealth]:
    channels = list(
        await session.scalars(
            select(Channel).where(Channel.is_active.is_(True)).order_by(Channel.id)
        )
    )
    groups = list(
        await session.scalars(
            select(TelegramGroup).where(TelegramGroup.is_active.is_(True)).order_by(TelegramGroup.id)
        )
    )
    results: list[ChatPermissionHealth] = []
    for kind, chat in [("channel", item) for item in channels] + [
        ("group", item) for item in groups
    ]:
        try:
            member = await bot.get_chat_member(chat.telegram_chat_id, bot_id)
        except TelegramAPIError as exc:
            results.append(
                ChatPermissionHealth(
                    kind=kind,
                    db_id=chat.id,
                    telegram_chat_id=chat.telegram_chat_id,
                    title=chat.title,
                    status="ERROR",
                    can_invite_users=None,
                    can_restrict_members=None,
                    can_post_messages=None,
                    error=str(exc),
                )
            )
            continue
        results.append(
            ChatPermissionHealth(
                kind=kind,
                db_id=chat.id,
                telegram_chat_id=chat.telegram_chat_id,
                title=chat.title,
                status=str(member.status),
                can_invite_users=getattr(member, "can_invite_users", None),
                can_restrict_members=getattr(member, "can_restrict_members", None),
                can_post_messages=getattr(member, "can_post_messages", None),
            )
        )
    return results
