from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.keyboards.admin import broadcast_targets_keyboard, plan_select_keyboard
from app.models.enums import Role
from app.services.admins import require_permission, require_role
from app.services.broadcasts import create_broadcast_job, enqueue_broadcast
from app.services.plans import list_plans
from app.services.users import get_or_create_user
from app.states.admin import BroadcastStates

router = Router(name="admin_broadcasts")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, message.from_user.id, settings, "broadcast")
    await message.answer(
        "<b>Broadcast</b>\n\nA quien deseas enviar?",
        reply_markup=broadcast_targets_keyboard(),
    )


@router.callback_query(F.data == "adm:broadcast")
async def cb_broadcast(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "broadcast")
    await callback.message.edit_text(
        "<b>Broadcast</b>\n\nA quien deseas enviar?",
        reply_markup=broadcast_targets_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "bc:t:plan")
async def cb_broadcast_plan_target(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "broadcast")
    plans = await list_plans(session, only_active=True)
    await callback.message.edit_text(
        "<b>Broadcast por plan</b>\n\nSelecciona el plan:",
        reply_markup=plan_select_keyboard(plans, "bc:plan"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bc:plan:"))
async def cb_broadcast_plan(callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "broadcast")
    plan_id = int(callback.data.split(":")[-1])
    await state.set_state(BroadcastStates.waiting_content)
    await state.update_data(target="plan", plan_id=plan_id)
    await callback.message.answer("Envia ahora el contenido del broadcast.")
    await callback.answer()


@router.callback_query(F.data.startswith("bc:t:"))
async def cb_broadcast_target(callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    await require_permission(session, callback.from_user.id, settings, "broadcast")
    target = callback.data.split(":")[-1]
    await state.set_state(BroadcastStates.waiting_content)
    await state.update_data(target=target, plan_id=None)
    await callback.message.answer("Envia ahora el contenido del broadcast.")
    await callback.answer()


@router.message(BroadcastStates.waiting_content)
async def receive_broadcast_content(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_permission(session, message.from_user.id, settings, "broadcast")
    actor = await get_or_create_user(session, message.from_user)
    data = await state.get_data()
    job = await create_broadcast_job(
        session,
        actor=actor,
        target=str(data["target"]),
        plan_id=data.get("plan_id"),
        source_chat_id=message.chat.id,
        source_message_id=message.message_id,
    )
    await session.commit()
    enqueue_broadcast(message.bot, settings, job.id)
    await state.clear()
    await message.answer(
        "<b>Broadcast encolado</b>\n\n"
        f"ID: <code>{job.id}</code>\n"
        f"Destinatarios: <b>{job.total}</b>"
    )
