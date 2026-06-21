import sys
sys.path.insert(0, "/mount/src/swing-platform")

import plotly.graph_objects as go
import streamlit as st

from src.dashboard.helpers import (
    ACCENT_BLUE, BEAR_RED, BULL_GREEN, GOLD, PLOTLY_LAYOUT, TEXT_DIM,
    TEXT_PRIMARY, apply_theme, async_run, candlestick_chart, render_freshness_bar,
)

apply_theme()
st.title("DXY Dashboard")
st.caption("US Dollar Index - regime filter for commodity signals")
render_freshness_bar("DXY data")


@st.cache_data(ttl=120, show_spinner=False)
def load_dxy():
    from src.data.market_data import fetch_dxy, enrich_ohlcv
    df = async_run(fetch_dxy())
    return enrich_ohlcv(df) if not df.empty else df


with st.spinner("Loading DXY data..."):
    df = load_dxy()

if df.empty:
    st.error("DXY data unavailable.")
    st.stop()

last = df.iloc[-1]
close_now = float(last["close"])
ma200 = float(last["ma_200"]) if "ma_200" in last and last["ma_200"] == last["ma_200"] else None
is_bullish = ma200 is not None and close_now > ma200
regime = "BULLISH" if is_bullish else "BEARISH"
regime_impact = "Headwind for commodities" if is_bullish else "Tailwind for commodities"

if is_bullish:
    st.warning(f"DXY Regime: {regime} - {regime_impact}")
else:
    st.success(f"DXY Regime: {regime} - {regime_impact}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("DXY Close", f"{close_now:.3f}")
if ma200:
    pct_vs_ma = (close_now / ma200 - 1) * 100
    c2.metric("vs MA200", f"{ma200:.3f}", f"{pct_vs_ma:+.2f}%", delta_color="inverse" if is_bullish else "normal")
c3.metric("MA50", f"{last.get('ma_50', 0):.3f}" if last.get("ma_50") else "N/A")
c4.metric("52wk Range", f"{df['close'].min():.2f}-{df['close'].max():.2f}")

st.divider()

st.subheader("DXY Price History")
fig = candlestick_chart(df.tail(252), "DXY - US Dollar Index")
st.plotly_chart(fig, use_container_width=True)

st.subheader("DXY vs MA200 - Monthly Regime")
df_monthly = df["close"].resample("ME").last().tail(24)
df_ma_monthly = df["ma_200"].resample("ME").last().tail(24)

monthly_regime = [1 if c > m else -1 for c, m in zip(df_monthly.values, df_ma_monthly.values) if m == m]
colors_m = [BULL_GREEN if r > 0 else BEAR_RED for r in monthly_regime]

fig_m = go.Figure(go.Bar(
    x=df_monthly.index[-len(monthly_regime):], y=monthly_regime,
    marker_color=colors_m, name="DXY vs MA200",
))
fig_m.add_hline(y=0, line_color=TEXT_DIM, line_width=1)
fig_m.update_layout(**{
    **PLOTLY_LAYOUT, "height": 260,
    "title": "DXY Regime: +1 = Above MA200, -1 = Below",
    "yaxis": {**PLOTLY_LAYOUT["yaxis"], "tickvals": [-1, 0, 1], "ticktext": ["Bearish $", "Neutral", "Bullish $"]},
})
st.plotly_chart(fig_m, use_container_width=True)

st.divider()
st.subheader("DXY Rule Impact on Commodities")
st.markdown("""
| DXY Regime | Effect on Commodity Longs | Effect on Commodity Shorts |
|------------|--------------------------|---------------------------|
| Bearish (below MA200) | Tailwind - full macro score | Headwind - reduced score |
| Bullish (above MA200) | Headwind - reduced score | Tailwind - full macro score |

Real Yield filter additionally applies to Gold (GC) and Silver (SI) only.
""")
