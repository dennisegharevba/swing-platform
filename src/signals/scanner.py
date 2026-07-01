import sys
sys.path.insert(0, "/mount/src/swing-platform")
import asyncio
import time
from datetime import datetime
from loguru import logger
from src.core.config import AGRICULTURE_MARKETS, COMMODITY_MARKETS, EQUITY_MARKETS, AssetClass
from src.data.market_data import fetch_market_regime, fetch_multiple, MarketRegime
from src.risk.risk_engine import attach_risk, compute_aggregate_macro_score
from src.signals.scorer import score_market
from src.signals.signal_tracker import sync_signal_history
from src.signals.lifecycle import sync_trade_lifecycle
class ScanResult:
    def __init__(self, signals, regime, scan_duration, scanned_at, lifecycle_transitions=None):
        self.signals = signals
        self.regime = regime
        self.scan_duration = scan_duration
        self.scanned_at = scanned_at
        self.lifecycle_transitions = lifecycle_transitions or []
    @property
    def equities(self):
        return [s for s in self.signals if s.asset_class == AssetClass.EQUITY]
    @property
    def commodities(self):
        return [s for s in self.signals if s.asset_class == AssetClass.COMMODITY]
    @property
    def agriculture(self):
        return [s for s in self.signals if s.asset_class == AssetClass.AGRICULTURE]
    @property
    def top_signals(self):
        return sorted(self.signals, key=lambda s: s.score, reverse=True)[:5]
    @property
    def aggregate_macro_score(self):
        return compute_aggregate_macro_score(self.signals)
async def scan_universe(symbols=None):
    start = time.perf_counter()
    scanned_at = datetime.utcnow()
    if symbols is None:
        all_markets = {**EQUITY_MARKETS, **COMMODITY_MARKETS, **AGRICULTURE_MARKETS}
        symbols = list(all_markets.keys())
    logger.info("Starting scan - {} markets", len(symbols))
    try:
        regime = await fetch_market_regime()
    except Exception as exc:
        logger.error("Failed to fetch regime: {}", exc)
        regime = MarketRegime(vix=20.0, dxy_bullish=False, us10y_above_ma=False, real_yield_rising=False)
    asset_class_map = {}
    for sym in symbols:
        if sym in EQUITY_MARKETS:
            asset_class_map[sym] = AssetClass.EQUITY
        elif sym in COMMODITY_MARKETS:
            asset_class_map[sym] = AssetClass.COMMODITY
        else:
            asset_class_map[sym] = AssetClass.AGRICULTURE
    price_data = await fetch_multiple(symbols)
    tasks = []
    valid_symbols = []
    for sym in symbols:
        df = price_data.get(sym)
        if df is None or df.empty:
            continue
        tasks.append(score_market(sym, asset_class_map[sym], df, regime))
        valid_symbols.append(sym)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    valid_signals = []
    for sym, res in zip(valid_symbols, results):
        if isinstance(res, Exception):
            logger.error("Score error for {}: {}", sym, res)
        elif res is not None:
            res = attach_risk(res)
            valid_signals.append(res)
    if valid_signals:
        try:
            valid_signals = await asyncio.to_thread(sync_signal_history, valid_signals)
        except Exception as exc:
            logger.error("Signal history tracking failed: {}", exc)
    lifecycle_transitions = []
    try:
        lifecycle_transitions = await sync_trade_lifecycle(valid_signals)
    except Exception as exc:
        logger.error("Trade lifecycle sync failed: {}", exc)
    duration = time.perf_counter() - start
    logger.info("Scan complete - {}/{} signals in {:.1f}s", len(valid_signals), len(symbols), duration)
    return ScanResult(
        signals=valid_signals, regime=regime, scan_duration=duration, scanned_at=scanned_at,
        lifecycle_transitions=lifecycle_transitions,
    )
async def scan_equities():
    return await scan_universe(symbols=list(EQUITY_MARKETS.keys()))
async def scan_commodities():
    return await scan_universe(symbols=list(COMMODITY_MARKETS.keys()))
async def scan_agriculture():
    return await scan_universe(symbols=list(AGRICULTURE_MARKETS.keys()))
