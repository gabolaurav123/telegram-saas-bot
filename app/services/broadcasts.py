from __future__ import annotations

import asyncio
from time import monotonic

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.database.session import async_session_factory
from app.models.broadcast import BroadcastJob, BroadcastRecipient
from app.models.enums import LogAction, MembershipStatus, UserStatus
from app.models.membership import Membership
from app.models.user import User
from app.services.logs import log_event
from app.services.notifications import notify_admins
from app.utils.time import utc_now


async def resolve_recipients(
    session: AsyncSession,
    *,
    target: str,
    plan_id: int | None = None,
) -> list[User]:
    active_membership = exists().where(
        Membership.user_id == User.id,
        Membership.status == MembershipStatus.ACTIVE,
        Membership.expires_at > utc_now(),
    )
    stmt = select(User).where(User.status == UserStatus.ACTIVE)
    if target == "active_today":
        start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = stmt.where(User.last_seen_at >= start)
    elif target == "subscribed":
        stmt = stmt.where(active_membership)
    elif target == "unsubscribed":
        stmt = stmt.where(~active_membership)
    elif target == "expired":
        expired_membership = exists().where(
            Membership.user_id == User.id,
            Membership.status == MembershipStatus.EXPIRED,
        )
        stmt = stmt.where(expired_membership)
    elif target == "plan":
        if plan_id is None:
            raise ValueError("Debe seleccionar un plan.")
        plan_membership = exists().where(
            Membership.user_id == User.id,
            Membership.plan_id == plan_id,
            Membership.status == MembershipStatus.ACTIVE,
            Membership.expires_at > utc_now(),
        )
        stmt = stmt.where(plan_membership)
    result = await session.scalars(stmt.order_by(User.id))
    return list(result)


async def create_broadcast_job(
    session: AsyncSession,
    *,
    actor: User,
    target: str,
    source_chat_id: int,
    source_message_id: int,
    plan_id: int | None = None,
) -> BroadcastJob:
    recipients = await resolve_recipients(session, target=target, plan_id=plan_id)
    job = BroadcastJob(
        created_by_user_id=actor.id,
        target=target,
        plan_id=plan_id,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
        total=len(recipients),
    )
    session.add(job)
    await session.flush()
    for user in recipients:
        session.add(BroadcastRecipient(job_id=job.id, user_id=user.id))
    await log_event(
        session,
        LogAction.BROADCAST_CREATED,
        f"Broadcast creado con {len(recipients)} destinatarios",
        actor_user_id=actor.id,
        details={"job_id": job.id, "target": target, "plan_id": plan_id},
    )
    return job


def enqueue_broadcast(bot: Bot, settings: Settings, job_id: int) -> asyncio.Task:
    return asyncio.create_task(run_broadcast_job(bot=bot, settings=settings, job_id=job_id))


async def run_broadcast_job(*, bot: Bot, settings: Settings, job_id: int) -> None:
    started = monotonic()
    async with async_session_factory() as session:
        job = await session.get(BroadcastJob, job_id)
        if job is None:
            return
        job.status = "RUNNING"
        job.started_at = utc_now()
        await session.commit()

    while True:
        async with async_session_factory() as session:
            rows = (
                await session.scalars(
                    select(BroadcastRecipient)
                    .options(selectinload(BroadcastRecipient.user))
                    .where(
                        BroadcastRecipient.job_id == job_id,
                        BroadcastRecipient.status.in_(["PENDING", "RETRY"]),
                    )
                    .order_by(BroadcastRecipient.id)
                    .limit(settings.broadcast_batch_size)
                )
            ).all()
            if not rows:
                job = await session.get(BroadcastJob, job_id)
                if job:
                    job.status = "COMPLETED"
                    job.finished_at = utc_now()
                    await log_event(
                        session,
                        LogAction.BROADCAST_COMPLETED,
                        f"Broadcast completado: {job.sent} enviados, {job.failed} fallidos, {job.blocked} bloqueados",
                        actor_user_id=job.created_by_user_id,
                        details={"job_id": job.id},
                    )
                    elapsed = round(monotonic() - started, 2)
                    await notify_admins(
                        bot=bot,
                        session=session,
                        settings=settings,
                        text=(
                            "<b>Broadcast finalizado</b>\n\n"
                            f"ID: <code>{job.id}</code>\n"
                            f"Enviados: <b>{job.sent}</b>\n"
                            f"Fallidos: <b>{job.failed}</b>\n"
                            f"Bloqueados: <b>{job.blocked}</b>\n"
                            f"Tiempo: <b>{elapsed}s</b>"
                        ),
                    )
                await session.commit()
                return

            job = await session.get(BroadcastJob, job_id)
            for row in rows:
                row.attempts += 1
                try:
                    await bot.copy_message(
                        chat_id=row.user.telegram_id,
                        from_chat_id=job.source_chat_id,
                        message_id=job.source_message_id,
                    )
                except TelegramRetryAfter as exc:
                    row.status = "RETRY"
                    row.last_error = f"FloodWait {exc.retry_after}s"
                    await session.commit()
                    await asyncio.sleep(exc.retry_after)
                    continue
                except TelegramForbiddenError as exc:
                    row.status = "BLOCKED"
                    row.last_error = str(exc)[:500]
                    job.blocked += 1
                except (TelegramBadRequest, TelegramAPIError) as exc:
                    if row.attempts <= settings.broadcast_max_retries:
                        row.status = "RETRY"
                    else:
                        row.status = "FAILED"
                        job.failed += 1
                    row.last_error = str(exc)[:500]
                else:
                    row.status = "SENT"
                    row.sent_at = utc_now()
                    job.sent += 1
                await asyncio.sleep(settings.broadcast_batch_delay_seconds)
            await session.commit()

