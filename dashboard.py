"""
Streamlit Dashboard — Main Entry Point
=======================================
Multi-page institutional dashboard for the Swing Trading Platform.
Run: streamlit run dashboard.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

st.set_page_config(
    page_title="COT Intelligence Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar navigation ────────────────────────────────────────────────────────
PAGES = {
    "🏠 Overview":              "src/dashboard/pages/overview.py",
    "💼 Portfolio":             "src/dashboard/pages/portfolio.py",
    "📡 Signals":               "src/dashboard/pages/signals.py",
    "📊 COT Dashboard":         "src/dashboard/pages/cot_dashboard.py",
    "🗓 Seasonality":           "src/dashboard/pages/seasonality.py",
    "⚡ VIX Dashboard":         "src/dashboard/pages/vix_dashboard.py",
    "💵 DXY Dashboard":         "src/dashboard/pages/dxy_dashboard.py",
    "📉 US10Y Dashboard":       "src/dashboard/pages/us10y_dashboard.py",
    "📈 Performance Analytics": "src/dashboard/pages/performance.py",
    "🗒 Trade History":         "src/dashboard/pages/trade_history.py",
}

with st.sidebar:
    st.image("https://img.icons8.com/color/96/combo-chart.png", width=60)
    st.title("COT Intelligence")
    st.caption("Institutional Swing Trading Platform")
    st.divider()
    selection = st.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    st.caption("v1.0.0 · Production")

# ── Load selected page ────────────────────────────────────────────────────────
page_path = Path(PAGES[selection])
if page_path.exists():
    with open(page_path) as f:
        exec(compile(f.read(), str(page_path), "exec"), {"__name__": "__main__"})
else:
    st.error(f"Page not found: {page_path}")
