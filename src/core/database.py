import sys
sys.path.insert(0, "/mount/src/swing-platform")


from datetime import datetime

from loguru import logger
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func, Boolean
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class SignalRecord(Base):
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
    scanned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    trades: Mapped[list["TradeRecord"]] = relationship("TradeRecord", back_populates="signal", lazy="select")


class TradeRecord(Base):
    """
    One row per open/closed lifecycle trade, keyed by symbol (one open trade
    per symbol at a time). Unlike SignalRecord -- which is a snapshot written
    once per scan -- a TradeRecord is opened the moment a symbol's signal is
    first detected and then updated in place as price action unfolds, so
    entry/stop/targets stay frozen at the moment of signal inception while
    status, P/L, and MFE/MAE evolve. See src/signals/lifecycle.py.
    """
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    signal_id: Mapped[int] = mapped_column(Integer, ForeignKey("signals.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    asset_class: Mapped[str] = mapped_column(String(20), nullable=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_1: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_2: Mapped[float] = mapped_column(Float, nullable=False)
    position_size: Mapped[float] = mapped_column(Float, nullable=True)
    pnl: Mapped[float] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float] = mapped_column(Float, nullable=True)
    mfe_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    mae_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    last_price: Mapped[float] = mapped_column(Float, nullable=True)
    session: Mapped[str] = mapped_column(String(30), nullable=True)
    expected_hold_days: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    opened_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    target_1_hit_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    signal: Mapped[SignalRecord] = relationship("SignalRecord", back_populates="trades")
    status_logs: Mapped[list["TradeStatusLog"]] = relationship(
        "TradeStatusLog", back_populates="trade", lazy="select"
    )


class TradeStatusLog(Base):
    """
    Append-only audit trail of every lifecycle status change for a trade
    (e.g. active -> target_1_hit -> final_target_hit). Powers the dashboard's
    historical archive view.
    """
    __tablename__ = "trade_status_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trade_id: Mapped[int] = mapped_column(Integer, ForeignKey("trades.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=True)
    price_at_change: Mapped[float] = mapped_column(Float, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    trade: Mapped[TradeRecord] = relationship("TradeRecord", back_populates="status_logs")


class MarketSnapshot(Base):
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


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


_TRADES_NEW_COLUMNS = {
    "asset_class": "VARCHAR(20)",
    "mfe_pct": "FLOAT DEFAULT 0",
    "mae_pct": "FLOAT DEFAULT 0",
    "last_price": "FLOAT",
    "session": "VARCHAR(30)",
    "expected_hold_days": "INTEGER",
    "target_1_hit_at": "DATETIME",
    "updated_at": "DATETIME",
}


async def _rebuild_trades_table_nullable_signal_id(conn):
    """
    SQLite can't ALTER COLUMN to drop a NOT NULL constraint, so on databases
    created before lifecycle trades existed (where trades.signal_id was
    NOT NULL), rebuild the table: rename it aside, recreate it from the
    current (nullable signal_id) model definition, copy over whatever
    columns actually existed, then drop the old copy.
    """
    from sqlalchemy import text
    result = await conn.execute(text("PRAGMA table_info(trades)"))
    legacy_cols = {row[1] for row in result.fetchall()}

    await conn.execute(text("ALTER TABLE trades RENAME TO trades_legacy"))
    await conn.run_sync(lambda sync_conn: Base.metadata.tables["trades"].create(sync_conn, checkfirst=False))

    new_cols = {c.name for c in Base.metadata.tables["trades"].columns}
    shared_cols = [c for c in legacy_cols if c in new_cols]
    if shared_cols:
        cols_csv = ", ".join(shared_cols)
        try:
            await conn.execute(text(f"INSERT INTO trades ({cols_csv}) SELECT {cols_csv} FROM trades_legacy"))
        except Exception as exc:
            logger.warning(
                "Could not carry over rows from the legacy trades table during migration "
                "(schema mismatch: {}). Starting the lifecycle table fresh instead.", exc
            )
    await conn.execute(text("DROP TABLE trades_legacy"))


async def _migrate_trades_table(conn):
    """
    Best-effort migration for the `trades` table on databases created before
    the lifecycle columns existed. Only applies to SQLite (ALTER TABLE ADD
    COLUMN / table rebuild), which is what this project uses by default;
    other backends are left untouched since Base.metadata.create_all already
    handles fresh DBs.
    """
    if "sqlite" not in str(engine.url):
        return
    from sqlalchemy import text
    result = await conn.execute(text("PRAGMA table_info(trades)"))
    table_info = result.fetchall()
    if not table_info:
        return  # table doesn't exist yet -- create_all already handled it

    # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
    signal_id_notnull = any(row[1] == "signal_id" and row[3] == 1 for row in table_info)
    if signal_id_notnull:
        await _rebuild_trades_table_nullable_signal_id(conn)
        result = await conn.execute(text("PRAGMA table_info(trades)"))
        table_info = result.fetchall()

    existing_cols = {row[1] for row in table_info}
    for col, ddl in _TRADES_NEW_COLUMNS.items():
        if col not in existing_cols:
            try:
                await conn.execute(text(f"ALTER TABLE trades ADD COLUMN {col} {ddl}"))
            except Exception:
                pass  # column already present (e.g. re-run) -- safe to ignore


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_trades_table(conn)
