from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.keyboards.user import (
    cancel_purchase_keyboard,
    main_menu_keyboard,
    renewal_payment_methods_keyboard,
)
from app.models.enums import ProofKind
from app.models.membership import Membership
from app.models.plan import Plan
from app.services.notifications import notify_admins_about_payment
from app.services.payment_methods import get_payment_method
from app.services.payments import create_payment_request, get_payment_request
from app.services.plans import get_plan
from app.services.users import get_or_create_user
from app.states.purchase import PurchaseStates
from app.utils.text import DEFAULT_PAYMENT_TEMPLATE, h, money, render_template

router = Router(name="purchase")


async def _render_payment_instructions(
    *,
    callback: CallbackQuery,
    state: FSMContext,
    plan: Plan,
    method_id: int,
    session: AsyncSession,
    renewal_membership_id: int | None = None,
) -> None:
    method = await get_payment_method(session, method_id)
    if method is None or not method.is_active:
        await callback.answer("Metodo no disponible.", show_alert=True)
        return

    custom_message = next(
        (
            item.message_template
            for item in plan.payment_messages
            if item.payment_method_id == method.id
        ),
        DEFAULT_PAYMENT_TEMPLATE,
    )
    rendered = render_template(
        custom_message,
        username=callback.from_user.username or callback.from_user.full_name,
        plan_name=plan.name,
        price=money(plan.price, plan.currency),
        duration=plan.duration_days,
        payment_method=method.name,
        instructions=method.instructions,
    )

    await state.set_state(PurchaseStates.waiting_for_proof)
    await state.update_data(
        plan_id=plan.id,
        payment_method_id=method.id,
        request_kind="renewal" if renewal_membership_id else "purchase",
        renewal_membership_id=renewal_membership_id,
    )
    await callback.message.edit_text(
        f"{h(rendered)}",
        reply_markup=cancel_purchase_keyboard(),
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("paymethod:"))
async def cb_select_payment_method(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    _, plan_id_raw, method_id_raw = callback.data.split(":")
    plan = await get_plan(session, int(plan_id_raw))
    if plan is None or not plan.is_active:
        await callback.answer("Plan no disponible.", show_alert=True)
        return
    await _render_payment_instructions(
        callback=callback,
        state=state,
        plan=plan,
        method_id=int(method_id_raw),
        session=session,
    )


@router.callback_query(F.data.startswith("renew:membership:"))
async def cb_renew_membership(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    membership_id = int(callback.data.split(":")[-1])
    membership = await session.scalar(
        select(Membership)
        .options(
            selectinload(Membership.user),
            selectinload(Membership.plan).selectinload(Plan.payment_methods),
        )
        .where(Membership.id == membership_id)
    )
    if membership is None or membership.user.telegram_id != callback.from_user.id:
        await callback.answer("Membresia no encontrada.", show_alert=True)
        return
    methods = [method for method in membership.plan.payment_methods if method.is_active]
    if not methods:
        await callback.answer("Este plan no tiene metodos de pago activos.", show_alert=True)
        return
    await callback.message.edit_text(
        f"<b>Renovar {h(membership.plan.name)}</b>\n\n"
        "Selecciona metodo de pago. La renovacion queda pendiente hasta que un admin apruebe el comprobante.",
        reply_markup=renewal_payment_methods_keyboard(
            membership_id=membership.id,
            plan_id=membership.plan.id,
            methods=methods,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("renewmethod:"))
async def cb_select_renewal_payment_method(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    _, membership_id_raw, plan_id_raw, method_id_raw = callback.data.split(":")
    membership = await session.scalar(
        select(Membership)
        .options(
            selectinload(Membership.user),
            selectinload(Membership.plan).selectinload(Plan.payment_messages),
        )
        .where(Membership.id == int(membership_id_raw), Membership.plan_id == int(plan_id_raw))
    )
    if membership is None or membership.user.telegram_id != callback.from_user.id:
        await callback.answer("Membresia no encontrada.", show_alert=True)
        return
    if membership.plan is None or not membership.plan.is_active:
        await callback.answer("Plan no disponible.", show_alert=True)
        return
    await _render_payment_instructions(
        callback=callback,
        state=state,
        plan=membership.plan,
        method_id=int(method_id_raw),
        session=session,
        renewal_membership_id=membership.id,
    )


@router.callback_query(F.data == "purchase:cancel")
async def cb_cancel_purchase(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "Compra cancelada. Puedes volver al menu principal.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.message(PurchaseStates.waiting_for_proof, F.photo | F.document)
async def receive_payment_proof(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    data = await state.get_data()
    plan = await get_plan(session, int(data["plan_id"]))
    method = await get_payment_method(session, int(data["payment_method_id"]))
    user = await get_or_create_user(session, message.from_user)

    if plan is None or method is None:
        await message.answer("La compra ya no esta disponible. Inicia de nuevo desde /plans.")
        await state.clear()
        return

    if message.photo:
        photo = message.photo[-1]
        proof_kind = ProofKind.PHOTO
        file_id = photo.file_id
        unique_id = photo.file_unique_id
    elif message.document:
        proof_kind = ProofKind.DOCUMENT
        file_id = message.document.file_id
        unique_id = message.document.file_unique_id
    else:
        await message.answer("Envia una imagen o documento como comprobante.")
        return

    try:
        metadata_json = {
            "request_kind": data.get("request_kind", "purchase"),
        }
        if data.get("renewal_membership_id"):
            metadata_json["renewal_membership_id"] = int(data["renewal_membership_id"])
        request = await create_payment_request(
            session,
            user=user,
            plan=plan,
            payment_method=method,
            proof_kind=proof_kind,
            proof_file_id=file_id,
            proof_file_unique_id=unique_id,
            proof_message_id=message.message_id,
            metadata_json=metadata_json,
        )
    except ValueError as exc:
        await message.answer(str(exc), reply_markup=main_menu_keyboard())
        await state.clear()
        return

    request = await get_payment_request(session, request.id)
    await notify_admins_about_payment(
        bot=message.bot,
        session=session,
        request=request,
        settings=settings,
    )
    await message.answer(
        "<b>Comprobante recibido</b>\n\n"
        "Tu solicitud quedo pendiente de revision. Te notificaremos cuando sea aprobada o rechazada.",
        reply_markup=main_menu_keyboard(),
    )
    await state.clear()


@router.message(PurchaseStates.waiting_for_proof)
async def receive_invalid_payment_proof(message: Message) -> None:
    await message.answer(
        "Necesito una imagen o documento del comprobante.",
        reply_markup=cancel_purchase_keyboard(),
    )
