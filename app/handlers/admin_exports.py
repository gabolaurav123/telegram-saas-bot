from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.keyboards.admin import export_clients_keyboard, plan_select_keyboard
from app.models.enums import Role
from app.services.admins import require_role
from app.services.exports import export_clients
from app.services.plans import list_plans
from app.services.users import get_or_create_user
from app.states.admin import ExportClientStates

router = Router(name="admin_exports")


@router.message(Command("exportclients"))
async def cmd_export_clients(message: Message, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    await message.answer("<b>Exportar clientes</b>\n\nSelecciona filtro:", reply_markup=export_clients_keyboard())


@router.callback_query(F.data == "adm:export")
async def cb_export_clients(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    await callback.message.edit_text(
        "<b>Exportar clientes</b>\n\nSelecciona filtro:",
        reply_markup=export_clients_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "export:plan")
async def cb_export_plan_select(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    plans = await list_plans(session)
    await callback.message.edit_text(
        "<b>Exportar por plan</b>\n\nSelecciona plan:",
        reply_markup=plan_select_keyboard(plans, "export:plan", back_callback="adm:section:clients"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("export:plan:"))
async def cb_export_plan(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await _run_export(callback, session, settings, "plan", int(callback.data.split(":")[-1]))


@router.callback_query(F.data.in_({"export:all", "export:active", "export:expired"}))
async def cb_export_filter(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await _run_export(callback, session, settings, callback.data.split(":")[-1], None)


@router.callback_query(F.data == "export:date")
async def cb_export_date(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    await state.set_state(ExportClientStates.waiting_date_range)
    await callback.message.answer(
        "Envia rango de fecha de registro en formato:\n"
        "<code>YYYY-MM-DD YYYY-MM-DD</code>"
    )
    await callback.answer()


@router.message(ExportClientStates.waiting_date_range)
async def receive_export_date_range(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await require_role(session, message.from_user.id, settings, Role.ADMIN)
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Formato invalido. Usa: YYYY-MM-DD YYYY-MM-DD")
        return
    from datetime import UTC, datetime, time

    try:
        start = datetime.combine(datetime.strptime(parts[0], "%Y-%m-%d").date(), time.min, tzinfo=UTC)
        end = datetime.combine(datetime.strptime(parts[1], "%Y-%m-%d").date(), time.max, tzinfo=UTC)
    except ValueError:
        await message.answer("Fechas invalidas. Usa: YYYY-MM-DD YYYY-MM-DD")
        return
    actor = await get_or_create_user(session, message.from_user)
    csv_path, xlsx_path = await export_clients(
        session,
        settings=settings,
        filter_name="date",
        date_from=start,
        date_to=end,
        actor_user_id=actor.id,
    )
    await state.clear()
    await message.answer_document(FSInputFile(csv_path), caption="Clientes CSV")
    await message.answer_document(FSInputFile(xlsx_path), caption="Clientes XLSX")


async def _run_export(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    filter_name: str,
    plan_id: int | None,
) -> None:
    await require_role(session, callback.from_user.id, settings, Role.ADMIN)
    actor = await get_or_create_user(session, callback.from_user)
    await callback.answer("Generando export...")
    csv_path, xlsx_path = await export_clients(
        session,
        settings=settings,
        filter_name=filter_name,
        plan_id=plan_id,
        actor_user_id=actor.id,
    )
    await callback.message.answer_document(FSInputFile(csv_path), caption="Clientes CSV")
    await callback.message.answer_document(FSInputFile(xlsx_path), caption="Clientes XLSX")
