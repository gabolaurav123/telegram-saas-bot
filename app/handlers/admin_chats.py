from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.keyboards.admin import chats_admin_keyboard
from app.models.access_event import MembershipAccessEvent
from app.models.channel import Channel
from app.models.enums import AccessEventKind, ChatKind, LogAction, Role
from app.models.group import TelegramGroup
from app.services.admins import require_role
from app.services.channels import list_channels, list_groups, register_managed_chat
from app.services.invite_links import confirm_invite_join
from app.services.logs import log_event
from app.services.notifications import send_admin_log
from app.services.users import get_or_create_user
from app.states.admin import AdminChatStates
from app.utils.text import h
from app.utils.validators import parse_telegram_id

router = Router(name="admin_chats")


@router.my_chat_member()
async def on_bot_chat_member_update(
    event: ChatMemberUpdated,
    session: AsyncSession,
) -> None:
    if event.chat.type not in {"channel", "group", "supergroup"}:
        return
    if event.new_chat_member.status in {"left", "kicked"}:
        return
    await register_managed_chat(session, chat=event.chat)


@router.chat_member()
async def on_user_chat_member_update(
    event: ChatMemberUpdated,
    session: AsyncSession,
    settings: Settings,
) -> None:
    user = event.new_chat_member.user
    db_user = await get_or_create_user(session, user)
    if event.invite_link and event.new_chat_member.status in {"member", "administrator", "creator"}:
        await confirm_invite_join(
            bot=event.bot,
            session=session,
            settings=settings,
            invite_link=event.invite_link.invite_link,
            user=db_user,
            chat_title=event.chat.title or str(event.chat.id),
            telegram_chat_id=event.chat.id,
        )
        return

    if event.old_chat_member.status in {"member", "administrator", "creator"} and event.new_chat_member.status in {
        "left",
        "kicked",
    }:
        access_event = MembershipAccessEvent(
            user_id=db_user.id,
            event_kind=AccessEventKind.LEAVE,
            telegram_chat_id=event.chat.id,
            chat_title=event.chat.title or str(event.chat.id),
            join_confirmed=False,
            event_at=event.date,
            kick_result=event.new_chat_member.status,
        )
        session.add(access_event)
        await log_event(
            session,
            LogAction.USER_LEFT_CHAT,
            f"Usuario salio de chat: {db_user.telegram_id}",
            target_user_id=db_user.id,
            details={"chat_id": event.chat.id, "status": event.new_chat_member.status},
        )
        await send_admin_log(
            bot=event.bot,
            session=session,
            settings=settings,
            title="Usuario salio de canal/grupo",
            lines=[
                f"Nombre: {h(db_user.display_name)}",
                f"ID: <code>{db_user.telegram_id}</code>",
                f"Canal/grupo: {h(str(event.chat.title or event.chat.id))}",
                f"Estado: {event.new_chat_member.status}",
            ],
        )


@router.message(F.text == "/register_chat")
async def cmd_register_chat(message: Message, session: AsyncSession, settings: Settings) -> None:
    if message.chat.type not in {"channel", "group", "supergroup"}:
        await message.answer("Este comando solo funciona en canales o grupos.")
        return
    if message.from_user:
        await require_role(session, message.from_user.id, settings, Role.ADMIN)
        actor = await get_or_create_user(session, message.from_user)
    else:
        actor = None
    item = await register_managed_chat(session, chat=message.chat, actor=actor)
    await message.answer(f"Chat registrado: <b>{h(item.title)}</b>")


@router.callback_query(F.data == "adm:chats")
async def cb_admin_chats(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    channels = await list_channels(session)
    groups = await list_groups(session)
    await callback.message.edit_text(
        "<b>Canales y grupos</b>\n\n"
        "El bot detecta automaticamente los chats cuando lo agregas como admin. "
        "Tambien puedes registrarlos manualmente.",
        reply_markup=chats_admin_keyboard(channels, groups),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:chats:create")
async def cb_create_chat(callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    await state.set_state(AdminChatStates.waiting_manual_chat)
    await callback.message.answer(
        "<b>Registrar chat manual</b>\n\n"
        "Formato:\n"
        "<code>channel | -1001234567890 | Nombre del canal | username_opcional</code>\n"
        "<code>group | -1001234567890 | Nombre del grupo | username_opcional</code>\n\n"
        "El bot debe ser admin del canal/grupo para crear links y expulsar usuarios."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:chats:toggle:"))
async def cb_toggle_managed_chat(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    _, _, _, kind, db_id_raw = callback.data.split(":")
    model = Channel if kind == "channel" else TelegramGroup if kind == "group" else None
    if model is None:
        await callback.answer("Tipo de chat invalido.", show_alert=True)
        return
    item = await session.get(model, int(db_id_raw))
    if item is None:
        await callback.answer("Chat no encontrado.", show_alert=True)
        return
    item.is_active = not item.is_active
    actor = await get_or_create_user(session, callback.from_user)
    await log_event(
        session,
        LogAction.CHAT_UPDATED,
        f"Chat {item.title} {'activado' if item.is_active else 'desactivado'}",
        actor_user_id=actor.id,
        details={"kind": kind, "db_id": item.id, "telegram_chat_id": item.telegram_chat_id},
    )
    channels = await list_channels(session)
    groups = await list_groups(session)
    await callback.message.edit_reply_markup(reply_markup=chats_admin_keyboard(channels, groups))
    await callback.answer("Estado actualizado.")


@router.message(AdminChatStates.waiting_manual_chat)
async def receive_manual_chat(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    actor = await get_or_create_user(session, message.from_user)
    parts = [part.strip() for part in (message.text or "").split("|")]
    if len(parts) < 3:
        await message.answer("Formato invalido.")
        return
    chat_type = parts[0].lower()
    chat_id = parse_telegram_id(parts[1])
    title = parts[2]
    username = parts[3].lstrip("@") if len(parts) > 3 and parts[3] else None

    if chat_type == "channel":
        item = await session.scalar(select(Channel).where(Channel.telegram_chat_id == chat_id))
        if item is None:
            item = Channel(
                telegram_chat_id=chat_id,
                title=title,
                username=username,
                kind=ChatKind.CHANNEL,
                added_by_id=actor.id,
            )
            session.add(item)
        else:
            item.title = title
            item.username = username
            item.is_active = True
    elif chat_type in {"group", "supergroup"}:
        item = await session.scalar(select(TelegramGroup).where(TelegramGroup.telegram_chat_id == chat_id))
        if item is None:
            item = TelegramGroup(
                telegram_chat_id=chat_id,
                title=title,
                username=username,
                kind=ChatKind.SUPERGROUP if chat_type == "supergroup" else ChatKind.GROUP,
                added_by_id=actor.id,
            )
            session.add(item)
        else:
            item.title = title
            item.username = username
            item.is_active = True
    else:
        await message.answer("Tipo invalido. Usa channel, group o supergroup.")
        return

    await log_event(
        session,
        LogAction.CHAT_REGISTERED,
        f"Chat manual registrado: {title}",
        actor_user_id=actor.id,
        details={"chat_id": chat_id, "type": chat_type},
    )
    await state.clear()
    await message.answer(f"Chat registrado: <b>{h(title)}</b>")
