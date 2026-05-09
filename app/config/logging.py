from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(level: str = "INFO", log_to_file: bool = True) -> None:
    log_dir = Path("app/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_to_file:
        handlers.append(
            RotatingFileHandler(
                log_dir / "bot.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
        )

    for handler in handlers:
        handler.setFormatter(formatter)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=handlers,
        force=True,
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)

