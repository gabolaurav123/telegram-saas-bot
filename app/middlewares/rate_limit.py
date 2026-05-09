from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, *, window_seconds: int, max_events: int) -> None:
        self.window_seconds = window_seconds
        self.max_events = max_events
        self.events: defaultdict[int, deque[float]] = defaultdict(deque)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = self._user_id(event)
        if user_id is None:
            return await handler(event, data)

        now = time.monotonic()
        bucket = self.events[user_id]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_events:
            if isinstance(event, CallbackQuery):
                await event.answer("Demasiadas acciones. Intenta de nuevo en unos segundos.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Demasiadas acciones. Intenta de nuevo en unos segundos.")
            return None

        bucket.append(now)
        return await handler(event, data)

    @staticmethod
    def _user_id(event: TelegramObject) -> int | None:
        if isinstance(event, Message) and event.from_user:
            return event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id
        return None

