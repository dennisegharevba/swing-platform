import sys
sys.path.insert(0, "/mount/src/swing-platform")

import asyncio

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.core.config import ALL_MARKETS
from src.dashboard.helpers import (
    ACCENT_BLUE, BEAR_RED, BULL_GREEN, GOLD, NEUTRAL_GREY, PLOTLY_LAYOUT,
    TEXT_DIM, TEXT_PRIMARY, apply_theme, async_run, cot_index_chart,
)

apply_theme()
st.title("ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã…Â  COT Dashboard")
st.caption("CFTC Commitments of Traders ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Commercial positioning percentile (3yr lookback)")


@st.cache_data(ttl=3600, show_spinner=False)
def load_cot_all() -> dict:
    async def _fetch_all():
        from src.data.market_data import fetch_cot_data
        results = {}
        for sym in ALL_MARKETS:
            df = await fetch_cot_data(sym)
            results[sym] = df
        return results
    return async_run(_fetch_all())


with st.spinner("Fetching COT data from CFTCÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦"):
    cot_data = load_cot_all()

# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ COT Index scoreboard ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
st.subheader("ÃƒÂ°Ã…Â¸Ã…Â½Ã‚Â¯ COT Index Scoreboard")
st.caption("Commercial net position as percentile rank over 3-year rolling window. >70 = bullish, <30 = bearish")

cols = st.columns(4)
for i, (sym, name) in enumerate(ALL_MARKETS.items()):
    df = cot_data.get(sym, pd.DataFrame())
    if df.empty or "cot_index" not in df.columns:
        idx_val = None
    else:
        s = df["cot_index"].dropna()
        idx_val = float(s.iloc[-1]) if not s.empty else None

    col = cols[i % 4]
    with col:
        if idx_val is not None:
            color = BULL_GREEN if idx_val >= 70 else BEAR_RED if idx_val <= 30 else GOLD
            signal = "ÃƒÂ°Ã…Â¸Ã…Â¸Ã‚Â¢ BULLISH" if idx_val >= 70 else "ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â´ BEARISH" if idx_val <= 30 else "ÃƒÂ¢Ã…Â¡Ã‚Âª NEUTRAL"
            st.markdown(
                f"""<div style="background:#1a1d26;border:1px solid #2a2d3a;border-radius:10px;
                padding:12px;margin-bottom:8px;text-align:center;">
                <div style="color:{TEXT_DIM};font-size:0.8rem;">{name}</div>
                <div style="color:{color};font-size:2rem;font-weight:800;">{idx_val:.0f}</div>
                <div style="color:{TEXT_DIM};font-size:0.75rem;">{signal}</div>
                </div>""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""<div style="background:#1a1d26;border:1px solid #2a2d3a;border-radius:10px;
                padding:12px;margin-bottom:8px;text-align:center;">
                <div style="color:{TEXT_DIM};font-size:0.8rem;">{name}</div>
                <div style="color:{NEUTRAL_GREY};font-size:2rem;font-weight:800;">N/A</div>
                </div>""",
                unsafe_allow_html=True,
            )

st.divider()

# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Individual market deep dive ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
st.subheader("ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â¬ Market Deep Dive")
selected = st.selectbox(
    "Select Market",
    options=list(ALL_MARKETS.keys()),
    format_func=lambda x: f"{x} ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â {ALL_MARKETS[x]}",
)

df_sel = cot_data.get(selected, pd.DataFrame())
if df_sel.empty:
    st.warning(f"No COT data available for {selected}. CFTC data may be loading.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‹â€  COT Index", "ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã…Â  Positions", "ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ¢â‚¬Å¾ Weekly Changes"])

with tab1:
    fig = cot_index_chart(df_sel, selected)
    st.plotly_chart(fig, use_container_width=True)

    # Summary stats
    if "cot_index" in df_sel.columns:
        s = df_sel["cot_index"].dropna()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current", f"{s.iloc[-1]:.1f}")
        c2.metric("4-Week Avg", f"{s.tail(4).mean():.1f}")
        c3.metric("13-Week Avg", f"{s.tail(13).mean():.1f}")
        c4.metric("52-Week Range", f"{s.tail(52).min():.0f}ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“{s.tail(52).max():.0f}")

with tab2:
    if "comm_long" in df_sel.columns and "comm_short" in df_sel.columns:
        df_pos = df_sel[["comm_long", "comm_short", "comm_net"]].dropna().tail(52)
        fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                             subplot_titles=["Commercial Long vs Short", "Commercial Net Position"])

        fig2.add_trace(go.Bar(x=df_pos.index, y=df_pos["comm_long"],
                              name="Comm Long", marker_color=BULL_GREEN, opacity=0.7), row=1, col=1)
        fig2.add_trace(go.Bar(x=df_pos.index, y=df_pos["comm_short"],
                              name="Comm Short", marker_color=BEAR_RED, opacity=0.7), row=1, col=1)
        colors_net = [BULL_GREEN if v >= 0 else BEAR_RED for v in df_pos["comm_net"]]
        fig2.add_trace(go.Bar(x=df_pos.index, y=df_pos["comm_net"],
                              name="Net", marker_color=colors_net), row=2, col=1)
        fig2.update_layout(**{**PLOTLY_LAYOUT, "height": 500, "barmode": "group"})
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Position breakdown unavailable.")

with tab3:
    if "comm_long_chg" in df_sel.columns:
        df_chg = df_sel[["comm_long_chg", "comm_short_chg"]].dropna().tail(26)
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=df_chg.index, y=df_chg["comm_long_chg"],
                              name="Long Change", marker_color=BULL_GREEN, opacity=0.8))
        fig3.add_trace(go.Bar(x=df_chg.index, y=df_chg["comm_short_chg"],
                              name="Short Change", marker_color=BEAR_RED, opacity=0.8))
        fig3.update_layout(**{**PLOTLY_LAYOUT, "height": 350, "barmode": "group",
                               "title": f"{ALL_MARKETS[selected]} ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Weekly COT Position Changes"})
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Weekly change data unavailable.")

st.divider()
st.caption("COT data source: CFTC Disaggregated Futures-Only Report Ãƒâ€šÃ‚Â· Released every Friday 15:30 ET")
if st.button("ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ¢â‚¬Å¾ Refresh COT Data"):
    from src.data.market_data import _cot_cache
    _cot_cache.clear()
    st.cache_data.clear()
    st.rerun()
