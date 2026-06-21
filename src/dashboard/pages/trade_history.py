import sys
sys.path.insert(0, "/mount/src/swing-platform")

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.helpers import (
    BEAR_RED, BULL_GREEN, GOLD, ACCENT_BLUE, PLOTLY_LAYOUT,
    TEXT_DIM, TEXT_PRIMARY, apply_theme, async_run,
)

apply_theme()
st.title("Trade History")
st.caption("Complete audit trail of all generated signals")


@st.cache_data(ttl=30)
def load_history():
    async def _q():
        from src.core.database import AsyncSessionLocal, SignalRecord, create_tables
        from sqlalchemy import select
        await create_tables()
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(SignalRecord).order_by(SignalRecord.scanned_at.desc()).limit(500)
            )
            records = res.scalars().all()
        return [
            {
                "Date": r.scanned_at.strftime("%Y-%m-%d %H:%M"),
                "Symbol": r.symbol,
                "Market": r.name,
                "Class": r.asset_class.title(),
                "Direction": r.direction.upper(),
                "Score": round(r.score, 1),
                "COT": round(r.cot_score or 0, 1),
                "Season": round(r.seasonality_score or 0, 1),
                "Macro": round(r.macro_score or 0, 1),
                "Entry": r.entry_price,
                "Stop": r.stop_loss,
                "TP1": r.take_profit_1,
                "TP2": r.take_profit_2,
                "R:R": r.risk_reward,
                "ATR%": r.atr_risk_pct,
                "Hold (d)": r.expected_hold_days,
                "VIX": r.vix_level,
                "DXY": r.dxy_regime,
                "US10Y": r.us10y_regime,
                "Alert Sent": "Yes" if r.alert_sent else "No",
            }
            for r in records
        ]
    return pd.DataFrame(async_run(_q()))


with st.spinner("Loading trade history..."):
    df = load_history()

if df.empty:
    st.info("No history yet. Signals appear here after each automated scan.")
    st.stop()

f1, f2, f3 = st.columns(3)
with f1:
    sym_filter = st.multiselect("Symbol", sorted(df["Symbol"].unique()), default=[])
with f2:
    dir_filter = st.multiselect("Direction", ["LONG", "SHORT"], default=[])
with f3:
    cls_filter = st.multiselect("Class", sorted(df["Class"].unique()), default=[])

filtered = df.copy()
if sym_filter:
    filtered = filtered[filtered["Symbol"].isin(sym_filter)]
if dir_filter:
    filtered = filtered[filtered["Direction"].isin(dir_filter)]
if cls_filter:
    filtered = filtered[filtered["Class"].isin(cls_filter)]

st.caption(f"Showing {len(filtered)} of {len(df)} records")

st.dataframe(
    filtered, use_container_width=True, hide_index=True,
    column_config={
        "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.1f"),
        "R:R": st.column_config.NumberColumn("R:R", format="%.1fx"),
        "Entry": st.column_config.NumberColumn("Entry", format="%.4f"),
        "Stop": st.column_config.NumberColumn("Stop", format="%.4f"),
        "TP1": st.column_config.NumberColumn("TP1", format="%.4f"),
        "TP2": st.column_config.NumberColumn("TP2", format="%.4f"),
    },
)

csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button("Export CSV", data=csv, file_name="signal_history.csv", mime="text/csv")

if len(filtered) > 1:
    st.divider()
    st.subheader("Score Trend")
    filtered_sorted = filtered.sort_values("Date")
    fig = go.Figure()
    for sym in filtered_sorted["Symbol"].unique():
        sub = filtered_sorted[filtered_sorted["Symbol"] == sym]
        fig.add_trace(go.Scatter(x=sub["Date"], y=sub["Score"], mode="lines+markers", name=sym))
    fig.add_hline(y=52, line_dash="dash", line_color=GOLD, annotation_text="Threshold")
    fig.update_layout(**{**PLOTLY_LAYOUT, "height": 320, "title": "Signal Scores Over Time"})
    st.plotly_chart(fig, use_container_width=True)

if st.button("Refresh"):
    st.cache_data.clear()
    st.rerun()
