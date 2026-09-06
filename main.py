from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from sqlalchemy import text

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.database.init_db import create_db_schema
from app.database.session import async_session_factory
from app.handlers import (
    admin,
    admin_broadcasts,
    admin_catalog,
    admin_chats,
    admin_exports,
    admin_inbox,
    admin_invite_links,
    admin_payments,
    admin_quick_replies,
    admin_users,
    common,
    plans,
    purchase,
    support,
)
from app.middlewares.database import DatabaseSessionMiddleware
from app.middlewares.rate_limit import RateLimitMiddleware
from app.scheduler.setup import setup_scheduler
from app.services.payment_methods import ensure_default_payment_methods
from app.services.quick_replies import ensure_default_quick_replies

logger = logging.getLogger(__name__)


async def on_error(event: ErrorEvent) -> bool:
    logger.exception("Unhandled aiogram error: %s", event.exception)
    return True


async def bootstrap() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_to_file)
    logger.info("Starting Telegram premium memberships bot")
    logger.info(
        "Runtime config loaded | env=%s timezone=%s owners=%s database=%s",
        settings.app_env,
        settings.app_timezone,
        len(settings.owner_ids),
        settings.safe_database_url,
    )

    if settings.auto_create_db:
        logger.info("AUTO_CREATE_DB enabled; creating database schema from metadata")
        await create_db_schema()

    async with async_session_factory() as session:
        logger.info("Checking PostgreSQL connectivity")
        await session.scalar(text("select 1"))
        logger.info("PostgreSQL connectivity OK")
        logger.info("Ensuring default payment methods")
        await ensure_default_payment_methods(session)
        logger.info("Ensuring default quick replies")
        await ensure_default_quick_replies(session)
        await session.commit()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    me = await bot.get_me()
    logger.info("Telegram bot authenticated | id=%s username=@%s", me.id, me.username)

    dp = Dispatcher(storage=MemoryStorage())
    dp.workflow_data.update(settings=settings)

    logger.info("Registering middlewares and routers")
    dp.update.middleware(DatabaseSessionMiddleware(async_session_factory))
    rate_limiter = RateLimitMiddleware(
        window_seconds=settings.rate_limit_window_seconds,
        max_events=settings.rate_limit_max_events,
    )
    dp.message.middleware(rate_limiter)
    dp.callback_query.middleware(rate_limiter)

    dp.include_routers(
        common.router,
        plans.router,
        purchase.router,
        admin.router,
        admin_payments.router,
        admin_catalog.router,
        admin_chats.router,
        admin_users.router,
        admin_inbox.router,
        admin_quick_replies.router,
        admin_invite_links.router,
        admin_broadcasts.router,
        admin_exports.router,
        support.router,
    )
    dp.errors.register(on_error)

    scheduler = None
    if settings.scheduler_enabled:
        scheduler = setup_scheduler(bot, settings)
        scheduler.start()
        logger.info("Scheduler started")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot polling started")
        await dp.start_polling(bot)
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
        await bot.session.close()
        logger.info("Bot session closed")


if __name__ == "__main__":
    try:
        asyncio.run(bootstrap())
    except Exception:
        logging.getLogger(__name__).exception("Fatal startup error")
        raise
