"""
Risk Management Engine
======================
Computes entry, stop loss, TP1, TP2, ATR risk, and expected hold time
for every qualifying signal.  No approximations — all values derived from
live price data and validated parameters.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from src.core.config import (
    ATR_PERIOD,
    ATR_STOP_MULTIPLIER,
    EXPECTED_HOLD_DAYS_MAX,
    EXPECTED_HOLD_DAYS_MIN,
    TP1_RISK_REWARD,
    TP2_RISK_REWARD,
    AssetClass,
    Direction,
    get_settings,
)
from src.signals.scorer import SignalResult

settings = get_settings()


@dataclass
class RiskParameters:
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward: float         # based on TP2
    atr: float
    atr_risk_pct: float        # (entry - stop) / entry
    expected_hold_days: int
    position_size_pct: float   # % of portfolio to deploy

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.stop_loss)

    @property
    def reward_tp1(self) -> float:
        return abs(self.take_profit_1 - self.entry)

    @property
    def reward_tp2(self) -> float:
        return abs(self.take_profit_2 - self.entry)


def compute_risk_parameters(signal: SignalResult) -> RiskParameters | None:
    """
    Compute all risk parameters for a validated signal.
    Returns None if price data is insufficient.
    """
    df = signal.price_df
    if df.empty or len(df) < ATR_PERIOD + 2:
        return None

    # Latest price
    last = df.iloc[-1]
    entry = float(last["close"])

    # ATR-based stop
    atr_col = "atr_14" if "atr_14" in df.columns else None
    if atr_col and pd.notna(last.get(atr_col)):
        atr = float(last[atr_col])
    else:
        # Compute manually from last N bars
        highs = df["high"].iloc[-ATR_PERIOD:]
        lows = df["low"].iloc[-ATR_PERIOD:]
        closes = df["close"].iloc[-ATR_PERIOD - 1:-1]
        tr = pd.concat(
            [highs - lows,
             (highs - closes.values).abs(),
             (lows - closes.values).abs()],
            axis=1,
        ).max(axis=1)
        atr = float(tr.mean())

    stop_distance = atr * ATR_STOP_MULTIPLIER

    if signal.direction == Direction.LONG:
        stop_loss = entry - stop_distance
        tp1 = entry + stop_distance * TP1_RISK_REWARD
        tp2 = entry + stop_distance * TP2_RISK_REWARD
    else:
        stop_loss = entry + stop_distance
        tp1 = entry - stop_distance * TP1_RISK_REWARD
        tp2 = entry - stop_distance * TP2_RISK_REWARD

    risk_per_unit = abs(entry - stop_loss)
    rr = (abs(tp2 - entry) / risk_per_unit) if risk_per_unit > 0 else 0.0
    atr_risk_pct = (risk_per_unit / entry) * 100

    # Expected hold time based on asset class and ATR normalised by price
    daily_atr_pct = (atr / entry) * 100
    if daily_atr_pct > 2.5:
        hold_days = EXPECTED_HOLD_DAYS_MIN
    elif daily_atr_pct > 1.0:
        hold_days = 10
    else:
        hold_days = EXPECTED_HOLD_DAYS_MAX

    # Adjust for asset class
    if signal.asset_class == AssetClass.AGRICULTURE:
        hold_days = max(hold_days, 12)

    # Position sizing: risk 2% of portfolio, size accordingly
    max_risk_pct = settings.max_portfolio_risk_pct
    position_size_pct = (max_risk_pct / (atr_risk_pct / 100)) if atr_risk_pct > 0 else 0.05
    position_size_pct = round(min(0.15, max(0.02, position_size_pct)), 4)

    return RiskParameters(
        entry=round(entry, 4),
        stop_loss=round(stop_loss, 4),
        take_profit_1=round(tp1, 4),
        take_profit_2=round(tp2, 4),
        risk_reward=round(rr, 2),
        atr=round(atr, 4),
        atr_risk_pct=round(atr_risk_pct, 2),
        expected_hold_days=hold_days,
        position_size_pct=position_size_pct,
    )


def attach_risk(signal: SignalResult) -> SignalResult:
    """Compute and attach risk parameters to a SignalResult in-place."""
    params = compute_risk_parameters(signal)
    if params:
        signal.entry_price = params.entry
        signal.stop_loss = params.stop_loss
        signal.take_profit_1 = params.take_profit_1
        signal.take_profit_2 = params.take_profit_2
        signal.risk_reward = params.risk_reward
        signal.atr_risk_pct = params.atr_risk_pct
        signal.expected_hold_days = params.expected_hold_days
    return signal


def compute_portfolio_cash_requirement(macro_score: float) -> float:
    """
    Return the required cash reserve percentage.
    Macro score < 48 → 30% cash.  Otherwise → 15%.
    """
    from src.core.config import get_settings
    s = get_settings()
    if macro_score < 48:
        return s.high_risk_cash_reserve_pct
    return s.min_cash_reserve_pct


def compute_aggregate_macro_score(signals: list[SignalResult]) -> float:
    """
    Aggregate macro component score across all signals for portfolio-level
    cash management decision.
    """
    if not signals:
        return 50.0
    macro_scores = [s.scores.macro_regime for s in signals]
    # Normalise to 0–100 scale (macro max is 20)
    avg_macro = sum(macro_scores) / len(macro_scores)
    return round((avg_macro / 20) * 100, 1)
