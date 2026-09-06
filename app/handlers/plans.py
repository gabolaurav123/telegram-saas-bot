from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.user import payment_methods_keyboard, plan_detail_keyboard, plans_keyboard
from app.models.enums import CRMStatus
from app.services.crm import record_funnel_event, set_crm_status
from app.services.plans import get_plan, list_plans
from app.services.users import get_or_create_user
from app.utils.i18n import t
from app.utils.text import h, money

router = Router(name="plans")


@router.message(Command("plans"))
async def cmd_plans(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user)
    plans = await list_plans(session, only_active=True)
    await message.answer(_plans_text(plans, user.preferred_language), reply_markup=plans_keyboard(plans, user.preferred_language))


@router.callback_query(F.data == "main:plans")
async def cb_plans(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user)
    plans = await list_plans(session, only_active=True)
    await callback.message.edit_text(
        _plans_text(plans, user.preferred_language),
        reply_markup=plans_keyboard(plans, user.preferred_language),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("plan:view:"))
async def cb_plan_view(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user)
    plan_id = int(callback.data.split(":")[-1])
    plan = await get_plan(session, plan_id)
    if plan is None or not plan.is_active:
        await callback.answer("Plan no disponible.", show_alert=True)
        return
    await set_crm_status(session, user=user, status=CRMStatus.PLAN_VIEWED, reason="plan_viewed")
    await record_funnel_event(session, user=user, event_name="PLAN_VIEWED", plan_id=plan.id)

    channels_count = len([item for item in plan.channels if item.is_active])
    groups_count = len([item for item in plan.groups if item.is_active])
    text = (
        f"<b>{h(plan.name)}</b>\n\n"
        f"{h(plan.description or t(user.preferred_language, 'plan.no_description'))}\n\n"
        f"{t(user.preferred_language, 'plan.price')}: <b>{money(plan.price, plan.currency)}</b>\n"
        f"{t(user.preferred_language, 'plan.duration')}: <b>{plan.duration_days} dias</b>\n"
        f"{t(user.preferred_language, 'plan.accesses')}: "
        f"{t(user.preferred_language, 'plan.channels_groups', channels=channels_count, groups=groups_count)}"
    )
    await callback.message.edit_text(text, reply_markup=plan_detail_keyboard(plan.id, user.preferred_language))
    await callback.answer()


@router.callback_query(F.data.startswith("plan:buy:"))
async def cb_plan_buy(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user)
    plan_id = int(callback.data.split(":")[-1])
    plan = await get_plan(session, plan_id)
    if plan is None or not plan.is_active:
        await callback.answer(t(user.preferred_language, "plan.unavailable"), show_alert=True)
        return
    await set_crm_status(session, user=user, status=CRMStatus.PLAN_SELECTED, reason="plan_selected")
    await record_funnel_event(session, user=user, event_name="PLAN_SELECTED", plan_id=plan.id)
    methods = [method for method in plan.payment_methods if method.is_active]
    if not methods:
        await callback.answer(t(user.preferred_language, "plan.no_methods"), show_alert=True)
        return
    await callback.message.edit_text(
        t(user.preferred_language, "plan.select_payment", plan=h(plan.name)),
        reply_markup=payment_methods_keyboard(plan.id, methods, user.preferred_language),
    )
    await callback.answer()


def _plans_text(plans: list, language: str) -> str:
    if not plans:
        return t(language, "plans.empty")
    return t(language, "plans.title")
