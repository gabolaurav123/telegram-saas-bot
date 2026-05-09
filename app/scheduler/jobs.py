from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.config.settings import Settings
from app.database.session import async_session_factory
from app.models.enums import LogAction
from app.services.backups import export_csv_zip
from app.services.channels import revoke_user_from_plan_chats
from app.services.logs import log_event
from app.services.memberships import (
    expire_membership,
    memberships_due_to_expire,
    memberships_for_reminder,
)
from app.services.notifications import send_membership_expired, send_membership_reminder

logger = logging.getLogger(__name__)


async def send_expiration_reminders(bot: Bot, settings: Settings, days_before: int) -> None:
    async with async_session_factory() as session:
        memberships = await memberships_for_reminder(session, days_before)
        for membership in memberships:
            try:
                await send_membership_reminder(
                    bot=bot,
                    membership=membership,
                    days_before=days_before,
                    settings=settings,
                )
                if days_before == 3:
                    membership.reminder_3d_sent = True
                else:
                    membership.reminder_1d_sent = True
            except TelegramAPIError:
                logger.exception("Could not send reminder for membership %s", membership.id)
        await session.commit()


async def expire_memberships(bot: Bot, settings: Settings) -> None:
    async with async_session_factory() as session:
        memberships = await memberships_due_to_expire(session)
        for membership in memberships:
            revoked_chat_ids = await revoke_user_from_plan_chats(
                bot=bot,
                plan=membership.plan,
                user_telegram_id=membership.user.telegram_id,
            )
            await expire_membership(session, membership)
            await log_event(
                session,
                LogAction.USER_KICKED,
                f"Accesos revocados para membresia {membership.id}",
                target_user_id=membership.user_id,
                details={"chat_ids": revoked_chat_ids},
            )
            try:
                await send_membership_expired(
                    bot=bot,
                    membership=membership,
                    settings=settings,
                )
            except TelegramAPIError:
                logger.exception("Could not notify expiration for membership %s", membership.id)
        await session.commit()


async def create_automatic_backup(settings: Settings) -> None:
    async with async_session_factory() as session:
        backup_path = await export_csv_zip(session, settings)
        await log_event(
            session,
            LogAction.BACKUP_CREATED,
            f"Backup creado: {backup_path}",
            details={"path": str(backup_path)},
        )
        await session.commit()

