from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.keyboards.admin import (
    admin_detail_keyboard,
    admins_keyboard,
    back_admin_keyboard,
    user_admin_actions_keyboard,
)
from app.models.admin import Admin
from app.models.access_event import MembershipAccessEvent
from app.models.crm import UserNote, UserTag
from app.models.enums import CRMStatus, LogAction, MembershipStatus, PaymentRequestStatus, Role, UserStatus
from app.models.generated_invite_link import GeneratedInviteLink
from app.models.growth import Referral
from app.models.log import SystemLog
from app.models.membership import Membership
from app.models.payment_request import PaymentRequest
from app.models.support import SupportReplyMap, SupportThread
from app.models.user import User
from app.services.admins import add_admin, list_admins, remove_admin, require_role
from app.services.crm import add_user_note, add_user_tag, set_crm_status
from app.services.logs import log_event
from app.services.messaging import MessagingService
from app.services.users import get_or_create_user, get_user_by_telegram_id
from app.states.admin import AdminUserStates
from app.utils.text import h, money
from app.utils.time import human_datetime
from app.utils.validators import parse_telegram_id

router = Router(name="admin_users")


@router.message(Command("userinfo"))
async def cmd_userinfo(message: Message, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Uso: <code>/userinfo TELEGRAM_ID</code>")
        return
    telegram_id = parse_telegram_id(parts[1])
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        await message.answer("Usuario no encontrado. Debe haber usado /start al menos una vez.")
        return
    await message.answer(
        await _userinfo_text(session, user.id, settings),
        reply_markup=user_admin_actions_keyboard(user.id),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "adm:admins")
async def cb_admins(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.OWNER)
    admins = await list_admins(session)
    await callback.message.edit_text(
        "<b>Administradores</b>\n\n"
        "Gestiona roles OWNER, SUPERVISOR, ADMIN, PAYMENTS, SUPPORT, SALES, MODERATOR y READ_ONLY. "
        "Los OWNER definidos en OWNER_IDS siempre conservan acceso.",
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
        "Roles: OWNER, SUPERVISOR, ADMIN, PAYMENTS, SUPPORT, SALES, MODERATOR, READ_ONLY\n"
        "El usuario debe haber ejecutado /start antes."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:admins:view:"))
async def cb_admin_detail(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.OWNER)
    admin = await session.scalar(
        select(Admin)
        .options(selectinload(Admin.user), selectinload(Admin.added_by))
        .where(Admin.id == int(callback.data.rsplit(":", 1)[-1]))
    )
    if admin is None:
        await callback.answer("Administrador no encontrado.", show_alert=True)
        return
    await callback.message.edit_text(
        "<b>Administrador</b>\n\n"
        f"Nombre: {h(admin.user.display_name)}\n"
        f"Telegram ID: <code>{admin.telegram_id}</code>\n"
        f"Rol: <b>{admin.role.value}</b>\n"
        f"Estado: <b>{'Activo' if admin.is_active else 'Inactivo'}</b>\n\n"
        "Selecciona un rol para actualizar sus permisos.",
        reply_markup=admin_detail_keyboard(admin.id, admin.role),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:admins:role:"))
async def cb_admin_change_role(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.OWNER)
    _, _, _, admin_id_raw, role_raw = callback.data.split(":")
    admin = await session.scalar(
        select(Admin).options(selectinload(Admin.user)).where(Admin.id == int(admin_id_raw))
    )
    if admin is None:
        await callback.answer("Administrador no encontrado.", show_alert=True)
        return
    if admin.telegram_id in settings.owner_ids:
        await callback.answer("El OWNER configurado por entorno conserva su rol.", show_alert=True)
        return
    role = Role(role_raw)
    actor = await get_or_create_user(session, callback.from_user)
    admin.role = role
    await log_event(
        session,
        LogAction.ADMIN_CREATED,
        f"Rol de administrador actualizado: {admin.telegram_id} -> {role.value}",
        actor_user_id=actor.id,
        target_user_id=admin.user_id,
        details={"admin_id": admin.id, "role": role.value},
    )
    await callback.message.edit_reply_markup(reply_markup=admin_detail_keyboard(admin.id, role))
    await callback.answer("Rol actualizado.")


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


@router.callback_query(F.data.startswith("user:msg:"))
async def cb_user_direct_message(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    user_id = int(callback.data.split(":")[-1])
    if await session.get(User, user_id) is None:
        await callback.answer("Usuario no encontrado.", show_alert=True)
        return
    await state.set_state(AdminUserStates.waiting_direct_message)
    await state.update_data(target_user_id=user_id)
    await callback.message.answer("Escribe el mensaje privado que quieres enviar al usuario.")
    await callback.answer()


@router.message(AdminUserStates.waiting_direct_message)
async def receive_user_direct_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    data = await state.get_data()
    target = await session.get(User, int(data["target_user_id"]))
    if target is None:
        await message.answer("Usuario no encontrado.")
        await state.clear()
        return
    actor = await get_or_create_user(session, message.from_user)
    outbound = await MessagingService(session).send_text_to_user(
        bot=message.bot,
        target=target,
        text=message.text or "",
        actor=actor,
        source="ADMIN_DIRECT",
    )
    await state.clear()
    await message.answer(f"Estado de envio: <b>{outbound.status.value}</b>")


@router.callback_query(F.data.startswith("user:note:"))
async def cb_user_note(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    user_id = int(callback.data.split(":")[-1])
    if await session.get(User, user_id) is None:
        await callback.answer("Usuario no encontrado.", show_alert=True)
        return
    await state.set_state(AdminUserStates.waiting_note)
    await state.update_data(target_user_id=user_id)
    await callback.message.answer("Escribe la nota interna para este cliente.")
    await callback.answer()


@router.message(AdminUserStates.waiting_note)
async def receive_user_note(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    data = await state.get_data()
    target = await session.get(User, int(data["target_user_id"]))
    if target is None:
        await message.answer("Usuario no encontrado.")
        await state.clear()
        return
    actor = await get_or_create_user(session, message.from_user)
    await add_user_note(session, user=target, author=actor, note=message.text or "")
    await state.clear()
    await message.answer("Nota interna agregada.")


@router.callback_query(F.data.startswith("user:tag:"))
async def cb_user_tag(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    user_id = int(callback.data.split(":")[-1])
    if await session.get(User, user_id) is None:
        await callback.answer("Usuario no encontrado.", show_alert=True)
        return
    await state.set_state(AdminUserStates.waiting_tag)
    await state.update_data(target_user_id=user_id)
    await callback.message.answer("Escribe el tag CRM a agregar.")
    await callback.answer()


@router.message(AdminUserStates.waiting_tag)
async def receive_user_tag(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    data = await state.get_data()
    target = await session.get(User, int(data["target_user_id"]))
    if target is None:
        await message.answer("Usuario no encontrado.")
        await state.clear()
        return
    actor = await get_or_create_user(session, message.from_user)
    await add_user_tag(session, user=target, tag_name=message.text or "", actor=actor)
    await state.clear()
    await message.answer("Tag agregado.")


@router.callback_query(F.data.startswith("user:vip:"))
async def cb_user_mark_vip(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    target = await session.get(User, int(callback.data.split(":")[-1]))
    if target is None:
        await callback.answer("Usuario no encontrado.", show_alert=True)
        return
    actor = await get_or_create_user(session, callback.from_user)
    target.is_vip = True
    await set_crm_status(session, user=target, status=CRMStatus.VIP, reason="admin_mark_vip", actor_user_id=actor.id)
    await callback.answer("Marcado como VIP.")
    await callback.message.edit_text(
        await _userinfo_text(session, target.id, settings),
        reply_markup=user_admin_actions_keyboard(target.id),
    )


@router.callback_query(F.data.startswith("user:block:"))
async def cb_user_block(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    target = await session.get(User, int(callback.data.split(":")[-1]))
    if target is None:
        await callback.answer("Usuario no encontrado.", show_alert=True)
        return
    actor = await get_or_create_user(session, callback.from_user)
    target.status = UserStatus.SUSPENDED
    await set_crm_status(session, user=target, status=CRMStatus.BLOCKED, reason="admin_block", actor_user_id=actor.id)
    await callback.answer("Usuario bloqueado en CRM.")
    await callback.message.edit_text(
        await _userinfo_text(session, target.id, settings),
        reply_markup=user_admin_actions_keyboard(target.id),
    )


@router.callback_query(F.data.startswith("user:reactivate:"))
async def cb_user_reactivate(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    target = await session.get(User, int(callback.data.split(":")[-1]))
    if target is None:
        await callback.answer("Usuario no encontrado.", show_alert=True)
        return
    actor = await get_or_create_user(session, callback.from_user)
    target.status = UserStatus.ACTIVE
    target.blocked_at = None
    active_membership = await session.scalar(
        select(Membership.id).where(
            Membership.user_id == target.id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    )
    await set_crm_status(
        session,
        user=target,
        status=CRMStatus.ACTIVE if active_membership else CRMStatus.INTERESTED,
        reason="admin_reactivate",
        actor_user_id=actor.id,
    )
    await log_event(
        session,
        LogAction.USER_REACTIVATED,
        f"Usuario reactivado: {target.telegram_id}",
        actor_user_id=actor.id,
        target_user_id=target.id,
    )
    await callback.answer("Usuario reactivado.")
    await callback.message.edit_text(
        await _userinfo_text(session, target.id, settings),
        reply_markup=user_admin_actions_keyboard(target.id),
    )


async def _userinfo_text(session: AsyncSession, user_id: int, settings: Settings) -> str:
    target = await session.get(User, user_id)
    if target is None:
        return "Usuario no encontrado."

    active_membership = await session.scalar(
        select(Membership)
        .options(selectinload(Membership.plan))
        .where(
            Membership.user_id == user_id,
            Membership.status == MembershipStatus.ACTIVE,
        )
        .order_by(Membership.expires_at.desc())
    )
    expired_count = await session.scalar(
        select(func.count(Membership.id)).where(
            Membership.user_id == user_id,
            Membership.status == MembershipStatus.EXPIRED,
        )
    )
    payments = list(
        await session.scalars(
            select(PaymentRequest)
            .options(selectinload(PaymentRequest.plan), selectinload(PaymentRequest.payment_method))
            .where(PaymentRequest.user_id == user_id)
            .order_by(desc(PaymentRequest.submitted_at))
            .limit(5)
        )
    )
    links = list(
        await session.scalars(
            select(GeneratedInviteLink)
            .options(selectinload(GeneratedInviteLink.plan))
            .where(GeneratedInviteLink.used_by_user_id == user_id)
            .order_by(desc(GeneratedInviteLink.used_at))
            .limit(5)
        )
    )
    events = list(
        await session.scalars(
            select(MembershipAccessEvent)
            .where(MembershipAccessEvent.user_id == user_id)
            .order_by(desc(MembershipAccessEvent.event_at))
            .limit(8)
        )
    )
    thread = await session.scalar(select(SupportThread).where(SupportThread.user_id == user_id))
    reply_count = await session.scalar(
        select(func.count(SupportReplyMap.id)).where(SupportReplyMap.user_id == user_id)
    )
    reg_log = await session.scalar(
        select(SystemLog)
        .where(SystemLog.target_user_id == user_id, SystemLog.action == LogAction.USER_REGISTERED)
        .order_by(desc(SystemLog.created_at))
    )
    referral = (reg_log.details or {}).get("referral") if reg_log else None
    referrals_count = await session.scalar(
        select(func.count(Referral.id)).where(Referral.referrer_user_id == user_id)
    )
    approved_amount = await session.scalar(
        select(func.coalesce(func.sum(PaymentRequest.amount), 0)).where(
            PaymentRequest.user_id == user_id,
            PaymentRequest.status == PaymentRequestStatus.APPROVED,
            PaymentRequest.currency == settings.default_currency,
        )
    )
    tags = list(
        await session.scalars(
            select(UserTag)
            .options(selectinload(UserTag.tag))
            .where(UserTag.user_id == user_id)
            .order_by(desc(UserTag.created_at))
            .limit(8)
        )
    )
    notes = list(
        await session.scalars(
            select(UserNote)
            .where(UserNote.user_id == user_id)
            .order_by(desc(UserNote.created_at))
            .limit(3)
        )
    )
    renewal_counts = {
        "requested": int(
            await session.scalar(
                select(func.count(SystemLog.id)).where(
                    SystemLog.target_user_id == user_id,
                    SystemLog.action == LogAction.MEMBERSHIP_RENEWAL_REQUESTED,
                )
            )
            or 0
        ),
        "approved": int(
            await session.scalar(
                select(func.count(SystemLog.id)).where(
                    SystemLog.target_user_id == user_id,
                    SystemLog.action == LogAction.MEMBERSHIP_RENEWAL_APPROVED,
                )
            )
            or 0
        ),
        "rejected": int(
            await session.scalar(
                select(func.count(SystemLog.id)).where(
                    SystemLog.target_user_id == user_id,
                    SystemLog.action == LogAction.MEMBERSHIP_RENEWAL_REJECTED,
                )
            )
            or 0
        ),
    }

    payment_lines = [
        f"#{payment.id} {payment.status.value} | {h(payment.plan.name)} | "
        f"{money(payment.amount, payment.currency)} | {h(payment.payment_method.name)}"
        for payment in payments
    ] or ["-"]
    link_lines = [
        f"#{link.id} {h(link.plan.name)} | {human_datetime(link.used_at, settings.app_timezone) if link.used_at else '-'} "
        f"| {'join ok' if link.join_confirmed else 'sin join'}"
        for link in links
    ] or ["-"]
    event_lines = [
        f"{event.event_kind.value} | {h(event.chat_title)} | {human_datetime(event.event_at, settings.app_timezone)}"
        for event in events
    ] or ["-"]
    tag_line = ", ".join(h(item.tag.name) for item in tags) or "-"
    note_lines = [h(note.note[:140]) for note in notes] or ["-"]

    plan_name = active_membership.plan.name if active_membership else "-"
    expires_at = (
        human_datetime(active_membership.expires_at, settings.app_timezone)
        if active_membership
        else "-"
    )
    return (
        "<b>User info</b>\n\n"
        f"Nombre: <b>{h(target.display_name)}</b>\n"
        f"Username: {h('@' + target.username if target.username else '-')}\n"
        f"Telegram ID: <code>{target.telegram_id}</code>\n"
        f"Registro: {human_datetime(target.registered_at, settings.app_timezone)}\n"
        f"Ultimo contacto: {human_datetime(target.last_contacted_at, settings.app_timezone)}\n"
        f"Plan actual: <b>{h(plan_name)}</b>\n"
        f"Expiracion: {expires_at}\n"
        f"Estado: <b>{target.status.value}</b>\n"
        f"CRM: <b>{target.crm_status.value}</b> | VIP: <b>{'SI' if target.is_vip else 'NO'}</b>\n"
        f"Entrega mensajes: <b>{h(target.delivery_status)}</b>\n"
        f"Source/Campaign: {h(target.source or '-')} / {h(target.campaign or '-')}\n"
        f"Referral code: <code>{h(target.referral_code or '-')}</code>\n"
        f"Tags: {tag_line}\n\n"
        "<b>Pagos recientes</b>\n"
        + "\n".join(payment_lines)
        + f"\nTotal aprobado ({h(settings.default_currency)}): {money(approved_amount, settings.default_currency)}"
        + "\n\n<b>Renovaciones recientes</b>\n"
        f"Solicitadas/aprobadas/rechazadas: "
        f"{renewal_counts['requested']}/{renewal_counts['approved']}/{renewal_counts['rejected']}\n"
        f"Expiraciones: {int(expired_count or 0)}\n\n"
        "<b>Links usados</b>\n"
        + "\n".join(link_lines)
        + "\n\n<b>Joins / expulsiones</b>\n"
        + "\n".join(event_lines)
        + "\n\n<b>Tickets / mensajes</b>\n"
        f"Thread: {thread.status if thread else '-'} | Mensajes puente: {int(reply_count or 0)}\n\n"
        "<b>Notas internas</b>\n"
        + "\n".join(note_lines)
        + "\n\n"
        "<b>Referral</b>\n"
        f"{h(str(referral)) if referral else '-'} | Referidos: {int(referrals_count or 0)}"
    )
