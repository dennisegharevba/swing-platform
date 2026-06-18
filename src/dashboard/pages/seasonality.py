from __future__ import annotations
import sys, os
for _p in ['/mount/src/swing-platform', os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import sys, os
for _p in ['/mount/src/swing-platform', os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

"""Seasonality Dashboard Ã¢â‚¬â€ monthly bias heatmaps for all markets."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.core.config import (
    AGRICULTURE_MARKETS, ALL_MARKETS, COMMODITY_MARKETS,
    EQUITY_MARKETS, SEASONALITY,
)
from src.dashboard.helpers import (
    BEAR_RED, BULL_GREEN, GOLD, PLOTLY_LAYOUT, TEXT_DIM, TEXT_PRIMARY,
    apply_theme, seasonality_heatmap,
)

apply_theme()
st.title("Ã°Å¸â€”â€œ Seasonality Dashboard")
st.caption("20-year average monthly returns by asset Ã¢â‚¬â€ positive = historically bullish month")

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# Ã¢â€â‚¬Ã¢â€â‚¬ Current month highlight Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
from datetime import datetime
current_month = datetime.utcnow().month
current_month_name = MONTHS[current_month - 1]

st.info(f"Ã°Å¸â€œâ€¦ Current month: **{current_month_name}** Ã¢â‚¬â€ highlighting seasonal bias for all markets")

# Ã¢â€â‚¬Ã¢â€â‚¬ Current month scorecard Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
st.subheader(f"Ã°Å¸Å½Â¯ {current_month_name} Seasonal Bias Ã¢â‚¬â€ All Markets")

rows = []
for sym, name in ALL_MARKETS.items():
    bias = SEASONALITY.get(sym, {}).get(current_month, 0.0)
    signal = "Ã°Å¸Å¸Â¢ Bullish" if bias > 0.5 else "Ã°Å¸â€Â´ Bearish" if bias < -0.5 else "Ã¢Å¡Âª Neutral"
    rows.append({"Symbol": sym, "Market": name, "Bias": round(bias, 2), "Signal": signal})

df_month = pd.DataFrame(rows).sort_values("Bias", ascending=False)

col_l, col_r = st.columns(2)
with col_l:
    bulls = df_month[df_month["Bias"] > 0.5]
    st.markdown(f"**Ã°Å¸Å¸Â¢ Bullish ({len(bulls)})**")
    for _, row in bulls.iterrows():
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;padding:4px 0;'
            f'border-bottom:1px solid #2a2d3a;">'
            f'<span style="color:{TEXT_PRIMARY}">{row["Market"]}</span>'
            f'<span style="color:{BULL_GREEN};font-weight:700">+{row["Bias"]:.2f}</span></div>',
            unsafe_allow_html=True,
        )
with col_r:
    bears = df_month[df_month["Bias"] < -0.5]
    neuts = df_month[(df_month["Bias"] >= -0.5) & (df_month["Bias"] <= 0.5)]
    st.markdown(f"**Ã°Å¸â€Â´ Bearish ({len(bears)})**")
    for _, row in bears.iterrows():
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;padding:4px 0;'
            f'border-bottom:1px solid #2a2d3a;">'
            f'<span style="color:{TEXT_PRIMARY}">{row["Market"]}</span>'
            f'<span style="color:{BEAR_RED};font-weight:700">{row["Bias"]:.2f}</span></div>',
            unsafe_allow_html=True,
        )
    st.markdown(f"**Ã¢Å¡Âª Neutral ({len(neuts)})**")
    for _, row in neuts.iterrows():
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;padding:4px 0;'
            f'border-bottom:1px solid #2a2d3a;">'
            f'<span style="color:{TEXT_PRIMARY}">{row["Market"]}</span>'
            f'<span style="color:{GOLD};font-weight:700">{row["Bias"]:+.2f}</span></div>',
            unsafe_allow_html=True,
        )

st.divider()

# Ã¢â€â‚¬Ã¢â€â‚¬ Full heatmap Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
st.subheader("Ã°Å¸â€”Âº Full Seasonality Heatmap")

symbols = list(ALL_MARKETS.keys())
names   = list(ALL_MARKETS.values())
data_matrix = [[SEASONALITY.get(sym, {}).get(m, 0.0) for m in range(1, 13)] for sym in symbols]

fig_heat = go.Figure(go.Heatmap(
    z=data_matrix,
    x=MONTHS,
    y=names,
    colorscale=[
        [0.0,  "#7b0000"],
        [0.35, "#cc2200"],
        [0.45, "#2a2d3a"],
        [0.55, "#2a2d3a"],
        [0.65, "#004400"],
        [1.0,  "#00cc44"],
    ],
    zmid=0,
    text=[[f"{v:+.2f}" for v in row] for row in data_matrix],
    texttemplate="%{text}",
    textfont={"size": 10, "color": "white"},
    colorbar=dict(title="Bias", tickfont=dict(color=TEXT_PRIMARY)),
))

# Highlight current month column
fig_heat.add_shape(
    type="rect",
    x0=current_month - 1.5, x1=current_month - 0.5,
    y0=-0.5, y1=len(symbols) - 0.5,
    line=dict(color=GOLD, width=2),
    fillcolor="rgba(245,197,24,0.05)",
)

fig_heat.update_layout(**{
    **PLOTLY_LAYOUT,
    "height": 550,
    "title": "Monthly Seasonal Bias Ã¢â‚¬â€ All Markets (20yr avg)",
    "yaxis": {**PLOTLY_LAYOUT["yaxis"], "tickfont": {"size": 11}},
})
st.plotly_chart(fig_heat, use_container_width=True)

st.divider()

# Ã¢â€â‚¬Ã¢â€â‚¬ Per-market charts Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
st.subheader("Ã°Å¸â€œÅ  Individual Market Seasonality")

tabs = st.tabs(["Ã°Å¸â€œË† Equities", "Ã°Å¸Ââ€¦ Commodities", "Ã°Å¸Å’Â¾ Agriculture"])

for tab, markets in zip(tabs, [EQUITY_MARKETS, COMMODITY_MARKETS, AGRICULTURE_MARKETS]):
    with tab:
        for sym in markets:
            fig = seasonality_heatmap(sym)
            st.plotly_chart(fig, use_container_width=True)
