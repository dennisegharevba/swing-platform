import sys
sys.path.insert(0, "/mount/src/swing-platform")


from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd

from src.core.config import (
    ALL_MARKETS,
    AssetClass,
    Direction,
    REAL_YIELD_MARKETS,
    SCORE_THRESHOLDS,
    SCORE_WEIGHTS,
    SEASONALITY,
)
from src.data.market_data import MarketRegime, enrich_ohlcv, get_cot_index
from loguru import logger


@dataclass
class ComponentScores:
    commercial_cot: float = 0.0
    seasonality: float = 0.0
    macro_regime: float = 0.0
    trend_alignment: float = 0.0
    momentum: float = 0.0

    @property
    def total(self):
        return (self.commercial_cot + self.seasonality + self.macro_regime
                + self.trend_alignment + self.momentum)


@dataclass
class SignalResult:
    symbol: str
    name: str
    asset_class: AssetClass
    direction: Direction
    scores: ComponentScores
    regime: MarketRegime
    price_df: pd.DataFrame
    scanned_at: datetime = field(default_factory=datetime.utcnow)
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0
    risk_reward: float = 0.0
    atr_risk_pct: float = 0.0
    expected_hold_days: int = 10
    cot_index_raw: float = None
    # Date the signal first appeared (stamped by signal_tracker.sync_signal_history).
    # None until the scanner runs it through the tracker.
    first_seen_date: date = None

    @property
    def score(self):
        return round(self.scores.total, 1)

    @property
    def passes_threshold(self):
        threshold = SCORE_THRESHOLDS.get(self.asset_class, 52)
        return self.score >= threshold

    @property
    def is_valid(self):
        return (self.direction != Direction.NEUTRAL
                and self.passes_threshold
                and not self.regime.vix_override)

    @property
    def days_in_signal(self):
        """1-indexed: the day the signal first appeared counts as Day 1."""
        if not self.first_seen_date:
            return 1
        return (datetime.utcnow().date() - self.first_seen_date).days + 1

    @property
    def days_remaining(self):
        """Can go negative once the signal has run past its expected hold window."""
        return self.expected_hold_days - self.days_in_signal

    @property
    def signal_age_label(self):
        held = self.days_in_signal
        remaining = self.days_remaining
        if remaining < 0:
            return f"Day {held} - overdue by {abs(remaining)}d"
        return f"Day {held} of ~{self.expected_hold_days} - {remaining}d left"

    def seasonality_label(self, month):
        bias = SEASONALITY.get(self.symbol, {}).get(month, 0)
        if bias > 0.5:
            return "Bullish"
        if bias < -0.5:
            return "Bearish"
        return "Neutral"


def score_commercial_cot(cot_index, direction):
    if cot_index is None:
        return 0.0
    w = SCORE_WEIGHTS["commercial_cot"]
    if direction == Direction.LONG:
        normalized = max(0.0, (cot_index - 30) / 70)
    else:
        normalized = max(0.0, (70 - cot_index) / 70)
    return round(min(w, normalized * w), 2)


def score_seasonality(symbol, direction, month):
    w = SCORE_WEIGHTS["seasonality"]
    bias = SEASONALITY.get(symbol, {}).get(month, 0.0)
    if direction == Direction.LONG:
        normalized = max(0.0, bias / 1.5)
    else:
        normalized = max(0.0, -bias / 1.5)
    return round(min(w, normalized * w), 2)


def score_macro_regime_equity(direction, regime):
    w = SCORE_WEIGHTS["macro_regime"]
    score = 0.0
    if regime.vix < 20:
        score += 12
    elif regime.vix < 25:
        score += 9
    elif regime.vix < 30:
        score += 5
    elif regime.vix <= 35:
        score += 2
    if direction == Direction.LONG and not regime.us10y_above_ma:
        score += 8
    elif direction == Direction.SHORT and regime.us10y_above_ma:
        score += 8
    return round(min(w, score), 2)


def score_macro_regime_commodity(symbol, direction, regime):
    w = SCORE_WEIGHTS["macro_regime"]
    score = 0.0
    if direction == Direction.LONG and not regime.dxy_bullish:
        score += 14
    elif direction == Direction.LONG and regime.dxy_bullish:
        score += 3
    elif direction == Direction.SHORT and regime.dxy_bullish:
        score += 14
    else:
        score += 3
    if symbol in REAL_YIELD_MARKETS:
        if direction == Direction.LONG and not regime.real_yield_rising:
            score += 6
        elif direction == Direction.SHORT and regime.real_yield_rising:
            score += 6
    return round(min(w, score), 2)


def score_macro_regime_agriculture(direction, regime):
    w = SCORE_WEIGHTS["macro_regime"]
    if direction == Direction.LONG and not regime.dxy_bullish:
        return round(w * 0.7, 2)
    if direction == Direction.SHORT and regime.dxy_bullish:
        return round(w * 0.7, 2)
    return round(w * 0.4, 2)


def score_trend_alignment(direction, df):
    w = SCORE_WEIGHTS["trend_alignment"]
    if df.empty or len(df) < 50:
        return 0.0
    last = df.iloc[-1]
    price = last.get("close", 0)
    ma20 = last.get("ma_20")
    ma50 = last.get("ma_50")
    ma200 = last.get("ma_200")
    points = 0
    if direction == Direction.LONG:
        if pd.notna(ma20) and price > ma20:
            points += 3
        if pd.notna(ma50) and price > ma50:
            points += 3
        if pd.notna(ma200) and price > ma200:
            points += 4
    else:
        if pd.notna(ma20) and price < ma20:
            points += 3
        if pd.notna(ma50) and price < ma50:
            points += 3
        if pd.notna(ma200) and price < ma200:
            points += 4
    return float(min(w, points))


def score_momentum(direction, df):
    w = SCORE_WEIGHTS["momentum"]
    if df.empty or len(df) < 22:
        return 0.0
    last = df.iloc[-1]
    rsi = last.get("rsi_14")
    score = 0.0
    if pd.isna(rsi):
        return 0.0
    if direction == Direction.LONG:
        if 50 < rsi < 70:
            score += 6
        elif 45 <= rsi <= 50:
            score += 3
        roc_20 = (df["close"].iloc[-1] / df["close"].iloc[-21] - 1) * 100
        if roc_20 > 2:
            score += 4
        elif roc_20 > 0:
            score += 2
    else:
        if 30 < rsi < 50:
            score += 6
        elif 50 <= rsi <= 55:
            score += 3
        roc_20 = (df["close"].iloc[-1] / df["close"].iloc[-21] - 1) * 100
        if roc_20 < -2:
            score += 4
        elif roc_20 < 0:
            score += 2
    return round(min(w, score), 2)


def determine_direction(cot_index, symbol, month, asset_class, regime, df):
    if cot_index is None:
        return Direction.NEUTRAL
    season_bias = SEASONALITY.get(symbol, {}).get(month, 0.0)
    if cot_index >= 60:
        cot_dir = Direction.LONG
    elif cot_index <= 40:
        cot_dir = Direction.SHORT
    else:
        if season_bias > 0.3:
            cot_dir = Direction.LONG
        elif season_bias < -0.3:
            cot_dir = Direction.SHORT
        else:
            return Direction.NEUTRAL
    if symbol in REAL_YIELD_MARKETS:
        if cot_dir == Direction.LONG and regime.real_yield_rising:
            return Direction.NEUTRAL
    if not df.empty and len(df) >= 50:
        last = df.iloc[-1]
        price = last.get("close", 0)
        ma50 = last.get("ma_50")
        if pd.notna(ma50):
            if cot_dir == Direction.LONG and price < ma50 * 0.97:
                return Direction.NEUTRAL
            if cot_dir == Direction.SHORT and price > ma50 * 1.03:
                return Direction.NEUTRAL
    return cot_dir


async def score_market(symbol, asset_class, df, regime):
    name = ALL_MARKETS.get(symbol, symbol)
    month = datetime.utcnow().month
    if regime.vix_override:
        return None
    df_enriched = enrich_ohlcv(df) if not df.empty else df
    cot_index = await get_cot_index(symbol)
    direction = determine_direction(cot_index, symbol, month, asset_class, regime, df_enriched)
    if direction == Direction.NEUTRAL:
        return None
    cot_score = score_commercial_cot(cot_index, direction)
    season_score = score_seasonality(symbol, direction, month)
    if asset_class == AssetClass.EQUITY:
        macro_score = score_macro_regime_equity(direction, regime)
    elif asset_class == AssetClass.COMMODITY:
        macro_score = score_macro_regime_commodity(symbol, direction, regime)
    else:
        macro_score = score_macro_regime_agriculture(direction, regime)
    trend_score = score_trend_alignment(direction, df_enriched)
    mom_score = score_momentum(direction, df_enriched)
    components = ComponentScores(
        commercial_cot=cot_score,
        seasonality=season_score,
        macro_regime=macro_score,
        trend_alignment=trend_score,
        momentum=mom_score,
    )
    result = SignalResult(
        symbol=symbol, name=name, asset_class=asset_class,
        direction=direction, scores=components, regime=regime,
        price_df=df_enriched, cot_index_raw=cot_index,
    )
    if not result.passes_threshold:
        return None
    return result
