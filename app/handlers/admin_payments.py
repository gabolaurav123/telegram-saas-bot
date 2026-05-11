from __future__ import annotations

import asyncio
from collections import defaultdict

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.models.enums import Role
from app.services.admins import require_role
from app.services.channels import create_invite_links_for_plan
from app.services.memberships import activate_membership
from app.services.notifications import send_access_links, send_payment_rejected
from app.services.payments import (
    get_payment_request,
    mark_payment_approved,
    mark_payment_banned,
    mark_payment_rejected,
)
from app.services.users import get_or_create_user
from app.states.admin import AdminPaymentReviewStates
from app.utils.text import h

router = Router(name="admin_payments")
PAYMENT_LOCKS: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


@router.callback_query(F.data.startswith("adm:pay:ok:"))
async def cb_approve_payment(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    admin_user = await get_or_create_user(session, callback.from_user)
    request_id = int(callback.data.split(":")[-1])
    async with PAYMENT_LOCKS[request_id]:
        request = await get_payment_request(session, request_id)
        if request is None:
            await callback.answer("Solicitud no encontrada.", show_alert=True)
            return

        try:
            await mark_payment_approved(session, request=request, admin_user=admin_user)
            links = await create_invite_links_for_plan(
                bot=callback.bot,
                plan=request.plan,
                user_telegram_id=request.user.telegram_id,
                settings=settings,
            )
            membership = await activate_membership(
                session,
                user=request.user,
                plan=request.plan,
                payment_request=request,
                access_payload={
                    "links_created": len(links),
                    "approved_by": admin_user.telegram_id,
                },
            )
            membership.plan = request.plan
            try:
                await send_access_links(
                    bot=callback.bot,
                    user_telegram_id=request.user.telegram_id,
                    membership=membership,
                    links=links,
                    settings=settings,
                )
            except TelegramAPIError:
                await callback.message.answer(
                    "Pago aprobado, pero no pude enviar el acceso al usuario. "
                    "Revisa si inicio el bot o si bloqueo mensajes privados."
                )
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return

    await _mark_admin_message(callback, f"Pago #{request.id} aprobado por {h(admin_user.display_name)}.")
    await callback.answer("Pago aprobado.")


@router.callback_query(F.data.startswith("adm:pay:no:"))
async def cb_reject_payment(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    request_id = int(callback.data.split(":")[-1])
    if await get_payment_request(session, request_id) is None:
        await callback.answer("Solicitud no encontrada.", show_alert=True)
        return
    await state.set_state(AdminPaymentReviewStates.waiting_rejection_reason)
    await state.update_data(payment_request_id=request_id)
    await callback.message.answer(
        "Escribe el motivo del rechazo. Envia <code>-</code> para usar un motivo generico."
    )
    await callback.answer()


@router.message(AdminPaymentReviewStates.waiting_rejection_reason)
async def receive_rejection_reason(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    admin_user = await get_or_create_user(session, message.from_user)
    data = await state.get_data()
    request_id = int(data["payment_request_id"])
    async with PAYMENT_LOCKS[request_id]:
        request = await get_payment_request(session, request_id)
        if request is None:
            await message.answer("Solicitud no encontrada.")
            await state.clear()
            return
        reason = (message.text or "").strip()
        if reason == "-":
            reason = "Comprobante no aprobado."
        try:
            await mark_payment_rejected(
                session,
                request=request,
                admin_user=admin_user,
                reason=reason,
            )
            try:
                await send_payment_rejected(
                    bot=message.bot,
                    user_telegram_id=request.user.telegram_id,
                    reason=request.rejection_reason,
                )
            except TelegramAPIError:
                await message.answer(
                    "Pago rechazado, pero no pude notificar al usuario por mensaje privado."
                )
        except ValueError as exc:
            await message.answer(str(exc))
        else:
            await message.answer(f"Pago #{request.id} rechazado.")
    await state.clear()


@router.callback_query(F.data.startswith("adm:pay:ban:"))
async def cb_ban_from_payment(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    admin_user = await get_or_create_user(session, callback.from_user)
    request_id = int(callback.data.split(":")[-1])
    async with PAYMENT_LOCKS[request_id]:
        request = await get_payment_request(session, request_id)
        if request is None:
            await callback.answer("Solicitud no encontrada.", show_alert=True)
            return
        await mark_payment_banned(session, request=request, admin_user=admin_user)
    await _mark_admin_message(callback, f"Usuario {h(request.user.display_name)} baneado.")
    await callback.answer("Usuario baneado.")


async def _mark_admin_message(callback: CallbackQuery, text: str) -> None:
    try:
        if callback.message.photo or callback.message.document:
            await callback.message.edit_caption(caption=text)
        else:
            await callback.message.edit_text(text)
    except Exception:
        await callback.message.answer(text)
