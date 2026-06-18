from __future__ import annotations
import sys, os
for _p in ['/mount/src/swing-platform', os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import sys, os
for _p in ['/mount/src/swing-platform', os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

"""DXY Dashboard Ã¢â‚¬â€ US Dollar regime for commodity signals."""

import plotly.graph_objects as go
import streamlit as st

from src.dashboard.helpers import (
    ACCENT_BLUE, BEAR_RED, BULL_GREEN, GOLD, PLOTLY_LAYOUT, TEXT_DIM,
    TEXT_PRIMARY, apply_theme, async_run, candlestick_chart,
)

apply_theme()
st.title("Ã°Å¸â€™Âµ DXY Dashboard")
st.caption("US Dollar Index Ã¢â‚¬â€ regime filter for commodity signals")

@st.cache_data(ttl=900, show_spinner=False)
def load_dxy():
    from src.data.market_data import fetch_dxy, enrich_ohlcv
    df = async_run(fetch_dxy())
    return enrich_ohlcv(df) if not df.empty else df

with st.spinner("Loading DXY dataÃ¢â‚¬Â¦"):
    df = load_dxy()

if df.empty:
    st.error("DXY data unavailable.")
    st.stop()

last = df.iloc[-1]
close_now = float(last["close"])
ma200 = float(last["ma_200"]) if "ma_200" in last and last["ma_200"] == last["ma_200"] else None
is_bullish = ma200 is not None and close_now > ma200
regime = "Ã°Å¸Å¸Â¢ BULLISH" if is_bullish else "Ã°Å¸â€Â´ BEARISH"
regime_impact = "Ã¢Å¡Â Ã¯Â¸Â Headwind for commodities" if is_bullish else "Ã¢Å“â€¦ Tailwind for commodities"

if is_bullish:
    st.warning(f"Ã°Å¸â€™Âµ DXY Regime: {regime} Ã¢â‚¬â€ {regime_impact}")
else:
    st.success(f"Ã°Å¸â€™Âµ DXY Regime: {regime} Ã¢â‚¬â€ {regime_impact}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("DXY Close", f"{close_now:.3f}")
if ma200:
    pct_vs_ma = (close_now / ma200 - 1) * 100
    c2.metric("vs MA200", f"{ma200:.3f}", f"{pct_vs_ma:+.2f}%",
              delta_color="inverse" if is_bullish else "normal")
c3.metric("MA50", f"{last.get('ma_50', 0):.3f}" if last.get("ma_50") else "N/A")
c4.metric("52wk Range", f"{df['close'].min():.2f}Ã¢â‚¬â€œ{df['close'].max():.2f}")

st.divider()

# Ã¢â€â‚¬Ã¢â€â‚¬ Chart Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
st.subheader("Ã°Å¸â€œË† DXY Price History")
fig = candlestick_chart(df.tail(252), "DXY Ã¢â‚¬â€ US Dollar Index")
st.plotly_chart(fig, use_container_width=True)

# Ã¢â€â‚¬Ã¢â€â‚¬ Regime by month Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
st.subheader("Ã°Å¸â€œâ€¦ DXY vs MA200 Ã¢â‚¬â€ Monthly Regime")
df_monthly = df["close"].resample("ME").last().tail(24)
df_ma_monthly = df["ma_200"].resample("ME").last().tail(24)

monthly_regime = [1 if c > m else -1
                  for c, m in zip(df_monthly.values, df_ma_monthly.values)
                  if m == m]
colors_m = [BULL_GREEN if r > 0 else BEAR_RED for r in monthly_regime]

fig_m = go.Figure(go.Bar(
    x=df_monthly.index[-len(monthly_regime):],
    y=monthly_regime,
    marker_color=colors_m,
    name="DXY vs MA200",
))
fig_m.add_hline(y=0, line_color=TEXT_DIM, line_width=1)
fig_m.update_layout(**{
    **PLOTLY_LAYOUT,
    "height": 260,
    "title": "DXY Regime: +1 = Above MA200 (Bullish $), -1 = Below (Bearish $)",
    "yaxis": {**PLOTLY_LAYOUT["yaxis"], "tickvals": [-1, 0, 1],
              "ticktext": ["Bearish $", "Neutral", "Bullish $"]},
})
st.plotly_chart(fig_m, use_container_width=True)

# Ã¢â€â‚¬Ã¢â€â‚¬ Impact on commodities Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
st.divider()
st.subheader("Ã°Å¸â€œÅ“ DXY Rule Impact on Commodities")
st.markdown("""
| DXY Regime | Effect on Commodity Longs | Effect on Commodity Shorts |
|------------|--------------------------|---------------------------|
| **Bearish** (below MA200) | Ã¢Å“â€¦ Tailwind Ã¢â‚¬â€ full macro score | Ã¢Å¡Â Ã¯Â¸Â Headwind Ã¢â‚¬â€ reduced score |
| **Bullish** (above MA200) | Ã¢Å¡Â Ã¯Â¸Â Headwind Ã¢â‚¬â€ reduced score | Ã¢Å“â€¦ Tailwind Ã¢â‚¬â€ full macro score |

**Real Yield filter additionally applies to Gold (GC) and Silver (SI) only.**
""")
