import sys
sys.path.insert(0, "/mount/src/swing-platform")

import streamlit as st

from src.dashboard.helpers import (
    BEAR_RED, BULL_GREEN, GOLD, PLOTLY_LAYOUT, TEXT_DIM, TEXT_PRIMARY,
    apply_theme, async_run, candlestick_chart, render_signal_card, score_gauge,
)

apply_theme()
st.title("Signal Intelligence")


@st.cache_data(ttl=900, show_spinner=False)
def get_scan():
    from src.signals.scanner import scan_universe
    return async_run(scan_universe())


with st.spinner("Scanning markets..."):
    result = get_scan()

st.subheader("Filters")
f1, f2, f3 = st.columns(3)
with f1:
    ac_filter = st.multiselect("Asset Class", ["Equity", "Commodity", "Agriculture"],
                                default=["Equity", "Commodity", "Agriculture"])
with f2:
    dir_filter = st.multiselect("Direction", ["Long", "Short"], default=["Long", "Short"])
with f3:
    min_score = st.slider("Minimum Score", 0, 100, 48)

filtered = [
    s for s in result.signals
    if s.asset_class.value.title() in ac_filter
    and s.direction.value.title() in dir_filter
    and s.score >= min_score
]

st.caption(f"Showing {len(filtered)} of {len(result.signals)} signals")
st.divider()

if not filtered:
    st.info("No signals match your filters.")
    st.stop()

selected_name = st.selectbox(
    "Select signal for detailed view",
    options=[f"{s.symbol} - {s.name} ({s.direction.value.upper()}, {s.score:.0f}/100)"
             for s in sorted(filtered, key=lambda x: x.score, reverse=True)],
)
selected_sym = selected_name.split(" - ")[0].strip()
selected_sig = next((s for s in filtered if s.symbol == selected_sym), None)

st.subheader("All Signals")
for sig in sorted(filtered, key=lambda x: x.score, reverse=True):
    render_signal_card(sig)

if selected_sig:
    st.divider()
    st.subheader(f"Detail: {selected_sig.name} ({selected_sig.symbol})")

    d1, d2 = st.columns([1, 2])
    with d1:
        st.plotly_chart(score_gauge(selected_sig.score, f"{selected_sig.symbol} Score"), use_container_width=True)

        import plotly.graph_objects as go
        components = {
            "COT (35)": selected_sig.scores.commercial_cot,
            "Season (25)": selected_sig.scores.seasonality,
            "Macro (20)": selected_sig.scores.macro_regime,
            "Trend (10)": selected_sig.scores.trend_alignment,
            "Momentum (10)": selected_sig.scores.momentum,
        }
        maxes = [35, 25, 20, 10, 10]
        fig_bar = go.Figure(go.Bar(
            y=list(components.keys()), x=list(components.values()), orientation="h",
            marker_color=[BULL_GREEN if v >= m*0.6 else GOLD if v >= m*0.3 else BEAR_RED
                          for v, m in zip(components.values(), maxes)],
            text=[f"{v:.1f}/{m}" for v, m in zip(components.values(), maxes)],
            textposition="outside",
        ))
        fig_bar.update_layout(**{**PLOTLY_LAYOUT, "height": 260, "showlegend": False,
                                  "xaxis": {**PLOTLY_LAYOUT["xaxis"], "range": [0, 38]}})
        st.plotly_chart(fig_bar, use_container_width=True)

    with d2:
        df_chart = selected_sig.price_df.tail(120)
        if not df_chart.empty:
            fig = candlestick_chart(df_chart, f"{selected_sig.name} - Price Chart")
            if selected_sig.entry_price:
                for price, color, label in [
                    (selected_sig.entry_price, "#ffffff", "Entry"),
                    (selected_sig.stop_loss, BEAR_RED, "Stop"),
                    (selected_sig.take_profit_1, GOLD, "TP1"),
                    (selected_sig.take_profit_2, BULL_GREEN, "TP2"),
                ]:
                    fig.add_hline(y=price, line_color=color, line_dash="dash",
                                  annotation_text=f"{label}: {price:.4f}",
                                  annotation_position="right", row=1, col=1)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Price chart unavailable.")
