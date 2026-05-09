from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.keyboards.admin import (
    admin_plan_detail_keyboard,
    admin_plans_keyboard,
    back_admin_keyboard,
    payment_methods_admin_keyboard,
)
from app.models.enums import PaymentProvider, Role
from app.services.admins import require_role
from app.services.payment_methods import (
    create_payment_method,
    list_payment_methods,
    toggle_payment_method,
)
from app.services.plans import (
    create_plan,
    delete_plan,
    get_plan,
    link_channel_to_plan,
    link_group_to_plan,
    list_plans,
    set_plan_payment_message,
    toggle_plan,
)
from app.services.users import get_or_create_user
from app.states.admin import AdminPaymentMethodStates, AdminPlanStates
from app.utils.text import h, money
from app.utils.validators import parse_decimal, parse_positive_int
from app.models.channel import Channel
from app.models.group import TelegramGroup

router = Router(name="admin_catalog")


@router.callback_query(F.data == "adm:plans")
async def cb_admin_plans(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    plans = await list_plans(session)
    await callback.message.edit_text(
        "<b>Planes</b>\n\nGestiona planes, estados, accesos y mensajes personalizados.",
        reply_markup=admin_plans_keyboard(plans),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:plans:create")
async def cb_create_plan(callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    await state.set_state(AdminPlanStates.waiting_create_payload)
    await callback.message.answer(
        "<b>Crear plan</b>\n\n"
        "Envia los datos en este formato:\n"
        "<code>Nombre | Precio | Moneda | Duracion dias | Descripcion</code>\n\n"
        "Ejemplo:\n"
        "<code>VIP Mensual | 19.99 | USD | 30 | Acceso completo VIP</code>"
    )
    await callback.answer()


@router.message(AdminPlanStates.waiting_create_payload)
async def receive_plan_payload(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    actor = await get_or_create_user(session, message.from_user)
    parts = [part.strip() for part in (message.text or "").split("|", 4)]
    if len(parts) != 5:
        await message.answer("Formato invalido. Usa: Nombre | Precio | Moneda | Duracion dias | Descripcion")
        return
    try:
        name, price_raw, currency, duration_raw, description = parts
        plan = await create_plan(
            session,
            name=name,
            description=description,
            price=parse_decimal(price_raw),
            duration_days=parse_positive_int(duration_raw, "duracion"),
            currency=currency,
            actor=actor,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await state.clear()
    await message.answer(f"Plan creado: <b>{h(plan.name)}</b>")


@router.callback_query(F.data.startswith("adm:plans:view:"))
async def cb_view_admin_plan(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    plan_id = int(callback.data.split(":")[-1])
    plan = await get_plan(session, plan_id)
    if plan is None:
        await callback.answer("Plan no encontrado.", show_alert=True)
        return
    await callback.message.edit_text(_plan_admin_text(plan), reply_markup=admin_plan_detail_keyboard(plan.id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:plans:toggle:"))
async def cb_toggle_plan(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    actor = await get_or_create_user(session, callback.from_user)
    plan = await toggle_plan(session, int(callback.data.split(":")[-1]), actor=actor)
    await callback.message.edit_text(_plan_admin_text(plan), reply_markup=admin_plan_detail_keyboard(plan.id))
    await callback.answer("Estado actualizado.")


@router.callback_query(F.data.startswith("adm:plans:delete:"))
async def cb_delete_plan(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    actor = await get_or_create_user(session, callback.from_user)
    await delete_plan(session, int(callback.data.split(":")[-1]), actor=actor)
    await callback.answer("Plan desactivado.")
    plans = await list_plans(session)
    await callback.message.edit_text("<b>Planes</b>", reply_markup=admin_plans_keyboard(plans))


@router.callback_query(F.data.startswith("adm:plans:link_channel:"))
async def cb_link_channel_prompt(callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    plan_id = int(callback.data.split(":")[-1])
    channels = (await session.scalars(select(Channel).order_by(Channel.title))).all()
    lines = [f"<code>{channel.id}</code> - {h(channel.title)} ({channel.telegram_chat_id})" for channel in channels]
    await state.set_state(AdminPlanStates.waiting_link_channel)
    await state.update_data(plan_id=plan_id)
    await callback.message.answer(
        "<b>Vincular canal</b>\n\n"
        + ("\n".join(lines) if lines else "No hay canales registrados.")
        + "\n\nEnvia el ID interno del canal."
    )
    await callback.answer()


@router.message(AdminPlanStates.waiting_link_channel)
async def receive_link_channel(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    actor = await get_or_create_user(session, message.from_user)
    data = await state.get_data()
    try:
        plan = await link_channel_to_plan(
            session,
            plan_id=int(data["plan_id"]),
            channel_id=parse_positive_int(message.text or "", "ID"),
            actor=actor,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.clear()
    await message.answer(f"Canal vinculado al plan <b>{h(plan.name)}</b>.")


@router.callback_query(F.data.startswith("adm:plans:link_group:"))
async def cb_link_group_prompt(callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    plan_id = int(callback.data.split(":")[-1])
    groups = (await session.scalars(select(TelegramGroup).order_by(TelegramGroup.title))).all()
    lines = [f"<code>{group.id}</code> - {h(group.title)} ({group.telegram_chat_id})" for group in groups]
    await state.set_state(AdminPlanStates.waiting_link_group)
    await state.update_data(plan_id=plan_id)
    await callback.message.answer(
        "<b>Vincular grupo</b>\n\n"
        + ("\n".join(lines) if lines else "No hay grupos registrados.")
        + "\n\nEnvia el ID interno del grupo."
    )
    await callback.answer()


@router.message(AdminPlanStates.waiting_link_group)
async def receive_link_group(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    actor = await get_or_create_user(session, message.from_user)
    data = await state.get_data()
    try:
        plan = await link_group_to_plan(
            session,
            plan_id=int(data["plan_id"]),
            group_id=parse_positive_int(message.text or "", "ID"),
            actor=actor,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.clear()
    await message.answer(f"Grupo vinculado al plan <b>{h(plan.name)}</b>.")


@router.callback_query(F.data.startswith("adm:plans:message:"))
async def cb_plan_message_prompt(callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    plan_id = int(callback.data.split(":")[-1])
    methods = await list_payment_methods(session)
    lines = [f"<code>{method.id}</code> - {h(method.name)}" for method in methods]
    await state.set_state(AdminPlanStates.waiting_message_template)
    await state.update_data(plan_id=plan_id)
    await callback.message.answer(
        "<b>Mensaje personalizado</b>\n\n"
        "Primera linea: ID del metodo de pago.\n"
        "Siguientes lineas: plantilla del mensaje.\n\n"
        "Metodos:\n"
        + "\n".join(lines)
        + "\n\nVariables: {username}, {plan_name}, {price}, {duration}, {payment_method}, {instructions}"
    )
    await callback.answer()


@router.message(AdminPlanStates.waiting_message_template)
async def receive_plan_message_template(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    actor = await get_or_create_user(session, message.from_user)
    data = await state.get_data()
    lines = (message.text or "").splitlines()
    if len(lines) < 2:
        await message.answer("Envia el ID del metodo en la primera linea y la plantilla debajo.")
        return
    try:
        method_id = parse_positive_int(lines[0], "metodo")
        template = "\n".join(lines[1:]).strip()
        await set_plan_payment_message(
            session,
            plan_id=int(data["plan_id"]),
            payment_method_id=method_id,
            template=template,
            actor=actor,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.clear()
    await message.answer("Mensaje personalizado actualizado.")


@router.callback_query(F.data == "adm:methods")
async def cb_admin_methods(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    methods = await list_payment_methods(session)
    await callback.message.edit_text(
        "<b>Metodos de pago</b>\n\nActiva, desactiva o crea metodos de pago.",
        reply_markup=payment_methods_admin_keyboard(methods),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:methods:create")
async def cb_create_method(callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    await state.set_state(AdminPaymentMethodStates.waiting_create_payload)
    await callback.message.answer(
        "<b>Crear metodo de pago</b>\n\n"
        "Formato:\n"
        "<code>Nombre | PROVIDER | Instrucciones</code>\n\n"
        "Providers: PAYPAL, BANK_TRANSFER, BINANCE, STRIPE, QR, CRYPTO, CUSTOM"
    )
    await callback.answer()


@router.message(AdminPaymentMethodStates.waiting_create_payload)
async def receive_method_payload(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    parts = [part.strip() for part in (message.text or "").split("|", 2)]
    if len(parts) != 3:
        await message.answer("Formato invalido. Usa: Nombre | PROVIDER | Instrucciones")
        return
    try:
        provider = PaymentProvider(parts[1].upper())
    except ValueError:
        await message.answer("Provider invalido.")
        return
    method = await create_payment_method(
        session,
        name=parts[0],
        provider=provider,
        instructions=parts[2],
    )
    await state.clear()
    await message.answer(f"Metodo creado: <b>{h(method.name)}</b>")


@router.callback_query(F.data.startswith("adm:methods:toggle:"))
async def cb_toggle_method(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    await toggle_payment_method(session, int(callback.data.split(":")[-1]))
    methods = await list_payment_methods(session)
    await callback.message.edit_text(
        "<b>Metodos de pago</b>",
        reply_markup=payment_methods_admin_keyboard(methods),
    )
    await callback.answer("Estado actualizado.")


def _plan_admin_text(plan) -> str:
    channels = ", ".join(f"{item.title}#{item.id}" for item in plan.channels) or "-"
    groups = ", ".join(f"{item.title}#{item.id}" for item in plan.groups) or "-"
    methods = ", ".join(f"{item.name}#{item.id}" for item in plan.payment_methods) or "-"
    return (
        f"<b>{h(plan.name)}</b>\n\n"
        f"Estado: <b>{'Activo' if plan.is_active else 'Inactivo'}</b>\n"
        f"Precio: <b>{money(plan.price, plan.currency)}</b>\n"
        f"Duracion: <b>{plan.duration_days} dias</b>\n"
        f"Slug: <code>{h(plan.slug)}</code>\n\n"
        f"Canales: {h(channels)}\n"
        f"Grupos: {h(groups)}\n"
        f"Metodos: {h(methods)}"
    )

