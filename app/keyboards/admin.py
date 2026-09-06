from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.admin import Admin
from app.models.channel import Channel
from app.models.enums import Role
from app.models.growth import Coupon
from app.models.group import TelegramGroup
from app.models.payment_method import PaymentMethod
from app.models.payment_request import PaymentRequest
from app.models.plan import Plan
from app.models.quick_reply import QuickReply
from app.services.admins import permissions_for
from app.utils.i18n import LANGUAGE_LABELS
from app.utils.text import money


def admin_menu_keyboard(
    role: Role,
    mini_app_admin_url: str | None = None,
    language: str = "es",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    permissions = permissions_for(role)
    if permissions.review_payments or permissions.support:
        builder.button(
            text=_admin_text(language, "Operacion", "Operations", "Operacao"),
            callback_data="adm:section:operations",
        )
    if permissions.manage_catalog:
        builder.button(
            text=_admin_text(language, "Catalogo y accesos", "Catalog and access", "Catalogo e acessos"),
            callback_data="adm:section:catalog",
        )
    if permissions.view_stats or permissions.support:
        builder.button(
            text=_admin_text(language, "Clientes y soporte", "Clients and support", "Clientes e suporte"),
            callback_data="adm:section:clients",
        )
    if permissions.view_stats:
        builder.button(
            text=_admin_text(language, "Crecimiento", "Growth", "Crescimento"),
            callback_data="adm:section:growth",
        )
        builder.button(
            text=_admin_text(language, "Sistema", "System", "Sistema"),
            callback_data="adm:section:system",
        )
    if mini_app_admin_url and permissions.view_stats:
        builder.button(
            text=_admin_text(language, "Abrir Mini App", "Open Mini App", "Abrir Mini App"),
            web_app=WebAppInfo(url=mini_app_admin_url),
        )
    builder.button(
        text=_admin_text(language, "Idioma del panel", "Panel language", "Idioma do painel"),
        callback_data="adm:language",
    )
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def admin_section_keyboard(section: str, role: Role, language: str = "es") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    permissions = permissions_for(role)
    if section == "operations":
        if permissions.review_payments:
            builder.button(text="Aprobaciones pendientes", callback_data="adm:pending")
        if permissions.support:
            builder.button(text="Bandeja de soporte", callback_data="adm:inbox")
        if permissions.view_stats:
            builder.button(text="Suscripciones activas", callback_data="adm:subs:active")
            builder.button(text="Suscripciones expiradas", callback_data="adm:subs:expired")
        if permissions.manage_catalog:
            builder.button(text="Enlaces de invitacion", callback_data="adm:links")
        if permissions.broadcast:
            builder.button(text="Crear difusion", callback_data="adm:broadcast")
    elif section == "catalog" and permissions.manage_catalog:
        builder.button(text="Planes", callback_data="adm:plans")
        builder.button(text="Metodos de pago", callback_data="adm:methods")
        builder.button(text="Canales y grupos", callback_data="adm:chats")
        builder.button(text="Mensajes automaticos", callback_data="adm:messages")
    elif section == "clients":
        if permissions.view_stats:
            builder.button(text="Usuarios", callback_data="adm:users")
            builder.button(text="Estadisticas", callback_data="adm:stats")
            builder.button(text="Exportar clientes", callback_data="adm:export")
        if permissions.support:
            builder.button(text="Bandeja de soporte", callback_data="adm:inbox")
            builder.button(text="Respuestas rapidas", callback_data="adm:quickreplies")
    elif section == "growth" and permissions.view_stats:
        builder.button(text="Analitica", callback_data="adm:analytics")
        builder.button(text="Embudo", callback_data="adm:funnel")
        builder.button(text="Retencion", callback_data="adm:retention")
        builder.button(text="Cupones", callback_data="adm:coupons")
        builder.button(text="Referidos", callback_data="adm:referrals")
        builder.button(text="Automatizaciones", callback_data="adm:automations")
    elif section == "system" and permissions.view_stats:
        if permissions.manage_admins:
            builder.button(text="Administradores", callback_data="adm:admins")
        if permissions.manage_settings:
            builder.button(text="Configuracion", callback_data="adm:config")
            builder.button(text="Backups", callback_data="adm:backups")
        builder.button(text="Logs", callback_data="adm:logs")
        builder.button(text="Estado del sistema", callback_data="adm:health")
        builder.button(text="Estado del scheduler", callback_data="adm:scheduler")
    builder.button(
        text=_admin_text(language, "Volver al panel", "Back to panel", "Voltar ao painel"),
        callback_data="adm:menu",
    )
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def admin_language_keyboard(current_language: str, supported_languages: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code in supported_languages:
        normalized = code.lower().strip()
        selected = "ON " if normalized == current_language else ""
        builder.button(
            text=f"{selected}{LANGUAGE_LABELS.get(normalized, normalized.upper())}",
            callback_data=f"adm:lang:set:{normalized}",
        )
    builder.button(text="Volver al panel", callback_data="adm:menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_config_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Marca publica", callback_data="adm:config:set:brand")
    builder.button(text="URL de soporte", callback_data="adm:config:set:support_url")
    builder.button(text="URL de FAQ", callback_data="adm:config:set:faq_url")
    builder.button(text="Idioma predeterminado", callback_data="adm:config:set:default_language")
    builder.button(text="Stars por USD", callback_data="adm:config:set:stars_per_usd")
    builder.button(text="Tasas a USD", callback_data="adm:config:set:currency_rates")
    builder.button(text="Volver", callback_data="adm:section:system")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def coupons_keyboard(coupons: list[Coupon]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Crear cupon", callback_data="adm:coupon:create")
    for coupon in coupons:
        status = "ON" if coupon.enabled else "OFF"
        builder.button(
            text=f"{status} {coupon.code} - {coupon.value:g}",
            callback_data=f"adm:coupon:toggle:{coupon.id}",
        )
    builder.button(text="Volver", callback_data="adm:section:growth")
    builder.adjust(1)
    return builder.as_markup()


def coupon_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Porcentaje", callback_data="adm:coupon:type:PERCENTAGE")
    builder.button(text="Monto fijo", callback_data="adm:coupon:type:FIXED")
    builder.button(text="Cancelar", callback_data="adm:coupons")
    builder.adjust(2, 1)
    return builder.as_markup()


def coupon_plan_keyboard(plans: list[Plan]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Todos los planes", callback_data="adm:coupon:plan:all")
    for plan in plans:
        builder.button(text=plan.name, callback_data=f"adm:coupon:plan:{plan.id}")
    builder.button(text="Cancelar", callback_data="adm:coupons")
    builder.adjust(1)
    return builder.as_markup()


def pending_payments_keyboard(requests: list[PaymentRequest]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for request in requests:
        user_name = request.user.display_name[:18]
        plan_name = request.plan.name[:18]
        builder.button(
            text=f"#{request.id} | {user_name} | {plan_name}",
            callback_data=f"adm:pending:view:{request.id}",
        )
    builder.button(text="Actualizar", callback_data="adm:pending")
    builder.button(text="Volver", callback_data="adm:section:operations")
    builder.adjust(1)
    return builder.as_markup()


def pending_payment_detail_keyboard(request_id: int, user_telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Aprobar", callback_data=f"adm:pay:ok:{request_id}")
    builder.button(text="Rechazar", callback_data=f"adm:pay:no:{request_id}")
    builder.button(text="Banear", callback_data=f"adm:pay:ban:{request_id}")
    builder.button(text="Contactar", url=f"tg://user?id={user_telegram_id}")
    builder.button(text="Volver a pendientes", callback_data="adm:pending")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def _admin_text(language: str, es: str, en: str, pt: str) -> str:
    return {"en": en, "pt": pt}.get(language, es)


def broadcast_targets_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Todos los usuarios", callback_data="bc:t:all")
    builder.button(text="Usuarios activos hoy", callback_data="bc:t:active_today")
    builder.button(text="Con suscripcion activa", callback_data="bc:t:subscribed")
    builder.button(text="Sin suscripcion", callback_data="bc:t:unsubscribed")
    builder.button(text="Expirados", callback_data="bc:t:expired")
    builder.button(text="Plan especifico", callback_data="bc:t:plan")
    builder.button(text="Cancelar", callback_data="adm:section:operations")
    builder.adjust(1)
    return builder.as_markup()


def export_clients_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Todos", callback_data="export:all")
    builder.button(text="Activos", callback_data="export:active")
    builder.button(text="Expirados", callback_data="export:expired")
    builder.button(text="Por plan", callback_data="export:plan")
    builder.button(text="Por fecha", callback_data="export:date")
    builder.button(text="Volver", callback_data="adm:section:clients")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def plan_select_keyboard(
    plans: list[Plan],
    prefix: str,
    *,
    back_callback: str = "adm:menu",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        builder.button(text=plan.name, callback_data=f"{prefix}:{plan.id}")
    builder.button(text="Cancelar", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def addmember_chat_keyboard(plan_id: int, channels: list, groups: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for channel in channels:
        builder.button(text=f"Canal: {channel.title}", callback_data=f"addm:chat:channel:{plan_id}:{channel.id}")
    for group in groups:
        builder.button(text=f"Grupo: {group.title}", callback_data=f"addm:chat:group:{plan_id}:{group.id}")
    builder.button(text="Cancelar", callback_data="adm:section:operations")
    builder.adjust(1)
    return builder.as_markup()


def generated_links_keyboard(link_ids: list[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for link_id in link_ids:
        builder.button(text=f"Revocar #{link_id}", callback_data=f"link:revoke:{link_id}")
        builder.button(text=f"Reemitir #{link_id}", callback_data=f"link:reissue:{link_id}")
    builder.button(text="Volver", callback_data="adm:section:operations")
    builder.adjust(2, 1)
    return builder.as_markup()


def payment_review_keyboard(request_id: int, user_telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Aprobar", callback_data=f"adm:pay:ok:{request_id}")
    builder.button(text="Rechazar", callback_data=f"adm:pay:no:{request_id}")
    builder.button(text="Banear", callback_data=f"adm:pay:ban:{request_id}")
    builder.button(text="Contactar usuario", url=f"tg://user?id={user_telegram_id}")
    builder.adjust(2)
    return builder.as_markup()


def admin_plans_keyboard(plans: list[Plan]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Crear plan", callback_data="adm:plans:create")
    for plan in plans:
        status = "ON" if plan.is_active else "OFF"
        builder.button(
            text=f"{status} {plan.name} - {money(plan.price, plan.currency)}",
            callback_data=f"adm:plans:view:{plan.id}",
        )
    builder.button(text="Volver", callback_data="adm:section:catalog")
    builder.adjust(1)
    return builder.as_markup()


def admin_plan_detail_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Activar/desactivar", callback_data=f"adm:plans:toggle:{plan_id}")
    builder.button(text="Metodos del plan", callback_data=f"adm:plans:methods:{plan_id}")
    builder.button(text="Vincular canal", callback_data=f"adm:plans:link_channel:{plan_id}")
    builder.button(text="Vincular grupo", callback_data=f"adm:plans:link_group:{plan_id}")
    builder.button(text="Mensaje por metodo", callback_data=f"adm:plans:message:{plan_id}")
    builder.button(text="Eliminar", callback_data=f"adm:plans:delete:{plan_id}")
    builder.button(text="Volver", callback_data="adm:plans")
    builder.adjust(1)
    return builder.as_markup()


def plan_payment_methods_keyboard(plan: Plan, methods: list[PaymentMethod]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    enabled_ids = {method.id for method in plan.payment_methods}
    for method in methods:
        status = "ON" if method.id in enabled_ids and method.is_active else "OFF"
        builder.button(
            text=f"{status} {method.name}",
            callback_data=f"adm:plans:method_toggle:{plan.id}:{method.id}",
        )
    builder.button(text="Volver al plan", callback_data=f"adm:plans:view:{plan.id}")
    builder.adjust(1)
    return builder.as_markup()


def payment_methods_admin_keyboard(methods: list[PaymentMethod]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Crear metodo", callback_data="adm:methods:create")
    for method in methods:
        status = "ON" if method.is_active else "OFF"
        builder.button(text=f"{status} {method.name}", callback_data=f"adm:methods:toggle:{method.id}")
    builder.button(text="Volver", callback_data="adm:section:catalog")
    builder.adjust(1)
    return builder.as_markup()


def chats_admin_keyboard(channels: list[Channel], groups: list[TelegramGroup]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Registrar chat manual", callback_data="adm:chats:create")
    for channel in channels:
        status = "ON" if channel.is_active else "OFF"
        builder.button(
            text=f"{status} Canal: {channel.title}",
            callback_data=f"adm:chats:toggle:channel:{channel.id}",
        )
    for group in groups:
        status = "ON" if group.is_active else "OFF"
        builder.button(
            text=f"{status} Grupo: {group.title}",
            callback_data=f"adm:chats:toggle:group:{group.id}",
        )
    builder.button(text="Volver", callback_data="adm:section:catalog")
    builder.adjust(1)
    return builder.as_markup()


def admins_keyboard(admins: list[Admin]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Agregar admin", callback_data="adm:admins:add")
    builder.button(text="Eliminar admin", callback_data="adm:admins:remove")
    for admin in admins:
        builder.button(
            text=f"{admin.role.value}: {admin.user.display_name}",
            callback_data=f"adm:admins:view:{admin.id}",
        )
    builder.button(text="Volver", callback_data="adm:section:system")
    builder.adjust(1)
    return builder.as_markup()


def admin_detail_keyboard(admin_id: int, current_role: Role) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role in (Role.OWNER, Role.ADMIN, Role.MODERATOR, Role.PAYMENTS, Role.SUPPORT, Role.SALES, Role.READ_ONLY):
        status = "ON " if role == current_role else ""
        builder.button(
            text=f"{status}{role.value}",
            callback_data=f"adm:admins:role:{admin_id}:{role.value}",
        )
    builder.button(text="Volver", callback_data="adm:admins")
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


def user_admin_actions_keyboard(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Enviar mensaje", callback_data=f"user:msg:{user_id}")
    builder.button(text="Agregar nota", callback_data=f"user:note:{user_id}")
    builder.button(text="Agregar tag", callback_data=f"user:tag:{user_id}")
    builder.button(text="Marcar VIP", callback_data=f"user:vip:{user_id}")
    builder.button(text="Bloquear CRM", callback_data=f"user:block:{user_id}")
    builder.button(text="Reactivar CRM", callback_data=f"user:reactivate:{user_id}")
    builder.button(text="Volver al panel", callback_data="adm:menu")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def quick_replies_keyboard(replies: list[QuickReply]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Crear respuesta rapida", callback_data="qr:create")
    for reply in replies:
        status = "ON" if reply.is_active else "OFF"
        builder.button(
            text=f"{status} {reply.command} - {reply.title}",
            callback_data=f"qr:toggle:{reply.id}",
        )
    builder.button(text="Volver", callback_data="adm:section:clients")
    builder.adjust(1)
    return builder.as_markup()


def back_admin_keyboard(
    callback_data: str = "adm:menu",
    text: str = "Volver al panel",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data=callback_data)
    return builder.as_markup()
