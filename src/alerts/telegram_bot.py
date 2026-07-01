import sys
sys.path.insert(0, "/mount/src/swing-platform")

import asyncio
from datetime import datetime
from typing import Any

from loguru import logger

from src.core.config import (
    ALL_MARKETS,
    AGRICULTURE_MARKETS,
    COMMODITY_MARKETS,
    EQUITY_MARKETS,
    AssetClass,
    Direction,
    get_settings,
)

settings = get_settings()

try:
    from telegram import Bot, Update
    from telegram.constants import ParseMode
    from telegram.ext import Application, CommandHandler, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed")

DIRECTION_EMOJI = {Direction.LONG: "🟢", Direction.SHORT: "🔴"}
ASSET_EMOJI = {
    AssetClass.EQUITY: "📈",
    AssetClass.COMMODITY: "🏅",
    AssetClass.AGRICULTURE: "🌾",
}


def format_signal_alert(signal):
    from src.signals.lifecycle import classify_session, format_countdown, signal_age_bucket
    from datetime import datetime, timedelta

    month = signal.scanned_at.month
    season_label = signal.seasonality_label(month)
    dir_emoji = DIRECTION_EMOJI.get(signal.direction, "⚪")
    asset_emoji = ASSET_EMOJI.get(signal.asset_class, "")
    cot_str = f"{signal.scores.commercial_cot:.0f}/35"
    if signal.cot_index_raw is not None:
        cot_str += f" (Index: {signal.cot_index_raw:.0f})"

    now = datetime.utcnow()
    first_seen = signal.first_seen_date
    if first_seen:
        issued_dt = datetime.combine(first_seen, datetime.min.time())
        age = now - issued_dt
        deadline = issued_dt + timedelta(days=signal.expected_hold_days)
        age_line = (
            f"⏱ <b>Issued:</b> {first_seen.strftime('%Y-%m-%d')} "
            f"({classify_session(now)} session at scan time)\n"
            f"  • Age: {signal_age_bucket(age)} — {signal.days_in_signal}d elapsed\n"
            f"  • Countdown to expected expiry: {format_countdown(deadline - now)}"
        )
    else:
        age_line = "⏱ <b>Issued:</b> Just now"

    lines = [
        "🔥 <b>ELITE SWING TRADE</b>",
        "",
        f"{asset_emoji} <b>Asset:</b> {signal.name} ({signal.symbol})",
        f"{dir_emoji} <b>Direction:</b> {signal.direction.value.upper()}",
        "",
        age_line,
        "",
        f"📊 <b>Score:</b> {signal.score}/100",
        f"  • Commercial COT: {cot_str}",
        f"  • Seasonality: {season_label} ({signal.scores.seasonality:.0f}/25)",
        f"  • Macro Regime: {signal.scores.macro_regime:.0f}/20",
        f"  • Trend Alignment: {signal.scores.trend_alignment:.0f}/10",
        f"  • Momentum: {signal.scores.momentum:.0f}/10",
        "",
    ]

    if signal.asset_class == AssetClass.EQUITY:
        lines += [
            "⚡ <b>Regime Filters:</b>",
            f"  • VIX: {signal.regime.vix:.1f}",
            f"  • US10Y: {'Above' if signal.regime.us10y_above_ma else 'Below'} 200-MA",
        ]
    elif signal.asset_class == AssetClass.COMMODITY:
        lines += [
            "⚡ <b>Regime Filters:</b>",
            f"  • DXY: {signal.regime.dxy_regime.title()} Regime",
        ]
        if signal.symbol in ("GC", "SI"):
            ry = "Rising ⚠️" if signal.regime.real_yield_rising else "Falling ✅"
            lines.append(f"  • Real Yield: {ry}")
    else:
        lines += ["⚡ <b>Market Focus:</b> Seasonal + COT driven"]

    lines += [
        "",
        "💰 <b>Trade Setup:</b>",
        f"  • Entry:  {signal.entry_price:.4f}",
        f"  • Stop:   {signal.stop_loss:.4f}",
        f"  • TP1:    {signal.take_profit_1:.4f}",
        f"  • TP2:    {signal.take_profit_2:.4f}",
        "",
        f"📐 <b>Risk/Reward:</b> {signal.risk_reward:.1f}x",
        f"📉 <b>ATR Risk:</b> {signal.atr_risk_pct:.2f}%",
        f"🕐 <b>Expected Hold:</b> {signal.expected_hold_days} Days",
        "",
        f"🤖 <i>COT Intelligence — {signal.scanned_at.strftime('%Y-%m-%d %H:%M UTC')}</i>",
    ]
    return "\n".join(lines)


def format_scan_summary(result):
    override_str = " ⛔ OVERRIDE ACTIVE" if result.regime.vix_override else ""
    lines = [
        "🔍 <b>FULL SCAN COMPLETE</b>",
        f"📅 {result.scanned_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"⏱ Duration: {result.scan_duration:.1f}s",
        "",
        "📊 <b>Macro Regime</b>",
        f"  • VIX: {result.regime.vix:.1f}{override_str}",
        f"  • DXY: {result.regime.dxy_regime.title()}",
        f"  • US10Y: {'Above' if result.regime.us10y_above_ma else 'Below'} 200-MA",
        f"  • Real Yield: {result.regime.real_yield_regime.title()}",
        "",
        f"✅ <b>Signals Found: {len(result.signals)}</b>",
    ]
    if result.signals:
        for sig in result.top_signals[:5]:
            dir_e = DIRECTION_EMOJI.get(sig.direction, "⚪")
            lines.append(f"  {dir_e} {sig.name} — {sig.direction.value.upper()} {sig.score:.0f}/100")
    else:
        lines.append("  No actionable signals at current thresholds.")
    cash = "30%" if result.aggregate_macro_score < 48 else "15%"
    lines += ["", f"💰 <b>Portfolio Cash Required:</b> {cash}"]
    return "\n".join(lines)


def format_regime_vix(vix, regime):
    override = " ⛔ <b>HARD OVERRIDE ACTIVE</b>" if vix > 35 else ""
    zone = "🔴 EXTREME" if vix > 35 else "🟠 HIGH" if vix > 25 else "🟡 ELEVATED" if vix > 20 else "🟢 LOW"
    return (
        f"📊 <b>VIX Dashboard</b>\n\n"
        f"Current Level: <b>{vix:.2f}</b>{override}\n\n"
        f"Regime Zones:\n"
        f"  🟢 &lt; 20: Low Volatility\n"
        f"  🟡 20-25: Elevated\n"
        f"  🟠 25-35: High\n"
        f"  🔴 &gt; 35: Extreme - No new positions\n\n"
        f"<i>Current Zone: {zone}</i>"
    )


async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Running full scan... (30-60s)")
    try:
        from src.signals.scanner import scan_universe
        result = await scan_universe()
        await update.message.reply_html(format_scan_summary(result))
        for sig in result.top_signals[:3]:
            await update.message.reply_html(format_signal_alert(sig))
    except Exception as exc:
        await update.message.reply_text(f"❌ Scan failed: {exc}")


async def cmd_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Fetching top signals...")
    try:
        from src.signals.scanner import scan_universe
        result = await scan_universe()
        if not result.top_signals:
            await update.message.reply_html("ℹ️ No signals above threshold.")
            return
        for sig in result.top_signals[:5]:
            await update.message.reply_html(format_signal_alert(sig))
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_portfolio(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        from src.signals.scanner import scan_universe
        result = await scan_universe()
        cash = "30%" if result.aggregate_macro_score < 48 else "15%"
        text = (
            f"💼 <b>PORTFOLIO STATUS</b>\n\n"
            f"🏦 Required Cash Reserve: <b>{cash}</b>\n"
            f"📊 Aggregate Macro Score: <b>{result.aggregate_macro_score:.0f}/100</b>\n\n"
            f"📋 Active Signals: <b>{len(result.signals)}</b>\n"
            f"  📈 Equities: {len(result.equities)}\n"
            f"  🏅 Commodities: {len(result.commodities)}\n"
            f"  🌾 Agriculture: {len(result.agriculture)}"
        )
        await update.message.reply_html(text)
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_equities(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Scanning equities...")
    try:
        from src.signals.scanner import scan_equities
        result = await scan_equities()
        if not result.signals:
            await update.message.reply_html("📈 No equity signals above threshold.")
            return
        for sig in result.signals:
            await update.message.reply_html(format_signal_alert(sig))
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_commodities(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Scanning commodities...")
    try:
        from src.signals.scanner import scan_commodities
        result = await scan_commodities()
        if not result.signals:
            await update.message.reply_html("🏅 No commodity signals above threshold.")
            return
        for sig in result.signals:
            await update.message.reply_html(format_signal_alert(sig))
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_agriculture(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Scanning agriculture...")
    try:
        from src.signals.scanner import scan_agriculture
        result = await scan_agriculture()
        if not result.signals:
            await update.message.reply_html("🌾 No agriculture signals above threshold.")
            return
        for sig in result.signals:
            await update.message.reply_html(format_signal_alert(sig))
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_gold(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Analysing Gold...")
    try:
        from src.signals.scanner import scan_universe
        result = await scan_universe(symbols=["GC"])
        if not result.signals:
            await update.message.reply_html("🏅 No Gold signal above threshold.")
            return
        await update.message.reply_html(format_signal_alert(result.signals[0]))
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_vix(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    from src.data.market_data import fetch_vix, fetch_market_regime
    vix = await fetch_vix()
    regime = await fetch_market_regime()
    await update.message.reply_html(format_regime_vix(vix, regime))


async def cmd_dxy(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    from src.data.market_data import fetch_dxy, enrich_ohlcv
    df = await fetch_dxy()
    if df.empty:
        await update.message.reply_text("❌ DXY data unavailable.")
        return
    df = enrich_ohlcv(df)
    last = df.iloc[-1]
    ma200 = last.get("ma_200")
    regime = "Bullish 🟢" if last["close"] > (ma200 or 0) else "Bearish 🔴"
    text = (
        f"💵 <b>DXY Dashboard</b>\n\n"
        f"Close: <b>{last['close']:.3f}</b>\n"
        f"MA200: <b>{ma200:.3f}</b>\n"
        f"Regime: <b>{regime}</b>\n\n"
        f"<i>Bearish DXY = Bullish Commodities</i>"
    )
    await update.message.reply_html(text)


async def cmd_us10y(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    from src.data.market_data import fetch_us10y, enrich_ohlcv
    df = await fetch_us10y()
    if df.empty:
        await update.message.reply_text("❌ US10Y data unavailable.")
        return
    df = enrich_ohlcv(df)
    last = df.iloc[-1]
    ma200 = last.get("ma_200")
    regime = "Above MA200 🔴" if last["close"] > (ma200 or 0) else "Below MA200 🟢"
    text = (
        f"📉 <b>US10Y Dashboard</b>\n\n"
        f"Yield: <b>{last['close']:.3f}%</b>\n"
        f"MA200: <b>{ma200:.3f}%</b>\n"
        f"Regime: <b>{regime}</b>"
    )
    await update.message.reply_html(text)


async def cmd_cot(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Fetching COT indices...")
    from src.data.market_data import get_cot_index
    lines = ["📊 <b>COT INDEX — ALL MARKETS</b>\n"]
    for sym, name in ALL_MARKETS.items():
        idx = await get_cot_index(sym)
        if idx is not None:
            emoji = "🟢" if idx >= 70 else "🔴" if idx <= 30 else "⚪"
            lines.append(f"{emoji} {name}: <b>{idx:.0f}</b>")
        else:
            lines.append(f"❓ {name}: N/A")
    lines.append("\n<i>&gt;70 = Commercially Bullish | &lt;30 = Commercially Bearish</i>")
    await update.message.reply_html("\n".join(lines))


async def send_signal_alert(signal) -> None:
    if not TELEGRAM_AVAILABLE or not settings.telegram_bot_token:
        return
    try:
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=format_signal_alert(signal),
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        logger.error("Telegram send failed: {}", exc)


async def send_scan_summary(result) -> None:
    if not TELEGRAM_AVAILABLE or not settings.telegram_bot_token:
        return
    try:
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=format_scan_summary(result),
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        logger.error("Telegram summary send failed: {}", exc)


STATUS_EMOJI = {
    "active": "🟦",
    "target_1_hit": "🎯",
    "final_target_hit": "🏁",
    "near_stop": "⚠️",
    "stop_hit": "🛑",
    "expired": "⌛",
    "invalidated": "❌",
    "extended_trend": "🚀",
    "trend_reversal": "🔄",
}


def format_active_trade(trade):
    from datetime import datetime, timedelta
    from src.signals.lifecycle import (
        STATUS_LABELS, classify_session, format_countdown, signal_age_bucket,
    )

    now = datetime.utcnow()
    dir_emoji = DIRECTION_EMOJI.get(trade.direction, "⚪")
    status_emoji = STATUS_EMOJI.get(trade.status, "⚪")
    age = now - trade.opened_at
    deadline = trade.opened_at + timedelta(days=trade.expected_hold_days or 10)
    last_price = trade.last_price or trade.entry_price

    is_long = trade.direction == "long"
    dist_tp1 = (trade.take_profit_1 - last_price) if is_long else (last_price - trade.take_profit_1)
    dist_tp2 = (trade.take_profit_2 - last_price) if is_long else (last_price - trade.take_profit_2)
    dist_stop = (last_price - trade.stop_loss) if is_long else (trade.stop_loss - last_price)

    updated = trade.updated_at or trade.opened_at
    time_since_update = format_countdown(updated - now)  # negative -> "time since" as elapsed

    lines = [
        f"{status_emoji} <b>{trade.symbol}</b> {dir_emoji} {trade.direction.upper()} — "
        f"{STATUS_LABELS.get(trade.status, trade.status)}",
        f"  • Issued: {trade.opened_at.strftime('%Y-%m-%d %H:%M UTC')} "
        f"({trade.session or classify_session(trade.opened_at)} session)",
        f"  • Age: {signal_age_bucket(age)} ({format_countdown(age)} since issuance)",
        f"  • Countdown to expiry: {format_countdown(deadline - now)}",
        f"  • P/L: {(trade.pnl_pct or 0):+.2f}% | MFE: {(trade.mfe_pct or 0):+.2f}% | MAE: {(trade.mae_pct or 0):+.2f}%",
        f"  • Distance — TP1: {dist_tp1:.4f} | TP2: {dist_tp2:.4f} | Stop: {dist_stop:.4f}",
        f"  • Last update: {time_since_update.lstrip('-')} ago",
    ]
    return "\n".join(lines)


def format_active_trades_summary(trades):
    if not trades:
        return "ℹ️ No active tracked signals right now."
    lines = ["📡 <b>ACTIVE SIGNAL LIFECYCLE</b>", ""]
    for t in trades:
        lines.append(format_active_trade(t))
        lines.append("")
    return "\n".join(lines).strip()


def format_status_change_alert(trade, old_status, new_status):
    from src.signals.lifecycle import STATUS_LABELS
    emoji = STATUS_EMOJI.get(new_status, "🔔")
    return (
        f"{emoji} <b>SIGNAL UPDATE — {trade.symbol}</b>\n\n"
        f"{STATUS_LABELS.get(old_status, old_status)} → <b>{STATUS_LABELS.get(new_status, new_status)}</b>\n"
        f"Price: {trade.last_price:.4f} | P/L: {(trade.pnl_pct or 0):+.2f}%\n"
        f"Entry: {trade.entry_price:.4f} | Stop: {trade.stop_loss:.4f} | TP2: {trade.take_profit_2:.4f}"
    )


async def cmd_active(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Fetching active signals...")
    try:
        from src.signals.lifecycle import get_active_trades
        trades = await get_active_trades()
        if not trades:
            await update.message.reply_html("ℹ️ No active tracked signals right now.")
            return
        for t in trades:
            await update.message.reply_html(format_active_trade(t))
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def send_status_change_alerts(transitions) -> None:
    """`transitions` is the list of (TradeRecord, old_status, new_status) returned
    by sync_trade_lifecycle. Sends one Telegram message per transition."""
    if not TELEGRAM_AVAILABLE or not settings.telegram_bot_token:
        return
    for trade, old_status, new_status in transitions:
        try:
            bot = Bot(token=settings.telegram_bot_token)
            await bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=format_status_change_alert(trade, old_status, new_status),
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            logger.error("Telegram status-change send failed for {}: {}", trade.symbol, exc)


def build_application():
    if not TELEGRAM_AVAILABLE:
        raise RuntimeError("python-telegram-bot not installed")
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("equities", cmd_equities))
    app.add_handler(CommandHandler("commodities", cmd_commodities))
    app.add_handler(CommandHandler("agriculture", cmd_agriculture))
    app.add_handler(CommandHandler("gold", cmd_gold))
    app.add_handler(CommandHandler("vix", cmd_vix))
    app.add_handler(CommandHandler("dxy", cmd_dxy))
    app.add_handler(CommandHandler("us10y", cmd_us10y))
    app.add_handler(CommandHandler("cot", cmd_cot))
    app.add_handler(CommandHandler("active", cmd_active))
    return app
