"""
Automation Scheduler
====================
APScheduler-based job runner.
Daily scan at configured time.
Weekly COT scan on Friday after 16:00 ET.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.core.config import get_settings
from src.core.database import AsyncSessionLocal, ScanLog, create_tables
from src.signals.scanner import scan_universe

settings = get_settings()


async def run_daily_scan() -> None:
    """Daily automated scan â€” sends top alerts."""
    logger.info("=== DAILY SCAN STARTING ===")
    started = datetime.utcnow()
    log = ScanLog(scan_type="daily", started_at=started)
    alerts_sent = 0
    error_msg = None

    try:
        result = await scan_universe()
        log.symbols_scanned = 13
        log.signals_found = len(result.signals)

        # Send alerts
        from src.alerts.telegram_bot import send_scan_summary, send_signal_alert

        await send_scan_summary(result)
        for sig in result.top_signals[:3]:
            await send_signal_alert(sig)
            alerts_sent += 1

        # Persist signals to database
        async with AsyncSessionLocal() as session:
            from src.core.database import SignalRecord

            for sig in result.signals:
                record = SignalRecord(
                    symbol=sig.symbol,
                    name=sig.name,
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
                    alert_sent=True,
                )
                session.add(record)
            await session.commit()

        log.alerts_sent = alerts_sent

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Daily scan error: {}", exc)

    finally:
        completed = datetime.utcnow()
        log.completed_at = completed
        log.duration_seconds = (completed - started).total_seconds()
        log.error = error_msg
        try:
            async with AsyncSessionLocal() as session:
                session.add(log)
                await session.commit()
        except Exception as db_exc:
            logger.error("Failed to persist scan log: {}", db_exc)

    logger.info(
        "=== DAILY SCAN COMPLETE: {} signals, {} alerts ===",
        log.signals_found,
        log.alerts_sent,
    )


async def run_weekly_cot_scan() -> None:
    """
    Weekly COT scan â€” runs Friday after COT data release.
    Full analysis including fresh COT download.
    """
    logger.info("=== WEEKLY COT SCAN STARTING ===")
    # Clear COT cache to force fresh download
    from src.data.market_data import _cot_cache
    _cot_cache.clear()
    logger.info("COT cache cleared â€” fetching fresh CFTC data")
    await run_daily_scan()


def create_scheduler() -> AsyncIOScheduler:
    """Build and return configured APScheduler instance."""
    tz = "America/New_York"
    scheduler = AsyncIOScheduler(timezone=tz)

    # Daily scan
    scheduler.add_job(
        run_daily_scan,
        CronTrigger(
            hour=settings.daily_scan_hour,
            minute=settings.daily_scan_minute,
            timezone=tz,
        ),
        id="daily_scan",
        name="Daily Market Scan",
        replace_existing=True,
    )

    # Weekly COT scan â€” Friday 16:00 ET (after CFTC release)
    scheduler.add_job(
        run_weekly_cot_scan,
        CronTrigger(
            day_of_week=settings.weekly_cot_day,
            hour=settings.weekly_cot_hour,
            minute=0,
            timezone=tz,
        ),
        id="weekly_cot_scan",
        name="Weekly COT Scan",
        replace_existing=True,
    )

    logger.info(
        "Scheduler configured â€” daily={}:{:02d}, COT=Friday {}:00 ET",
        settings.daily_scan_hour,
        settings.daily_scan_minute,
        settings.weekly_cot_hour,
    )
    return scheduler


async def start_scheduler() -> None:
    """Initialise DB tables and start the scheduler loop."""
    await create_tables()
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler running. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped.")
