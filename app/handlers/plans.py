from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.user import payment_methods_keyboard, plan_detail_keyboard, plans_keyboard
from app.services.plans import get_plan, list_plans
from app.services.users import get_or_create_user
from app.utils.text import h, money

router = Router(name="plans")


@router.message(Command("plans"))
async def cmd_plans(message: Message, session: AsyncSession) -> None:
    await get_or_create_user(session, message.from_user)
    plans = await list_plans(session, only_active=True)
    await message.answer(_plans_text(plans), reply_markup=plans_keyboard(plans))


@router.callback_query(F.data == "main:plans")
async def cb_plans(callback: CallbackQuery, session: AsyncSession) -> None:
    await get_or_create_user(session, callback.from_user)
    plans = await list_plans(session, only_active=True)
    await callback.message.edit_text(_plans_text(plans), reply_markup=plans_keyboard(plans))
    await callback.answer()


@router.callback_query(F.data.startswith("plan:view:"))
async def cb_plan_view(callback: CallbackQuery, session: AsyncSession) -> None:
    plan_id = int(callback.data.split(":")[-1])
    plan = await get_plan(session, plan_id)
    if plan is None or not plan.is_active:
        await callback.answer("Plan no disponible.", show_alert=True)
        return

    channels_count = len([item for item in plan.channels if item.is_active])
    groups_count = len([item for item in plan.groups if item.is_active])
    text = (
        f"<b>{h(plan.name)}</b>\n\n"
        f"{h(plan.description or 'Sin descripcion')}\n\n"
        f"Precio: <b>{money(plan.price, plan.currency)}</b>\n"
        f"Duracion: <b>{plan.duration_days} dias</b>\n"
        f"Accesos incluidos: {channels_count} canal(es), {groups_count} grupo(s)"
    )
    await callback.message.edit_text(text, reply_markup=plan_detail_keyboard(plan.id))
    await callback.answer()


@router.callback_query(F.data.startswith("plan:buy:"))
async def cb_plan_buy(callback: CallbackQuery, session: AsyncSession) -> None:
    plan_id = int(callback.data.split(":")[-1])
    plan = await get_plan(session, plan_id)
    if plan is None or not plan.is_active:
        await callback.answer("Plan no disponible.", show_alert=True)
        return
    methods = [method for method in plan.payment_methods if method.is_active]
    if not methods:
        await callback.answer("Este plan no tiene metodos de pago activos.", show_alert=True)
        return
    await callback.message.edit_text(
        f"<b>{h(plan.name)}</b>\n\nSelecciona el metodo de pago:",
        reply_markup=payment_methods_keyboard(plan.id, methods),
    )
    await callback.answer()


def _plans_text(plans: list) -> str:
    if not plans:
        return "<b>Planes</b>\n\nNo hay planes activos por ahora."
    return "<b>Planes disponibles</b>\n\nSelecciona un plan para ver detalles y comprar."

