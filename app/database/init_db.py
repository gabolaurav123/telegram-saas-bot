from __future__ import annotations

from app.database.base import Base
from app.database.session import engine
from app import models  # noqa: F401


async def create_db_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

