"""
Telegram Bot Integration
========================
Full async Telegram bot with all 11 slash commands.
Sends alert messages and responds to manual queries.
"""
from __future__ import annotations

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
from src.signals.scanner import (
    ScanResult,
    scan_agriculture,
    scan_commodities,
    scan_equities,
    scan_universe,
)
from src.signals.scorer import SignalResult

settings = get_settings()

# Lazily import telegram to avoid crash when token not configured
try:
    from telegram import Bot, Update
    from telegram.constants import ParseMode
    from telegram.ext import Application, CommandHandler, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed — Telegram disabled")


# ---------------------------------------------------------------------------
# Alert formatting
# ---------------------------------------------------------------------------

DIRECTION_EMOJI = {Direction.LONG: "🟢", Direction.SHORT: "🔴"}
ASSET_EMOJI = {
    AssetClass.EQUITY: "📈",
    AssetClass.COMMODITY: "🏅",
    AssetClass.AGRICULTURE: "🌾",
}


def format_signal_alert(signal: SignalResult) -> str:
    """Format a signal as the institutional alert message."""
    month = signal.scanned_at.month
    season_label = signal.seasonality_label(month)

    dir_emoji = DIRECTION_EMOJI.get(signal.direction, "⚪")
    asset_emoji = ASSET_EMOJI.get(signal.asset_class, "")

    lines = [
        f"🔥 <b>ELITE SWING TRADE</b>",
        f"",
        f"{asset_emoji} <b>Asset:</b> {signal.name} ({signal.symbol})",
        f"{dir_emoji} <b>Direction:</b> {signal.direction.value.upper()}",
        f"",
        f"📊 <b>Score:</b> {signal.score}/100",
        f"  • Commercial COT: {signal.scores.commercial_cot:.0f}/35"
        + (f" (Index: {signal.cot_index_raw:.0f})" if signal.cot_index_raw is not None else ""),
        f"  • Seasonality: {season_label} ({signal.scores.seasonality:.0f}/25)",
        f"  • Macro Regime: {signal.scores.macro_regime:.0f}/20",
        f"  • Trend Alignment: {signal.scores.trend_alignment:.0f}/10",
        f"  • Momentum: {signal.scores.momentum:.0f}/10",
        f"",
    ]

    # Regime details
    if signal.asset_class == AssetClass.EQUITY:
        vix_str = f"{signal.regime.vix:.1f}"
        lines += [
            f"⚡ <b>Regime Filters:</b>",
            f"  • VIX: {vix_str}",
            f"  • US10Y: {'Above' if signal.regime.us10y_above_ma else 'Below'} 200-MA",
        ]
    elif signal.asset_class == AssetClass.COMMODITY:
        lines += [
            f"⚡ <b>Regime Filters:</b>",
            f"  • DXY: {signal.regime.dxy_regime.title()} Regime",
        ]
        if signal.symbol in ("GC", "SI"):
            lines.append(
                f"  • Real Yield: {'Rising ⚠️' if signal.regime.real_yield_rising else 'Falling ✅'}"
            )
    else:
        lines += [f"⚡ <b>Market Focus:</b> Seasonal + COT driven"]

    lines += [
        f"",
        f"💰 <b>Trade Setup:</b>",
        f"  • Entry:  {signal.entry_price:.4f}",
        f"  • Stop:   {signal.stop_loss:.4f}",
        f"  • TP1:    {signal.take_profit_1:.4f}",
        f"  • TP2:    {signal.take_profit_2:.4f}",
        f"",
        f"📐 <b>Risk/Reward:</b> {signal.risk_reward:.1f}x",
        f"📉 <b>ATR Risk:</b> {signal.atr_risk_pct:.2f}%",
        f"🕐 <b>Expected Hold:</b> {signal.expected_hold_days} Days",
        f"",
        f"🤖 <i>COT Intelligence Platform — {signal.scanned_at.strftime('%Y-%m-%d %H:%M UTC')}</i>",
    ]

    return "\n".join(lines)


def format_scan_summary(result: ScanResult) -> str:
    """Format full scan summary."""
    lines = [
        f"🔍 <b>FULL SCAN COMPLETE</b>",
        f"📅 {result.scanned_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"⏱ Duration: {result.scan_duration:.1f}s",
        f"",
        f"📊 <b>Macro Regime</b>",
        f"  • VIX: {result.regime.vix:.1f}"
        + (" ⛔ OVERRIDE ACTIVE" if result.regime.vix_override else ""),
        f"  • DXY: {result.regime.dxy_regime.title()}",
        f"  • US10Y: {'Above' if result.regime.us10y_above_ma else 'Below'} 200-MA",
        f"  • Real Yield: {result.regime.real_yield_regime.title()}",
        f"",
        f"✅ <b>Signals Found: {len(result.signals)}</b>",
    ]

    if result.signals:
        for sig in result.top_signals[:5]:
            dir_e = DIRECTION_EMOJI.get(sig.direction, "⚪")
            lines.append(
                f"  {dir_e} {sig.name} — {sig.direction.value.upper()} {sig.score:.0f}/100"
            )
    else:
        lines.append("  No actionable signals at current thresholds.")

    lines += [
        f"",
        f"💰 <b>Portfolio Cash Required:</b> "
        f"{'30%' if result.aggregate_macro_score < 48 else '15%'}",
    ]

    return "\n".join(lines)


def format_regime_vix(vix: float, regime: Any) -> str:
    override = " ⛔ <b>HARD OVERRIDE ACTIVE — No New Positions</b>" if vix > 35 else ""
    return (
        f"📊 <b>VIX Dashboard</b>\n\n"
        f"Current Level: <b>{vix:.2f}</b>{override}\n\n"
        f"Regime Zones:\n"
        f"  🟢 < 20: Low Volatility (Full allocation)\n"
        f"  🟡 20–25: Elevated (Reduce size)\n"
        f"  🟠 25–35: High (Caution)\n"
        f"  🔴 > 35: Extreme ⛔ No new positions\n\n"
        f"<i>Current Zone: {'🔴 EXTREME' if vix > 35 else '🟠 HIGH' if vix > 25 else '🟡 ELEVATED' if vix > 20 else '🟢 LOW'}</i>"
    )


def format_no_signals() -> str:
    return "ℹ️ <b>No signals above threshold at this time.</b>\nCheck back after COT release (Friday 15:30 ET)."


# ---------------------------------------------------------------------------
# Bot command handlers
# ---------------------------------------------------------------------------

async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text("🔄 Running full scan… (may take 30–60s)")
    try:
        result = await scan_universe()
        await update.message.reply_html(format_scan_summary(result))
        for sig in result.top_signals[:3]:
            await update.message.reply_html(format_signal_alert(sig))
    except Exception as exc:
        logger.error("Scan error: {}", exc)
        await update.message.reply_text(f"❌ Scan failed: {exc}")


async def cmd_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text("🔄 Fetching top signals…")
    try:
        result = await scan_universe()
        if not result.top_signals:
            await update.message.reply_html(format_no_signals())
            return
        for sig in result.top_signals[:5]:
            await update.message.reply_html(format_signal_alert(sig))
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_portfolio(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    try:
        result = await scan_universe()
        cash = "30%" if result.aggregate_macro_score < 48 else "15%"
        lines = [
            f"💼 <b>PORTFOLIO STATUS</b>",
            f"",
            f"🏦 Required Cash Reserve: <b>{cash}</b>",
            f"📊 Aggregate Macro Score: <b>{result.aggregate_macro_score:.0f}/100</b>",
            f"",
            f"📋 Active Signals: <b>{len(result.signals)}</b>",
            f"  📈 Equities: {len(result.equities)}",
            f"  🏅 Commodities: {len(result.commodities)}",
            f"  🌾 Agriculture: {len(result.agriculture)}",
        ]
        await update.message.reply_html("\n".join(lines))
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_equities(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text("🔄 Scanning equities…")
    try:
        result = await scan_equities()
        if not result.signals:
            await update.message.reply_html("📈 No equity signals above threshold.")
            return
        for sig in result.signals:
            await update.message.reply_html(format_signal_alert(sig))
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_commodities(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text("🔄 Scanning commodities…")
    try:
        result = await scan_commodities()
        if not result.signals:
            await update.message.reply_html("🏅 No commodity signals above threshold.")
            return
        for sig in result.signals:
            await update.message.reply_html(format_signal_alert(sig))
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_agriculture(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text("🔄 Scanning agriculture…")
    try:
        result = await scan_agriculture()
        if not result.signals:
            await update.message.reply_html("🌾 No agriculture signals above threshold.")
            return
        for sig in result.signals:
            await update.message.reply_html(format_signal_alert(sig))
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_gold(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text("🔄 Analysing Gold…")
    try:
        result = await scan_universe(symbols=["GC"])
        if not result.signals:
            await update.message.reply_html("🏅 No Gold signal above threshold currently.")
            return
        await update.message.reply_html(format_signal_alert(result.signals[0]))
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_vix(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    from src.data.market_data import fetch_vix, fetch_market_regime
    vix = await fetch_vix()
    regime = await fetch_market_regime()
    await update.message.reply_html(format_regime_vix(vix, regime))


async def cmd_dxy(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
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
    assert update.message
    from src.data.market_data import fetch_us10y, enrich_ohlcv
    df = await fetch_us10y()
    if df.empty:
        await update.message.reply_text("❌ US10Y data unavailable.")
        return
    df = enrich_ohlcv(df)
    last = df.iloc[-1]
    ma200 = last.get("ma_200")
    regime = "Above MA200 🔴 (Equity Headwind)" if last["close"] > (ma200 or 0) else "Below MA200 🟢 (Equity Tailwind)"
    text = (
        f"📉 <b>US10Y Dashboard</b>\n\n"
        f"Yield: <b>{last['close']:.3f}%</b>\n"
        f"MA200: <b>{ma200:.3f}%</b>\n"
        f"Regime: <b>{regime}</b>\n\n"
        f"<i>Below MA200 → Allow equity longs\n"
        f"Above MA200 → Allow equity shorts</i>"
    )
    await update.message.reply_html(text)


async def cmd_cot(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text("🔄 Fetching COT indices for all markets…")
    from src.data.market_data import get_cot_index
    lines = ["📊 <b>COT INDEX — ALL MARKETS</b>\n"]
    for sym, name in ALL_MARKETS.items():
        idx = await get_cot_index(sym)
        if idx is not None:
            if idx >= 70:
                emoji = "🟢"
            elif idx <= 30:
                emoji = "🔴"
            else:
                emoji = "⚪"
            lines.append(f"{emoji} {name}: <b>{idx:.0f}</b>")
        else:
            lines.append(f"❓ {name}: N/A")
    lines.append("\n<i>>70 = Commercially Bullish | <30 = Commercially Bearish</i>")
    await update.message.reply_html("\n".join(lines))


# ---------------------------------------------------------------------------
# Push alert (called from scheduler)
# ---------------------------------------------------------------------------

async def send_signal_alert(signal: SignalResult) -> None:
    """Push a signal alert to the configured Telegram chat."""
    if not TELEGRAM_AVAILABLE or not settings.telegram_bot_token:
        logger.info("Telegram not configured — alert suppressed for {}", signal.symbol)
        return
    try:
        bot = Bot(token=settings.telegram_bot_token)
        text = format_signal_alert(signal)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
        )
        logger.info("Telegram alert sent: {}", signal.symbol)
    except Exception as exc:
        logger.error("Telegram send failed: {}", exc)


async def send_scan_summary(result: ScanResult) -> None:
    """Push scan summary to Telegram."""
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


# ---------------------------------------------------------------------------
# Bot application
# ---------------------------------------------------------------------------

def build_application() -> Any:
    """Build and return the Telegram Application (call .run_polling() on it)."""
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

    logger.info("Telegram bot configured — {} commands registered", 11)
    return app
