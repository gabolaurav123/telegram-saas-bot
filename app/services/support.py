from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.models.enums import LogAction
from app.models.messaging import InboxMessage
from app.models.support import SupportReplyMap, SupportThread
from app.models.user import User
from app.services.logs import log_event
from app.services.messaging import MessagingService
from app.services.notifications import admin_chat_ids
from app.utils.text import h
from app.utils.time import utc_now


async def forward_user_message_to_admins(
    *,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    user: User,
    message: Message,
) -> int:
    thread = await session.scalar(select(SupportThread).where(SupportThread.user_id == user.id))
    if thread is None:
        thread = SupportThread(
            user_id=user.id,
            status="OPEN",
            unread_admin_count=1,
            last_message_at=utc_now(),
        )
        session.add(thread)
        await session.flush()
    else:
        thread.status = "OPEN"
        thread.last_message_at = utc_now()
        thread.unread_admin_count += 1

    session.add(
        InboxMessage(
            support_thread_id=thread.id,
            user_id=user.id,
            direction="USER_TO_ADMIN",
            telegram_chat_id=message.chat.id,
            telegram_message_id=message.message_id,
            content_type=message.content_type,
            text=message.text or message.caption,
            file_id=_message_file_id(message),
            sent_at=utc_now(),
        )
    )

    text_preview = message.text or message.caption or message.content_type
    header = (
        "<b>Nuevo mensaje de usuario</b>\n\n"
        f"Nombre: {h(user.display_name)}\n"
        f"ID: <code>{user.telegram_id}</code>\n\n"
        f"Mensaje:\n{h(text_preview)}"
    )
    sent_count = 0
    for chat_id in await admin_chat_ids(session, settings):
        try:
            header_message = await bot.send_message(chat_id, header)
            copied = await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
        except TelegramAPIError:
            continue
        for admin_message_id in [header_message.message_id, copied.message_id]:
            session.add(
                SupportReplyMap(
                    thread_id=thread.id,
                    user_id=user.id,
                    admin_chat_id=chat_id,
                    admin_message_id=admin_message_id,
                    user_message_id=message.message_id,
                )
            )
        sent_count += 1

    await log_event(
        session,
        LogAction.SUPPORT_MESSAGE,
        f"Mensaje de soporte reenviado a {sent_count} admins",
        target_user_id=user.id,
        details={"thread_id": thread.id, "message_id": message.message_id},
    )
    return sent_count


async def bridge_admin_reply(
    *,
    bot: Bot,
    session: AsyncSession,
    admin_message: Message,
    admin_user: User,
    override_text: str | None = None,
) -> bool:
    if not admin_message.reply_to_message:
        return False
    mapping = await session.scalar(
        select(SupportReplyMap)
        .options(selectinload(SupportReplyMap.user))
        .where(
            SupportReplyMap.admin_chat_id == admin_message.chat.id,
            SupportReplyMap.admin_message_id == admin_message.reply_to_message.message_id,
        )
    )
    if mapping is None:
        return False
    if override_text:
        outbound = await MessagingService(session).send_text_to_user(
            bot=bot,
            target=mapping.user,
            text=override_text,
            actor=admin_user,
            source="SUPPORT_QUICK_REPLY",
            metadata={"thread_id": mapping.thread_id},
        )
    else:
        outbound = await MessagingService(session).copy_admin_reply_to_user(
            bot=bot,
            admin_message=admin_message,
            target=mapping.user,
            actor=admin_user,
            source="SUPPORT_REPLY",
            metadata={"thread_id": mapping.thread_id},
        )
    thread = await session.get(SupportThread, mapping.thread_id)
    if thread:
        thread.assigned_admin_user_id = admin_user.id
        thread.unread_admin_count = 0
        thread.unread_user_count += 1
        thread.last_message_at = utc_now()
    session.add(
        InboxMessage(
            support_thread_id=mapping.thread_id,
            user_id=mapping.user_id,
            admin_user_id=admin_user.id,
            direction="ADMIN_TO_USER",
            telegram_chat_id=admin_message.chat.id,
            telegram_message_id=admin_message.message_id,
            content_type="text" if override_text else admin_message.content_type,
            text=override_text or admin_message.text or admin_message.caption,
            file_id=None if override_text else _message_file_id(admin_message),
            sent_at=utc_now(),
            metadata_json={"outbound_message_id": outbound.id},
        )
    )
    await log_event(
        session,
        LogAction.SUPPORT_REPLY,
        "Respuesta privada enviada a usuario",
        actor_user_id=admin_user.id,
        target_user_id=mapping.user_id,
        details={"thread_id": mapping.thread_id},
    )
    return True


def _message_file_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id
    if message.document:
        return message.document.file_id
    if message.video:
        return message.video.file_id
    if message.sticker:
        return message.sticker.file_id
    if message.voice:
        return message.voice.file_id
    if message.audio:
        return message.audio.file_id
    if message.video_note:
        return message.video_note.file_id
    return None
