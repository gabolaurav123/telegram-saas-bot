from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.keyboards.admin import back_admin_keyboard
from app.models.messaging import InboxMessage
from app.models.support import SupportThread
from app.services.admins import permissions_for, require_role
from app.services.logs import log_event
from app.services.users import get_or_create_user
from app.models.enums import LogAction, Role
from app.utils.text import h
from app.utils.time import human_datetime, utc_now

router = Router(name="admin_inbox")


@router.message(Command("inbox"))
async def cmd_inbox(message: Message, session: AsyncSession, settings: Settings) -> None:
    role = await require_role(session, message.from_user.id, settings, Role.MODERATOR)
    if not permissions_for(role).support:
        await message.answer("No tienes permisos de soporte.")
        return
    text, keyboard = await _inbox_payload(session, settings)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "adm:inbox")
async def cb_inbox(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    role = await require_role(session, callback.from_user.id, settings, Role.MODERATOR)
    if not permissions_for(role).support:
        await callback.answer("Sin permisos.", show_alert=True)
        return
    text, keyboard = await _inbox_payload(session, settings)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("inbox:view:"))
async def cb_inbox_view(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    role = await require_role(session, callback.from_user.id, settings, Role.MODERATOR)
    if not permissions_for(role).support:
        await callback.answer("Sin permisos.", show_alert=True)
        return
    thread_id = int(callback.data.split(":")[-1])
    thread = await session.scalar(
        select(SupportThread)
        .options(selectinload(SupportThread.user), selectinload(SupportThread.assigned_admin))
        .where(SupportThread.id == thread_id)
    )
    if thread is None:
        await callback.answer("Ticket no encontrado.", show_alert=True)
        return
    messages = list(
        await session.scalars(
            select(InboxMessage)
            .where(InboxMessage.support_thread_id == thread.id)
            .order_by(desc(InboxMessage.created_at))
            .limit(8)
        )
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="Asignarme", callback_data=f"inbox:assign:{thread.id}")
    builder.button(text="Resolver", callback_data=f"inbox:resolve:{thread.id}")
    builder.button(text="Volver", callback_data="adm:inbox")
    builder.adjust(2, 1)
    lines = [
        "<b>Inbox thread</b>",
        "",
        f"Usuario: <b>{h(thread.user.display_name)}</b>",
        f"Telegram ID: <code>{thread.user.telegram_id}</code>",
        f"Estado: <b>{h(thread.status)}</b>",
        f"Asignado: {h(thread.assigned_admin.display_name) if thread.assigned_admin else '-'}",
        f"Ultimo mensaje: {human_datetime(thread.last_message_at, settings.app_timezone)}",
        "",
        "<b>Mensajes recientes</b>",
    ]
    for item in reversed(messages):
        preview = item.text or item.content_type
        lines.append(f"{h(item.direction)} | {h(preview[:160])}")
    await callback.message.edit_text("\n".join(lines), reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("inbox:assign:"))
async def cb_inbox_assign(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    role = await require_role(session, callback.from_user.id, settings, Role.MODERATOR)
    if not permissions_for(role).support:
        await callback.answer("Sin permisos.", show_alert=True)
        return
    thread = await session.get(SupportThread, int(callback.data.split(":")[-1]))
    if thread is None:
        await callback.answer("Ticket no encontrado.", show_alert=True)
        return
    actor = await get_or_create_user(session, callback.from_user)
    thread.assigned_admin_user_id = actor.id
    await log_event(
        session,
        LogAction.INBOX_ASSIGNED,
        f"Inbox asignado: {thread.id}",
        actor_user_id=actor.id,
        target_user_id=thread.user_id,
        details={"thread_id": thread.id},
    )
    await cb_inbox_view(callback, session, settings)


@router.callback_query(F.data.startswith("inbox:resolve:"))
async def cb_inbox_resolve(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    role = await require_role(session, callback.from_user.id, settings, Role.MODERATOR)
    if not permissions_for(role).support:
        await callback.answer("Sin permisos.", show_alert=True)
        return
    thread = await session.get(SupportThread, int(callback.data.split(":")[-1]))
    if thread is None:
        await callback.answer("Ticket no encontrado.", show_alert=True)
        return
    actor = await get_or_create_user(session, callback.from_user)
    thread.status = "RESOLVED"
    thread.resolved_at = utc_now()
    thread.assigned_admin_user_id = actor.id
    await log_event(
        session,
        LogAction.INBOX_RESOLVED,
        f"Inbox resuelto: {thread.id}",
        actor_user_id=actor.id,
        target_user_id=thread.user_id,
        details={"thread_id": thread.id},
    )
    await cb_inbox(callback, session, settings)


async def _inbox_payload(session: AsyncSession, settings: Settings):
    threads = list(
        await session.scalars(
            select(SupportThread)
            .options(selectinload(SupportThread.user), selectinload(SupportThread.assigned_admin))
            .order_by(desc(SupportThread.last_message_at), desc(SupportThread.created_at))
            .limit(12)
        )
    )
    builder = InlineKeyboardBuilder()
    lines = ["<b>Admin inbox</b>", ""]
    if not threads:
        lines.append("Sin mensajes de soporte.")
    for thread in threads:
        label = f"{thread.status} #{thread.id} {thread.user.display_name}"
        builder.button(text=label[:64], callback_data=f"inbox:view:{thread.id}")
        lines.append(
            f"#{thread.id} | {h(thread.status)} | {h(thread.user.display_name)} | "
            f"no leidos admin: {thread.unread_admin_count}"
        )
    builder.button(text="Volver", callback_data="adm:menu")
    builder.adjust(1)
    return "\n".join(lines), builder.as_markup() if threads else back_admin_keyboard()
