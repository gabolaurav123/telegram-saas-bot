from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.models.enums import Role
from app.services.admins import get_role, permissions_for
from app.services.quick_replies import get_quick_reply_by_command
from app.services.support import bridge_admin_reply, forward_user_message_to_admins
from app.services.users import get_or_create_user

router = Router(name="support")


@router.message(F.reply_to_message)
async def admin_reply_bridge(message: Message, session: AsyncSession, settings: Settings) -> None:
    if message.from_user is None:
        return
    role = await get_role(session, message.from_user.id, settings)
    if role is None or not permissions_for(role).support:
        return
    admin_user = await get_or_create_user(session, message.from_user)
    quick_reply = None
    if message.text:
        quick_reply = await get_quick_reply_by_command(session, message.text.split()[0])
    sent = await bridge_admin_reply(
        bot=message.bot,
        session=session,
        admin_message=message,
        admin_user=admin_user,
        override_text=quick_reply.body if quick_reply else None,
    )
    if sent:
        await message.reply("Respuesta enviada al usuario.")


@router.message(F.chat.type == "private")
async def user_support_catchall(message: Message, session: AsyncSession, settings: Settings) -> None:
    if message.from_user is None:
        return
    if message.text and message.text.startswith("/"):
        return
    role = await get_role(session, message.from_user.id, settings)
    if role is not None and permissions_for(role).support:
        return
    user = await get_or_create_user(session, message.from_user)
    count = await forward_user_message_to_admins(
        bot=message.bot,
        session=session,
        settings=settings,
        user=user,
        message=message,
    )
    await message.answer(
        "Mensaje enviado a soporte." if count else "No hay administradores disponibles para soporte."
    )
