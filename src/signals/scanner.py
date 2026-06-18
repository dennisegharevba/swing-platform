import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

"""
Market Scanner
==============
Orchestrates the full scan across all 13 markets.
Returns validated, risk-parameterised SignalResult objects.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime

from loguru import logger

from src.core.config import (
    AGRICULTURE_MARKETS,
    COMMODITY_MARKETS,
    EQUITY_MARKETS,
    AssetClass,
)
from src.data.market_data import (
    fetch_market_regime,
    fetch_multiple,
    MarketRegime,
)
from src.risk.risk_engine import attach_risk, compute_aggregate_macro_score
from src.signals.scorer import SignalResult, score_market


class ScanResult:
    """Container for a complete scan pass."""

    def __init__(
        self,
        signals: list[SignalResult],
        regime: MarketRegime,
        scan_duration: float,
        scanned_at: datetime,
    ) -> None:
        self.signals = signals
        self.regime = regime
        self.scan_duration = scan_duration
        self.scanned_at = scanned_at

    @property
    def equities(self) -> list[SignalResult]:
        return [s for s in self.signals if s.asset_class == AssetClass.EQUITY]

    @property
    def commodities(self) -> list[SignalResult]:
        return [s for s in self.signals if s.asset_class == AssetClass.COMMODITY]

    @property
    def agriculture(self) -> list[SignalResult]:
        return [s for s in self.signals if s.asset_class == AssetClass.AGRICULTURE]

    @property
    def top_signals(self) -> list[SignalResult]:
        return sorted(self.signals, key=lambda s: s.score, reverse=True)[:5]

    @property
    def aggregate_macro_score(self) -> float:
        return compute_aggregate_macro_score(self.signals)


async def scan_universe(
    symbols: list[str] | None = None,
) -> ScanResult:
    """
    Run a full (or partial) scan.  Returns ScanResult with all valid signals.
    """
    start = time.perf_counter()
    scanned_at = datetime.utcnow()

    # Build scan list
    if symbols is None:
        all_markets = {
            **EQUITY_MARKETS,
            **COMMODITY_MARKETS,
            **AGRICULTURE_MARKETS,
        }
        symbols = list(all_markets.keys())

    logger.info("Starting scan ??? {} markets", len(symbols))

    # Fetch regime first (shared across all markets)
    try:
        regime = await fetch_market_regime()
        logger.info(
            "Regime: VIX={:.1f} DXY={} US10Y={} RealYield={}",
            regime.vix,
            regime.dxy_regime,
            regime.us10y_regime,
            regime.real_yield_regime,
        )
    except Exception as exc:
        logger.error("Failed to fetch regime: {}", exc)
        from src.data.market_data import MarketRegime
        regime = MarketRegime(
            vix=20.0,
            dxy_bullish=False,
            us10y_above_ma=False,
            real_yield_rising=False,
        )

    # Determine asset class per symbol
    asset_class_map: dict[str, AssetClass] = {}
    for sym in symbols:
        if sym in EQUITY_MARKETS:
            asset_class_map[sym] = AssetClass.EQUITY
        elif sym in COMMODITY_MARKETS:
            asset_class_map[sym] = AssetClass.COMMODITY
        else:
            asset_class_map[sym] = AssetClass.AGRICULTURE

    # Fetch all price data concurrently
    price_data = await fetch_multiple(symbols)

    # Score each market
    tasks = []
    for sym in symbols:
        ac = asset_class_map[sym]
        df = price_data.get(sym)
        if df is None or df.empty:
            logger.warning("No price data for {} ??? skipping", sym)
            continue
        tasks.append(score_market(sym, ac, df, regime))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid_signals: list[SignalResult] = []
    for sym, res in zip(symbols, results):
        if isinstance(res, Exception):
            logger.error("Score error for {}: {}", sym, res)
        elif res is not None:
            # Attach risk parameters
            res = attach_risk(res)
            valid_signals.append(res)
            logger.info(
                "{} {} score={:.1f} entry={:.4f}",
                sym,
                res.direction.value.upper(),
                res.score,
                res.entry_price,
            )

    duration = time.perf_counter() - start
    logger.info(
        "Scan complete ??? {}/{} signals in {:.1f}s",
        len(valid_signals), len(symbols), duration,
    )

    return ScanResult(
        signals=valid_signals,
        regime=regime,
        scan_duration=duration,
        scanned_at=scanned_at,
    )


async def scan_equities() -> ScanResult:
    return await scan_universe(symbols=list(EQUITY_MARKETS.keys()))


async def scan_commodities() -> ScanResult:
    return await scan_universe(symbols=list(COMMODITY_MARKETS.keys()))


async def scan_agriculture() -> ScanResult:
    return await scan_universe(symbols=list(AGRICULTURE_MARKETS.keys()))

