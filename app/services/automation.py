from __future__ import annotations

import logging
from datetime import timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.database.session import async_session_factory
from app.models.automation import AutomationJob, AutomationRule
from app.models.enums import AutomationJobStatus, LogAction
from app.models.user import User
from app.services.logs import log_event
from app.services.messaging import MessagingService
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


async def schedule_automation_jobs(
    session: AsyncSession,
    *,
    trigger: str,
    user: User | None = None,
    payload: dict | None = None,
) -> list[AutomationJob]:
    rules = list(
        await session.scalars(
            select(AutomationRule).where(
                AutomationRule.trigger == trigger,
                AutomationRule.enabled.is_(True),
            )
        )
    )
    jobs: list[AutomationJob] = []
    for rule in rules:
        dedupe_key = f"{rule.id}:{user.id if user else 'system'}:{trigger}"
        if await session.scalar(select(AutomationJob.id).where(AutomationJob.dedupe_key == dedupe_key)):
            continue
        job = AutomationJob(
            rule_id=rule.id,
            user_id=user.id if user else None,
            trigger=trigger,
            dedupe_key=dedupe_key,
            run_at=utc_now() + timedelta(seconds=rule.delay_seconds),
            payload_json=payload or {},
        )
        session.add(job)
        jobs.append(job)
        await log_event(
            session,
            LogAction.AUTOMATION_SCHEDULED,
            f"Automation job programado: {trigger}",
            target_user_id=user.id if user else None,
            details={"rule_id": rule.id, "dedupe_key": dedupe_key},
        )
    return jobs


async def run_due_automation_jobs(bot: Bot, settings: Settings) -> None:
    async with async_session_factory() as session:
        jobs = list(
            await session.scalars(
                select(AutomationJob)
                .where(
                    AutomationJob.status == AutomationJobStatus.PENDING,
                    AutomationJob.run_at <= utc_now(),
                )
                .order_by(AutomationJob.run_at)
                .limit(50)
            )
        )
        for job in jobs:
            await _run_job(session, bot=bot, job=job)
        await session.commit()


async def _run_job(session: AsyncSession, *, bot: Bot, job: AutomationJob) -> None:
    job.status = AutomationJobStatus.RUNNING
    job.attempts += 1
    try:
        rule = await session.get(AutomationRule, job.rule_id) if job.rule_id else None
        user = await session.get(User, job.user_id) if job.user_id else None
        if rule is None or user is None:
            job.status = AutomationJobStatus.CANCELLED
            job.last_error = "Missing rule or user"
            return
        if rule.action == "SEND_MESSAGE":
            text = str(rule.action_payload_json.get("text") or "")
            if not text:
                raise ValueError("Automation SEND_MESSAGE requires action_payload_json.text")
            await MessagingService(session).send_text_to_user(
                bot=bot,
                target=user,
                text=text,
                source="AUTOMATION",
                metadata={"automation_job_id": job.id, "automation_rule_id": rule.id},
            )
        job.status = AutomationJobStatus.COMPLETED
        job.executed_at = utc_now()
        await log_event(
            session,
            LogAction.AUTOMATION_EXECUTED,
            f"Automation job ejecutado: {job.id}",
            target_user_id=job.user_id,
            details={"rule_id": job.rule_id, "action": rule.action if rule else None},
        )
    except Exception as exc:
        logger.exception("Automation job failed: %s", job.id)
        job.status = AutomationJobStatus.FAILED
        job.last_error = str(exc)[:500]
