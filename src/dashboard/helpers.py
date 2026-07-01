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

    signal_date_str = sig.first_seen_date.strftime("%b %d, %Y") if sig.first_seen_date else "N/A"
    countdown_color = BEAR_RED if sig.days_remaining < 0 else (GOLD if sig.days_remaining <= 2 else TEXT_PRIMARY)

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
      <div style="margin-top:6px; font-size:0.85rem; color:{TEXT_DIM};">
        Signal date: <b style="color:{TEXT_PRIMARY};">{signal_date_str}</b>
        &nbsp;|&nbsp;
        <b style="color:{countdown_color};">{sig.signal_age_label}</b>
      </div>
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


LIFECYCLE_STATUS_COLORS = {
    "active": ACCENT_BLUE,
    "target_1_hit": "#8fd9c4",
    "final_target_hit": BULL_GREEN,
    "near_stop": GOLD,
    "stop_hit": BEAR_RED,
    "expired": TEXT_DIM,
    "invalidated": TEXT_DIM,
    "extended_trend": "#c792ea",
    "trend_reversal": "#ff8c42",
}


def status_color(status):
    return LIFECYCLE_STATUS_COLORS.get(status, TEXT_DIM)


def render_live_countdown(label, target_dt_utc, key):
    """
    A small HTML/JS widget that ticks in real browser time between Streamlit
    reruns, rather than freezing at page-render time. `target_dt_utc` is the
    instant the countdown counts down to (pass a past instant for a
    count-up "time since" display via a negative-looking label upstream).
    """
    import streamlit.components.v1 as components
    iso = target_dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    html = f"""
    <div id="cd-{key}" style="font-family: Inter, sans-serif; font-size: 0.95rem; color: {TEXT_PRIMARY};">
      <span style="color:{TEXT_DIM};">{label}:</span> <b id="cd-val-{key}">--</b>
    </div>
    <script>
      (function() {{
        const target = new Date("{iso}").getTime();
        function tick() {{
          const now = new Date().getTime();
          let diff = target - now;
          const sign = diff < 0 ? "-" : "";
          diff = Math.abs(diff);
          const d = Math.floor(diff / 86400000);
          const h = Math.floor((diff % 86400000) / 3600000);
          const m = Math.floor((diff % 3600000) / 60000);
          const s = Math.floor((diff % 60000) / 1000);
          let text;
          if (d > 0) {{ text = sign + d + "d " + String(h).padStart(2,'0') + "h " + String(m).padStart(2,'0') + "m"; }}
          else if (h > 0) {{ text = sign + h + "h " + String(m).padStart(2,'0') + "m " + String(s).padStart(2,'0') + "s"; }}
          else {{ text = sign + m + "m " + String(s).padStart(2,'0') + "s"; }}
          const el = document.getElementById("cd-val-{key}");
          if (el) {{ el.textContent = text; }}
        }}
        tick();
        setInterval(tick, 1000);
      }})();
    </script>
    """
    components.html(html, height=28)


def render_lifecycle_card(trade):
    """Renders a single tracked signal's lifecycle: status, P/L, MFE/MAE,
    progress toward target, age, session, and live countdowns."""
    from datetime import datetime, timedelta
    from src.signals.lifecycle import compute_progress, STATUS_LABELS

    progress = compute_progress(trade)
    dir_class = "long" if trade.direction == "long" else "short"
    s_color = status_color(trade.status)
    pnl_color = BULL_GREEN if (trade.pnl_pct or 0) >= 0 else BEAR_RED

    html = f"""
    <div class="signal-card {dir_class}">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <span style="font-size:1.15rem; font-weight:700; color:{TEXT_PRIMARY};">{trade.symbol}</span>
          <span style="color:{TEXT_DIM}; margin-left:8px;">{trade.direction.upper()}</span>
        </div>
        <div style="font-size:0.85rem; font-weight:700; color:{s_color}; border:1px solid {s_color};
                    border-radius:6px; padding:2px 8px;">{STATUS_LABELS.get(trade.status, trade.status)}</div>
      </div>
      <div style="margin-top:8px; font-size:0.85rem; color:{TEXT_DIM};">
        Entry <b style="color:{TEXT_PRIMARY};">{trade.entry_price:.4f}</b> &nbsp;|&nbsp;
        Stop <b style="color:{BEAR_RED};">{trade.stop_loss:.4f}</b> &nbsp;|&nbsp;
        TP1 <b style="color:{TEXT_PRIMARY};">{trade.take_profit_1:.4f}</b> &nbsp;|&nbsp;
        TP2 <b style="color:{BULL_GREEN};">{trade.take_profit_2:.4f}</b> &nbsp;|&nbsp;
        Last <b style="color:{TEXT_PRIMARY};">{(trade.last_price or trade.entry_price):.4f}</b>
      </div>
      <div style="margin-top:6px; font-size:0.85rem; color:{TEXT_DIM};">
        P/L <b style="color:{pnl_color};">{(trade.pnl_pct or 0):+.2f}%</b> &nbsp;|&nbsp;
        MFE <b style="color:{BULL_GREEN};">{(trade.mfe_pct or 0):+.2f}%</b> &nbsp;|&nbsp;
        MAE <b style="color:{BEAR_RED};">{(trade.mae_pct or 0):+.2f}%</b> &nbsp;|&nbsp;
        {progress.age_bucket} &nbsp;|&nbsp; {progress.session} session
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        render_live_countdown("Time since issued", trade.opened_at, key=f"since_{trade.id}")
    with c2:
        deadline = trade.opened_at + timedelta(days=trade.expected_hold_days or 10)
        render_live_countdown("Time to expected expiry", deadline, key=f"expiry_{trade.id}")

    st.progress(min(1.0, max(0.0, progress.pct_to_target / 100)),
                text=f"{progress.pct_to_target:.0f}% of the way to the final target")


def render_freshness_bar(timestamp_label="Data as of"):
    """Render a consistent live-data freshness indicator and manual refresh button."""
    from datetime import datetime
    col1, col2 = st.columns([4, 1])
    with col1:
        st.caption(f"{timestamp_label}: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC (page render time)")
    with col2:
        if st.button("Refresh Now", key=f"refresh_{timestamp_label}"):
            st.cache_data.clear()
            st.rerun()


@st.cache_data(ttl=120, show_spinner=False)
def get_cached_scan():
    """
    Single shared scan cache used by Overview, Portfolio, and Signals pages.
    Ensures all pages show the exact same live data within the same 2-minute window,
    rather than each page running its own independent scan at slightly different times.
    """
    from src.signals.scanner import scan_universe
    return async_run(scan_universe())


@st.cache_data(ttl=30, show_spinner=False)
def get_cached_active_trades():
    """Active/open lifecycle trades, refreshed independently of the heavier scan cache."""
    from src.signals.lifecycle import get_active_trades
    return async_run(get_active_trades())
