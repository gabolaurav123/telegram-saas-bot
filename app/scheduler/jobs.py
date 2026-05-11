from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.database.session import async_session_factory
from app.models.access_event import MembershipAccessEvent
from app.models.enums import AccessEventKind, LogAction, MembershipStatus
from app.models.generated_invite_link import GeneratedInviteLink
from app.models.membership import Membership
from app.services.backups import export_csv_zip
from app.services.channels import revoke_user_from_plan_chats
from app.services.invite_links import reissue_expired_link
from app.services.logs import log_event
from app.services.memberships import (
    expire_membership,
    memberships_due_to_expire,
    memberships_for_reminder,
)
from app.services.notifications import send_admin_log, send_membership_expired, send_membership_reminder
from app.utils.text import h
from app.utils.time import human_datetime, utc_now

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
            revoke_results = await revoke_user_from_plan_chats(
                bot=bot,
                plan=membership.plan,
                user_telegram_id=membership.user.telegram_id,
            )
            kicked_at = utc_now()
            for result in revoke_results:
                session.add(
                    MembershipAccessEvent(
                        user_id=membership.user_id,
                        membership_id=membership.id,
                        plan_id=membership.plan_id,
                        event_kind=AccessEventKind.KICK,
                        telegram_chat_id=int(result["chat_id"]),
                        chat_title=str(result["title"]),
                        channel_id=result.get("channel_id"),
                        group_id=result.get("group_id"),
                        event_at=kicked_at,
                        kick_result=str(result["result"]),
                        metadata_json={"error": result.get("error")} if result.get("error") else {},
                    )
                )
            await expire_membership(session, membership)
            await log_event(
                session,
                LogAction.USER_KICKED,
                f"Accesos revocados para membresia {membership.id}",
                target_user_id=membership.user_id,
                details={"results": revoke_results},
            )
            admin_results = revoke_results or [
                {
                    "title": "-",
                    "chat_id": 0,
                    "channel_id": None,
                    "group_id": None,
                    "result": "NO_LINKED_CHATS",
                }
            ]
            for result in admin_results:
                await send_admin_log(
                    bot=bot,
                    session=session,
                    settings=settings,
                    title="❌ Membresia expirada",
                    lines=[
                        f"👤 {h(membership.user.display_name)}",
                        f"🆔 <code>{membership.user.telegram_id}</code>",
                        f"📦 Plan: {h(membership.plan.name)}",
                        f"📍 Canal: {h(str(result['title']))}",
                        f"🕒 Expiró: {human_datetime(membership.expires_at, settings.app_timezone)}",
                        "🚫 Usuario expulsado automaticamente"
                        if result["result"] == "KICKED"
                        else f"🚫 Resultado: {result['result']}",
                    ],
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


async def reissue_expired_unused_links(bot: Bot, settings: Settings) -> None:
    async with async_session_factory() as session:
        result = await session.scalars(
            select(GeneratedInviteLink)
            .options(
                selectinload(GeneratedInviteLink.membership).selectinload(Membership.user),
                selectinload(GeneratedInviteLink.plan),
                selectinload(GeneratedInviteLink.approved_by),
                selectinload(GeneratedInviteLink.creator),
            )
            .where(
                GeneratedInviteLink.join_confirmed.is_(False),
                GeneratedInviteLink.revoked_at.is_(None),
                GeneratedInviteLink.expire_at <= utc_now(),
                GeneratedInviteLink.membership_id.is_not(None),
            )
            .order_by(GeneratedInviteLink.expire_at)
            .limit(50)
        )
        links = list(result)
        for old_link in links:
            if old_link.membership is None or old_link.membership.status != MembershipStatus.ACTIVE:
                continue
            try:
                new_link = await reissue_expired_link(
                    bot=bot,
                    session=session,
                    settings=settings,
                    link_id=old_link.id,
                    actor=old_link.approved_by or old_link.creator,
                )
            except (TelegramAPIError, ValueError):
                logger.exception("Could not reissue expired invite link %s", old_link.id)
                continue
            user = old_link.membership.user
            try:
                await bot.send_message(
                    user.telegram_id,
                    "<b>Nuevo enlace de acceso</b>\n\n"
                    f"Tu enlace anterior para <b>{h(old_link.chat_title)}</b> expiro sin ingreso confirmado.\n"
                    "Generamos uno nuevo de un solo uso:\n\n"
                    f"{h(new_link.invite_link)}",
                    disable_web_page_preview=True,
                )
            except TelegramAPIError:
                logger.exception("Could not send reissued link %s to user %s", new_link.id, user.telegram_id)
            await send_admin_log(
                bot=bot,
                session=session,
                settings=settings,
                title="Invite link reemitido",
                lines=[
                    f"Usuario: {h(user.display_name)}",
                    f"ID: <code>{user.telegram_id}</code>",
                    f"Plan: {h(old_link.plan.name if old_link.plan else '-')}",
                    f"Canal: {h(old_link.chat_title)}",
                    f"Link anterior: INV-{old_link.id}",
                    f"Link nuevo: INV-{new_link.id}",
                ],
            )
        await session.commit()
