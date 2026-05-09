from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LogAction
from app.models.log import SystemLog

logger = logging.getLogger(__name__)


async def log_event(
    session: AsyncSession,
    action: LogAction,
    message: str,
    *,
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    severity: str = "INFO",
    details: dict[str, Any] | None = None,
) -> SystemLog:
    record = SystemLog(
        action=action,
        message=message,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        severity=severity.upper(),
        details=details or {},
    )
    session.add(record)
    logger.log(getattr(logging, severity.upper(), logging.INFO), "%s: %s", action, message)
    return record

