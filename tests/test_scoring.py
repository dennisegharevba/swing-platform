"""
Test Suite — Core Scoring Engine
=================================
Validates the scoring model against specification:
- Component weights sum to 100
- Thresholds enforced correctly
- VIX override fires at >35
- Real yield filter blocks Gold/Silver longs
- Direction logic follows COT primary signal
"""
from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.core.config import AssetClass, Direction, SCORE_WEIGHTS, SCORE_THRESHOLDS
from src.signals.scorer import (
    ComponentScores,
    SignalResult,
    score_commercial_cot,
    score_seasonality,
    score_macro_regime_equity,
    score_macro_regime_commodity,
    score_macro_regime_agriculture,
    score_trend_alignment,
    score_momentum,
    determine_direction,
)
from src.data.market_data import MarketRegime


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_regime(
    vix: float = 18.0,
    dxy_bullish: bool = False,
    us10y_above_ma: bool = False,
    real_yield_rising: bool = False,
) -> MarketRegime:
    return MarketRegime(vix, dxy_bullish, us10y_above_ma, real_yield_rising)


def make_price_df(n: int = 250, trend: str = "up") -> pd.DataFrame:
    """Synthetic OHLCV dataframe."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    base = 100.0
    if trend == "up":
        closes = base + np.cumsum(np.random.normal(0.1, 0.8, n))
    else:
        closes = base + np.cumsum(np.random.normal(-0.1, 0.8, n))
    closes = np.maximum(closes, 10)
    df = pd.DataFrame({
        "open":   closes * np.random.uniform(0.995, 1.0, n),
        "high":   closes * np.random.uniform(1.001, 1.015, n),
        "low":    closes * np.random.uniform(0.985, 0.999, n),
        "close":  closes,
        "volume": np.random.randint(100000, 500000, n).astype(float),
    }, index=dates)
    return df


# ── Score weight validation ───────────────────────────────────────────────────

def test_score_weights_sum_to_100():
    assert sum(SCORE_WEIGHTS.values()) == 100, "Score weights must sum to 100"


def test_score_weight_keys():
    expected = {"commercial_cot", "seasonality", "macro_regime", "trend_alignment", "momentum"}
    assert set(SCORE_WEIGHTS.keys()) == expected


def test_score_thresholds_defined():
    for ac in [AssetClass.EQUITY, AssetClass.COMMODITY, AssetClass.AGRICULTURE]:
        assert ac in SCORE_THRESHOLDS
    assert SCORE_THRESHOLDS[AssetClass.AGRICULTURE] == 48
    assert SCORE_THRESHOLDS[AssetClass.EQUITY] == 52
    assert SCORE_THRESHOLDS[AssetClass.COMMODITY] == 52


# ── COT scoring ───────────────────────────────────────────────────────────────

def test_cot_score_long_high_index():
    """High COT index (90) for long should give near-maximum score."""
    score = score_commercial_cot(90.0, Direction.LONG)
    assert score >= 30, f"Expected ≥30, got {score}"
    assert score <= 35


def test_cot_score_short_low_index():
    """Low COT index (10) for short should give near-maximum score."""
    score = score_commercial_cot(10.0, Direction.SHORT)
    assert score >= 30


def test_cot_score_long_low_index():
    """Low COT index for long should give low score."""
    score = score_commercial_cot(10.0, Direction.LONG)
    assert score <= 5


def test_cot_score_none():
    assert score_commercial_cot(None, Direction.LONG) == 0.0


def test_cot_score_never_exceeds_max():
    for v in [0, 25, 50, 75, 100]:
        for d in [Direction.LONG, Direction.SHORT]:
            s = score_commercial_cot(float(v), d)
            assert s <= SCORE_WEIGHTS["commercial_cot"]
            assert s >= 0


# ── Seasonality scoring ───────────────────────────────────────────────────────

def test_seasonality_score_range():
    from src.core.config import SEASONALITY
    for sym in SEASONALITY:
        for month in range(1, 13):
            for d in [Direction.LONG, Direction.SHORT]:
                s = score_seasonality(sym, d, month)
                assert 0 <= s <= 25, f"{sym} m={month} d={d} score={s}"


def test_seasonality_gold_bullish_august():
    """Gold August has positive bias — long should score higher than short."""
    long_s  = score_seasonality("GC", Direction.LONG, 8)
    short_s = score_seasonality("GC", Direction.SHORT, 8)
    assert long_s > short_s


# ── Macro regime scoring ──────────────────────────────────────────────────────

def test_equity_macro_vix_below_20():
    regime = make_regime(vix=16.0, us10y_above_ma=False)
    s = score_macro_regime_equity(Direction.LONG, regime)
    assert s >= 18, "Low VIX + below MA200 should be near max"


def test_equity_macro_vix_override_check():
    """VIX override check is at the SignalResult level, not component level."""
    regime = make_regime(vix=40.0)
    assert regime.vix_override is True


def test_equity_macro_us10y_headwind_for_longs():
    regime_good = make_regime(vix=18.0, us10y_above_ma=False)
    regime_bad  = make_regime(vix=18.0, us10y_above_ma=True)
    s_good = score_macro_regime_equity(Direction.LONG, regime_good)
    s_bad  = score_macro_regime_equity(Direction.LONG, regime_bad)
    assert s_good > s_bad


def test_commodity_macro_bearish_dxy_favours_longs():
    regime_bear_dxy = make_regime(dxy_bullish=False)
    regime_bull_dxy = make_regime(dxy_bullish=True)
    s_good = score_macro_regime_commodity("HG", Direction.LONG, regime_bear_dxy)
    s_bad  = score_macro_regime_commodity("HG", Direction.LONG, regime_bull_dxy)
    assert s_good > s_bad


def test_real_yield_filter_gold_long():
    """Rising real yields should reduce Gold long macro score."""
    regime_ry_falling = make_regime(dxy_bullish=False, real_yield_rising=False)
    regime_ry_rising  = make_regime(dxy_bullish=False, real_yield_rising=True)
    s_good = score_macro_regime_commodity("GC", Direction.LONG, regime_ry_falling)
    s_bad  = score_macro_regime_commodity("GC", Direction.LONG, regime_ry_rising)
    assert s_good > s_bad


def test_real_yield_NOT_applied_to_copper():
    """Real yield should not affect Copper macro score."""
    regime_ry_rising  = make_regime(dxy_bullish=False, real_yield_rising=True)
    regime_ry_falling = make_regime(dxy_bullish=False, real_yield_rising=False)
    s1 = score_macro_regime_commodity("HG", Direction.LONG, regime_ry_rising)
    s2 = score_macro_regime_commodity("HG", Direction.LONG, regime_ry_falling)
    # Copper should get same score regardless of real yield
    assert s1 == s2


def test_macro_scores_never_exceed_max():
    for vix in [15.0, 25.0, 34.0]:
        for dxy in [True, False]:
            for us10y in [True, False]:
                for ry in [True, False]:
                    r = make_regime(vix, dxy, us10y, ry)
                    for d in [Direction.LONG, Direction.SHORT]:
                        se = score_macro_regime_equity(d, r)
                        assert 0 <= se <= 20, f"Equity macro {se}"
                        sc = score_macro_regime_commodity("GC", d, r)
                        assert 0 <= sc <= 20, f"Commodity macro {sc}"
                        sa = score_macro_regime_agriculture(d, r)
                        assert 0 <= sa <= 20, f"Agri macro {sa}"


# ── Trend & Momentum ──────────────────────────────────────────────────────────

def test_trend_score_uptrend_long():
    from src.data.market_data import enrich_ohlcv
    df = enrich_ohlcv(make_price_df(250, trend="up"))
    s = score_trend_alignment(Direction.LONG, df)
    assert s >= 0
    assert s <= 10


def test_trend_score_empty_df():
    assert score_trend_alignment(Direction.LONG, pd.DataFrame()) == 0.0


def test_momentum_score_range():
    from src.data.market_data import enrich_ohlcv
    df = enrich_ohlcv(make_price_df(100))
    for d in [Direction.LONG, Direction.SHORT]:
        s = score_momentum(d, df)
        assert 0 <= s <= 10


# ── Direction determination ───────────────────────────────────────────────────

def test_direction_high_cot_is_long():
    df = make_price_df(250)
    regime = make_regime()
    d = determine_direction(80.0, "GC", 8, AssetClass.COMMODITY, regime, df)
    assert d == Direction.LONG


def test_direction_low_cot_is_short():
    df = make_price_df(250)
    regime = make_regime()
    d = determine_direction(15.0, "GC", 1, AssetClass.COMMODITY, regime, df)
    assert d == Direction.SHORT


def test_direction_gold_long_blocked_by_rising_real_yield():
    df = make_price_df(250)
    regime = make_regime(real_yield_rising=True)
    d = determine_direction(85.0, "GC", 8, AssetClass.COMMODITY, regime, df)
    # Gold long blocked when real yields rising
    assert d == Direction.NEUTRAL


def test_direction_copper_NOT_blocked_by_real_yield():
    """Copper must NOT be subject to real yield filter."""
    df = make_price_df(250)
    regime = make_regime(real_yield_rising=True)
    d = determine_direction(85.0, "HG", 3, AssetClass.COMMODITY, regime, df)
    # Copper should still be LONG if COT is high
    assert d == Direction.LONG


def test_direction_neutral_cot_uses_seasonality():
    df = make_price_df(250)
    regime = make_regime()
    # COT = 50 (neutral), August gold is seasonally bullish
    d = determine_direction(50.0, "GC", 8, AssetClass.COMMODITY, regime, df)
    assert d in (Direction.LONG, Direction.NEUTRAL)


# ── SignalResult ──────────────────────────────────────────────────────────────

def test_signal_result_total_score():
    scores = ComponentScores(
        commercial_cot=28.0,
        seasonality=18.0,
        macro_regime=15.0,
        trend_alignment=8.0,
        momentum=7.0,
    )
    assert scores.total == pytest.approx(76.0)


def test_signal_result_passes_threshold():
    regime = make_regime()
    scores = ComponentScores(commercial_cot=28, seasonality=18, macro_regime=14,
                             trend_alignment=7, momentum=6)
    sig = SignalResult(
        symbol="GC", name="Gold", asset_class=AssetClass.COMMODITY,
        direction=Direction.LONG, scores=scores, regime=regime,
        price_df=pd.DataFrame(),
    )
    assert sig.passes_threshold is True  # 73 > 52


def test_signal_result_fails_threshold():
    regime = make_regime()
    scores = ComponentScores(commercial_cot=10, seasonality=8, macro_regime=5,
                             trend_alignment=2, momentum=1)
    sig = SignalResult(
        symbol="GC", name="Gold", asset_class=AssetClass.COMMODITY,
        direction=Direction.LONG, scores=scores, regime=regime,
        price_df=pd.DataFrame(),
    )
    assert sig.passes_threshold is False  # 26 < 52


def test_signal_vix_override_invalidates():
    regime = make_regime(vix=40.0)
    scores = ComponentScores(commercial_cot=35, seasonality=25, macro_regime=20,
                             trend_alignment=10, momentum=10)
    sig = SignalResult(
        symbol="NQ", name="Nasdaq 100", asset_class=AssetClass.EQUITY,
        direction=Direction.LONG, scores=scores, regime=regime,
        price_df=pd.DataFrame(),
    )
    assert sig.is_valid is False


# ── Risk engine ───────────────────────────────────────────────────────────────

def test_risk_engine_stop_below_entry_for_long():
    from src.risk.risk_engine import compute_risk_parameters
    from src.data.market_data import enrich_ohlcv

    df = enrich_ohlcv(make_price_df(100))
    regime = make_regime()
    scores = ComponentScores(commercial_cot=28, seasonality=18, macro_regime=14,
                             trend_alignment=7, momentum=6)
    sig = SignalResult(
        symbol="GC", name="Gold", asset_class=AssetClass.COMMODITY,
        direction=Direction.LONG, scores=scores, regime=regime, price_df=df,
    )
    params = compute_risk_parameters(sig)
    assert params is not None
    assert params.stop_loss < params.entry
    assert params.take_profit_1 > params.entry
    assert params.take_profit_2 > params.take_profit_1
    assert params.risk_reward >= 1.5


def test_risk_engine_stop_above_entry_for_short():
    from src.risk.risk_engine import compute_risk_parameters
    from src.data.market_data import enrich_ohlcv

    df = enrich_ohlcv(make_price_df(100))
    regime = make_regime()
    scores = ComponentScores(commercial_cot=28, seasonality=18, macro_regime=14,
                             trend_alignment=7, momentum=6)
    sig = SignalResult(
        symbol="NQ", name="Nasdaq", asset_class=AssetClass.EQUITY,
        direction=Direction.SHORT, scores=scores, regime=regime, price_df=df,
    )
    params = compute_risk_parameters(sig)
    assert params is not None
    assert params.stop_loss > params.entry
    assert params.take_profit_1 < params.entry
    assert params.take_profit_2 < params.take_profit_1


def test_cash_requirement_low_macro():
    from src.risk.risk_engine import compute_portfolio_cash_requirement
    assert compute_portfolio_cash_requirement(40.0) == pytest.approx(0.30)
    assert compute_portfolio_cash_requirement(60.0) == pytest.approx(0.15)
    assert compute_portfolio_cash_requirement(48.0) == pytest.approx(0.15)  # boundary
    assert compute_portfolio_cash_requirement(47.9) == pytest.approx(0.30)
