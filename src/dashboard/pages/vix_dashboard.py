import sys
sys.path.insert(0, "/mount/src/swing-platform")

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.dashboard.helpers import (
    BEAR_RED, BULL_GREEN, GOLD, PLOTLY_LAYOUT, TEXT_DIM, TEXT_PRIMARY,
    apply_theme, async_run, candlestick_chart,
)

apply_theme()
st.title("⚡ VIX Dashboard")
st.caption("CBOE Volatility Index — market fear gauge and position override rules")

@st.cache_data(ttl=300, show_spinner=False)
def load_vix():
    from src.data.market_data import fetch_price_data, enrich_ohlcv
    df = async_run(fetch_price_data("VIX", period="2y"))
    return enrich_ohlcv(df) if not df.empty else df

with st.spinner("Loading VIX data…"):
    df = load_vix()

if df.empty:
    st.error("VIX data unavailable.")
    st.stop()

last = df.iloc[-1]
vix_now = float(last["close"])
vix_prev = float(df["close"].iloc[-2]) if len(df) > 1 else vix_now
vix_chg = vix_now - vix_prev

# ── Regime header ─────────────────────────────────────────────────────────────
if vix_now > 35:
    st.error(f"⛔ VIX HARD OVERRIDE ACTIVE — {vix_now:.2f} > 35 — NO NEW POSITIONS")
elif vix_now > 25:
    st.warning(f"⚠️ VIX Elevated: {vix_now:.2f} — Reduce position sizing")
else:
    st.success(f"✅ VIX Normal: {vix_now:.2f} — Full allocation permitted")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Current VIX", f"{vix_now:.2f}", f"{vix_chg:+.2f}", delta_color="inverse")
c2.metric("20-Day Avg", f"{df['close'].tail(20).mean():.2f}")
c3.metric("52-Week High", f"{df['close'].max():.2f}")
c4.metric("52-Week Low",  f"{df['close'].min():.2f}")

st.divider()

# ── VIX chart ─────────────────────────────────────────────────────────────────
st.subheader("📈 VIX History")

vix_series = df["close"].tail(252)
fig = go.Figure()

# Colour by zone
for threshold, color, label in [
    (35, "#7b0000", "Extreme (>35) — Override Zone"),
    (25, "#cc4400", "High (25–35)"),
    (20, "#ccaa00", "Elevated (20–25)"),
    (0,  "#006633", "Low (<20)"),
]:
    pass  # handled by shaded regions below

fig.add_trace(go.Scatter(
    x=vix_series.index, y=vix_series.values,
    name="VIX", line=dict(color="#e0e0e0", width=2),
    fill="tozeroy", fillcolor="rgba(200,200,200,0.05)",
))

for y, color, label in [
    (35, BEAR_RED, "Override Threshold (35)"),
    (25, "#ff8c00", "High Zone (25)"),
    (20, GOLD, "Elevated Zone (20)"),
]:
    fig.add_hline(y=y, line_dash="dash", line_color=color,
                  annotation_text=label, annotation_position="right")

fig.update_layout(**{**PLOTLY_LAYOUT, "height": 380,
                     "title": "VIX — CBOE Volatility Index (252 days)"})
st.plotly_chart(fig, use_container_width=True)

# ── Zone distribution ─────────────────────────────────────────────────────────
st.subheader("📊 Regime Zone Distribution (1yr)")
zones = {
    "Low (<20)":      (df["close"].tail(252) < 20).sum(),
    "Elevated (20-25)": ((df["close"].tail(252) >= 20) & (df["close"].tail(252) < 25)).sum(),
    "High (25-35)":   ((df["close"].tail(252) >= 25) & (df["close"].tail(252) <= 35)).sum(),
    "Extreme (>35)":  (df["close"].tail(252) > 35).sum(),
}
colors_z = [BULL_GREEN, GOLD, "#ff8c00", BEAR_RED]
fig_z = go.Figure(go.Bar(
    x=list(zones.keys()), y=list(zones.values()),
    marker_color=colors_z,
    text=[f"{v} days ({v/252*100:.0f}%)" for v in zones.values()],
    textposition="outside",
))
fig_z.update_layout(**{**PLOTLY_LAYOUT, "height": 280, "showlegend": False})
st.plotly_chart(fig_z, use_container_width=True)

# ── Rules reminder ────────────────────────────────────────────────────────────
st.divider()
st.subheader("📜 VIX Rules")
st.markdown("""
| VIX Level | Action |
|-----------|--------|
| < 20      | 🟢 Full allocation — all signals valid |
| 20–25     | 🟡 Elevated — consider reducing size by 25% |
| 25–35     | 🟠 High — caution, tighten stops |
| > 35      | 🔴 **HARD OVERRIDE — No new longs or shorts** |
""")
