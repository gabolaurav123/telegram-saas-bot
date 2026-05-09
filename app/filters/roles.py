from __future__ import annotations

from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.models.enums import Role
from app.services.admins import has_role


class RoleFilter(BaseFilter):
    def __init__(self, minimum_role: Role) -> None:
        self.minimum_role = minimum_role

    async def __call__(
        self,
        event: Message | CallbackQuery,
        session: AsyncSession,
        settings: Settings,
        **_: Any,
    ) -> bool:
        if event.from_user is None:
            return False
        return await has_role(session, event.from_user.id, settings, self.minimum_role)

