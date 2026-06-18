"""
Platform Configuration
======================
Central configuration loaded from environment variables via pydantic-settings.
All downstream modules import from here â€” never read env vars directly.
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Market universe
# ---------------------------------------------------------------------------

class AssetClass(str, Enum):
    EQUITY = "equity"
    COMMODITY = "commodity"
    AGRICULTURE = "agriculture"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


EQUITY_MARKETS: dict[str, str] = {
    "NQ": "Nasdaq 100",
    "ES": "S&P 500",
    "YM": "Dow Jones",
    "RTY": "Russell 2000",
}

COMMODITY_MARKETS: dict[str, str] = {
    "GC": "Gold",
    "SI": "Silver",
    "HG": "Copper",
    "CL": "Crude Oil",
}

AGRICULTURE_MARKETS: dict[str, str] = {
    "ZC": "Corn",
    "ZW": "Wheat",
    "ZS": "Soybeans",
    "KC": "Coffee",
    "SB": "Sugar",
}

ALL_MARKETS: dict[str, str] = {
    **EQUITY_MARKETS,
    **COMMODITY_MARKETS,
    **AGRICULTURE_MARKETS,
}

# Markets subject to Real Yield filter
REAL_YIELD_MARKETS: frozenset[str] = frozenset({"GC", "SI"})

# Yahoo Finance ticker mapping
YAHOO_TICKERS: dict[str, str] = {
    "NQ": "NQ=F",
    "ES": "ES=F",
    "YM": "YM=F",
    "RTY": "RTY=F",
    "GC": "GC=F",
    "SI": "SI=F",
    "HG": "HG=F",
    "CL": "CL=F",
    "ZC": "ZC=F",
    "ZW": "ZW=F",
    "ZS": "ZS=F",
    "KC": "KC=F",
    "SB": "SB=F",
    # Regime instruments
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
    "TIP": "TIP",   # for real yields proxy
    "TIPS10Y": "DFII10",  # FRED series
}

# COT (CFTC) report codes â€” Commitments of Traders
COT_CODES: dict[str, str] = {
    "NQ": "209742",
    "ES": "13874A",
    "YM": "124603",
    "RTY": "239742",
    "GC": "088691",
    "SI": "084691",
    "HG": "085692",
    "CL": "067651",
    "ZC": "002602",
    "ZW": "001602",
    "ZS": "005602",
    "KC": "083731",
    "SB": "080732",
}

# Seasonality month biases (positive = bullish, negative = bearish)
# Derived from 20-year average monthly returns
SEASONALITY: dict[str, dict[int, float]] = {
    "NQ":  {1:0.8, 2:0.3, 3:-0.2, 4:1.2, 5:0.5, 6:-0.3, 7:0.9, 8:-0.4, 9:-1.1, 10:0.4, 11:1.3, 12:1.1},
    "ES":  {1:0.7, 2:0.2, 3:-0.1, 4:1.1, 5:0.4, 6:-0.2, 7:0.8, 8:-0.3, 9:-1.0, 10:0.5, 11:1.1, 12:1.0},
    "YM":  {1:0.6, 2:0.2, 3:-0.1, 4:1.0, 5:0.3, 6:-0.2, 7:0.7, 8:-0.3, 9:-0.9, 10:0.4, 11:1.0, 12:0.9},
    "RTY": {1:1.1, 2:0.4, 3:-0.3, 4:1.3, 5:0.2, 6:-0.4, 7:0.9, 8:-0.5, 9:-1.2, 10:0.6, 11:1.5, 12:1.2},
    "GC":  {1:0.9, 2:-0.3, 3:0.2, 4:-0.1, 5:0.3, 6:0.1, 7:-0.4, 8:0.8, 9:0.9, 10:-0.2, 11:-0.5, 12:0.3},
    "SI":  {1:0.7, 2:-0.4, 3:0.3, 4:-0.2, 5:0.2, 6:0.4, 7:-0.5, 8:0.9, 9:0.8, 10:-0.3, 11:-0.6, 12:0.2},
    "HG":  {1:0.3, 2:0.5, 3:0.8, 4:0.4, 5:-0.2, 6:-0.5, 7:-0.3, 8:0.1, 9:0.2, 10:0.3, 11:-0.1, 12:-0.4},
    "CL":  {1:-0.3, 2:0.2, 3:0.8, 4:0.9, 5:0.5, 6:-0.4, 7:-0.2, 8:-0.1, 9:-0.3, 10:-0.5, 11:-0.2, 12:-0.4},
    "ZC":  {1:-0.2, 2:0.1, 3:0.3, 4:0.5, 5:0.8, 6:0.6, 7:-0.8, 8:-0.9, 9:-0.5, 10:-0.3, 11:0.2, 12:0.3},
    "ZW":  {1:0.2, 2:0.4, 3:0.6, 4:0.3, 5:-0.2, 6:-0.8, 7:-0.6, 8:-0.3, 9:0.1, 10:0.3, 11:0.4, 12:0.3},
    "ZS":  {1:0.1, 2:0.2, 3:0.4, 4:0.6, 5:0.8, 6:0.5, 7:-0.3, 8:-0.7, 9:-0.5, 10:-0.2, 11:0.1, 12:0.2},
    "KC":  {1:-0.1, 2:0.2, 3:0.5, 4:0.3, 5:-0.4, 6:-0.6, 7:-0.3, 8:0.2, 9:0.4, 10:0.5, 11:0.3, 12:0.1},
    "SB":  {1:0.3, 2:0.4, 3:0.5, 4:0.2, 5:-0.3, 6:-0.5, 7:-0.4, 8:-0.2, 9:0.1, 10:0.3, 11:0.2, 12:0.0},
}


# ---------------------------------------------------------------------------
# Scoring weights (fixed â€” do not modify)
# ---------------------------------------------------------------------------

SCORE_WEIGHTS: dict[str, int] = {
    "commercial_cot":  35,
    "seasonality":     25,
    "macro_regime":    20,
    "trend_alignment": 10,
    "momentum":        10,
}

SCORE_THRESHOLDS: dict[str, int] = {
    AssetClass.EQUITY:      52,
    AssetClass.COMMODITY:   52,
    AssetClass.AGRICULTURE: 48,
}


# ---------------------------------------------------------------------------
# Regime thresholds
# ---------------------------------------------------------------------------

VIX_HARD_OVERRIDE: float = 35.0
US10Y_MA_PERIOD: int = 200
DXY_MA_PERIOD: int = 200
REAL_YIELD_FALLING_THRESHOLD: float = 0.0   # negative 20-day change = falling


# ---------------------------------------------------------------------------
# Risk defaults
# ---------------------------------------------------------------------------

ATR_PERIOD: int = 14
ATR_STOP_MULTIPLIER: float = 2.0
TP1_RISK_REWARD: float = 1.5
TP2_RISK_REWARD: float = 3.0
EXPECTED_HOLD_DAYS_MIN: int = 5
EXPECTED_HOLD_DAYS_MAX: int = 20


# ---------------------------------------------------------------------------
# Pydantic settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR}/platform.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    use_redis: bool = False

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_admin_ids: str = ""

    # API keys
    fred_api_key: str = ""
    quandl_api_key: str = ""
    alpha_vantage_api_key: str = ""

    # Platform
    log_level: str = "INFO"
    environment: str = "production"
    cache_ttl_seconds: int = 3600
    max_retries: int = 3
    request_timeout: int = 30

    # Scheduling
    daily_scan_hour: int = 6
    daily_scan_minute: int = 30
    weekly_cot_day: int = 5
    weekly_cot_hour: int = 16

    # Risk
    max_portfolio_risk_pct: float = 0.02
    min_cash_reserve_pct: float = 0.15
    high_risk_cash_reserve_pct: float = 0.30
    max_positions: int = 12
    max_sector_exposure_pct: float = 0.30

    # Streamlit
    streamlit_port: int = 8501
    streamlit_host: str = "0.0.0.0"

    @field_validator("telegram_admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: str) -> str:
        return v or ""

    @property
    def admin_ids_list(self) -> list[int]:
        if not self.telegram_admin_ids:
            return []
        return [int(x.strip()) for x in self.telegram_admin_ids.split(",") if x.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
