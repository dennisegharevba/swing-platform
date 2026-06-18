"""
CLI Entry Point
===============
Usage:
  python -m src.cli scan          # run a full scan now
  python -m src.cli scan --equities
  python -m src.cli scan --commodities
  python -m src.cli scan --agriculture
  python -m src.cli bot           # start Telegram bot (polling)
  python -m src.cli scheduler     # start automated scheduler
  python -m src.cli init-db       # initialise database tables
"""
from __future__ import annotations

import asyncio
import sys

from loguru import logger


def _banner() -> None:
    print("""
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘      COT Intelligence â€” Institutional Swing Platform  â•‘
â•‘      v1.0.0 Â· Production Ready                        â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
""")


async def cmd_scan(subset: str = "all") -> None:
    from src.signals.scanner import (
        scan_universe, scan_equities, scan_commodities, scan_agriculture,
    )
    from src.alerts.telegram_bot import send_scan_summary, send_signal_alert
    from src.core.database import create_tables, AsyncSessionLocal, SignalRecord

    await create_tables()

    if subset == "equities":
        result = await scan_equities()
    elif subset == "commodities":
        result = await scan_commodities()
    elif subset == "agriculture":
        result = await scan_agriculture()
    else:
        result = await scan_universe()

    print(f"\n{'='*60}")
    print(f"SCAN COMPLETE â€” {len(result.signals)} signals found")
    print(f"VIX: {result.regime.vix:.2f} | DXY: {result.regime.dxy_regime} | "
          f"US10Y: {result.regime.us10y_regime}")
    print(f"{'='*60}")

    for sig in result.top_signals:
        print(f"\n  {sig.symbol:5s} {sig.name:20s} "
              f"{sig.direction.value.upper():6s} "
              f"Score={sig.score:.1f}  "
              f"Entry={sig.entry_price:.4f}  "
              f"Stop={sig.stop_loss:.4f}  "
              f"TP2={sig.take_profit_2:.4f}  "
              f"R:R={sig.risk_reward:.1f}x")

    # Persist to DB
    async with AsyncSessionLocal() as session:
        for sig in result.signals:
            record = SignalRecord(
                symbol=sig.symbol, name=sig.name,
                asset_class=sig.asset_class.value,
                direction=sig.direction.value,
                score=sig.score,
                cot_score=sig.scores.commercial_cot,
                seasonality_score=sig.scores.seasonality,
                macro_score=sig.scores.macro_regime,
                trend_score=sig.scores.trend_alignment,
                momentum_score=sig.scores.momentum,
                vix_level=sig.regime.vix,
                dxy_regime=sig.regime.dxy_regime,
                us10y_regime=sig.regime.us10y_regime,
                real_yield_regime=sig.regime.real_yield_regime,
                entry_price=sig.entry_price,
                stop_loss=sig.stop_loss,
                take_profit_1=sig.take_profit_1,
                take_profit_2=sig.take_profit_2,
                risk_reward=sig.risk_reward,
                atr_risk_pct=sig.atr_risk_pct,
                expected_hold_days=sig.expected_hold_days,
                alert_sent=False,
            )
            session.add(record)
        await session.commit()

    # Send Telegram alerts
    await send_scan_summary(result)
    for sig in result.top_signals[:3]:
        await send_signal_alert(sig)

    print(f"\nResults persisted. Telegram alerts sent.")


async def cmd_bot() -> None:
    from src.alerts.telegram_bot import build_application
    app = build_application()
    print("Starting Telegram bot (polling mode)â€¦")
    await app.run_polling()


async def cmd_scheduler() -> None:
    from src.automation.scheduler import start_scheduler
    await start_scheduler()


async def cmd_init_db() -> None:
    from src.core.database import create_tables
    await create_tables()
    print("Database tables created.")


def main() -> None:
    _banner()
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    command = args[0]

    if command == "scan":
        subset = "all"
        if "--equities" in args:
            subset = "equities"
        elif "--commodities" in args:
            subset = "commodities"
        elif "--agriculture" in args:
            subset = "agriculture"
        asyncio.run(cmd_scan(subset))

    elif command == "bot":
        asyncio.run(cmd_bot())

    elif command == "scheduler":
        asyncio.run(cmd_scheduler())

    elif command == "init-db":
        asyncio.run(cmd_init_db())

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
