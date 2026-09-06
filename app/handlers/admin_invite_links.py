from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.keyboards.admin import (
    addmember_chat_keyboard,
    generated_links_keyboard,
    plan_select_keyboard,
)
from app.models.enums import Role
from app.services.admins import require_role
from app.services.invite_links import (
    chat_options_for_plan,
    generate_links,
    link_stats,
    list_recent_links,
    reissue_expired_link,
    revoke_link,
)
from app.services.plans import get_plan, list_plans
from app.services.users import get_or_create_user
from app.states.admin import AddMemberStates
from app.utils.text import h
from app.utils.time import human_datetime
from app.utils.validators import parse_positive_int

router = Router(name="admin_invite_links")


@router.message(Command("addmember"))
async def cmd_addmember(message: Message, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    plans = await list_plans(session, only_active=True)
    await message.answer(
        "<b>Generar invite links</b>\n\nSelecciona el plan:",
        reply_markup=plan_select_keyboard(plans, "addm:plan"),
    )


@router.callback_query(F.data == "adm:links")
async def cb_links_panel(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    stats = await link_stats(session)
    builder = InlineKeyboardBuilder()
    builder.button(text="Generar links", callback_data="links:add")
    builder.button(text="Listar links", callback_data="links:list")
    builder.button(text="Estadisticas", callback_data="links:stats")
    builder.button(text="Volver", callback_data="adm:menu")
    builder.adjust(1)
    await callback.message.edit_text(
        "<b>Invite links</b>\n\n"
        f"Total: <b>{stats['total']}</b>\n"
        f"Activos: <b>{stats['active']}</b>\n"
        f"Usados: <b>{stats['used']}</b>\n"
        f"Joins confirmados: <b>{stats['joined']}</b>\n"
        f"Expirados sin join: <b>{stats['expired_unused']}</b>\n"
        f"Revocados: <b>{stats['revoked']}</b>",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "links:add")
async def cb_links_add(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    plans = await list_plans(session, only_active=True)
    await callback.message.edit_text(
        "<b>Generar invite links</b>\n\nSelecciona el plan:",
        reply_markup=plan_select_keyboard(plans, "addm:plan"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("addm:plan:"))
async def cb_addmember_plan(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    plan_id = int(callback.data.split(":")[-1])
    plan = await get_plan(session, plan_id)
    if plan is None:
        await callback.answer("Plan no encontrado.", show_alert=True)
        return
    await callback.message.edit_text(
        f"<b>{h(plan.name)}</b>\n\nSelecciona canal o grupo asociado:",
        reply_markup=addmember_chat_keyboard(plan.id, plan.channels, plan.groups),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("addm:chat:"))
async def cb_addmember_chat(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    _, _, chat_kind, plan_id, chat_db_id = callback.data.split(":")
    options = await chat_options_for_plan(session, int(plan_id))
    if not any(option.kind == chat_kind and option.db_id == int(chat_db_id) for option in options):
        await callback.answer("Ese chat no esta asociado al plan.", show_alert=True)
        return
    await state.set_state(AddMemberStates.waiting_amount)
    await state.update_data(plan_id=int(plan_id), chat_kind=chat_kind, chat_db_id=int(chat_db_id))
    await callback.message.answer(
        f"Cantidad de links a generar. Maximo: <b>{settings.max_invite_links_per_batch}</b>"
    )
    await callback.answer()


@router.message(AddMemberStates.waiting_amount)
async def receive_addmember_amount(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    actor = await get_or_create_user(session, message.from_user)
    data = await state.get_data()
    amount = parse_positive_int(message.text or "", "cantidad")
    links = await generate_links(
        bot=message.bot,
        session=session,
        settings=settings,
        creator=actor,
        plan_id=int(data["plan_id"]),
        chat_kind=str(data["chat_kind"]),
        chat_db_id=int(data["chat_db_id"]),
        amount=amount,
    )
    await state.clear()
    lines = [f"#{link.id}: {link.invite_link}" for link in links]
    await message.answer(
        "<b>Links generados</b>\n\n"
        f"Expiran: {human_datetime(links[0].expire_at, settings.app_timezone)}\n\n"
        + "\n".join(lines),
        disable_web_page_preview=True,
    )


@router.message(Command("listlinks"))
@router.callback_query(F.data == "links:list")
async def list_links(event: Message | CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, event.from_user.id, settings, Role.ADMIN)
    links = await list_recent_links(session, limit=20)
    if not links:
        text = "<b>Invite links</b>\n\nNo hay links generados."
        keyboard = None
    else:
        text = "<b>Ultimos invite links</b>\n\n" + "\n".join(
            f"#{link.id} | {h(link.plan.name)} | {'usado' if link.is_used else 'libre'} | "
            f"{'join ok' if link.join_confirmed else 'sin join'} | "
            f"{'revocado' if link.revoked_at else 'activo'}"
            for link in links
        )
        keyboard = generated_links_keyboard([link.id for link in links if not link.join_confirmed])
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=keyboard)
        await event.answer()
    else:
        await event.answer(text, reply_markup=keyboard)


@router.message(Command("linkstats"))
@router.callback_query(F.data == "links:stats")
async def show_link_stats(event: Message | CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, event.from_user.id, settings, Role.ADMIN)
    stats = await link_stats(session)
    text = (
        "<b>Estadisticas de invite links</b>\n\n"
        f"Total: <b>{stats['total']}</b>\n"
        f"Activos: <b>{stats['active']}</b>\n"
        f"Usados: <b>{stats['used']}</b>\n"
        f"Joins confirmados: <b>{stats['joined']}</b>\n"
        f"Expirados sin join: <b>{stats['expired_unused']}</b>\n"
        f"Revocados: <b>{stats['revoked']}</b>"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text)
        await event.answer()
    else:
        await event.answer(text)


@router.message(Command("revokelink"))
async def cmd_revoke_link(message: Message, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Uso: <code>/revokelink ID</code>")
        return
    actor = await get_or_create_user(session, message.from_user)
    record = await revoke_link(
        bot=message.bot,
        session=session,
        link_id=parse_positive_int(parts[1], "ID"),
        actor=actor,
    )
    await message.answer(f"Link #{record.id} revocado.")


@router.message(Command("reissuelink"))
async def cmd_reissue_link(message: Message, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Uso: <code>/reissuelink ID</code>")
        return
    actor = await get_or_create_user(session, message.from_user)
    record = await reissue_expired_link(
        bot=message.bot,
        session=session,
        settings=settings,
        link_id=parse_positive_int(parts[1], "ID"),
        actor=actor,
    )
    await message.answer(
        f"Link #{record.id} reemitido.\n\n{h(record.invite_link)}",
        disable_web_page_preview=True,
    )


@router.callback_query(F.data.startswith("link:revoke:"))
async def cb_revoke_link(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    actor = await get_or_create_user(session, callback.from_user)
    record = await revoke_link(
        bot=callback.bot,
        session=session,
        link_id=int(callback.data.split(":")[-1]),
        actor=actor,
    )
    await cb_links_panel(callback, session, settings)


@router.callback_query(F.data.startswith("link:reissue:"))
async def cb_reissue_link(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    actor = await get_or_create_user(session, callback.from_user)
    record = await reissue_expired_link(
        bot=callback.bot,
        session=session,
        settings=settings,
        link_id=int(callback.data.split(":")[-1]),
        actor=actor,
    )
    await callback.message.answer(
        f"Link #{record.id} reemitido.\n\n{h(record.invite_link)}",
        disable_web_page_preview=True,
    )
    await callback.answer("Link reemitido.")
