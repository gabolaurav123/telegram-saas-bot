from __future__ import annotations

from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.support import SupportReplyMap


class SupportReplyTargetFilter(BaseFilter):
    """Match replies to bot messages that are mapped to a support user."""

    async def __call__(
        self,
        message: Message,
        session: AsyncSession,
        **_: Any,
    ) -> bool:
        if message.reply_to_message is None:
            return False
        mapping_id = await session.scalar(
            select(SupportReplyMap.id).where(
                SupportReplyMap.admin_chat_id == message.chat.id,
                SupportReplyMap.admin_message_id == message.reply_to_message.message_id,
            )
        )
        return mapping_id is not None
