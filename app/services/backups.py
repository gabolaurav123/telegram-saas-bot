from __future__ import annotations

import csv
import json
import zipfile
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.models import (
    Admin,
    Channel,
    Membership,
    PaymentMethod,
    PaymentRequest,
    Plan,
    PlanPaymentMessage,
    Setting,
    Statistic,
    SystemLog,
    TelegramGroup,
    User,
)
from app.models.notification import Notification


EXPORT_MODELS = [
    User,
    Admin,
    Plan,
    PaymentMethod,
    PlanPaymentMessage,
    PaymentRequest,
    Membership,
    Channel,
    TelegramGroup,
    SystemLog,
    Setting,
    Notification,
    Statistic,
]


def _serialize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


async def export_csv_zip(session: AsyncSession, settings: Settings) -> Path:
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    output = settings.backup_dir / f"telegram-premium-backup-{timestamp}.zip"

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for model in EXPORT_MODELS:
            table = model.__table__
            rows = (await session.execute(select(model))).scalars().all()
            csv_path = tmp_path / f"{table.name}.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                columns = [column.name for column in table.columns]
                writer.writerow(columns)
                for row in rows:
                    writer.writerow([_serialize(getattr(row, column)) for column in columns])

        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for csv_file in tmp_path.glob("*.csv"):
                archive.write(csv_file, arcname=csv_file.name)
    return output

