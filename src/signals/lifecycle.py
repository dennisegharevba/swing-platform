import sys
sys.path.insert(0, "/mount/src/swing-platform")

"""
Signal Lifecycle & Countdown System
====================================
Turns a scored signal into a tracked, stateful "trade" the moment it first
appears, then keeps it updated on every subsequent scan until it resolves
(target hit, stop hit, expiry, invalidation, or trend reversal).

Design notes
------------
- Entry / stop / TP1 / TP2 are frozen the moment a TradeRecord is opened
  (see risk_engine.attach_risk, which computes them off the live price at
  detection time). Re-scans never move these levels -- only `evaluate_status`,
  `update_extremes`, and `compute_pnl_pct` react to fresh prices.
- All pure logic (session/age classification, countdown formatting, the
  status state machine, MFE/MAE bookkeeping) lives in plain functions that
  take primitives in and return primitives out, so they're unit-testable
  without a database. `sync_trade_lifecycle` is the only piece that talks
  to SQLAlchemy.
- Session boundaries below are fixed UTC clock hours for simplicity; they're
  approximate and don't shift for daylight saving time.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger

from src.core.config import Direction

# ── Trading sessions ─────────────────────────────────────────────────────────

SESSION_ASIAN = "Asian"
SESSION_LONDON = "London"
SESSION_PREMARKET = "Pre-Market"
SESSION_NEW_YORK = "New York"
SESSION_AFTER_HOURS = "After-Hours"


def classify_session(dt_utc):
    """Bucket a UTC timestamp into an approximate trading session."""
    hour = dt_utc.hour
    if 7 <= hour < 11:
        return SESSION_LONDON
    if 11 <= hour < 13:
        return SESSION_PREMARKET
    if 13 <= hour < 21:
        return SESSION_NEW_YORK
    if 21 <= hour < 22:
        return SESSION_AFTER_HOURS
    return SESSION_ASIAN


# ── Signal age ────────────────────────────────────────────────────────────────

AGE_FRESH = "Fresh"
AGE_DEVELOPING = "Developing"
AGE_MATURE = "Mature"
AGE_AGING = "Aging"
AGE_EXPIRED = "Expired"


def signal_age_bucket(age):
    """`age` is a timedelta since the signal was first detected."""
    hours = age.total_seconds() / 3600
    if hours < 0:
        hours = 0
    if hours < 24:
        return AGE_FRESH
    if hours < 24 * 3:
        return AGE_DEVELOPING
    if hours < 24 * 7:
        return AGE_MATURE
    if hours < 24 * 14:
        return AGE_AGING
    return AGE_EXPIRED


def format_countdown(delta):
    """Human-readable duration, e.g. '2d 04h 13m' or '-1d 02h 00m' if overdue."""
    total_seconds = int(delta.total_seconds())
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    if days:
        return f"{sign}{days}d {hours:02d}h {minutes:02d}m"
    if hours:
        return f"{sign}{hours}h {minutes:02d}m {seconds:02d}s"
    return f"{sign}{minutes}m {seconds:02d}s"


# ── Status state machine ────────────────────────────────────────────────────

STATUS_ACTIVE = "active"
STATUS_TARGET_1_HIT = "target_1_hit"
STATUS_FINAL_TARGET_HIT = "final_target_hit"
STATUS_NEAR_STOP = "near_stop"
STATUS_STOP_HIT = "stop_hit"
STATUS_EXPIRED = "expired"
STATUS_INVALIDATED = "invalidated"
STATUS_EXTENDED_TREND = "extended_trend"
STATUS_TREND_REVERSAL = "trend_reversal"

TERMINAL_STATUSES = {
    STATUS_STOP_HIT, STATUS_FINAL_TARGET_HIT, STATUS_EXPIRED,
    STATUS_INVALIDATED, STATUS_TREND_REVERSAL,
}

STATUS_LABELS = {
    STATUS_ACTIVE: "Active",
    STATUS_TARGET_1_HIT: "Target 1 Hit",
    STATUS_FINAL_TARGET_HIT: "Final Target Hit",
    STATUS_NEAR_STOP: "Near Stop-Loss",
    STATUS_STOP_HIT: "Stop-Loss Hit",
    STATUS_EXPIRED: "Expired",
    STATUS_INVALIDATED: "Invalidated",
    STATUS_EXTENDED_TREND: "Extended Trend",
    STATUS_TREND_REVERSAL: "Trend Reversal",
}

# Once price has retraced this fraction of the entry-to-stop distance
# without actually hitting the stop, the trade is flagged "near stop".
NEAR_STOP_RISK_THRESHOLD = 0.75


def _is_long(direction):
    return direction == Direction.LONG or direction == "long"


def evaluate_status(direction, entry, stop_loss, take_profit_1, take_profit_2,
                     current_price, opened_at, expected_hold_days, prior_status, now=None):
    """
    Pure function: given the frozen trade levels and a fresh price, returns
    the new lifecycle status. Terminal statuses never change once reached.
    """
    now = now or datetime.utcnow()
    if prior_status in TERMINAL_STATUSES:
        return prior_status

    is_long = _is_long(direction)

    def hit_stop():
        return current_price <= stop_loss if is_long else current_price >= stop_loss

    def hit_final():
        return current_price >= take_profit_2 if is_long else current_price <= take_profit_2

    def hit_t1():
        return current_price >= take_profit_1 if is_long else current_price <= take_profit_1

    if hit_stop():
        return STATUS_STOP_HIT
    if hit_final():
        return STATUS_FINAL_TARGET_HIT

    status = STATUS_TARGET_1_HIT if (hit_t1() or prior_status == STATUS_TARGET_1_HIT) else STATUS_ACTIVE

    risk = abs(entry - stop_loss)
    if status == STATUS_ACTIVE and risk > 0:
        consumed = (entry - current_price) if is_long else (current_price - entry)
        if consumed / risk >= NEAR_STOP_RISK_THRESHOLD:
            status = STATUS_NEAR_STOP

    if expected_hold_days:
        deadline = opened_at + timedelta(days=expected_hold_days)
        if now > deadline:
            pnl_pct = compute_pnl_pct(direction, entry, current_price)
            status = STATUS_EXTENDED_TREND if pnl_pct > 0 else STATUS_EXPIRED

    return status


def compute_pnl_pct(direction, entry, current_price):
    if not entry:
        return 0.0
    is_long = _is_long(direction)
    pct = ((current_price - entry) / entry * 100) if is_long else ((entry - current_price) / entry * 100)
    return round(pct, 3)


def update_extremes(direction, entry, current_price, prior_mfe_pct, prior_mae_pct):
    """
    Returns (mfe_pct, mae_pct): the best and worst unrealized excursions
    seen so far, in percent of entry, direction-aware. Monotonic -- mfe only
    grows, mae only shrinks.
    """
    move_pct = compute_pnl_pct(direction, entry, current_price)
    prior_mfe_pct = prior_mfe_pct or 0.0
    prior_mae_pct = prior_mae_pct or 0.0
    mfe = max(prior_mfe_pct, move_pct)
    mae = min(prior_mae_pct, move_pct)
    return round(mfe, 3), round(mae, 3)


@dataclass
class TradeProgress:
    """Convenience bundle for rendering a trade's current state."""
    status: str
    status_label: str
    pnl_pct: float
    mfe_pct: float
    mae_pct: float
    pct_to_target: float  # 0-100+, progress from entry toward the final target
    age_bucket: str
    session: str
    age: timedelta
    time_to_expiry: timedelta


def compute_progress(trade, now=None):
    now = now or datetime.utcnow()
    is_long = _is_long(trade.direction)
    total_distance = abs(trade.take_profit_2 - trade.entry_price)
    covered = (trade.last_price - trade.entry_price) if is_long else (trade.entry_price - trade.last_price)
    pct_to_target = round(max(0.0, min(150.0, (covered / total_distance) * 100)), 1) if total_distance else 0.0

    age = now - trade.opened_at
    expected_hold_days = trade.expected_hold_days or 10
    deadline = trade.opened_at + timedelta(days=expected_hold_days)
    time_to_expiry = deadline - now

    return TradeProgress(
        status=trade.status,
        status_label=STATUS_LABELS.get(trade.status, trade.status),
        pnl_pct=trade.pnl_pct or 0.0,
        mfe_pct=trade.mfe_pct or 0.0,
        mae_pct=trade.mae_pct or 0.0,
        pct_to_target=pct_to_target,
        age_bucket=signal_age_bucket(age),
        session=trade.session or classify_session(trade.opened_at),
        age=age,
        time_to_expiry=time_to_expiry,
    )


# ── DB orchestration ─────────────────────────────────────────────────────────

def _open_trade(sig, now):
    from src.core.database import TradeRecord
    return TradeRecord(
        symbol=sig.symbol,
        asset_class=sig.asset_class.value,
        direction=sig.direction.value,
        entry_price=sig.entry_price,
        stop_loss=sig.stop_loss,
        take_profit_1=sig.take_profit_1,
        take_profit_2=sig.take_profit_2,
        status=STATUS_ACTIVE,
        opened_at=now,
        expected_hold_days=sig.expected_hold_days,
        session=classify_session(now),
        mfe_pct=0.0,
        mae_pct=0.0,
        last_price=sig.entry_price,
        pnl_pct=0.0,
        updated_at=now,
    )


async def sync_trade_lifecycle(signals, now=None):
    """
    Reconciles open TradeRecords against the latest scan:
      - opens a new trade for any symbol with a fresh valid signal and no
        open trade,
      - closes and reopens on a direction flip (trend reversal),
      - refreshes P/L, MFE/MAE, and status for every open trade using the
        latest available price -- including symbols that dropped out of
        this scan's signal list, so a trade keeps running toward its
        target/stop/expiry even if it later falls below the score threshold.

    Returns a list of (TradeRecord, old_status, new_status) for every status
    change this call produced, so callers (e.g. the Telegram bot) can alert
    on transitions without re-deriving them.
    """
    from sqlalchemy import select
    from src.core.database import AsyncSessionLocal, TradeRecord, TradeStatusLog, create_tables

    await create_tables()
    now = now or datetime.utcnow()
    signal_by_symbol = {s.symbol: s for s in signals}
    transitions = []

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TradeRecord).where(TradeRecord.status.notin_(TERMINAL_STATUSES))
        )
        open_trades = result.scalars().all()
        open_by_symbol = {t.symbol: t for t in open_trades}

        missing_symbols = [sym for sym in open_by_symbol if sym not in signal_by_symbol]
        extra_prices = {}
        if missing_symbols:
            try:
                from src.data.market_data import fetch_multiple
                dfs = await fetch_multiple(missing_symbols, period="3mo")
                extra_prices = {
                    sym: float(df["close"].iloc[-1]) for sym, df in dfs.items() if not df.empty
                }
            except Exception as exc:
                logger.error("Lifecycle price refresh failed: {}", exc)

        # 1. Open new trades / handle direction flips (trend reversal)
        for sym, sig in signal_by_symbol.items():
            existing = open_by_symbol.get(sym)
            if existing is None:
                trade = _open_trade(sig, now)
                session.add(trade)
                session.add(TradeStatusLog(
                    trade=trade, symbol=sym, status=STATUS_ACTIVE,
                    note="Signal detected", price_at_change=sig.entry_price, changed_at=now,
                ))
                open_by_symbol[sym] = trade
                continue

            if existing.direction != sig.direction.value:
                prior_status = existing.status
                existing.status = STATUS_TREND_REVERSAL
                existing.closed_at = now
                existing.updated_at = now
                session.add(TradeStatusLog(
                    trade=existing, symbol=sym, status=STATUS_TREND_REVERSAL,
                    note=f"Direction flipped {existing.direction} -> {sig.direction.value}",
                    price_at_change=existing.last_price, changed_at=now,
                ))
                transitions.append((existing, prior_status, STATUS_TREND_REVERSAL))

                trade = _open_trade(sig, now)
                session.add(trade)
                session.add(TradeStatusLog(
                    trade=trade, symbol=sym, status=STATUS_ACTIVE,
                    note="Re-opened after trend reversal", price_at_change=sig.entry_price, changed_at=now,
                ))
                open_by_symbol[sym] = trade

        # 2. Refresh every still-open trade with the latest price
        for sym, trade in list(open_by_symbol.items()):
            if trade.status in TERMINAL_STATUSES:
                continue  # just closed by the reversal step above

            sig = signal_by_symbol.get(sym)
            if sig is not None and sig.price_df is not None and not sig.price_df.empty:
                current_price = float(sig.price_df["close"].iloc[-1])
            else:
                current_price = extra_prices.get(sym)
            if current_price is None:
                continue

            prior_status = trade.status
            new_status = evaluate_status(
                trade.direction, trade.entry_price, trade.stop_loss,
                trade.take_profit_1, trade.take_profit_2, current_price,
                trade.opened_at, trade.expected_hold_days, prior_status, now,
            )
            mfe, mae = update_extremes(
                trade.direction, trade.entry_price, current_price, trade.mfe_pct, trade.mae_pct
            )
            trade.mfe_pct = mfe
            trade.mae_pct = mae
            trade.last_price = current_price
            trade.pnl_pct = compute_pnl_pct(trade.direction, trade.entry_price, current_price)
            trade.updated_at = now

            if new_status == STATUS_TARGET_1_HIT and trade.target_1_hit_at is None:
                trade.target_1_hit_at = now

            if new_status != prior_status:
                trade.status = new_status
                if new_status in TERMINAL_STATUSES:
                    trade.closed_at = now
                session.add(TradeStatusLog(
                    trade=trade, symbol=sym, status=new_status,
                    note=f"{STATUS_LABELS.get(prior_status, prior_status)} -> {STATUS_LABELS.get(new_status, new_status)}",
                    price_at_change=current_price, changed_at=now,
                ))
                transitions.append((trade, prior_status, new_status))

        await session.commit()

    return transitions


async def get_active_trades():
    from sqlalchemy import select
    from src.core.database import AsyncSessionLocal, TradeRecord, create_tables
    await create_tables()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TradeRecord)
            .where(TradeRecord.status.notin_(TERMINAL_STATUSES))
            .order_by(TradeRecord.opened_at.desc())
        )
        return result.scalars().all()


async def get_trade_history(limit=500):
    from sqlalchemy import select
    from src.core.database import AsyncSessionLocal, TradeRecord, create_tables
    await create_tables()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TradeRecord).order_by(TradeRecord.opened_at.desc()).limit(limit)
        )
        return result.scalars().all()


async def get_status_log(trade_id):
    from sqlalchemy import select
    from src.core.database import AsyncSessionLocal, TradeStatusLog, create_tables
    await create_tables()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TradeStatusLog)
            .where(TradeStatusLog.trade_id == trade_id)
            .order_by(TradeStatusLog.changed_at.asc())
        )
        return result.scalars().all()
