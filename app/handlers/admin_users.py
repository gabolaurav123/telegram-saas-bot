from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.keyboards.admin import admins_keyboard, back_admin_keyboard
from app.models.access_event import MembershipAccessEvent
from app.models.enums import LogAction, MembershipStatus, Role
from app.models.generated_invite_link import GeneratedInviteLink
from app.models.log import SystemLog
from app.models.membership import Membership
from app.models.payment_request import PaymentRequest
from app.models.support import SupportReplyMap, SupportThread
from app.models.user import User
from app.services.admins import add_admin, list_admins, remove_admin, require_role
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
        reply_markup=back_admin_keyboard(),
        disable_web_page_preview=True,
    )


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
        f"Plan actual: <b>{h(plan_name)}</b>\n"
        f"Expiracion: {expires_at}\n"
        f"Estado: <b>{target.status.value}</b>\n\n"
        "<b>Pagos recientes</b>\n"
        + "\n".join(payment_lines)
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
        "<b>Referral</b>\n"
        f"{h(str(referral)) if referral else '-'}"
    )
