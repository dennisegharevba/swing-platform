import sys
sys.path.insert(0, "/mount/src/swing-platform")

import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/platform.db")

import asyncio
import concurrent.futures
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="COT Intelligence Platform",
    page_icon="chart",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _init_db():
    async def _run():
        from src.core.database import create_tables
        await create_tables()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, _run()).result(timeout=30)


try:
    _init_db()
except Exception:
    pass

PAGES = {
    "Overview": "src/dashboard/pages/overview.py",
    "Portfolio": "src/dashboard/pages/portfolio.py",
    "Signals": "src/dashboard/pages/signals.py",
    "Signal Lifecycle": "src/dashboard/pages/signal_lifecycle.py",
    "COT Dashboard": "src/dashboard/pages/cot_dashboard.py",
    "Seasonality": "src/dashboard/pages/seasonality.py",
    "VIX Dashboard": "src/dashboard/pages/vix_dashboard.py",
    "DXY Dashboard": "src/dashboard/pages/dxy_dashboard.py",
    "US10Y Dashboard": "src/dashboard/pages/us10y_dashboard.py",
    "Performance Analytics": "src/dashboard/pages/performance.py",
    "Trade History": "src/dashboard/pages/trade_history.py",
}

with st.sidebar:
    st.title("COT Intelligence")
    st.caption("Institutional Swing Trading Platform")
    st.divider()
    selection = st.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    st.caption("v1.0.0 - Production")

page_path = Path(PAGES[selection])
if page_path.exists():
    with open(page_path) as f:
        exec(compile(f.read(), str(page_path), "exec"), {"__name__": "__main__", "__file__": str(page_path)})
else:
    st.error(f"Page not found: {page_path}")
