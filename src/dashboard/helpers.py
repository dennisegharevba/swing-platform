import sys
sys.path.insert(0, "/mount/src/swing-platform")


import asyncio
import concurrent.futures
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

BULL_GREEN = "#00d2a8"
BEAR_RED = "#ff4b6e"
NEUTRAL_GREY = "#888888"
ACCENT_BLUE = "#4fa3ff"
BG_DARK = "#0f1117"
BG_PANEL = "#1a1d26"
TEXT_PRIMARY = "#f0f2f6"
TEXT_DIM = "#8a8fa8"
GOLD = "#f5c518"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT_PRIMARY, family="Inter, sans-serif", size=12),
    xaxis=dict(gridcolor="#2a2d3a", zeroline=False),
    yaxis=dict(gridcolor="#2a2d3a", zeroline=False),
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#2a2d3a"),
)

STREAMLIT_THEME = """
<style>
  [data-testid="stAppViewContainer"] { background: #0f1117; }
  [data-testid="stSidebar"]          { background: #13151f; border-right: 1px solid #2a2d3a; }
  [data-testid="metric-container"] {
    background: #1a1d26;
    border: 1px solid #2a2d3a;
    border-radius: 10px;
    padding: 1rem;
  }
  [data-testid="stDataFrame"] { border: 1px solid #2a2d3a; border-radius: 8px; }
  .stButton > button {
    background: linear-gradient(135deg, #4fa3ff, #7b5cff);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
  }
  .stButton > button:hover { opacity: 0.85; }
  .signal-card {
    background: #1a1d26;
    border: 1px solid #2a2d3a;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
  }
  .signal-card.long  { border-left: 4px solid #00d2a8; }
  .signal-card.short { border-left: 4px solid #ff4b6e; }
</style>
"""


def apply_theme():
    st.markdown(STREAMLIT_THEME, unsafe_allow_html=True)


def async_run(coro):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result(timeout=120)


def candlestick_chart(df, title, show_ma=True):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.75, 0.25])

    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="Price",
            increasing_line_color=BULL_GREEN, decreasing_line_color=BEAR_RED,
            increasing_fillcolor=BULL_GREEN, decreasing_fillcolor=BEAR_RED,
        ),
        row=1, col=1,
    )

    if show_ma:
        for col, color, label in [("ma_20", ACCENT_BLUE, "MA20"), ("ma_50", GOLD, "MA50"), ("ma_200", "#ff8c42", "MA200")]:
            if col in df.columns:
                fig.add_trace(
                    go.Scatter(x=df.index, y=df[col], name=label, line=dict(color=color, width=1.5), opacity=0.85),
                    row=1, col=1,
                )

    if "volume" in df.columns:
        colors = [BULL_GREEN if df["close"].iloc[i] >= df["open"].iloc[i] else BEAR_RED for i in range(len(df))]
        fig.add_trace(go.Bar(x=df.index, y=df["volume"], name="Volume", marker_color=colors, opacity=0.6), row=2, col=1)

    layout = {**PLOTLY_LAYOUT, "title": title, "height": 500}
    fig.update_layout(**layout)
    fig.update_xaxes(rangeslider_visible=False)
    return fig


def score_gauge(score, title="Score"):
    color = BULL_GREEN if score >= 70 else GOLD if score >= 52 else BEAR_RED
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": title, "font": {"color": TEXT_PRIMARY, "size": 14}},
        number={"font": {"color": color, "size": 32}, "suffix": "/100"},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": TEXT_DIM},
            "bar": {"color": color},
            "bgcolor": BG_PANEL,
            "bordercolor": "#2a2d3a",
            "steps": [
                {"range": [0, 48], "color": "#2a1a1f"},
                {"range": [48, 70], "color": "#1f2a1a"},
                {"range": [70, 100], "color": "#162a24"},
            ],
            "threshold": {"line": {"color": TEXT_PRIMARY, "width": 2}, "thickness": 0.8, "value": score},
        },
    ))
    fig.update_layout(**{**PLOTLY_LAYOUT, "height": 200, "margin": dict(t=40, b=10, l=10, r=10)})
    return fig


def cot_index_chart(df, symbol):
    fig = go.Figure()
    if "cot_index" not in df.columns:
        return fig

    series = df["cot_index"].dropna().tail(156)

    fig.add_trace(go.Scatter(
        x=series.index, y=series.values, name="COT Index",
        line=dict(color=ACCENT_BLUE, width=2), fill="tozeroy", fillcolor="rgba(79,163,255,0.1)",
    ))

    for y, color, label in [(70, BULL_GREEN, "Bullish Zone"), (30, BEAR_RED, "Bearish Zone")]:
        fig.add_hline(y=y, line_dash="dash", line_color=color, annotation_text=label, annotation_position="right")

    fig.update_layout(**{
        **PLOTLY_LAYOUT,
        "title": f"{symbol} - Commercial COT Index (3yr percentile)",
        "height": 300,
        "yaxis": {**PLOTLY_LAYOUT["yaxis"], "range": [0, 100]},
    })
    return fig


def regime_timeline(dates, values, title, threshold=0):
    colors = [BULL_GREEN if v > threshold else BEAR_RED for v in values]
    fig = go.Figure(go.Bar(x=dates, y=values, marker_color=colors, name=title))
    fig.add_hline(y=threshold, line_dash="dash", line_color=TEXT_DIM)
    fig.update_layout(**{**PLOTLY_LAYOUT, "title": title, "height": 260})
    return fig


def seasonality_heatmap(symbol):
    from src.core.config import SEASONALITY
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    biases = [SEASONALITY.get(symbol, {}).get(m, 0) for m in range(1, 13)]
    colors = [BULL_GREEN if b > 0 else BEAR_RED for b in biases]

    fig = go.Figure(go.Bar(
        x=months, y=biases, marker_color=colors, name="Seasonal Bias",
        text=[f"{b:+.2f}" for b in biases], textposition="outside",
    ))
    fig.add_hline(y=0, line_color=TEXT_DIM, line_width=1)
    fig.update_layout(**{
        **PLOTLY_LAYOUT,
        "title": f"{symbol} - Monthly Seasonal Bias (20yr avg)",
        "height": 300,
        "yaxis": {**PLOTLY_LAYOUT["yaxis"], "title": "Avg Monthly Bias"},
    })
    return fig


def score_color(score):
    if score >= 70:
        return BULL_GREEN
    if score >= 52:
        return GOLD
    return BEAR_RED


def direction_badge(direction):
    if direction.lower() == "long":
        return "LONG"
    if direction.lower() == "short":
        return "SHORT"
    return "NEUTRAL"


def render_signal_card(sig):
    from src.core.config import Direction
    dir_class = "long" if sig.direction == Direction.LONG else "short"
    dir_label = direction_badge(sig.direction.value)
    month = sig.scanned_at.month
    season = sig.seasonality_label(month)

    html = f"""
    <div class="signal-card {dir_class}">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <span style="font-size:1.2rem; font-weight:700; color:{TEXT_PRIMARY};">{sig.name}</span>
          <span style="color:{TEXT_DIM}; margin-left:8px;">({sig.symbol})</span>
        </div>
        <div style="font-size:1.4rem; font-weight:800; color:{score_color(sig.score)};">{sig.score:.0f}/100</div>
      </div>
      <div style="margin-top:6px; font-size:1rem;">{dir_label}</div>
      <hr style="border-color:#2a2d3a; margin:8px 0;">
      <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; font-size:0.85rem; color:{TEXT_DIM};">
        <div>COT: <b style="color:{TEXT_PRIMARY};">{sig.scores.commercial_cot:.0f}/35</b></div>
        <div>Season: <b style="color:{TEXT_PRIMARY};">{season}</b></div>
        <div>Macro: <b style="color:{TEXT_PRIMARY};">{sig.scores.macro_regime:.0f}/20</b></div>
        <div>Entry: <b style="color:{TEXT_PRIMARY};">{sig.entry_price:.4f}</b></div>
        <div>Stop: <b style="color:{BEAR_RED};">{sig.stop_loss:.4f}</b></div>
        <div>TP2: <b style="color:{BULL_GREEN};">{sig.take_profit_2:.4f}</b></div>
        <div>R:R: <b style="color:{TEXT_PRIMARY};">{sig.risk_reward:.1f}x</b></div>
        <div>Hold: <b style="color:{TEXT_PRIMARY};">{sig.expected_hold_days}d</b></div>
        <div>ATR%: <b style="color:{TEXT_PRIMARY};">{sig.atr_risk_pct:.2f}%</b></div>
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
