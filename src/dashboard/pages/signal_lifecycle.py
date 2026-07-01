import sys
sys.path.insert(0, "/mount/src/swing-platform")

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from src.dashboard.helpers import (
    apply_theme, async_run, get_cached_active_trades, render_freshness_bar,
    render_lifecycle_card, status_color, TEXT_DIM, TEXT_PRIMARY,
)
from src.signals.lifecycle import (
    STATUS_LABELS, TERMINAL_STATUSES, get_trade_history, get_status_log,
)

apply_theme()
st.title("Signal Lifecycle")
st.caption("Live status, countdowns, and trade progress for every tracked signal")
render_freshness_bar("Lifecycle data")

st.info(
    "A trade is opened the moment a symbol's signal is first detected, with entry/stop/targets "
    "frozen at that instant. It's then tracked here -- independent of whether the symbol keeps "
    "scoring above threshold on later scans -- until it hits a target, hits its stop, expires, "
    "or reverses direction.",
    icon="ℹ️",
)

with st.spinner("Loading active signals..."):
    active_trades = get_cached_active_trades()

st.subheader(f"Active Signals ({len(active_trades)})")

if not active_trades:
    st.info("No active tracked signals yet. They appear here as soon as a scan detects one.")
else:
    f1, f2, f3 = st.columns(3)
    with f1:
        status_options = sorted({STATUS_LABELS.get(t.status, t.status) for t in active_trades})
        status_filter = st.multiselect("Status", status_options, default=status_options)
    with f2:
        sort_order = st.selectbox("Sort by", ["Newest first", "Oldest first", "Nearest to expiry"])
    with f3:
        symbol_filter = st.multiselect(
            "Symbol", sorted({t.symbol for t in active_trades}), default=[]
        )

    filtered = [
        t for t in active_trades
        if STATUS_LABELS.get(t.status, t.status) in status_filter
        and (not symbol_filter or t.symbol in symbol_filter)
    ]

    if sort_order == "Newest first":
        filtered.sort(key=lambda t: t.opened_at, reverse=True)
    elif sort_order == "Oldest first":
        filtered.sort(key=lambda t: t.opened_at)
    else:
        now = datetime.utcnow()
        filtered.sort(key=lambda t: (t.opened_at + timedelta(days=t.expected_hold_days or 10)) - now)

    st.caption(f"Showing {len(filtered)} of {len(active_trades)} active signals")
    st.divider()

    for trade in filtered:
        render_lifecycle_card(trade)

st.divider()
st.subheader("Historical Archive")
st.caption("Every status change ever recorded, across active and closed signals")


@st.cache_data(ttl=60, show_spinner=False)
def load_closed_trades():
    async def _q():
        history = await get_trade_history(limit=500)
        return [t for t in history if t.status in TERMINAL_STATUSES]
    return async_run(_q())


closed_trades = load_closed_trades()

if not closed_trades:
    st.info("No closed signals yet.")
else:
    rows = []
    for t in closed_trades:
        rows.append({
            "Symbol": t.symbol,
            "Direction": t.direction.upper(),
            "Status": STATUS_LABELS.get(t.status, t.status),
            "Opened": t.opened_at.strftime("%Y-%m-%d %H:%M UTC") if t.opened_at else "N/A",
            "Closed": t.closed_at.strftime("%Y-%m-%d %H:%M UTC") if t.closed_at else "N/A",
            "Entry": t.entry_price,
            "Exit / Last": t.last_price,
            "P/L %": round(t.pnl_pct or 0, 2),
            "MFE %": round(t.mfe_pct or 0, 2),
            "MAE %": round(t.mae_pct or 0, 2),
        })
    df = pd.DataFrame(rows)
    st.dataframe(
        df, use_container_width=True, hide_index=True,
        column_config={
            "P/L %": st.column_config.NumberColumn("P/L %", format="%.2f%%"),
            "MFE %": st.column_config.NumberColumn("MFE %", format="%.2f%%"),
            "MAE %": st.column_config.NumberColumn("MAE %", format="%.2f%%"),
        },
    )

    selected_symbol = st.selectbox(
        "View status-change timeline for a closed signal",
        options=[f"{t.symbol} ({t.direction.upper()}) - opened {t.opened_at.strftime('%Y-%m-%d %H:%M')}"
                 for t in closed_trades],
    )
    idx = [f"{t.symbol} ({t.direction.upper()}) - opened {t.opened_at.strftime('%Y-%m-%d %H:%M')}"
           for t in closed_trades].index(selected_symbol)
    picked = closed_trades[idx]

    log = async_run(get_status_log(picked.id))
    if log:
        log_rows = [
            {
                "Time": entry.changed_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "Status": STATUS_LABELS.get(entry.status, entry.status),
                "Price": entry.price_at_change,
                "Note": entry.note,
            }
            for entry in log
        ]
        st.dataframe(pd.DataFrame(log_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No status-change log recorded for this signal.")

if st.button("Refresh"):
    st.cache_data.clear()
    st.rerun()
