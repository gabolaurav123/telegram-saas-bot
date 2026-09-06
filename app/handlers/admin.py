from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.keyboards.admin import admin_menu_keyboard, back_admin_keyboard
from app.models.automation import AutomationRule
from app.models.crm import FunnelEvent
from app.models.enums import CRMStatus, MembershipStatus, PaymentRequestStatus, Role
from app.models.growth import Coupon, Referral
from app.models.log import SystemLog
from app.models.membership import Membership
from app.models.payment_request import PaymentRequest
from app.services.admins import require_permission, require_role
from app.services.backups import export_csv_zip
from app.services.bot_health import audit_managed_chat_permissions
from app.services.stats import get_overview
from app.services.users import get_or_create_user
from app.utils.text import h, money
from app.utils.time import human_datetime

router = Router(name="admin")


@router.message(Command("settings"))
async def cmd_settings(message: Message, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, message.from_user)
    try:
        role = await require_role(session, user.telegram_id, settings, Role.MODERATOR)
    except PermissionError:
        await message.answer("No tienes permisos para abrir el panel administrativo.")
        return
    await message.answer(_admin_menu_text(role), reply_markup=admin_menu_keyboard(role))


@router.callback_query(F.data == "adm:menu")
async def cb_admin_menu(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, callback.from_user)
    try:
        role = await require_role(session, user.telegram_id, settings, Role.MODERATOR)
    except PermissionError:
        await callback.answer("Sin permisos.", show_alert=True)
        return
    await callback.message.edit_text(_admin_menu_text(role), reply_markup=admin_menu_keyboard(role))
    await callback.answer()


@router.callback_query(F.data == "adm:stats")
async def cb_admin_stats(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    stats = await get_overview(session)
    top_plans = stats["top_plans"] or []
    top_lines = "\n".join(f"- {h(name)}: {count}" for name, count in top_plans) or "-"
    text = (
        "<b>Estadisticas</b>\n\n"
        f"Usuarios totales: <b>{stats['total_users']}</b>\n"
        f"Usuarios activos: <b>{stats['active_users']}</b>\n"
        f"Activos hoy: <b>{stats['active_today']}</b>\n"
        f"Activos semana: <b>{stats['active_week']}</b>\n"
        f"Membresias activas: <b>{stats['active_memberships']}</b>\n"
        f"Pagos pendientes: <b>{stats['pending_payments']}</b>\n"
        f"Ingresos aprobados: <b>{money(stats['revenue'], settings.default_currency)}</b>\n"
        f"Renovaciones solicitadas: <b>{stats['renewal_requested']}</b>\n"
        f"Renovaciones aprobadas: <b>{stats['renewal_approved']}</b>\n"
        f"Renovaciones rechazadas: <b>{stats['renewal_rejected']}</b>\n"
        f"Joins confirmados: <b>{stats['successful_joins']}</b>\n"
        f"Expiraciones: <b>{stats['expirations']}</b>\n\n"
        f"Conversion rate: <b>{stats['conversion_rate']}%</b>\n\n"
        "<b>Planes mas vendidos</b>\n"
        f"{top_lines}"
    )
    await callback.message.edit_text(text, reply_markup=back_admin_keyboard())
    await callback.answer()


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, message.from_user.id, settings, "view_stats")
    stats = await get_overview(session)
    await message.answer(
        "<b>Estadisticas</b>\n\n"
        f"Usuarios totales: <b>{stats['total_users']}</b>\n"
        f"Activos hoy: <b>{stats['active_today']}</b>\n"
        f"Activos semana: <b>{stats['active_week']}</b>\n"
        f"Membresias activas: <b>{stats['active_memberships']}</b>\n"
        f"Ingresos: <b>{money(stats['revenue'], settings.default_currency)}</b>\n"
        f"Joins confirmados: <b>{stats['successful_joins']}</b>\n"
        f"Renovaciones solicitadas/aprobadas/rechazadas: "
        f"<b>{stats['renewal_requested']}/{stats['renewal_approved']}/{stats['renewal_rejected']}</b>\n"
        f"Conversion rate: <b>{stats['conversion_rate']}%</b>"
    )


@router.callback_query(F.data == "adm:users")
async def cb_admin_users(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    stats = await get_overview(session)
    await callback.message.edit_text(
        "<b>Usuarios</b>\n\n"
        f"Usuarios registrados: <b>{stats['total_users']}</b>\n"
        f"Usuarios con membresia activa: <b>{stats['active_users']}</b>\n\n"
        "Para ubicar a un usuario pide que ejecute /id y usa ese Telegram ID para soporte o admins.",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:analytics")
async def cb_admin_analytics(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    stats = await get_overview(session)
    await callback.message.edit_text(
        "<b>Analytics</b>\n\n"
        f"Usuarios totales: <b>{stats['total_users']}</b>\n"
        f"Leads: <b>{stats['leads']}</b>\n"
        f"Interesados: <b>{stats['interested']}</b>\n"
        f"Pendientes de pago: <b>{stats['payment_pending']}</b>\n"
        f"Activos: <b>{stats['active_memberships']}</b>\n"
        f"Ingresos aprobados: <b>{money(stats['revenue'], settings.default_currency)}</b>\n"
        f"Conversion rate: <b>{stats['conversion_rate']}%</b>",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:funnel")
async def cb_admin_funnel(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    rows = await session.execute(
        select(FunnelEvent.event_name, func.count(FunnelEvent.id))
        .group_by(FunnelEvent.event_name)
        .order_by(func.count(FunnelEvent.id).desc())
        .limit(12)
    )
    lines = [f"- {h(name)}: <b>{count}</b>" for name, count in rows] or ["-"]
    await callback.message.edit_text(
        "<b>Funnel</b>\n\n" + "\n".join(lines),
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:retention")
async def cb_admin_retention(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    stats = await get_overview(session)
    await callback.message.edit_text(
        "<b>Retention</b>\n\n"
        f"Renovaciones solicitadas: <b>{stats['renewal_requested']}</b>\n"
        f"Renovaciones aprobadas: <b>{stats['renewal_approved']}</b>\n"
        f"Renovaciones rechazadas: <b>{stats['renewal_rejected']}</b>\n"
        f"Expirados: <b>{stats['expirations']}</b>\n"
        f"Recuperados: <b>{stats['recovered']}</b>",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:coupons")
async def cb_admin_coupons(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    total = await session.scalar(select(func.count(Coupon.id)))
    active = await session.scalar(select(func.count(Coupon.id)).where(Coupon.enabled.is_(True)))
    await callback.message.edit_text(
        "<b>Coupons</b>\n\n"
        f"Cupones totales: <b>{int(total or 0)}</b>\n"
        f"Cupones activos: <b>{int(active or 0)}</b>\n\n"
        "La base de datos ya soporta codigos por monto fijo o porcentaje, ventanas de fecha, "
        "limites de uso, nuevos usuarios y usuarios expirados.",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:referrals")
async def cb_admin_referrals(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    total = await session.scalar(select(func.count(Referral.id)))
    rewarded = await session.scalar(select(func.count(Referral.id)).where(Referral.reward_granted_at.is_not(None)))
    await callback.message.edit_text(
        "<b>Referrals</b>\n\n"
        f"Referidos registrados: <b>{int(total or 0)}</b>\n"
        f"Referidos recompensados: <b>{int(rewarded or 0)}</b>\n\n"
        "Los deep links de /start ya guardan source, campaign y referral.",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:automations")
async def cb_admin_automations(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    total = await session.scalar(select(func.count(AutomationRule.id)))
    active = await session.scalar(select(func.count(AutomationRule.id)).where(AutomationRule.enabled.is_(True)))
    await callback.message.edit_text(
        "<b>Automations</b>\n\n"
        f"Reglas configuradas: <b>{int(total or 0)}</b>\n"
        f"Reglas activas: <b>{int(active or 0)}</b>\n\n"
        "El motor soporta reglas, condiciones, payloads y jobs con dedupe. "
        "El scheduler actual sigue manejando expiraciones, recordatorios, backups y reemision de links.",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:config")
async def cb_admin_config(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.OWNER)
    await callback.message.edit_text(
        "<b>Configuracion</b>\n\n"
        f"Entorno: <code>{h(settings.app_env)}</code>\n"
        f"Zona horaria: <code>{h(settings.app_timezone)}</code>\n"
        f"Marca publica: <code>{h(settings.public_brand_name)}</code>\n"
        f"Scheduler: <code>{settings.scheduler_enabled}</code>\n"
        f"Backups automaticos: <code>{settings.backup_enabled}</code>\n\n"
        "Las configuraciones globales se controlan desde variables de entorno en Railway.",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:messages")
async def cb_admin_messages(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    await callback.message.edit_text(
        "<b>Mensajes automaticos</b>\n\n"
        "Cada plan puede tener un mensaje personalizado por metodo de pago.\n\n"
        "Variables disponibles:\n"
        "<code>{username}</code>, <code>{plan_name}</code>, <code>{price}</code>, "
        "<code>{duration}</code>, <code>{payment_method}</code>, <code>{instructions}</code>\n\n"
        "Entra en Planes -> Mensaje por metodo para editar.",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:logs")
async def cb_admin_logs(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    logs = (
        await session.scalars(select(SystemLog).order_by(SystemLog.created_at.desc()).limit(10))
    ).all()
    if not logs:
        text = "<b>Logs</b>\n\nSin eventos registrados."
    else:
        lines = [
            f"- {human_datetime(log.created_at, settings.app_timezone)} | {log.severity} | "
            f"{h(log.action.value)} | {h(log.message)}"
            for log in logs
        ]
        text = "<b>Logs recientes</b>\n\n" + "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=back_admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "adm:backups")
async def cb_admin_backups(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.OWNER)
    await callback.answer("Generando backup...")
    backup_path = await export_csv_zip(session, settings)
    await callback.message.answer_document(
        FSInputFile(backup_path),
        caption="Backup CSV generado.",
    )


@router.callback_query(F.data == "adm:pending")
async def cb_pending_approvals(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "review_payments")
    count = await session.scalar(
        select(func.count(PaymentRequest.id)).where(PaymentRequest.status == PaymentRequestStatus.PENDING)
    )
    await callback.message.edit_text(
        "<b>Pending approvals</b>\n\n"
        f"Solicitudes pendientes: <b>{int(count or 0)}</b>\n\n"
        "Las nuevas solicitudes llegan automaticamente con botones de aprobacion.",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"adm:subs:active", "adm:subs:expired"}))
async def cb_subscription_status(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    status = MembershipStatus.ACTIVE if callback.data.endswith("active") else MembershipStatus.EXPIRED
    count = await session.scalar(select(func.count(Membership.id)).where(Membership.status == status))
    await callback.message.edit_text(
        f"<b>{'Active' if status == MembershipStatus.ACTIVE else 'Expired'} subscriptions</b>\n\n"
        f"Total: <b>{int(count or 0)}</b>",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:health")
async def cb_system_health(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    await session.scalar(select(1))
    bot_info = await callback.bot.get_me()
    webhook = await callback.bot.get_webhook_info()
    chat_health = await audit_managed_chat_permissions(
        bot=callback.bot,
        session=session,
        bot_id=bot_info.id,
    )
    if chat_health:
        chat_lines = []
        for item in chat_health[:10]:
            state = "OK" if item.operational_ok else "WARN"
            detail = (
                f"invite={item.can_invite_users} kick={item.can_restrict_members} "
                f"msg={item.can_post_messages}"
                if item.error is None
                else h(item.error[:120])
            )
            chat_lines.append(
                f"- {state} {h(item.kind)} #{item.db_id} {h(item.title)} "
                f"status={h(item.status)} {detail}"
            )
        if len(chat_health) > 10:
            chat_lines.append(f"- ... {len(chat_health) - 10} chats mas")
    else:
        chat_lines = ["- Sin canales/grupos activos registrados."]
    await callback.message.edit_text(
        "<b>System health</b>\n\n"
        "PostgreSQL: <b>OK</b>\n"
        f"Bot API: <b>OK</b> <code>{bot_info.id}</code> @{h(bot_info.username or '-')}\n"
        f"Webhook: <code>{h(webhook.url or '-')}</code>\n"
        f"Pending updates: <code>{webhook.pending_update_count}</code>\n"
        f"Environment: <code>{h(settings.app_env)}</code>\n\n"
        "<b>Managed chat permissions</b>\n"
        + "\n".join(chat_lines),
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:scheduler")
async def cb_scheduler_status(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    await callback.message.edit_text(
        "<b>Scheduler status</b>\n\n"
        f"Enabled: <code>{settings.scheduler_enabled}</code>\n"
        f"Expire check: <code>{settings.expire_check_minutes} min</code>\n"
        f"Reminder check: <code>{settings.reminder_check_minutes} min</code>"
        f"\nLink reissue: <code>{max(1, settings.expired_link_reissue_hours)} h</code>",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


def _admin_menu_text(role: Role) -> str:
    return (
        "<b>Panel administrativo</b>\n\n"
        f"Rol activo: <b>{role.value}</b>\n"
        "Selecciona una seccion:"
    )
