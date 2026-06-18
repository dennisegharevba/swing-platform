"""
Signal Scoring Engine
=====================
Implements the validated research model exactly as specified.
Scores every market from 0Ã¢â‚¬â€œ100 across five components.
No parameter changes.  No new filters.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from src.core.config import (
    AGRICULTURE_MARKETS,
    ALL_MARKETS,
    AssetClass,
    COMMODITY_MARKETS,
    Direction,
    EQUITY_MARKETS,
    REAL_YIELD_MARKETS,
    SCORE_THRESHOLDS,
    SCORE_WEIGHTS,
    SEASONALITY,
)
from src.data.market_data import (
    MarketRegime,
    enrich_ohlcv,
    get_cot_index,
)
from loguru import logger


# ---------------------------------------------------------------------------
# Signal data model
# ---------------------------------------------------------------------------

@dataclass
class ComponentScores:
    commercial_cot: float = 0.0       # 0Ã¢â‚¬â€œ35
    seasonality: float = 0.0          # 0Ã¢â‚¬â€œ25
    macro_regime: float = 0.0         # 0Ã¢â‚¬â€œ20
    trend_alignment: float = 0.0      # 0Ã¢â‚¬â€œ10
    momentum: float = 0.0             # 0Ã¢â‚¬â€œ10

    @property
    def total(self) -> float:
        return (
            self.commercial_cot
            + self.seasonality
            + self.macro_regime
            + self.trend_alignment
            + self.momentum
        )


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

    # Risk parameters (filled by risk engine)
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0
    risk_reward: float = 0.0
    atr_risk_pct: float = 0.0
    expected_hold_days: int = 10

    # Raw COT index for display
    cot_index_raw: float | None = None

    @property
    def score(self) -> float:
        return round(self.scores.total, 1)

    @property
    def passes_threshold(self) -> bool:
        threshold = SCORE_THRESHOLDS.get(self.asset_class, 52)
        return self.score >= threshold

    @property
    def is_valid(self) -> bool:
        return (
            self.direction != Direction.NEUTRAL
            and self.passes_threshold
            and not self.regime.vix_override
        )

    def seasonality_label(self, month: int) -> str:
        bias = SEASONALITY.get(self.symbol, {}).get(month, 0)
        if bias > 0.5:
            return "Bullish"
        if bias < -0.5:
            return "Bearish"
        return "Neutral"


# ---------------------------------------------------------------------------
# Individual component scorers
# ---------------------------------------------------------------------------

def score_commercial_cot(cot_index: float | None, direction: Direction) -> float:
    """
    Commercial COT score (max 35 pts).
    COT index 0Ã¢â‚¬â€œ100: >70 = heavy commercial buying (bullish for price).
    For longs: high COT index Ã¢â€ â€™ high score.
    For shorts: low COT index Ã¢â€ â€™ high score.
    """
    if cot_index is None:
        return 0.0

    w = SCORE_WEIGHTS["commercial_cot"]  # 35

    if direction == Direction.LONG:
        # COT index 70Ã¢â‚¬â€œ100 maps to full score; 0Ã¢â‚¬â€œ30 maps to near zero
        normalized = max(0.0, (cot_index - 30) / 70)
    else:
        # Inverted: low COT index (heavy commercial shorting) is bearish signal
        normalized = max(0.0, (70 - cot_index) / 70)

    return round(min(w, normalized * w), 2)


def score_seasonality(symbol: str, direction: Direction, month: int) -> float:
    """
    Seasonality score (max 25 pts).
    Uses 20-year average monthly bias table.
    """
    w = SCORE_WEIGHTS["seasonality"]  # 25
    bias = SEASONALITY.get(symbol, {}).get(month, 0.0)

    # Scale: bias range roughly -1.5 to +1.5
    # We map [0, 1.5] Ã¢â€ â€™ [0, 25] for the favoured direction
    if direction == Direction.LONG:
        normalized = max(0.0, bias / 1.5)
    else:
        normalized = max(0.0, -bias / 1.5)

    return round(min(w, normalized * w), 2)


def score_macro_regime_equity(
    direction: Direction,
    regime: MarketRegime,
) -> float:
    """
    Equity macro score (max 20 pts).
    Uses VIX (hard override already applied) + US10Y vs 200-MA.
    VIX < 20: full points.  VIX 20-35: partial.
    US10Y: below MA Ã¢â€ â€™ bullish equity; above MA Ã¢â€ â€™ bearish equity.
    """
    w = SCORE_WEIGHTS["macro_regime"]  # 20
    score = 0.0

    # VIX component (up to 12 pts)
    if regime.vix < 20:
        score += 12
    elif regime.vix < 25:
        score += 9
    elif regime.vix < 30:
        score += 5
    elif regime.vix <= 35:
        score += 2

    # US10Y component (up to 8 pts)
    if direction == Direction.LONG and not regime.us10y_above_ma:
        score += 8
    elif direction == Direction.SHORT and regime.us10y_above_ma:
        score += 8
    elif direction == Direction.LONG and regime.us10y_above_ma:
        score += 0   # headwind for longs
    else:
        score += 0

    return round(min(w, score), 2)


def score_macro_regime_commodity(
    symbol: str,
    direction: Direction,
    regime: MarketRegime,
) -> float:
    """
    Commodity macro score (max 20 pts).
    DXY regime: bearish DXY Ã¢â€ â€™ bullish commodities.
    Real yield filter applied to Gold/Silver only.
    """
    w = SCORE_WEIGHTS["macro_regime"]  # 20
    score = 0.0

    # DXY component (up to 14 pts)
    if direction == Direction.LONG and not regime.dxy_bullish:
        score += 14   # bearish DXY helps commodities
    elif direction == Direction.LONG and regime.dxy_bullish:
        score += 3    # headwind
    elif direction == Direction.SHORT and regime.dxy_bullish:
        score += 14
    else:
        score += 3

    # Real yield component Ã¢â‚¬â€ Gold/Silver only (up to 6 pts)
    if symbol in REAL_YIELD_MARKETS:
        if direction == Direction.LONG and not regime.real_yield_rising:
            score += 6   # falling real yields = bullish gold/silver
        elif direction == Direction.SHORT and regime.real_yield_rising:
            score += 6
        else:
            score += 0   # unfavourable

    return round(min(w, score), 2)


def score_macro_regime_agriculture(
    direction: Direction,
    regime: MarketRegime,
) -> float:
    """
    Agriculture macro score (max 20 pts).
    Macro filters have lower importance here; partial credit always given.
    """
    w = SCORE_WEIGHTS["macro_regime"]  # 20
    # Neutral: give partial score since agri macro weight is lower importance
    # Still check DXY softly
    if direction == Direction.LONG and not regime.dxy_bullish:
        return round(w * 0.7, 2)
    if direction == Direction.SHORT and regime.dxy_bullish:
        return round(w * 0.7, 2)
    return round(w * 0.4, 2)


def score_trend_alignment(
    direction: Direction,
    df: pd.DataFrame,
) -> float:
    """
    Trend alignment score (max 10 pts).
    Price vs MA20/MA50/MA200 alignment.
    """
    w = SCORE_WEIGHTS["trend_alignment"]  # 10
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


def score_momentum(direction: Direction, df: pd.DataFrame) -> float:
    """
    Momentum score (max 10 pts).
    RSI alignment and 20-day rate of change.
    """
    w = SCORE_WEIGHTS["momentum"]  # 10
    if df.empty or len(df) < 22:
        return 0.0

    last = df.iloc[-1]
    rsi = last.get("rsi_14")

    score = 0.0
    if pd.isna(rsi):
        return 0.0

    if direction == Direction.LONG:
        # RSI > 50 and not overbought
        if 50 < rsi < 70:
            score += 6
        elif 45 <= rsi <= 50:
            score += 3
        # 20-day momentum
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


# ---------------------------------------------------------------------------
# Direction determination
# ---------------------------------------------------------------------------

def determine_direction(
    cot_index: float | None,
    symbol: str,
    month: int,
    asset_class: AssetClass,
    regime: MarketRegime,
    df: pd.DataFrame,
) -> Direction:
    """
    Determine trade direction from COT signal + seasonality + regime.
    COT is the primary driver.
    """
    if cot_index is None:
        return Direction.NEUTRAL

    season_bias = SEASONALITY.get(symbol, {}).get(month, 0.0)

    # COT primary signal
    if cot_index >= 60:
        cot_dir = Direction.LONG
    elif cot_index <= 40:
        cot_dir = Direction.SHORT
    else:
        # Ambiguous COT Ã¢â‚¬â€ use seasonality as tiebreaker
        if season_bias > 0.3:
            cot_dir = Direction.LONG
        elif season_bias < -0.3:
            cot_dir = Direction.SHORT
        else:
            return Direction.NEUTRAL

    # Apply hard regime overrides for equities
    if asset_class == AssetClass.EQUITY:
        if cot_dir == Direction.LONG and regime.us10y_above_ma:
            # Unfavourable but not blocked Ã¢â‚¬â€ weaken signal via scoring
            pass
        if cot_dir == Direction.SHORT and not regime.us10y_above_ma:
            pass

    # Apply real yield filter for Gold/Silver
    if symbol in REAL_YIELD_MARKETS:
        if cot_dir == Direction.LONG and regime.real_yield_rising:
            # Avoid longs when real yields rising
            return Direction.NEUTRAL

    # Trend confirmation
    if not df.empty and len(df) >= 50:
        last = df.iloc[-1]
        price = last.get("close", 0)
        ma50 = last.get("ma_50")
        if pd.notna(ma50):
            if cot_dir == Direction.LONG and price < ma50 * 0.97:
                return Direction.NEUTRAL  # price too extended below trend
            if cot_dir == Direction.SHORT and price > ma50 * 1.03:
                return Direction.NEUTRAL

    return cot_dir


# ---------------------------------------------------------------------------
# Full signal scorer
# ---------------------------------------------------------------------------

async def score_market(
    symbol: str,
    asset_class: AssetClass,
    df: pd.DataFrame,
    regime: MarketRegime,
) -> SignalResult | None:
    """
    Score a single market and return a SignalResult, or None if not actionable.
    """
    name = ALL_MARKETS.get(symbol, symbol)
    month = datetime.utcnow().month

    # VIX hard override Ã¢â‚¬â€ no new positions at all
    if regime.vix_override:
        logger.info("VIX override ({:.1f}) Ã¢â‚¬â€ skipping {}", regime.vix, symbol)
        return None

    # Enrich price data
    df_enriched = enrich_ohlcv(df) if not df.empty else df

    # Fetch COT
    cot_index = await get_cot_index(symbol)

    # Determine direction
    direction = determine_direction(
        cot_index, symbol, month, asset_class, regime, df_enriched
    )

    if direction == Direction.NEUTRAL:
        return None

    # Score components
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
        symbol=symbol,
        name=name,
        asset_class=asset_class,
        direction=direction,
        scores=components,
        regime=regime,
        price_df=df_enriched,
        cot_index_raw=cot_index,
    )

    if not result.passes_threshold:
        logger.debug(
            "{} score {:.1f} below threshold Ã¢â‚¬â€ skipping",
            symbol, result.score,
        )
        return None

    return result
