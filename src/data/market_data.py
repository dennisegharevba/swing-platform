import sys
sys.path.insert(0, "/mount/src/swing-platform")


import asyncio
import io
import zipfile
from datetime import date, timedelta

import httpx
import numpy as np
import pandas as pd
import yfinance as yf
from cachetools import TTLCache
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import COT_CODES, YAHOO_TICKERS, get_settings

settings = get_settings()

_price_cache = TTLCache(maxsize=200, ttl=settings.cache_ttl_seconds)
_macro_cache = TTLCache(maxsize=50, ttl=settings.cache_ttl_seconds)
_cot_cache = TTLCache(maxsize=30, ttl=settings.cache_ttl_seconds * 6)


@retry(stop=stop_after_attempt(settings.max_retries), wait=wait_exponential(multiplier=1, min=2, max=15), reraise=True)
def _fetch_yf_sync(ticker, period="2y", interval="1d"):
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval, auto_adjust=True)
    if df.empty:
        raise ValueError(f"Empty data for {ticker}")
    df.index = pd.DatetimeIndex(df.index.date)
    df.index.name = "date"
    df = df[["Open", "High", "Low", "Close", "Volume"]].rename(columns=str.lower)
    return df


async def fetch_price_data(symbol, period="2y", interval="1d"):
    cache_key = f"{symbol}:{period}:{interval}"
    if cache_key in _price_cache:
        return _price_cache[cache_key]

    ticker = YAHOO_TICKERS.get(symbol, symbol)
    try:
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(None, _fetch_yf_sync, ticker, period, interval)
        _price_cache[cache_key] = df
        return df
    except Exception as exc:
        logger.error("Price fetch failed for {}: {}", symbol, exc)
        return pd.DataFrame()


async def fetch_multiple(symbols, period="2y"):
    tasks = [fetch_price_data(sym, period) for sym in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = {}
    for sym, res in zip(symbols, results):
        if isinstance(res, pd.DataFrame) and not res.empty:
            out[sym] = res
    return out


def compute_atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def compute_rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_ma(series, period):
    return series.rolling(period).mean()


def enrich_ohlcv(df):
    if df.empty:
        return df
    df = df.copy()
    df["atr_14"] = compute_atr(df, 14)
    df["ma_20"] = compute_ma(df["close"], 20)
    df["ma_50"] = compute_ma(df["close"], 50)
    df["ma_200"] = compute_ma(df["close"], 200)
    df["rsi_14"] = compute_rsi(df, 14)
    df["pct_change"] = df["close"].pct_change()
    return df


async def fetch_fred_series(series_id, limit=500):
    if series_id in _macro_cache:
        return _macro_cache[series_id]

    api_key = settings.fred_api_key
    if not api_key:
        return pd.Series(dtype=float)

    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={api_key}&file_type=json"
        f"&observation_start={(date.today() - timedelta(days=limit)).isoformat()}"
    )
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        observations = data.get("observations", [])
        s = pd.Series(
            {obs["date"]: float(obs["value"]) for obs in observations if obs["value"] != "."},
            dtype=float,
        )
        s.index = pd.to_datetime(s.index)
        s = s.sort_index()
        _macro_cache[series_id] = s
        return s
    except Exception as exc:
        logger.error("FRED fetch failed for {}: {}", series_id, exc)
        return pd.Series(dtype=float)


async def fetch_vix():
    df = await fetch_price_data("VIX")
    if df.empty:
        return 20.0
    return float(df["close"].iloc[-1])


async def fetch_dxy():
    return await fetch_price_data("DXY", period="2y")


async def fetch_us10y():
    df = await fetch_price_data("US10Y", period="2y")
    if not df.empty:
        for col in ["open", "high", "low", "close"]:
            if df[col].mean() > 15:
                df[col] = df[col] / 10
    return df


async def fetch_real_yield():
    s = await fetch_fred_series("DFII10", limit=60)
    if len(s) < 25:
        df = await fetch_price_data("TIP")
        if df.empty:
            return 0.0
        recent = df["close"].dropna()
        if len(recent) < 22:
            return 0.0
        chg = (recent.iloc[-1] - recent.iloc[-22]) / recent.iloc[-22]
        return float(-chg * 100)

    recent = s.dropna()
    change_20d = float(recent.iloc[-1] - recent.iloc[-min(20, len(recent))])
    return change_20d


CFTC_COT_URL = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"

# CFTC has used a few different date-column names over time; check all of them
DATE_COLUMN_CANDIDATES = [
    "Report_Date_as_MM_DD_YYYY",
    "Report_Date_as_YYYY-MM-DD",
    "Report_Date_as_YYYY_MM_DD",
    "As_of_Date_In_Form_YYMMDD",
]

# This pulls the DISAGGREGATED report, which has 4 trader categories, not 2.
# "comm_long/short" here maps to Producer/Merchant/Processor/User -- the closest
# disaggregated analog to "commercial hedger" from the legacy report.
# "noncomm_long/short" maps to Managed Money -- the closest analog to speculators.
# Listed as candidate lists because CFTC's own files are inconsistently
# capitalized (ALL vs All) across different years.
COT_COLUMN_ALIASES = {
    "market": ["Market_and_Exchange_Names"],
    "comm_long": ["Prod_Merc_Positions_Long_ALL", "Prod_Merc_Positions_Long_All"],
    "comm_short": ["Prod_Merc_Positions_Short_ALL", "Prod_Merc_Positions_Short_All"],
    "noncomm_long": ["M_Money_Positions_Long_ALL", "M_Money_Positions_Long_All"],
    "noncomm_short": ["M_Money_Positions_Short_ALL", "M_Money_Positions_Short_All"],
    "open_interest": ["Open_Interest_All", "Open_Interest_ALL"],
    "comm_long_chg": ["Change_in_Prod_Merc_Long_All", "Change_in_Prod_Merc_Long_ALL"],
    "comm_short_chg": ["Change_in_Prod_Merc_Short_All", "Change_in_Prod_Merc_Short_ALL"],
}


def _resolve_columns(df, aliases):
    """Case-insensitive match of conceptual field names to actual CFTC column names."""
    lower_map = {c.lower(): c for c in df.columns}
    resolved = {}
    for target, candidates in aliases.items():
        for cand in candidates:
            if cand.lower() in lower_map:
                resolved[lower_map[cand.lower()]] = target
                break
    return resolved


async def _download_cot_year(year):
    url = CFTC_COT_URL.format(year=year)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(resp.content))
        fname = [n for n in z.namelist() if n.endswith(".txt")][0]
        df = pd.read_csv(z.open(fname), low_memory=False)
        return df
    except Exception as exc:
        logger.error("COT download failed year={}: {}", year, exc)
        return pd.DataFrame()


async def fetch_cot_data(symbol):
    cache_key = f"cot:{symbol}"
    if cache_key in _cot_cache:
        return _cot_cache[cache_key]

    code = COT_CODES.get(symbol)
    if not code:
        return pd.DataFrame()

    current_year = date.today().year
    frames = []
    for yr in [current_year - 1, current_year]:
        df_raw = await _download_cot_year(yr)
        if not df_raw.empty:
            frames.append(df_raw)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    code_col = "CFTC_Contract_Market_Code"
    if code_col not in df.columns:
        return pd.DataFrame()

    df = df[df[code_col].astype(str).str.strip() == code.strip()].copy()
    if df.empty:
        return pd.DataFrame()

    date_col = next((c for c in DATE_COLUMN_CANDIDATES if c in df.columns), None)
    if date_col is None:
        logger.error(
            "COT data for {}: no recognized date column. Actual columns: {}",
            symbol, list(df.columns),
        )
        return pd.DataFrame()

    available = _resolve_columns(df, COT_COLUMN_ALIASES)
    if "comm_long" not in available.values() or "comm_short" not in available.values():
        logger.error(
            "COT data for {}: no recognized commercial position columns. Actual columns: {}",
            symbol, list(df.columns),
        )
        return pd.DataFrame()

    df = df[[date_col] + list(available.keys())].rename(columns={**available, date_col: "date"})

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").set_index("date")
    df["comm_net"] = df["comm_long"] - df["comm_short"]

    lookback = 156
    df["cot_index"] = (
        df["comm_net"]
        .rolling(lookback, min_periods=52)
        .apply(lambda x: (x[-1] > x[:-1]).mean() * 100, raw=True)
    )

    _cot_cache[cache_key] = df
    return df


async def get_cot_index(symbol):
    df = await fetch_cot_data(symbol)
    if df.empty or "cot_index" not in df.columns:
        return None
    val = df["cot_index"].dropna()
    if val.empty:
        return None
    return float(val.iloc[-1])


class MarketRegime:
    def __init__(self, vix, dxy_bullish, us10y_above_ma, real_yield_rising):
        self.vix = vix
        self.dxy_bullish = dxy_bullish
        self.us10y_above_ma = us10y_above_ma
        self.real_yield_rising = real_yield_rising

    @property
    def vix_override(self):
        from src.core.config import VIX_HARD_OVERRIDE
        return self.vix > VIX_HARD_OVERRIDE

    @property
    def dxy_regime(self):
        return "bullish" if self.dxy_bullish else "bearish"

    @property
    def us10y_regime(self):
        return "above_ma" if self.us10y_above_ma else "below_ma"

    @property
    def real_yield_regime(self):
        return "rising" if self.real_yield_rising else "falling"


async def fetch_market_regime():
    vix_task = fetch_vix()
    dxy_task = fetch_dxy()
    us10y_task = fetch_us10y()
    ry_task = fetch_real_yield()

    vix, dxy_df, us10y_df, real_yield_chg = await asyncio.gather(vix_task, dxy_task, us10y_task, ry_task)

    dxy_bullish = False
    if not dxy_df.empty:
        dxy_e = enrich_ohlcv(dxy_df)
        if "ma_200" in dxy_e.columns and not dxy_e["ma_200"].isna().all():
            last = dxy_e.iloc[-1]
            dxy_bullish = bool(last["close"] > last["ma_200"])

    us10y_above_ma = False
    if not us10y_df.empty:
        us10y_e = enrich_ohlcv(us10y_df)
        if "ma_200" in us10y_e.columns and not us10y_e["ma_200"].isna().all():
            last = us10y_e.iloc[-1]
            us10y_above_ma = bool(last["close"] > last["ma_200"])

    real_yield_rising = real_yield_chg > 0

    return MarketRegime(
        vix=float(vix),
        dxy_bullish=dxy_bullish,
        us10y_above_ma=us10y_above_ma,
        real_yield_rising=real_yield_rising,
    )
