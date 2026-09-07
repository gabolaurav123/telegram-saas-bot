from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.keyboards.admin import (
    admin_config_keyboard,
    admin_language_keyboard,
    admin_menu_keyboard,
    admin_section_keyboard,
    back_admin_keyboard,
    coupon_plan_keyboard,
    coupon_type_keyboard,
    coupons_keyboard,
    pending_payment_detail_keyboard,
    pending_payments_keyboard,
)
from app.models.automation import AutomationRule
from app.models.crm import FunnelEvent
from app.models.enums import (
    CouponType,
    CRMStatus,
    LogAction,
    MembershipStatus,
    PaymentRequestStatus,
    ProofKind,
    Role,
)
from app.models.growth import Coupon, Referral
from app.models.log import SystemLog
from app.models.membership import Membership
from app.models.payment_request import PaymentRequest
from app.models.plan import Plan
from app.services.admins import require_permission, require_role
from app.services.backups import export_csv_zip
from app.services.bot_health import audit_managed_chat_permissions
from app.services.logs import log_event
from app.services.stats import get_overview
from app.services.payments import get_payment_request, list_pending_payment_requests
from app.services.plans import list_plans
from app.services.runtime_settings import update_runtime_setting
from app.services.users import get_or_create_user, set_preferred_language
from app.states.admin import AdminConfigStates, AdminCouponStates
from app.utils.text import h, money
from app.utils.time import human_datetime

router = Router(name="admin")


@router.message(Command("settings"))
async def cmd_settings(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    user = await get_or_create_user(session, message.from_user)
    try:
        role = await require_role(session, user.telegram_id, settings, Role.MODERATOR)
    except PermissionError:
        await message.answer("No tienes permisos para abrir el panel administrativo.")
        return
    await state.clear()
    await message.answer(
        _admin_menu_text(role, user.preferred_language),
        reply_markup=admin_menu_keyboard(role, settings.mini_app_admin_url, user.preferred_language),
    )


@router.callback_query(F.data == "adm:menu")
async def cb_admin_menu(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    user = await get_or_create_user(session, callback.from_user)
    try:
        role = await require_role(session, user.telegram_id, settings, Role.MODERATOR)
    except PermissionError:
        await callback.answer("Sin permisos.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        _admin_menu_text(role, user.preferred_language),
        reply_markup=admin_menu_keyboard(role, settings.mini_app_admin_url, user.preferred_language),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:section:"))
async def cb_admin_section(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    user = await get_or_create_user(session, callback.from_user)
    role = await require_role(session, user.telegram_id, settings, Role.MODERATOR)
    await state.clear()
    section = callback.data.rsplit(":", 1)[-1]
    titles = {
        "operations": ("Operacion diaria", "Daily operations", "Operacao diaria"),
        "catalog": ("Catalogo y accesos", "Catalog and access", "Catalogo e acessos"),
        "clients": ("Clientes y soporte", "Clients and support", "Clientes e suporte"),
        "growth": ("Crecimiento", "Growth", "Crescimento"),
        "system": ("Sistema", "System", "Sistema"),
    }
    localized_titles = titles.get(section)
    if localized_titles is None:
        await callback.answer("Seccion no disponible.", show_alert=True)
        return
    language_index = {"en": 1, "pt": 2}.get(user.preferred_language, 0)
    title = localized_titles[language_index]
    prompt = {
        "en": "Choose the tool you want to use.",
        "pt": "Selecione a ferramenta que deseja usar.",
    }.get(user.preferred_language, "Selecciona la herramienta que deseas utilizar.")
    await callback.message.edit_text(
        f"<b>{title}</b>\n\n{prompt}",
        reply_markup=admin_section_keyboard(section, role, user.preferred_language),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:language")
async def cb_admin_language(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, callback.from_user)
    await require_role(session, user.telegram_id, settings, Role.MODERATOR)
    await callback.message.edit_text(
        "<b>Idioma del panel</b>\n\nSelecciona el idioma de tu interfaz administrativa.",
        reply_markup=admin_language_keyboard(user.preferred_language, settings.supported_languages),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:lang:set:"))
async def cb_admin_language_set(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, callback.from_user)
    await require_role(session, user.telegram_id, settings, Role.MODERATOR)
    selected = callback.data.rsplit(":", 1)[-1]
    if selected not in settings.supported_languages:
        await callback.answer("Idioma no disponible.", show_alert=True)
        return
    user = await set_preferred_language(
        session,
        user=user,
        language=selected,
        supported_languages=settings.supported_languages,
    )
    await callback.message.edit_text(
        _admin_menu_text(role=await require_role(session, user.telegram_id, settings, Role.MODERATOR), language=selected),
        reply_markup=admin_menu_keyboard(
            await require_role(session, user.telegram_id, settings, Role.MODERATOR),
            settings.mini_app_admin_url,
            selected,
        ),
    )
    await callback.answer("Idioma actualizado.")


@router.callback_query(F.data == "adm:miniapp")
async def cb_admin_miniapp(callback: CallbackQuery, settings: Settings) -> None:
    if settings.mini_app_admin_url:
        await callback.answer("Abre el boton Admin Mini App del panel.", show_alert=True)
        return
    await callback.answer(
        "Admin Mini App no configurada. Define MINI_APP_ADMIN_URL en Seenode con una URL HTTPS.",
        show_alert=True,
    )


@router.callback_query(F.data == "adm:stats")
async def cb_admin_stats(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    stats = await get_overview(session, settings)
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
        f"Ingresos aprobados: <b>{money(stats['revenue'], 'USD')}</b>\n"
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
    stats = await get_overview(session, settings)
    await message.answer(
        "<b>Estadisticas</b>\n\n"
        f"Usuarios totales: <b>{stats['total_users']}</b>\n"
        f"Activos hoy: <b>{stats['active_today']}</b>\n"
        f"Activos semana: <b>{stats['active_week']}</b>\n"
        f"Membresias activas: <b>{stats['active_memberships']}</b>\n"
        f"Ingresos: <b>{money(stats['revenue'], 'USD')}</b>\n"
        f"Joins confirmados: <b>{stats['successful_joins']}</b>\n"
        f"Renovaciones solicitadas/aprobadas/rechazadas: "
        f"<b>{stats['renewal_requested']}/{stats['renewal_approved']}/{stats['renewal_rejected']}</b>\n"
        f"Conversion rate: <b>{stats['conversion_rate']}%</b>"
    )


@router.callback_query(F.data == "adm:users")
async def cb_admin_users(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    stats = await get_overview(session, settings)
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
    stats = await get_overview(session, settings)
    await callback.message.edit_text(
        "<b>Analitica</b>\n\n"
        f"Usuarios totales: <b>{stats['total_users']}</b>\n"
        f"Leads: <b>{stats['leads']}</b>\n"
        f"Interesados: <b>{stats['interested']}</b>\n"
        f"Pendientes de pago: <b>{stats['payment_pending']}</b>\n"
        f"Activos: <b>{stats['active_memberships']}</b>\n"
        f"Ingresos aprobados: <b>{money(stats['revenue'], 'USD')}</b>\n"
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
        "<b>Embudo</b>\n\n" + "\n".join(lines),
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:retention")
async def cb_admin_retention(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    stats = await get_overview(session, settings)
    await callback.message.edit_text(
        "<b>Retencion</b>\n\n"
        f"Renovaciones solicitadas: <b>{stats['renewal_requested']}</b>\n"
        f"Renovaciones aprobadas: <b>{stats['renewal_approved']}</b>\n"
        f"Renovaciones rechazadas: <b>{stats['renewal_rejected']}</b>\n"
        f"Expirados: <b>{stats['expirations']}</b>\n"
        f"Recuperados: <b>{stats['recovered']}</b>",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:coupons")
async def cb_admin_coupons(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    await state.clear()
    total = await session.scalar(select(func.count(Coupon.id)))
    active = await session.scalar(select(func.count(Coupon.id)).where(Coupon.enabled.is_(True)))
    coupons = (
        await session.scalars(select(Coupon).order_by(Coupon.created_at.desc()).limit(20))
    ).all()
    await callback.message.edit_text(
        "<b>Cupones</b>\n\n"
        f"Cupones totales: <b>{int(total or 0)}</b>\n"
        f"Cupones activos: <b>{int(active or 0)}</b>\n\n"
        "Pulsa Crear cupon para generar uno paso a paso. Pulsa un cupon existente para activarlo o desactivarlo.",
        reply_markup=coupons_keyboard(list(coupons)),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:coupon:create")
async def cb_coupon_create(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    await state.clear()
    await state.set_state(AdminCouponStates.waiting_code)
    await callback.message.answer(
        "<b>Nuevo cupon: codigo</b>\n\n"
        "Escribe un codigo de 3 a 32 caracteres. Usa letras, numeros, guion o guion bajo.\n\n"
        "Ejemplo: <code>VIP20</code>"
    )
    await callback.answer()


@router.message(AdminCouponStates.waiting_code)
async def receive_coupon_code(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    code = (message.text or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,32}", code):
        await message.answer("Codigo invalido. Ejemplo valido: <code>VIP20</code>.")
        return
    if await session.scalar(select(Coupon.id).where(Coupon.code == code)):
        await message.answer("Ese codigo ya existe. Escribe uno diferente.")
        return
    await state.update_data(code=code)
    await message.answer(
        "<b>Tipo de descuento</b>\n\nElige si descontara un porcentaje o un monto fijo.",
        reply_markup=coupon_type_keyboard(),
    )


@router.callback_query(F.data.startswith("adm:coupon:type:"))
async def cb_coupon_type(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    coupon_type = CouponType(callback.data.rsplit(":", 1)[-1])
    await state.update_data(coupon_type=coupon_type.value)
    await state.set_state(AdminCouponStates.waiting_value)
    await callback.message.edit_text(
        "<b>Valor del descuento</b>\n\n"
        + (
            "Escribe el porcentaje entre 0 y 100. Ejemplo: <code>20</code>."
            if coupon_type == CouponType.PERCENTAGE
            else "Escribe el monto que se descontara. Ejemplo: <code>50</code>."
        )
    )
    await callback.answer()


@router.message(AdminCouponStates.waiting_value)
async def receive_coupon_value(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    data = await state.get_data()
    try:
        value = Decimal((message.text or "").strip().replace(",", "."))
    except InvalidOperation:
        await message.answer("Escribe un numero valido.")
        return
    if value <= 0 or (data["coupon_type"] == CouponType.PERCENTAGE.value and value > 100):
        await message.answer("El valor debe ser mayor que cero y el porcentaje no puede superar 100.")
        return
    await state.update_data(value=str(value))
    plans = await list_plans(session, only_active=True)
    await message.answer(
        "<b>Plan aplicable</b>\n\nSelecciona un plan o permite usar el cupon en todos.",
        reply_markup=coupon_plan_keyboard(plans),
    )


@router.callback_query(F.data.startswith("adm:coupon:plan:"))
async def cb_coupon_plan(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    raw_plan = callback.data.rsplit(":", 1)[-1]
    await state.update_data(plan_id=None if raw_plan == "all" else int(raw_plan))
    await state.set_state(AdminCouponStates.waiting_max_uses)
    await callback.message.edit_text(
        "<b>Limite de usos</b>\n\nEscribe el maximo de usos totales. Envia <code>0</code> para uso ilimitado."
    )
    await callback.answer()


@router.message(AdminCouponStates.waiting_max_uses)
async def receive_coupon_max_uses(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    try:
        max_uses_raw = int((message.text or "").strip())
    except ValueError:
        await message.answer("Escribe un numero entero. Usa 0 para ilimitado.")
        return
    if max_uses_raw < 0:
        await message.answer("El limite no puede ser negativo.")
        return
    data = await state.get_data()
    coupon = Coupon(
        code=data["code"],
        coupon_type=CouponType(data["coupon_type"]),
        value=Decimal(data["value"]),
        plan_id=data.get("plan_id"),
        max_uses=max_uses_raw or None,
        uses_per_user=1,
        enabled=True,
    )
    session.add(coupon)
    await session.flush()
    actor = await get_or_create_user(session, message.from_user)
    await log_event(
        session,
        LogAction.COUPON_CREATED,
        f"Cupon creado: {coupon.code}",
        actor_user_id=actor.id,
        details={"coupon_id": coupon.id, "plan_id": coupon.plan_id},
    )
    await state.clear()
    await message.answer(
        f"Cupon <code>{h(coupon.code)}</code> creado y activo.",
        reply_markup=back_admin_keyboard("adm:coupons", "Ver cupones"),
    )


@router.callback_query(F.data.startswith("adm:coupon:toggle:"))
async def cb_coupon_toggle(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    coupon = await session.get(Coupon, int(callback.data.rsplit(":", 1)[-1]))
    if coupon is None:
        await callback.answer("Cupon no encontrado.", show_alert=True)
        return
    coupon.enabled = not coupon.enabled
    actor = await get_or_create_user(session, callback.from_user)
    await log_event(
        session,
        LogAction.COUPON_UPDATED,
        f"Cupon {coupon.code} {'activado' if coupon.enabled else 'desactivado'}",
        actor_user_id=actor.id,
        details={"coupon_id": coupon.id, "enabled": coupon.enabled},
    )
    await callback.answer("Estado actualizado.")
    coupons = (
        await session.scalars(select(Coupon).order_by(Coupon.created_at.desc()).limit(20))
    ).all()
    await callback.message.edit_reply_markup(reply_markup=coupons_keyboard(list(coupons)))


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
        "<b>Automatizaciones</b>\n\n"
        f"Reglas configuradas: <b>{int(total or 0)}</b>\n"
        f"Reglas activas: <b>{int(active or 0)}</b>\n\n"
        "El motor soporta reglas, condiciones, payloads y jobs con dedupe. "
        "El scheduler actual sigue manejando expiraciones, recordatorios, backups y reemision de links.",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:config")
async def cb_admin_config(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.OWNER)
    await state.clear()
    await callback.message.edit_text(
        "<b>Configuracion</b>\n\n"
        f"Entorno: <code>{h(settings.app_env)}</code>\n"
        f"Zona horaria: <code>{h(settings.app_timezone)}</code>\n"
        f"Marca publica: <code>{h(settings.public_brand_name)}</code>\n"
        f"Idioma default: <code>{h(settings.default_language)}</code>\n"
        f"Idiomas: <code>{h(','.join(settings.supported_languages))}</code>\n"
        f"Stars/USD: <code>{settings.effective_stars_per_usd}</code>\n"
        f"Tasas USD: <code>{h(','.join(sorted(settings.currency_usd_rates)))}</code>\n"
        f"Scheduler: <code>{settings.scheduler_enabled}</code>\n"
        f"Backups automaticos: <code>{settings.backup_enabled}</code>\n\n"
        "Los cambios realizados aqui se guardan en PostgreSQL y se conservan despues de cada redeploy.",
        reply_markup=admin_config_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:config:set:"))
async def cb_admin_config_set(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.OWNER)
    key = callback.data.rsplit(":", 1)[-1]
    prompts = {
        "brand": "Escribe la nueva marca publica.",
        "support_url": "Escribe la URL de soporte o <code>-</code> para quitarla.",
        "faq_url": "Escribe la URL de FAQ o <code>-</code> para quitarla.",
        "default_language": "Escribe el idioma: <code>es</code>, <code>en</code> o <code>pt</code>.",
        "stars_per_usd": "Escribe cuantas Stars equivalen a 1 USD. Referencia actual: <code>44.11764706</code>.",
        "currency_rates": "Escribe el valor en USD de cada moneda. Ejemplo: <code>USD=1,MXN=0.05926,BOB=0.145</code>.",
    }
    prompt = prompts.get(key)
    if prompt is None:
        await callback.answer("Configuracion no disponible.", show_alert=True)
        return
    await state.set_state(AdminConfigStates.waiting_value)
    await state.update_data(config_key=key)
    await callback.message.answer(
        f"<b>Editar configuracion</b>\n\n{prompt}",
        reply_markup=back_admin_keyboard("adm:config", "Cancelar edicion"),
    )
    await callback.answer()


@router.message(AdminConfigStates.waiting_value)
async def receive_admin_config_value(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, message.from_user.id, settings, Role.OWNER)
    data = await state.get_data()
    actor = await get_or_create_user(session, message.from_user)
    try:
        await update_runtime_setting(
            session,
            settings=settings,
            key=str(data["config_key"]),
            raw_value=message.text or "",
            actor=actor,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.clear()
    await message.answer(
        "Configuracion actualizada y aplicada.",
        reply_markup=back_admin_keyboard("adm:config", "Volver a configuracion"),
    )


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
    requests = await list_pending_payment_requests(session, limit=20)
    await callback.message.edit_text(
        "<b>Aprobaciones pendientes</b>\n\n"
        f"Solicitudes mostradas: <b>{len(requests)}</b>\n\n"
        + ("Selecciona una solicitud para ver sus datos y comprobante." if requests else "No hay pagos pendientes."),
        reply_markup=pending_payments_keyboard(requests),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:pending:view:"))
async def cb_pending_payment_detail(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_permission(session, callback.from_user.id, settings, "review_payments")
    request = await get_payment_request(session, int(callback.data.rsplit(":", 1)[-1]))
    if request is None or request.status != PaymentRequestStatus.PENDING:
        await callback.answer("La solicitud ya no esta pendiente.", show_alert=True)
        return
    caption = (
        f"<b>Solicitud #{request.id}</b>\n\n"
        f"Usuario: {h(request.user.display_name)}\n"
        f"Telegram ID: <code>{request.user.telegram_id}</code>\n"
        f"Plan: <b>{h(request.plan.name)}</b>\n"
        f"Metodo: {h(request.payment_method.name)}\n"
        f"Monto: <b>{money(request.amount, request.currency)}</b>\n"
        f"Fecha: {human_datetime(request.submitted_at, settings.app_timezone)}\n"
        f"Tipo: {'Renovacion' if request.metadata_json.get('request_kind') == 'renewal' else 'Compra'}"
    )
    keyboard = pending_payment_detail_keyboard(request.id, request.user.telegram_id)
    if request.proof_file_id and request.proof_kind == ProofKind.PHOTO:
        await callback.message.answer_photo(request.proof_file_id, caption=caption, reply_markup=keyboard)
    elif request.proof_file_id:
        await callback.message.answer_document(request.proof_file_id, caption=caption, reply_markup=keyboard)
    else:
        await callback.message.answer(caption + "\n\nSin comprobante adjunto.", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.in_({"adm:subs:active", "adm:subs:expired"}))
async def cb_subscription_status(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    status = MembershipStatus.ACTIVE if callback.data.endswith("active") else MembershipStatus.EXPIRED
    memberships = (
        await session.scalars(
            select(Membership)
            .options(selectinload(Membership.user), selectinload(Membership.plan))
            .where(Membership.status == status)
            .order_by(Membership.expires_at.desc())
            .limit(15)
        )
    ).all()
    lines = [
        f"- {h(item.user.display_name)} | {h(item.plan.name)} | {human_datetime(item.expires_at, settings.app_timezone)}"
        for item in memberships
    ]
    await callback.message.edit_text(
        f"<b>{'Suscripciones activas' if status == MembershipStatus.ACTIVE else 'Suscripciones expiradas'}</b>\n\n"
        f"Mostradas: <b>{len(memberships)}</b>\n\n"
        + ("\n".join(lines) if lines else "Sin resultados."),
        reply_markup=back_admin_keyboard("adm:section:operations", "Volver a operacion"),
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
        "<b>Estado del sistema</b>\n\n"
        "PostgreSQL: <b>OK</b>\n"
        f"Bot API: <b>OK</b> <code>{bot_info.id}</code> @{h(bot_info.username or '-')}\n"
        f"Webhook: <code>{h(webhook.url or '-')}</code>\n"
        f"Actualizaciones pendientes: <code>{webhook.pending_update_count}</code>\n"
        f"Entorno: <code>{h(settings.app_env)}</code>\n\n"
        "<b>Permisos de canales y grupos</b>\n"
        + "\n".join(chat_lines),
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:scheduler")
async def cb_scheduler_status(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "view_stats")
    await callback.message.edit_text(
        "<b>Estado del scheduler</b>\n\n"
        f"Activo: <code>{settings.scheduler_enabled}</code>\n"
        f"Revision de vencimientos: <code>{settings.expire_check_minutes} min</code>\n"
        f"Revision de recordatorios: <code>{settings.reminder_check_minutes} min</code>"
        f"\nReemision de enlaces: <code>{max(1, settings.expired_link_reissue_hours)} h</code>",
        reply_markup=back_admin_keyboard(),
    )
    await callback.answer()


def _admin_menu_text(role: Role, language: str = "es") -> str:
    translations = {
        "en": ("Administration panel", "Active role", "Choose an area:"),
        "pt": ("Painel administrativo", "Funcao ativa", "Selecione uma area:"),
    }
    title, role_label, prompt = translations.get(
        language,
        ("Panel administrativo", "Rol activo", "Selecciona un area:"),
    )
    return f"<b>{title}</b>\n\n{role_label}: <b>{role.value}</b>\n{prompt}"
