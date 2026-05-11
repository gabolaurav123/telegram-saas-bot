from __future__ import annotations

import logging
from collections.abc import Iterable

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.keyboards.admin import payment_review_keyboard
from app.models.admin import Admin
from app.models.enums import ProofKind
from app.models.membership import Membership
from app.models.payment_request import PaymentRequest
from app.services.admins import list_admins
from app.utils.text import h, money
from app.utils.time import human_datetime

logger = logging.getLogger(__name__)


def _unique_chat_ids(values: Iterable[int | None]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value is None or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


async def notify_admins_about_payment(
    *,
    bot: Bot,
    session: AsyncSession,
    request: PaymentRequest,
    settings: Settings,
) -> None:
    chat_ids = await admin_chat_ids(session, settings)
    if not chat_ids:
        logger.warning("No admin chat IDs configured for payment notifications")
        return

    caption = (
        "<b>Nueva solicitud de pago</b>\n\n"
        f"ID: <code>{request.id}</code>\n"
        f"Usuario: {h(request.user.display_name)}\n"
        f"Telegram ID: <code>{request.user.telegram_id}</code>\n"
        f"Plan: <b>{h(request.plan.name)}</b>\n"
        f"Metodo: {h(request.payment_method.name)}\n"
        f"Monto: {money(request.amount, request.currency)}\n"
        f"Fecha: {human_datetime(request.submitted_at, settings.app_timezone)}"
    )
    keyboard = payment_review_keyboard(request.id, request.user.telegram_id)

    for chat_id in chat_ids:
        try:
            if request.proof_kind == ProofKind.PHOTO:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=request.proof_file_id,
                    caption=caption,
                    reply_markup=keyboard,
                )
            else:
                await bot.send_document(
                    chat_id=chat_id,
                    document=request.proof_file_id,
                    caption=caption,
                    reply_markup=keyboard,
                )
        except TelegramAPIError:
            logger.exception("Could not notify admin chat %s about payment %s", chat_id, request.id)


async def admin_chat_ids(session: AsyncSession, settings: Settings) -> list[int]:
    admins: list[Admin] = await list_admins(session)
    return _unique_chat_ids(
        [
            settings.admin_notification_chat_id,
            *settings.owner_ids,
            *(admin.telegram_id for admin in admins),
        ]
    )


async def notify_admins(
    *,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool = True,
) -> list[Message]:
    messages: list[Message] = []
    chat_ids = await admin_chat_ids(session, settings)
    if not chat_ids:
        logger.warning("No admin chat IDs configured")
        return messages
    for chat_id in chat_ids:
        try:
            sent = await bot.send_message(
                chat_id,
                text,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview,
            )
        except TelegramAPIError:
            logger.exception("Could not notify admin chat %s", chat_id)
            continue
        messages.append(sent)
    return messages


async def send_admin_log(
    *,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    title: str,
    lines: list[str],
) -> list[Message]:
    text = f"<b>{h(title)}</b>\n\n" + "\n".join(lines)
    return await notify_admins(bot=bot, session=session, settings=settings, text=text)


async def send_access_links(
    *,
    bot: Bot,
    user_telegram_id: int,
    membership: Membership,
    links: list[tuple[str, str]],
    settings: Settings,
) -> None:
    if links:
        link_lines = "\n".join(f"- <b>{h(title)}</b>: {h(link)}" for title, link in links)
    else:
        link_lines = (
            "El pago fue aprobado, pero no hay canales o grupos vinculados al plan. "
            "Contacta soporte para recibir acceso."
        )
    text = (
        "<b>Pago aprobado</b>\n\n"
        f"Tu membresia <b>{h(membership.plan.name)}</b> esta activa.\n"
        f"Vence: {human_datetime(membership.expires_at, settings.app_timezone)}\n\n"
        "Enlaces temporales de un solo uso:\n"
        f"{link_lines}"
    )
    await bot.send_message(user_telegram_id, text, disable_web_page_preview=True)


async def send_payment_rejected(
    *,
    bot: Bot,
    user_telegram_id: int,
    reason: str,
) -> None:
    await bot.send_message(
        user_telegram_id,
        "<b>Comprobante rechazado</b>\n\n"
        f"Motivo: {h(reason)}\n\n"
        "Puedes iniciar la compra nuevamente desde /plans y enviar otro comprobante.",
    )


async def send_membership_reminder(
    *,
    bot: Bot,
    membership: Membership,
    days_before: int,
    settings: Settings,
) -> None:
    await bot.send_message(
        membership.user.telegram_id,
        "<b>Recordatorio de membresia</b>\n\n"
        f"Tu plan <b>{h(membership.plan.name)}</b> vence en {days_before} dia(s).\n"
        f"Fecha de vencimiento: {human_datetime(membership.expires_at, settings.app_timezone)}\n\n"
        "Puedes renovar desde el menu principal o con /plans.",
    )


async def send_membership_expired(
    *,
    bot: Bot,
    membership: Membership,
    settings: Settings,
) -> None:
    await bot.send_message(
        membership.user.telegram_id,
        "<b>Membresia vencida</b>\n\n"
        f"Tu plan <b>{h(membership.plan.name)}</b> vencio el "
        f"{human_datetime(membership.expires_at, settings.app_timezone)}.\n\n"
        "El acceso fue revocado automaticamente. Puedes renovar desde /plans.",
    )
