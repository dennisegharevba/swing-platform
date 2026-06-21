import sys
sys.path.insert(0, "/mount/src/swing-platform")

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.helpers import (
    ACCENT_BLUE, BEAR_RED, BULL_GREEN, GOLD, NEUTRAL_GREY, PLOTLY_LAYOUT,
    TEXT_DIM, TEXT_PRIMARY, apply_theme, async_run, score_color, render_freshness_bar,
    get_cached_scan,
)

apply_theme()
st.title("Portfolio Management")
render_freshness_bar("Portfolio scan")


def get_scan():
    return get_cached_scan()


with st.spinner("Loading portfolio data..."):
    result = get_scan()

macro_score = result.aggregate_macro_score
cash_pct = 0.30 if macro_score < 48 else 0.15

st.subheader("Portfolio Cash Rule")
c1, c2, c3 = st.columns(3)
c1.metric("Aggregate Macro Score", f"{macro_score:.1f}/100")
c2.metric("Required Cash Reserve", f"{cash_pct*100:.0f}%",
          delta="High Risk Mode" if macro_score < 48 else "Normal Mode",
          delta_color="inverse" if macro_score < 48 else "normal")
c3.metric("Max Deployable Capital", f"{(1-cash_pct)*100:.0f}%")

st.divider()

st.subheader("Active Signal Position Sizing")

if result.signals:
    rows = []
    for sig in sorted(result.signals, key=lambda x: x.score, reverse=True):
        from src.risk.risk_engine import compute_risk_parameters
        params = compute_risk_parameters(sig)
        pos_pct = params.position_size_pct if params else 0.05
        rows.append({
            "Symbol": sig.symbol,
            "Name": sig.name,
            "Class": sig.asset_class.value.title(),
            "Dir": sig.direction.value.upper(),
            "Score": sig.score,
            "Entry": sig.entry_price,
            "Stop": sig.stop_loss,
            "TP1": sig.take_profit_1,
            "TP2": sig.take_profit_2,
            "R:R": f"{sig.risk_reward:.1f}x",
            "ATR%": f"{sig.atr_risk_pct:.2f}%",
            "Size%": f"{pos_pct*100:.1f}%",
            "Hold": f"{sig.expected_hold_days}d",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Sector Exposure")
    class_counts = {"Equity": 0, "Commodity": 0, "Agriculture": 0}
    for sig in result.signals:
        key = sig.asset_class.value.title()
        class_counts[key] = class_counts.get(key, 0) + 1

    fig_pie = go.Figure(go.Pie(
        labels=list(class_counts.keys()), values=list(class_counts.values()),
        hole=0.5, marker_colors=[ACCENT_BLUE, GOLD, BULL_GREEN],
    ))
    fig_pie.update_layout(**{**PLOTLY_LAYOUT, "height": 280, "showlegend": True})
    st.plotly_chart(fig_pie, use_container_width=True)

else:
    st.info("No active signals - portfolio is in full cash mode.")

st.divider()
st.subheader("Portfolio Rules")
rules = [
    ("Minimum Cash Reserve", "15% always"),
    ("Elevated Cash Reserve", "30% when Aggregate Macro Score < 48"),
    ("Max Risk Per Position", "2% of portfolio"),
    ("Stop Method", "2x ATR from entry"),
    ("TP1", "1.5x risk distance"),
    ("TP2", "3.0x risk distance"),
    ("Max Positions", "12 simultaneous"),
    ("VIX Hard Override", "No new positions when VIX > 35"),
]
for rule, val in rules:
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
        f'border-bottom:1px solid #2a2d3a;">'
        f'<span style="color:{TEXT_DIM}">{rule}</span>'
        f'<span style="color:{TEXT_PRIMARY};font-weight:600">{val}</span></div>',
        unsafe_allow_html=True,
    )
