from __future__ import annotations

from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserStatus
from app.models.user import User
from app.utils.time import utc_now


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_or_create_user(session: AsyncSession, telegram_user: TelegramUser) -> User:
    user, _ = await get_or_create_user_with_flag(session, telegram_user)
    return user


async def get_or_create_user_with_flag(
    session: AsyncSession,
    telegram_user: TelegramUser,
) -> tuple[User, bool]:
    user = await get_user_by_telegram_id(session, telegram_user.id)
    now = utc_now()
    if user is None:
        user = User(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=telegram_user.language_code,
            is_bot=telegram_user.is_bot,
            status=UserStatus.ACTIVE,
            last_seen_at=now,
        )
        session.add(user)
        await session.flush()
        return user, True

    user.username = telegram_user.username
    user.first_name = telegram_user.first_name
    user.last_name = telegram_user.last_name
    user.language_code = telegram_user.language_code
    user.is_bot = telegram_user.is_bot
    user.last_seen_at = now
    return user, False


async def ban_user(session: AsyncSession, user: User) -> None:
    user.status = UserStatus.BANNED
    user.banned_at = utc_now()
