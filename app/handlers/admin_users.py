from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.keyboards.admin import admins_keyboard
from app.models.enums import Role
from app.services.admins import add_admin, list_admins, remove_admin, require_role
from app.services.users import get_or_create_user
from app.states.admin import AdminUserStates
from app.utils.validators import parse_telegram_id

router = Router(name="admin_users")


@router.callback_query(F.data == "adm:admins")
async def cb_admins(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.OWNER)
    admins = await list_admins(session)
    await callback.message.edit_text(
        "<b>Administradores</b>\n\n"
        "Gestiona roles OWNER, ADMIN y MODERATOR. Los OWNER definidos en OWNER_IDS siempre conservan acceso.",
        reply_markup=admins_keyboard(admins),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:admins:add")
async def cb_add_admin(callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.OWNER)
    await state.set_state(AdminUserStates.waiting_add_admin)
    await callback.message.answer(
        "<b>Agregar administrador</b>\n\n"
        "Formato:\n"
        "<code>telegram_id ROLE</code>\n\n"
        "Roles: OWNER, ADMIN, MODERATOR\n"
        "El usuario debe haber ejecutado /start antes."
    )
    await callback.answer()


@router.message(AdminUserStates.waiting_add_admin)
async def receive_add_admin(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.OWNER)
    actor = await get_or_create_user(session, message.from_user)
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Formato invalido. Usa: telegram_id ROLE")
        return
    try:
        telegram_id = parse_telegram_id(parts[0])
        role = Role(parts[1].upper())
        await add_admin(
            session,
            telegram_id=telegram_id,
            role=role,
            actor=actor,
            settings=settings,
        )
    except (ValueError, PermissionError) as exc:
        await message.answer(str(exc))
        return
    await state.clear()
    await message.answer("Administrador agregado o actualizado.")


@router.callback_query(F.data == "adm:admins:remove")
async def cb_remove_admin(callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.OWNER)
    await state.set_state(AdminUserStates.waiting_remove_admin)
    await callback.message.answer("Envia el Telegram ID del admin a eliminar.")
    await callback.answer()


@router.message(AdminUserStates.waiting_remove_admin)
async def receive_remove_admin(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.OWNER)
    actor = await get_or_create_user(session, message.from_user)
    try:
        await remove_admin(
            session,
            telegram_id=parse_telegram_id(message.text or ""),
            actor=actor,
            settings=settings,
        )
    except (ValueError, PermissionError) as exc:
        await message.answer(str(exc))
        return
    await state.clear()
    await message.answer("Administrador eliminado.")

