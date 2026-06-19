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
st.title("Performance Analytics")
st.caption("Historical signal statistics from database")


@st.cache_data(ttl=300)
def load_signals_df():
    async def _q():
        from src.core.database import AsyncSessionLocal, SignalRecord, create_tables
        from sqlalchemy import select
        await create_tables()
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(SignalRecord).order_by(SignalRecord.scanned_at.desc()))
            records = result.scalars().all()
        return [
            {
                "id": r.id, "symbol": r.symbol, "name": r.name,
                "asset_class": r.asset_class, "direction": r.direction,
                "score": r.score, "cot_score": r.cot_score,
                "seasonality_score": r.seasonality_score,
                "macro_score": r.macro_score, "trend_score": r.trend_score,
                "momentum_score": r.momentum_score,
                "vix_level": r.vix_level, "dxy_regime": r.dxy_regime,
                "us10y_regime": r.us10y_regime,
                "entry_price": r.entry_price, "stop_loss": r.stop_loss,
                "take_profit_1": r.take_profit_1, "take_profit_2": r.take_profit_2,
                "risk_reward": r.risk_reward, "atr_risk_pct": r.atr_risk_pct,
                "expected_hold_days": r.expected_hold_days,
                "scanned_at": r.scanned_at,
            }
            for r in records
        ]
    return pd.DataFrame(async_run(_q()))


with st.spinner("Loading historical data..."):
    df_signals = load_signals_df()

if df_signals.empty:
    st.info("No historical signal data yet. Run the daily scan to populate the database.")
    st.markdown("""
    To generate data, run a scan from the Overview page or wait for the automated daily scan.
    """)
    st.stop()

st.subheader("Signal Statistics")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Signals", len(df_signals))
c2.metric("Unique Markets", df_signals["symbol"].nunique())
c3.metric("Avg Score", f"{df_signals['score'].mean():.1f}")
c4.metric("Longs", (df_signals["direction"] == "long").sum())
c5.metric("Shorts", (df_signals["direction"] == "short").sum())

st.divider()

st.subheader("Score Distribution")
fig_hist = go.Figure()
fig_hist.add_trace(go.Histogram(x=df_signals["score"], nbinsx=20, marker_color=ACCENT_BLUE, opacity=0.8))
fig_hist.add_vline(x=52, line_dash="dash", line_color=GOLD, annotation_text="Threshold 52")
fig_hist.add_vline(x=70, line_dash="dash", line_color=BULL_GREEN, annotation_text="High Conviction 70")
fig_hist.update_layout(**{**PLOTLY_LAYOUT, "height": 300, "title": "Signal Score Distribution"})
st.plotly_chart(fig_hist, use_container_width=True)

st.subheader("Signals Over Time")
df_signals["date"] = pd.to_datetime(df_signals["scanned_at"]).dt.date
daily_counts = df_signals.groupby("date").size().reset_index(name="count")

fig_time = go.Figure(go.Bar(x=daily_counts["date"], y=daily_counts["count"], marker_color=ACCENT_BLUE))
fig_time.update_layout(**{**PLOTLY_LAYOUT, "height": 280, "title": "Signals Generated Per Day"})
st.plotly_chart(fig_time, use_container_width=True)

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Signals by Market")
    by_market = df_signals.groupby("name")["score"].agg(["count", "mean"]).sort_values("count", ascending=True)
    fig_mkt = go.Figure(go.Bar(y=by_market.index, x=by_market["count"], orientation="h", marker_color=ACCENT_BLUE))
    fig_mkt.update_layout(**{**PLOTLY_LAYOUT, "height": 350})
    st.plotly_chart(fig_mkt, use_container_width=True)

with col_b:
    st.subheader("Avg Score by Market")
    fig_avg = go.Figure(go.Bar(
        y=by_market.index, x=by_market["mean"].round(1), orientation="h",
        marker_color=[BULL_GREEN if v >= 70 else GOLD if v >= 52 else BEAR_RED for v in by_market["mean"]],
        text=[f"{v:.1f}" for v in by_market["mean"]], textposition="outside",
    ))
    fig_avg.add_vline(x=52, line_dash="dash", line_color=GOLD)
    fig_avg.update_layout(**{**PLOTLY_LAYOUT, "height": 350})
    st.plotly_chart(fig_avg, use_container_width=True)

st.subheader("Signal Distribution by Asset Class")
ac_counts = df_signals["asset_class"].value_counts()
fig_pie = go.Figure(go.Pie(labels=ac_counts.index.str.title(), values=ac_counts.values, hole=0.5,
                            marker_colors=[ACCENT_BLUE, GOLD, BULL_GREEN]))
fig_pie.update_layout(**{**PLOTLY_LAYOUT, "height": 280})
st.plotly_chart(fig_pie, use_container_width=True)

st.divider()
st.subheader("Average Component Scores")
comp_avgs = {
    "COT (max 35)": df_signals["cot_score"].mean(),
    "Seasonality (max 25)": df_signals["seasonality_score"].mean(),
    "Macro (max 20)": df_signals["macro_score"].mean(),
    "Trend (max 10)": df_signals["trend_score"].mean(),
    "Momentum (max 10)": df_signals["momentum_score"].mean(),
}
maxes = [35, 25, 20, 10, 10]
pcts = [v / m * 100 for v, m in zip(comp_avgs.values(), maxes)]
fig_comp = go.Figure(go.Bar(
    x=list(comp_avgs.keys()), y=pcts,
    marker_color=[BULL_GREEN if p >= 60 else GOLD if p >= 40 else BEAR_RED for p in pcts],
    text=[f"{v:.1f}" for v in comp_avgs.values()], textposition="outside",
))
fig_comp.add_hline(y=60, line_dash="dash", line_color=GOLD, annotation_text="60% efficiency")
fig_comp.update_layout(**{**PLOTLY_LAYOUT, "height": 320, "title": "Average Score per Component",
                          "yaxis": {**PLOTLY_LAYOUT["yaxis"], "range": [0, 110], "title": "% of Max"}})
st.plotly_chart(fig_comp, use_container_width=True)

if st.button("Refresh"):
    st.cache_data.clear()
    st.rerun()
