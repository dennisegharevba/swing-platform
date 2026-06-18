"""
Logging Configuration
=====================
Structured logging via loguru with file rotation.
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from src.core.config import DATA_DIR, get_settings

LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


def setup_logging() -> None:
    settings = get_settings()
    logger.remove()

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>"
    )

    # Console
    logger.add(sys.stderr, format=fmt, level=settings.log_level, colorize=True)

    # Rotating file
    logger.add(
        LOG_DIR / "platform_{time:YYYY-MM-DD}.log",
        format=fmt,
        level="DEBUG",
        rotation="00:00",
        retention="30 days",
        compression="gz",
        enqueue=True,
    )

    # Errors only
    logger.add(
        LOG_DIR / "errors.log",
        format=fmt,
        level="ERROR",
        rotation="10 MB",
        retention="90 days",
        compression="gz",
        enqueue=True,
    )

    logger.info("Logging initialised — level={}", settings.log_level)


setup_logging()
