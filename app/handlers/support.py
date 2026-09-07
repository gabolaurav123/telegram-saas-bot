from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.filters.support_reply import SupportReplyTargetFilter
from app.models.enums import DeliveryStatus
from app.services.admins import get_role, permissions_for
from app.services.quick_replies import get_quick_reply_by_command
from app.services.support import bridge_admin_reply, forward_user_message_to_admins
from app.services.users import get_or_create_user

reply_router = Router(name="support_replies")
router = Router(name="support")


@reply_router.message(SupportReplyTargetFilter())
async def admin_reply_bridge(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    role = await get_role(session, message.from_user.id, settings)
    if role is None or not permissions_for(role).support:
        await message.reply("No tienes permisos para responder conversaciones de soporte.")
        return
    admin_user = await get_or_create_user(session, message.from_user)
    quick_reply = None
    if message.text and message.text.startswith("/"):
        quick_reply = await get_quick_reply_by_command(session, message.text.split()[0])
    outbound = await bridge_admin_reply(
        bot=message.bot,
        session=session,
        admin_message=message,
        admin_user=admin_user,
        override_text=quick_reply.body if quick_reply else None,
    )
    if outbound is None:
        await message.reply("No se encontro el usuario asociado a este mensaje.")
        return

    # A support reply is intentional and takes precedence over an abandoned admin form.
    await state.clear()
    if outbound.status == DeliveryStatus.SENT:
        await message.reply("Respuesta enviada al usuario.")
    elif outbound.status == DeliveryStatus.BLOCKED:
        await message.reply("No se pudo responder: el usuario bloqueo o detuvo el bot.")
    else:
        await message.reply("No se pudo enviar la respuesta. Revisa los logs e intenta nuevamente.")


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
