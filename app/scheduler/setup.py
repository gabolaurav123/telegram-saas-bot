from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot

from app.config.settings import Settings
from app.scheduler.jobs import (
    create_automatic_backup,
    expire_memberships,
    run_automation_jobs,
    reissue_expired_unused_links,
    send_expiration_reminders,
)


def setup_scheduler(bot: Bot, settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.app_timezone)
    scheduler.add_job(
        expire_memberships,
        "interval",
        minutes=settings.expire_check_minutes,
        kwargs={"bot": bot, "settings": settings},
        id="expire_memberships",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        send_expiration_reminders,
        "interval",
        minutes=settings.reminder_check_minutes,
        kwargs={"bot": bot, "settings": settings, "days_before": 3},
        id="reminders_3d",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        send_expiration_reminders,
        "interval",
        minutes=settings.reminder_check_minutes,
        kwargs={"bot": bot, "settings": settings, "days_before": 1},
        id="reminders_1d",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        reissue_expired_unused_links,
        "interval",
        hours=max(1, settings.expired_link_reissue_hours),
        kwargs={"bot": bot, "settings": settings},
        id="reissue_expired_unused_links",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        run_automation_jobs,
        "interval",
        minutes=1,
        kwargs={"bot": bot, "settings": settings},
        id="run_automation_jobs",
        replace_existing=True,
        max_instances=1,
    )
    if settings.backup_enabled:
        scheduler.add_job(
            create_automatic_backup,
            "interval",
            hours=settings.backup_interval_hours,
            kwargs={"settings": settings},
            id="automatic_backups",
            replace_existing=True,
            max_instances=1,
        )
    return scheduler
