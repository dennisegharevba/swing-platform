import sys
sys.path.insert(0, "/mount/src/swing-platform")

"""US10Y Dashboard — 10-year yield regime for equity signals."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard.helpers import (
    BEAR_RED, BULL_GREEN, GOLD, PLOTLY_LAYOUT, TEXT_DIM, TEXT_PRIMARY,
    apply_theme, async_run, candlestick_chart,
)

apply_theme()
st.title("📉 US10Y Dashboard")
st.caption("US 10-Year Treasury Yield — regime filter for equity long/short signals")

@st.cache_data(ttl=900, show_spinner=False)
def load_us10y():
    from src.data.market_data import fetch_us10y, enrich_ohlcv
    df = async_run(fetch_us10y())
    return enrich_ohlcv(df) if not df.empty else df

with st.spinner("Loading US10Y data…"):
    df = load_us10y()

if df.empty:
    st.error("US10Y data unavailable.")
    st.stop()

last = df.iloc[-1]
yield_now = float(last["close"])
ma200 = float(last["ma_200"]) if "ma_200" in last and last["ma_200"] == last["ma_200"] else None
above_ma = ma200 is not None and yield_now > ma200

if above_ma:
    st.warning(
        f"📉 US10Y {yield_now:.3f}% — **Above MA200 ({ma200:.3f}%)** "
        f"→ ⚠️ Headwind for equity longs / ✅ Favour equity shorts"
    )
else:
    st.success(
        f"📉 US10Y {yield_now:.3f}% — **Below MA200 ({ma200:.3f}%)** "
        f"→ ✅ Allow equity longs / ⚠️ Avoid equity shorts"
    )

c1, c2, c3, c4 = st.columns(4)
c1.metric("10Y Yield", f"{yield_now:.3f}%")
if ma200:
    diff = yield_now - ma200
    c2.metric("MA200", f"{ma200:.3f}%", f"{diff:+.3f}%", delta_color="inverse")
c3.metric("MA50", f"{last.get('ma_50', 0):.3f}%" if last.get("ma_50") else "N/A")
c4.metric("YTD Range", f"{df['close'].tail(252).min():.3f}–{df['close'].tail(252).max():.3f}%")

st.divider()

# ── Yield chart ───────────────────────────────────────────────────────────────
st.subheader("📈 US 10Y Yield History")
fig = candlestick_chart(df.tail(252), "US 10Y Treasury Yield (%)")
st.plotly_chart(fig, use_container_width=True)

# ── Regime over time ──────────────────────────────────────────────────────────
st.subheader("📊 Yield vs MA200 — Rolling Regime")
if "ma_200" in df.columns:
    diff_series = (df["close"] - df["ma_200"]).dropna().tail(252)
    colors_d = [BULL_GREEN if v < 0 else BEAR_RED for v in diff_series.values]
    fig_d = go.Figure(go.Bar(
        x=diff_series.index, y=diff_series.values,
        marker_color=colors_d,
        name="Yield - MA200",
    ))
    fig_d.add_hline(y=0, line_color=TEXT_DIM, line_width=1)
    fig_d.update_layout(**{
        **PLOTLY_LAYOUT,
        "height": 260,
        "title": "10Y Yield minus MA200 — negative (green) = equity longs favoured",
    })
    st.plotly_chart(fig_d, use_container_width=True)

# ── Real yield section ────────────────────────────────────────────────────────
st.divider()
st.subheader("💎 Real Yield (Gold / Silver Filter)")

@st.cache_data(ttl=3600, show_spinner=False)
def load_real_yield():
    from src.data.market_data import fetch_real_yield
    return async_run(fetch_real_yield())

ry_chg = load_real_yield()
ry_label = "Rising ⚠️ — Avoid Gold/Silver Longs" if ry_chg > 0 else "Falling ✅ — Gold/Silver Longs Allowed"
if ry_chg > 0:
    st.warning(f"Real Yield 20d Change: **{ry_chg:+.3f}%** → {ry_label}")
else:
    st.success(f"Real Yield 20d Change: **{ry_chg:+.3f}%** → {ry_label}")

st.divider()
st.subheader("📜 US10Y Rules")
st.markdown("""
| US10Y vs MA200 | Equity Longs | Equity Shorts |
|----------------|-------------|---------------|
| **Below MA200** | ✅ Allowed — full macro score | ⚠️ Reduced macro score |
| **Above MA200** | ⚠️ Reduced macro score | ✅ Allowed — full macro score |

Real yield filter applies **only to Gold and Silver** — not Copper or Crude Oil.
""")
