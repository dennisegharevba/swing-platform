import sys
sys.path.insert(0, "/mount/src/swing-platform")

import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.core.config import get_settings

settings = get_settings()


async def run_daily_scan():
    logger.info("=== DAILY SCAN STARTING ===")
    started = datetime.utcnow()
    from src.core.database import AsyncSessionLocal, ScanLog
    log = ScanLog(scan_type="daily", started_at=started)
    alerts_sent = 0
    error_msg = None

    try:
        from src.signals.scanner import scan_universe
        result = await scan_universe()
        log.symbols_scanned = 13
        log.signals_found = len(result.signals)

        from src.alerts.telegram_bot import send_scan_summary, send_signal_alert, send_status_change_alerts
        await send_scan_summary(result)
        for sig in result.top_signals[:3]:
            await send_signal_alert(sig)
            alerts_sent += 1

        if result.lifecycle_transitions:
            await send_status_change_alerts(result.lifecycle_transitions)
            alerts_sent += len(result.lifecycle_transitions)

        async with AsyncSessionLocal() as session:
            from src.core.database import SignalRecord
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

    logger.info("=== DAILY SCAN COMPLETE ===")


async def run_lifecycle_check():
    """
    Lighter-weight than the full daily scan: re-scans the universe purely to
    refresh trade lifecycle status (target/stop hits, expiry, near-stop
    warnings) and alerts on any transitions. Runs more frequently than the
    once-daily full scan so status updates and countdowns stay current
    throughout market hours.
    """
    logger.info("=== LIFECYCLE CHECK STARTING ===")
    try:
        from src.signals.scanner import scan_universe
        from src.alerts.telegram_bot import send_status_change_alerts
        result = await scan_universe()
        if result.lifecycle_transitions:
            logger.info("Lifecycle check: {} status change(s)", len(result.lifecycle_transitions))
            await send_status_change_alerts(result.lifecycle_transitions)
    except Exception as exc:
        logger.error("Lifecycle check error: {}", exc)
    logger.info("=== LIFECYCLE CHECK COMPLETE ===")


async def run_weekly_cot_scan():
    logger.info("=== WEEKLY COT SCAN STARTING ===")
    from src.data.market_data import _cot_cache
    _cot_cache.clear()
    await run_daily_scan()


def create_scheduler():
    tz = "America/New_York"
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        run_daily_scan,
        CronTrigger(hour=settings.daily_scan_hour, minute=settings.daily_scan_minute, timezone=tz),
        id="daily_scan", name="Daily Market Scan", replace_existing=True,
    )

    scheduler.add_job(
        run_weekly_cot_scan,
        CronTrigger(day_of_week=settings.weekly_cot_day, hour=settings.weekly_cot_hour, minute=0, timezone=tz),
        id="weekly_cot_scan", name="Weekly COT Scan", replace_existing=True,
    )

    scheduler.add_job(
        run_lifecycle_check,
        CronTrigger(day_of_week="mon-fri", hour="0-23", minute="*/15", timezone=tz),
        id="lifecycle_check", name="Signal Lifecycle Check", replace_existing=True,
    )

    return scheduler


async def start_scheduler():
    from src.core.database import create_tables
    await create_tables()
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler running.")
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
