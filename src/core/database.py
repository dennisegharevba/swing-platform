"""
Database Layer
==============
SQLAlchemy 2.0 async ORM.  Supports SQLite (default) and PostgreSQL.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False}
    if "sqlite" in settings.database_url
    else {},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class SignalRecord(Base):
    """Persisted signal snapshot from each scan."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    cot_score: Mapped[float] = mapped_column(Float, nullable=True)
    seasonality_score: Mapped[float] = mapped_column(Float, nullable=True)
    macro_score: Mapped[float] = mapped_column(Float, nullable=True)
    trend_score: Mapped[float] = mapped_column(Float, nullable=True)
    momentum_score: Mapped[float] = mapped_column(Float, nullable=True)
    vix_level: Mapped[float] = mapped_column(Float, nullable=True)
    dxy_regime: Mapped[str] = mapped_column(String(20), nullable=True)
    us10y_regime: Mapped[str] = mapped_column(String(20), nullable=True)
    real_yield_regime: Mapped[str] = mapped_column(String(20), nullable=True)
    entry_price: Mapped[float] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=True)
    take_profit_1: Mapped[float] = mapped_column(Float, nullable=True)
    take_profit_2: Mapped[float] = mapped_column(Float, nullable=True)
    risk_reward: Mapped[float] = mapped_column(Float, nullable=True)
    atr_risk_pct: Mapped[float] = mapped_column(Float, nullable=True)
    expected_hold_days: Mapped[int] = mapped_column(Integer, nullable=True)
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    trades: Mapped[list["TradeRecord"]] = relationship(
        "TradeRecord", back_populates="signal", lazy="select"
    )


class TradeRecord(Base):
    """Tracks active and historical trades."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    signal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signals.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_1: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_2: Mapped[float] = mapped_column(Float, nullable=False)
    position_size: Mapped[float] = mapped_column(Float, nullable=True)
    pnl: Mapped[float] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    opened_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    closed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    signal: Mapped[SignalRecord] = relationship("SignalRecord", back_populates="trades")


class MarketSnapshot(Base):
    """Daily market data cache."""

    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    atr: Mapped[float] = mapped_column(Float, nullable=True)
    ma_200: Mapped[float] = mapped_column(Float, nullable=True)
    rsi: Mapped[float] = mapped_column(Float, nullable=True)


class ScanLog(Base):
    """Audit log of every automated scan."""

    __tablename__ = "scan_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_type: Mapped[str] = mapped_column(String(20), nullable=False)
    symbols_scanned: Mapped[int] = mapped_column(Integer, default=0)
    signals_found: Mapped[int] = mapped_column(Integer, default=0)
    alerts_sent: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def get_db() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
