from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.keyboards.user import main_menu_keyboard
from app.models.enums import LogAction
from app.services.crm import apply_start_attribution
from app.services.logs import log_event
from app.services.memberships import get_active_memberships
from app.services.notifications import send_admin_log
from app.services.users import get_or_create_user, get_or_create_user_with_flag
from app.utils.text import h
from app.utils.time import human_datetime, remaining_days

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    settings: Settings,
) -> None:
    user, created = await get_or_create_user_with_flag(session, message.from_user)
    referral = command.args.strip() if command.args else None
    attribution = await apply_start_attribution(
        session,
        user=user,
        raw_parameter=referral,
        is_first_start=created,
    )
    if created:
        await send_admin_log(
            bot=message.bot,
            session=session,
            settings=settings,
            title="Nuevo usuario registrado",
            lines=[
                f"Nombre: {h(user.display_name)}",
                f"Username: {h('@' + user.username if user.username else '-')}",
                f"ID: <code>{user.telegram_id}</code>",
                f"Fecha: {human_datetime(user.registered_at, settings.app_timezone)}",
                "Estado: Primer ingreso al bot",
                f"Origen: {h(attribution.source or referral) if (attribution.source or referral) else '-'}",
                f"Campana: {h(attribution.campaign) if attribution.campaign else '-'}",
                f"Referral: {h(attribution.referral) if attribution.referral else '-'}",
            ],
        )
        await log_event(
            session,
            LogAction.USER_REGISTERED,
            f"Nuevo usuario registrado: {user.telegram_id}",
            target_user_id=user.id,
            details={
                "referral": attribution.referral or referral,
                "source": attribution.source,
                "campaign": attribution.campaign,
            },
        )
    text = (
        f"<b>{h(settings.public_brand_name)}</b>\n\n"
        f"Hola {h(user.display_name)}. Desde aqui puedes comprar, renovar y revisar "
        "tu acceso premium de forma automatica.\n\n"
        "Selecciona una opcion:"
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "main:menu")
async def cb_main_menu(callback: CallbackQuery, settings: Settings) -> None:
    await callback.message.edit_text(
        f"<b>{h(settings.public_brand_name)}</b>\n\nSelecciona una opcion:",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Ayuda</b>\n\n"
        "<b>Comandos</b>\n"
        "/start - Abrir menu principal\n"
        "/plans - Ver planes disponibles\n"
        "/profile - Estado de tu membresia\n"
        "/id - Ver tu Telegram ID\n"
        "/support - Contactar soporte\n"
        "/paysupport - Ayuda con pagos\n"
        "/settings - Panel administrativo\n\n"
        "<b>Como comprar</b>\n"
        "1. Entra a /plans.\n"
        "2. Elige un plan y un metodo de pago.\n"
        "3. Sigue las instrucciones y envia tu comprobante.\n"
        "4. Un administrador aprobara o rechazara la solicitud.\n\n"
        "Tambien puedes pagar con Telegram Stars si el plan tiene ese metodo activo.\n\n"
        "<b>Renovacion</b>\n"
        "Puedes renovar desde /plans antes o despues del vencimiento.\n\n"
        "<b>Reglas</b>\n"
        "No compartas enlaces de acceso. Los links son temporales y de un solo uso."
    )


@router.message(Command("id"))
async def cmd_id(message: Message, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, message.from_user)
    await message.answer(
        "<b>Tu informacion</b>\n\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Username: {h('@' + user.username if user.username else '-')}\n"
        f"Registro: {human_datetime(user.registered_at, settings.app_timezone)}"
    )


@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, message.from_user)
    await message.answer(
        await _membership_status_text(session, user.id, settings),
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "main:membership")
async def cb_membership(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, callback.from_user)
    await callback.message.edit_text(
        await _membership_status_text(session, user.id, settings),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.message(Command("support"))
async def cmd_support(message: Message, settings: Settings) -> None:
    await message.answer(_support_text(settings), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "main:support")
async def cb_support(callback: CallbackQuery, settings: Settings) -> None:
    await callback.message.edit_text(_support_text(settings), reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "main:faq")
async def cb_faq(callback: CallbackQuery, settings: Settings) -> None:
    text = (
        "<b>FAQ</b>\n\n"
        "<b>Los links son permanentes?</b>\n"
        "No. Son temporales y de un solo uso.\n\n"
        "<b>Cuando recibo acceso?</b>\n"
        "Despues de que un administrador apruebe el comprobante.\n\n"
        "<b>Puedo renovar?</b>\n"
        "Si. Elige un plan desde /plans y envia el nuevo comprobante."
    )
    if settings.faq_url:
        text += f"\n\nFAQ completa: {h(settings.faq_url)}"
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard(), disable_web_page_preview=True)
    await callback.answer()


async def _membership_status_text(
    session: AsyncSession,
    user_id: int,
    settings: Settings,
) -> str:
    memberships = await get_active_memberships(session, user_id)
    if not memberships:
        return "<b>Estado de membresia</b>\n\nNo tienes membresias activas."

    lines = ["<b>Estado de membresia</b>\n"]
    for membership in memberships:
        lines.append(
            f"<b>{h(membership.plan.name)}</b>\n"
            f"Vence: {human_datetime(membership.expires_at, settings.app_timezone)}\n"
            f"Dias restantes: {remaining_days(membership.expires_at)}"
        )
    return "\n\n".join(lines)


def _support_text(settings: Settings) -> str:
    if settings.support_url:
        return (
            "<b>Soporte</b>\n\n"
            "Contacta al equipo desde este enlace:\n"
            f"{h(settings.support_url)}"
        )
    return (
        "<b>Soporte</b>\n\n"
        "Soporte aun no esta configurado. Pide al administrador definir SUPPORT_URL."
    )
