from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.keyboards.admin import quick_replies_keyboard
from app.models.enums import Role
from app.services.admins import require_role
from app.services.quick_replies import create_quick_reply, list_quick_replies
from app.services.users import get_or_create_user
from app.states.admin import QuickReplyStates

router = Router(name="admin_quick_replies")


@router.message(Command("quickreplies"))
async def cmd_quick_replies(message: Message, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.MODERATOR)
    replies = await list_quick_replies(session, only_active=False)
    await message.answer(_quick_reply_text(), reply_markup=quick_replies_keyboard(replies))


@router.callback_query(F.data == "adm:quickreplies")
async def cb_quick_replies(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.MODERATOR)
    replies = await list_quick_replies(session, only_active=False)
    await callback.message.edit_text(_quick_reply_text(), reply_markup=quick_replies_keyboard(replies))
    await callback.answer()


@router.callback_query(F.data == "qr:create")
async def cb_create_quick_reply(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    await state.set_state(QuickReplyStates.waiting_payload)
    await callback.message.answer(
        "<b>Crear respuesta rapida</b>\n\n"
        "Formato:\n"
        "<code>/comando | Titulo | Mensaje que recibira el usuario</code>"
    )
    await callback.answer()


@router.message(QuickReplyStates.waiting_payload)
async def receive_quick_reply_payload(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    parts = [part.strip() for part in (message.text or "").split("|", 2)]
    if len(parts) != 3:
        await message.answer("Formato invalido. Usa: /comando | Titulo | Mensaje")
        return
    actor = await get_or_create_user(session, message.from_user)
    try:
        await create_quick_reply(
            session,
            command=parts[0],
            title=parts[1],
            body=parts[2],
            actor=actor,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.clear()
    replies = await list_quick_replies(session, only_active=False)
    await message.answer("Respuesta rapida creada.", reply_markup=quick_replies_keyboard(replies))


def _quick_reply_text() -> str:
    return (
        "<b>Quick replies</b>\n\n"
        "Para responder desde soporte, responde al mensaje puente del usuario escribiendo "
        "el comando de una respuesta rapida activa."
    )
