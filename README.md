# COT Intelligence — Institutional Swing Trading Platform

Production-ready swing trading platform built on validated COT research.
Covers 13 futures markets across equities, commodities, and agriculture.

---

## Architecture Overview

```
swing-platform/
├── src/
│   ├── core/
│   │   ├── config.py          # All constants, market universe, score weights
│   │   ├── database.py        # SQLAlchemy async ORM (SQLite / PostgreSQL)
│   │   └── logging_config.py  # Loguru structured logging
│   ├── data/
│   │   └── market_data.py     # yfinance, FRED, CFTC COT fetchers
│   ├── signals/
│   │   ├── scorer.py          # 5-component scoring engine (exact spec)
│   │   └── scanner.py         # Orchestrates full/partial universe scans
│   ├── risk/
│   │   └── risk_engine.py     # Entry, Stop, TP1, TP2, ATR, position sizing
│   ├── alerts/
│   │   └── telegram_bot.py    # Bot + 11 slash commands + push alerts
│   ├── automation/
│   │   └── scheduler.py       # APScheduler daily + weekly COT jobs
│   ├── dashboard/
│   │   ├── helpers.py         # Plotly charts, Streamlit theme, async bridge
│   │   └── pages/             # 10 dashboard pages
│   └── cli.py                 # CLI entry point
├── tests/
│   └── test_scoring.py        # Full test suite (40+ tests)
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx.conf
├── scripts/
│   ├── vps_setup.sh           # One-command VPS provisioning
│   └── manage.sh              # Day-to-day operations CLI
├── .github/workflows/ci.yml   # CI/CD pipeline
├── dashboard.py               # Streamlit entry point
└── .env.example               # Environment template
```

---

## Signal Model (Fixed — Do Not Modify)

### Score Components (max 100)

| Component       | Weight | Signal Source         |
|----------------|--------|-----------------------|
| Commercial COT  | 35     | CFTC Disaggregated    |
| Seasonality     | 25     | 20yr monthly avg      |
| Macro Regime    | 20     | VIX / DXY / US10Y / Real Yield |
| Trend Alignment | 10     | Price vs MA20/50/200  |
| Momentum        | 10     | RSI + 20d ROC         |

### Thresholds

| Asset Class  | Minimum Score |
|-------------|---------------|
| Equities    | 52            |
| Commodities | 52            |
| Agriculture | 48            |

### Hard Rules

- **VIX > 35**: No new longs or shorts (hard override, all markets)
- **US10Y < MA200**: Allow equity longs
- **US10Y > MA200**: Allow equity shorts
- **Real Yield falling**: Allow Gold/Silver longs (does NOT apply to Copper/Crude)
- **DXY bearish**: Commodity tailwind
- **Cash reserve**: 15% minimum; 30% when Aggregate Macro Score < 48

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- Git

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USER/swing-platform.git
cd swing-platform
cp .env.example .env
# Edit .env — add your FRED_API_KEY and TELEGRAM_BOT_TOKEN
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

### 3. Initialise database

```bash
python -m src.cli init-db
```

### 4. Run a manual scan

```bash
python -m src.cli scan
```

### 5. Launch dashboard

```bash
# Copy Streamlit config
mkdir -p .streamlit
cp config/streamlit_config.toml .streamlit/config.toml

streamlit run dashboard.py
# Open: http://localhost:8501
```

### 6. Run tests

```bash
pytest tests/ -v
```

---

## Docker Deployment (Recommended)

### Prerequisites
- Docker 24+
- Docker Compose v2

### 1. Configure environment

```bash
cp .env.example .env
nano .env   # Fill in all required values
```

Required values in `.env`:

```
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
FRED_API_KEY=your_fred_key
DATABASE_URL=postgresql+asyncpg://swing:password@postgres:5432/swing_platform
REDIS_URL=redis://redis:6379/0
```

### 2. Build and start

```bash
# Build images
docker-compose -f docker/docker-compose.yml build

# Start everything
docker-compose -f docker/docker-compose.yml up -d

# Check status
docker-compose -f docker/docker-compose.yml ps

# View logs
docker-compose -f docker/docker-compose.yml logs -f
```

### 3. Access

- **Dashboard**: http://localhost (port 80 via nginx) or http://localhost:8501 direct
- **Logs**: `./scripts/manage.sh logs`

### 4. Using the management script

```bash
chmod +x scripts/manage.sh

./scripts/manage.sh start           # Start all services
./scripts/manage.sh scan            # Trigger manual scan
./scripts/manage.sh scan-equities   # Equities only
./scripts/manage.sh logs scheduler  # Scheduler logs
./scripts/manage.sh backup-db       # Backup database
./scripts/manage.sh update          # Pull & redeploy
```

---

## VPS Deployment (Production)

### Recommended VPS specs
- Ubuntu 22.04 or 24.04 LTS
- 2 vCPU, 4GB RAM minimum (DigitalOcean Droplet / Hetzner CX22 / Vultr)
- 40GB SSD

### One-command setup

```bash
# SSH into your VPS as root
ssh root@YOUR_VPS_IP

# Download and run setup script
curl -fsSL https://raw.githubusercontent.com/YOUR_USER/swing-platform/main/scripts/vps_setup.sh | \
  bash -s https://github.com/YOUR_USER/swing-platform.git
```

This script:
1. Installs Python 3.12, Docker, Nginx, PostgreSQL, Redis
2. Clones the repo to `/opt/swing-platform`
3. Configures UFW firewall (blocks direct DB access)
4. Installs fail2ban
5. Creates a systemd service for auto-start on reboot
6. Sets up log rotation

### After setup

```bash
cd /opt/swing-platform
nano .env   # Add your API keys

# Start platform
./scripts/manage.sh start

# Verify
./scripts/manage.sh status
```

### SSL with Let's Encrypt

```bash
# Point your domain to the VPS IP first, then:
certbot --nginx -d yourdomain.com
# Uncomment the HTTPS server block in docker/nginx.conf
./scripts/manage.sh restart
```

### GitHub Actions auto-deploy

Add these secrets to your GitHub repository (Settings → Secrets):

| Secret         | Value                          |
|---------------|--------------------------------|
| `VPS_HOST`    | Your VPS IP address            |
| `VPS_USER`    | `swing` (or your deploy user)  |
| `VPS_SSH_KEY` | Private SSH key for VPS access |

Every push to `main` will:
1. Run the test suite
2. Run lint checks
3. Build and push Docker image to GHCR
4. SSH into VPS and redeploy

---

## Telegram Bot Setup

### 1. Create a bot

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`
3. Follow the prompts, save the token

### 2. Get your Chat ID

1. Add the bot to your channel or send it a message
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat": {"id": XXXXXXX}` in the response

### 3. Configure .env

```
TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh
TELEGRAM_CHAT_ID=-100123456789
TELEGRAM_ADMIN_IDS=123456789
```

### 4. Start the bot

```bash
# Via Docker (recommended):
docker-compose -f docker/docker-compose.yml up -d telegram_bot

# Locally:
python -m src.cli bot
```

### Available Commands

| Command         | Description                                    |
|----------------|------------------------------------------------|
| `/scan`        | Full scan of all 13 markets                    |
| `/top`         | Top 5 signals with full alert format           |
| `/portfolio`   | Cash reserve rule + active signal count        |
| `/equities`    | Equity index signals only (NQ/ES/YM/RTY)       |
| `/commodities` | Commodity signals (Gold/Silver/Copper/Crude)   |
| `/agriculture` | Agriculture signals (Corn/Wheat/Soy/Coffee/Sugar) |
| `/gold`        | Gold-specific analysis                         |
| `/vix`         | VIX level + regime classification              |
| `/dxy`         | DXY level + MA200 regime                       |
| `/us10y`       | 10Y yield + MA200 regime + real yield          |
| `/cot`         | COT index for all 13 markets                   |

### Alert Format

```
🔥 ELITE SWING TRADE

🏅 Asset: Gold (GC)
🟢 Direction: LONG

📊 Score: 91/100
  • Commercial COT: 32/35 (Index: 84)
  • Seasonality: Bullish (21/25)
  • Macro Regime: 18/20
  • Trend Alignment: 10/10
  • Momentum: 10/10

⚡ Regime Filters:
  • DXY: Bearish Regime
  • Real Yield: Falling ✅

💰 Trade Setup:
  • Entry:  1985.4000
  • Stop:   1942.1000
  • TP1:    2050.3500
  • TP2:    2115.3000

📐 Risk/Reward: 3.0x
📉 ATR Risk: 2.18%
🕐 Expected Hold: 12 Days
```

---

## Data Sources

| Data Type          | Source                        | API Key Required |
|-------------------|-------------------------------|-----------------|
| Price / OHLCV     | Yahoo Finance (yfinance)      | No              |
| COT Reports       | CFTC Direct Download          | No              |
| Real Yield (TIPS) | FRED (DFII10)                 | Yes (free)      |
| VIX               | Yahoo Finance (^VIX)          | No              |
| DXY               | Yahoo Finance (DX-Y.NYB)      | No              |
| US10Y             | Yahoo Finance (^TNX)          | No              |

### Getting a FRED API Key (Free)

1. Go to https://fred.stlouisfed.org/docs/api/api_key.html
2. Create an account
3. Request an API key (instant approval)
4. Add to `.env`: `FRED_API_KEY=your_key`

Without a FRED key, real yield data falls back to the TIP ETF proxy (less precise but functional).

---

## Automated Schedule

| Job               | Schedule             | Description                           |
|------------------|----------------------|---------------------------------------|
| Daily Scan        | 06:30 ET every day   | Full 13-market scan + Telegram alerts |
| Weekly COT Scan   | 16:00 ET every Friday| Clears COT cache, fetches fresh CFTC data |

Modify timing in `.env`:
```
DAILY_SCAN_HOUR=6
DAILY_SCAN_MINUTE=30
WEEKLY_COT_DAY=5      # 0=Monday, 5=Friday
WEEKLY_COT_HOUR=16
```

---

## Dashboard Pages

| Page                  | Description                                        |
|----------------------|----------------------------------------------------|
| 🏠 Overview           | Regime strip + top signals + score distribution    |
| 💼 Portfolio          | Cash rules + position sizing table + sector pie    |
| 📡 Signals            | Filterable signal list + price charts + detail view |
| 📊 COT Dashboard      | COT index scoreboard + positions + weekly changes  |
| 🗓 Seasonality        | Monthly bias heatmap for all 13 markets            |
| ⚡ VIX Dashboard      | Volatility regime + zone distribution              |
| 💵 DXY Dashboard      | Dollar regime vs MA200                             |
| 📉 US10Y Dashboard    | Yield regime + real yield                          |
| 📈 Performance Analytics | Historical signal stats from database           |
| 🗒 Trade History      | Full audit trail + CSV export                      |

---

## Environment Variables Reference

```bash
# Database (SQLite default; switch to PostgreSQL for production)
DATABASE_URL=sqlite+aiosqlite:///./data/platform.db

# Telegram
TELEGRAM_BOT_TOKEN=          # Required for alerts
TELEGRAM_CHAT_ID=            # Channel or group chat ID
TELEGRAM_ADMIN_IDS=          # Comma-separated user IDs

# Data APIs
FRED_API_KEY=                # Free from fred.stlouisfed.org
QUANDL_API_KEY=              # Optional backup

# Scheduling
DAILY_SCAN_HOUR=6
DAILY_SCAN_MINUTE=30
WEEKLY_COT_DAY=5
WEEKLY_COT_HOUR=16

# Risk
MAX_PORTFOLIO_RISK_PCT=0.02  # 2% risk per trade
MIN_CASH_RESERVE_PCT=0.15    # 15% minimum cash
HIGH_RISK_CASH_RESERVE_PCT=0.30  # 30% when macro weak
MAX_POSITIONS=12
```

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src --cov-report=html

# Single module
pytest tests/test_scoring.py -v

# Fast (skip slow integration)
pytest tests/ -v -m "not integration"
```

Key test coverage:
- Score weights sum to 100
- All component scores stay within max bounds
- VIX override fires at exactly >35
- Real yield filter blocks Gold/Silver longs (not Copper)
- Direction logic follows COT primary signal
- Risk parameters: stop below entry for longs, above for shorts
- Cash requirement: 30% when macro < 48

---

## Troubleshooting

**No COT data appearing**
- CFTC sometimes delays the Friday release. Wait until ~17:00 ET.
- Check connectivity: `curl -I https://www.cftc.gov`
- Clear cache: `./scripts/manage.sh scan` (forces fresh download)

**Telegram bot not responding**
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Check logs: `./scripts/manage.sh logs telegram_bot`
- Ensure the bot has been started in the chat (send `/start`)

**Dashboard won't load**
- Check all containers running: `./scripts/manage.sh status`
- View dashboard logs: `./scripts/manage.sh logs dashboard`
- Verify port 8501 is not blocked

**yfinance rate limiting**
- The platform caches price data for 1 hour by default
- If hitting limits, increase `CACHE_TTL_SECONDS=7200` in `.env`

**Database errors**
- Re-initialise: `./scripts/manage.sh init-db`
- Check disk space: `df -h`

---

## License

Private / Proprietary — All rights reserved.
