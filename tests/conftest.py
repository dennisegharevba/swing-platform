"""Pytest configuration and shared fixtures."""
from __future__ import annotations

import asyncio
import os

import pytest

# Use in-memory SQLite for tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")
os.environ.setdefault("FRED_API_KEY", "")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
