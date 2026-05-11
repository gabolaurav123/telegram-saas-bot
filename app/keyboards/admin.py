from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.admin import Admin
from app.models.channel import Channel
from app.models.enums import Role
from app.models.group import TelegramGroup
from app.models.payment_method import PaymentMethod
from app.models.plan import Plan
from app.utils.text import money


def admin_menu_keyboard(role: Role) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Planes", callback_data="adm:plans")
    builder.button(text="Metodos de pago", callback_data="adm:methods")
    builder.button(text="Pending approvals", callback_data="adm:pending")
    builder.button(text="Administradores", callback_data="adm:admins")
    builder.button(text="Canales y grupos", callback_data="adm:chats")
    builder.button(text="Estadisticas", callback_data="adm:stats")
    builder.button(text="Payment stats", callback_data="adm:stats")
    builder.button(text="User stats", callback_data="adm:stats")
    builder.button(text="Active subscriptions", callback_data="adm:subs:active")
    builder.button(text="Expired subscriptions", callback_data="adm:subs:expired")
    builder.button(text="Invite links", callback_data="adm:links")
    builder.button(text="Broadcast", callback_data="adm:broadcast")
    builder.button(text="Export clients", callback_data="adm:export")
    builder.button(text="System health", callback_data="adm:health")
    builder.button(text="Scheduler status", callback_data="adm:scheduler")
    builder.button(text="Usuarios", callback_data="adm:users")
    builder.button(text="Configuracion", callback_data="adm:config")
    builder.button(text="Logs", callback_data="adm:logs")
    builder.button(text="Mensajes automaticos", callback_data="adm:messages")
    builder.button(text="Backups", callback_data="adm:backups")
    builder.adjust(2)
    return builder.as_markup()


def broadcast_targets_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Todos los usuarios", callback_data="bc:t:all")
    builder.button(text="Usuarios activos hoy", callback_data="bc:t:active_today")
    builder.button(text="Con suscripcion activa", callback_data="bc:t:subscribed")
    builder.button(text="Sin suscripcion", callback_data="bc:t:unsubscribed")
    builder.button(text="Expirados", callback_data="bc:t:expired")
    builder.button(text="Plan especifico", callback_data="bc:t:plan")
    builder.button(text="Cancelar", callback_data="adm:menu")
    builder.adjust(1)
    return builder.as_markup()


def export_clients_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Todos", callback_data="export:all")
    builder.button(text="Activos", callback_data="export:active")
    builder.button(text="Expirados", callback_data="export:expired")
    builder.button(text="Por plan", callback_data="export:plan")
    builder.button(text="Por fecha", callback_data="export:date")
    builder.button(text="Volver", callback_data="adm:menu")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def plan_select_keyboard(plans: list[Plan], prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        builder.button(text=plan.name, callback_data=f"{prefix}:{plan.id}")
    builder.button(text="Cancelar", callback_data="adm:menu")
    builder.adjust(1)
    return builder.as_markup()


def addmember_chat_keyboard(plan_id: int, channels: list, groups: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for channel in channels:
        builder.button(text=f"Canal: {channel.title}", callback_data=f"addm:chat:channel:{plan_id}:{channel.id}")
    for group in groups:
        builder.button(text=f"Grupo: {group.title}", callback_data=f"addm:chat:group:{plan_id}:{group.id}")
    builder.button(text="Cancelar", callback_data="adm:menu")
    builder.adjust(1)
    return builder.as_markup()


def generated_links_keyboard(link_ids: list[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for link_id in link_ids:
        builder.button(text=f"Revocar #{link_id}", callback_data=f"link:revoke:{link_id}")
        builder.button(text=f"Reemitir #{link_id}", callback_data=f"link:reissue:{link_id}")
    builder.button(text="Volver", callback_data="adm:menu")
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
    builder.button(text="Volver", callback_data="adm:menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_plan_detail_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Activar/desactivar", callback_data=f"adm:plans:toggle:{plan_id}")
    builder.button(text="Vincular canal", callback_data=f"adm:plans:link_channel:{plan_id}")
    builder.button(text="Vincular grupo", callback_data=f"adm:plans:link_group:{plan_id}")
    builder.button(text="Mensaje por metodo", callback_data=f"adm:plans:message:{plan_id}")
    builder.button(text="Eliminar", callback_data=f"adm:plans:delete:{plan_id}")
    builder.button(text="Volver", callback_data="adm:plans")
    builder.adjust(1)
    return builder.as_markup()


def payment_methods_admin_keyboard(methods: list[PaymentMethod]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Crear metodo", callback_data="adm:methods:create")
    for method in methods:
        status = "ON" if method.is_active else "OFF"
        builder.button(text=f"{status} {method.name}", callback_data=f"adm:methods:toggle:{method.id}")
    builder.button(text="Volver", callback_data="adm:menu")
    builder.adjust(1)
    return builder.as_markup()


def chats_admin_keyboard(channels: list[Channel], groups: list[TelegramGroup]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Registrar chat manual", callback_data="adm:chats:create")
    for channel in channels:
        status = "ON" if channel.is_active else "OFF"
        builder.button(text=f"{status} Canal: {channel.title}", callback_data=f"adm:noop")
    for group in groups:
        status = "ON" if group.is_active else "OFF"
        builder.button(text=f"{status} Grupo: {group.title}", callback_data=f"adm:noop")
    builder.button(text="Volver", callback_data="adm:menu")
    builder.adjust(1)
    return builder.as_markup()


def admins_keyboard(admins: list[Admin]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Agregar admin", callback_data="adm:admins:add")
    builder.button(text="Eliminar admin", callback_data="adm:admins:remove")
    for admin in admins:
        builder.button(
            text=f"{admin.role.value}: {admin.user.display_name}",
            callback_data="adm:noop",
        )
    builder.button(text="Volver", callback_data="adm:menu")
    builder.adjust(1)
    return builder.as_markup()


def back_admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Volver al panel", callback_data="adm:menu")
    return builder.as_markup()
