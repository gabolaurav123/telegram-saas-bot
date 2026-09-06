from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.keyboards.user import language_keyboard, main_menu_keyboard, support_keyboard
from app.models.enums import LogAction
from app.services.crm import apply_start_attribution
from app.services.logs import log_event
from app.services.memberships import get_active_memberships
from app.services.notifications import send_admin_log
from app.services.users import get_or_create_user, get_or_create_user_with_flag, set_preferred_language
from app.utils.i18n import t
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
        f"{t(user.preferred_language, 'start.body', name=h(user.display_name))}\n\n"
        f"{t(user.preferred_language, 'start.choose')}"
    )
    await message.answer(
        text,
        reply_markup=main_menu_keyboard(settings.mini_app_client_url, user.preferred_language),
    )


@router.callback_query(F.data == "main:menu")
async def cb_main_menu(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, callback.from_user)
    await callback.message.edit_text(
        f"<b>{h(settings.public_brand_name)}</b>\n\n{t(user.preferred_language, 'menu.choose')}",
        reply_markup=main_menu_keyboard(settings.mini_app_client_url, user.preferred_language),
    )
    await callback.answer()


@router.callback_query(F.data == "main:miniapp")
async def cb_main_miniapp(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, callback.from_user)
    if settings.mini_app_client_url:
        await callback.answer("Abre el boton Mini App del menu.", show_alert=True)
        return
    await callback.answer(
        t(user.preferred_language, "miniapp.missing"),
        show_alert=True,
    )


@router.message(Command("help"))
async def cmd_help(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user)
    await message.answer(
        f"{t(user.preferred_language, 'help.title')}\n\n"
        f"{t(user.preferred_language, 'help.commands')}\n"
        "/start - Abrir menu principal\n"
        "/plans - Ver planes disponibles\n"
        "/profile - Estado de tu membresia\n"
        "/id - Ver tu Telegram ID\n"
        "/language - Cambiar idioma\n"
        "/support - Contactar soporte\n"
        "/paysupport - Ayuda con pagos\n"
        "/settings - Panel administrativo\n\n"
        f"{t(user.preferred_language, 'help.buy_title')}\n"
        f"{t(user.preferred_language, 'help.body')}\n\n"
        f"{t(user.preferred_language, 'help.stars')}\n\n"
        f"{t(user.preferred_language, 'help.renewal_title')}\n"
        f"{t(user.preferred_language, 'help.renewal')}\n\n"
        f"{t(user.preferred_language, 'help.rules_title')}\n"
        f"{t(user.preferred_language, 'help.rules')}"
    )


@router.message(Command("language"))
async def cmd_language(message: Message, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, message.from_user)
    await message.answer(
        t(user.preferred_language, "language.title"),
        reply_markup=language_keyboard(user.preferred_language, settings.supported_languages),
    )


@router.callback_query(F.data == "lang:select")
async def cb_language_select(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, callback.from_user)
    await callback.message.edit_text(
        t(user.preferred_language, "language.title"),
        reply_markup=language_keyboard(user.preferred_language, settings.supported_languages),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lang:set:"))
async def cb_language_set(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, callback.from_user)
    selected = callback.data.split(":")[-1].lower().strip().split("-")[0]
    if selected not in settings.supported_languages:
        await callback.answer(t(user.preferred_language, "language.invalid"), show_alert=True)
        return
    user = await set_preferred_language(
        session,
        user=user,
        language=selected,
        supported_languages=settings.supported_languages,
    )
    await callback.message.edit_text(
        f"<b>{h(settings.public_brand_name)}</b>\n\n{t(user.preferred_language, 'menu.choose')}",
        reply_markup=main_menu_keyboard(settings.mini_app_client_url, user.preferred_language),
    )
    await callback.answer(t(user.preferred_language, "language.updated"))


@router.message(Command("id"))
async def cmd_id(message: Message, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, message.from_user)
    await message.answer(
        f"{t(user.preferred_language, 'id.title')}\n\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Username: {h('@' + user.username if user.username else '-')}\n"
        f"Registro: {human_datetime(user.registered_at, settings.app_timezone)}"
    )


@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, message.from_user)
    await message.answer(
        await _membership_status_text(session, user.id, settings, user.preferred_language),
        reply_markup=main_menu_keyboard(settings.mini_app_client_url, user.preferred_language),
    )


@router.callback_query(F.data == "main:membership")
async def cb_membership(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, callback.from_user)
    await callback.message.edit_text(
        await _membership_status_text(session, user.id, settings, user.preferred_language),
        reply_markup=main_menu_keyboard(settings.mini_app_client_url, user.preferred_language),
    )
    await callback.answer()


@router.message(Command("support"))
async def cmd_support(message: Message, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, message.from_user)
    await message.answer(
        _support_text(settings, user.preferred_language),
        reply_markup=support_keyboard(user.preferred_language),
    )


@router.callback_query(F.data == "main:support")
async def cb_support_with_session(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, callback.from_user)
    await callback.message.edit_text(
        _support_text(settings, user.preferred_language),
        reply_markup=support_keyboard(user.preferred_language),
    )
    await callback.answer()


@router.callback_query(F.data == "main:faq")
async def cb_faq(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, callback.from_user)
    text = t(user.preferred_language, "faq.body")
    if settings.faq_url:
        text += f"\n\nFAQ completa: {h(settings.faq_url)}"
    await callback.message.edit_text(
        text,
        reply_markup=main_menu_keyboard(settings.mini_app_client_url, user.preferred_language),
        disable_web_page_preview=True,
    )
    await callback.answer()


async def _membership_status_text(
    session: AsyncSession,
    user_id: int,
    settings: Settings,
    language: str,
) -> str:
    memberships = await get_active_memberships(session, user_id)
    if not memberships:
        return t(language, "membership.empty")

    lines = [t(language, "membership.title") + "\n"]
    for membership in memberships:
        lines.append(
            f"<b>{h(membership.plan.name)}</b>\n"
            f"Vence: {human_datetime(membership.expires_at, settings.app_timezone)}\n"
            f"Dias restantes: {remaining_days(membership.expires_at)}"
        )
    return "\n\n".join(lines)


def _support_text(settings: Settings, language: str) -> str:
    if settings.support_url:
        return t(language, "support.url", url=h(settings.support_url))
    return t(language, "support.prompt")
