# 🧠 OracleAI — ML Trading Decision System

> Short-term AI-powered trading signals for **XAU/USD**, **GBP/JPY**, and **NASDAQ 100**  
> Horizon: 30 min – 3 h · Model: XGBoost + Calibrated Probabilities · Stack: FastAPI + React

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)               │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  Dashboard   │  │  Backtest    │  │  Model Manager  │  │
│  │  AssetCards  │  │  Equity Crv  │  │  Retrain UI     │  │
│  │  TopTrade    │  │  Stats Grid  │  │  Metrics View   │  │
│  └──────────────┘  └──────────────┘  └─────────────────┘  │
│           │                 │                  │            │
│           └─────────────────┴──────────────────┘            │
│                           fetch()                           │
└───────────────────────────│─────────────────────────────────┘
                            │ HTTP REST
┌───────────────────────────▼─────────────────────────────────┐
│                    BACKEND (FastAPI / Python)                │
│                                                             │
│  /api/predict/all/signals ──► TradingModel.predict()        │
│  /api/backtest/:asset     ──► run_backtest()                │
│  /api/retrain             ──► train_all_models()            │
│  /api/model-status        ──► get_model()                   │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ DataService │  │FeatureEngine │  │   ML Service       │ │
│  │ yfinance /  │  │ RSI,MACD,BB  │  │ XGBoost + Platt   │ │
│  │ Simulator   │  │ ATR,OBV,ADX  │  │ TimeSeriesSplit   │ │
│  └─────────────┘  └──────────────┘  └────────────────────┘ │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ NewsService │  │TradingLogic  │  │ BacktestService    │ │
│  │ RSS/NewsAPI │  │ EV Formula   │  │ Simulation + Stats │ │
│  │ Sentiment   │  │ BUY/SELL/NO  │  │ Equity Curve       │ │
│  └─────────────┘  └──────────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │    Data Sources            │
              │  yfinance (live)           │
              │  GBM Simulator (fallback)  │
              │  RSS Feeds (news)          │
              │  NewsAPI.org (optional)    │
              └───────────────────────────┘
```

---

## Folder Structure

```
trading-ai/
├── backend/
│   ├── main.py                    # FastAPI app + startup
│   ├── requirements.txt
│   ├── .env.example
│   ├── api/
│   │   └── routes.py              # All API endpoints
│   ├── services/
│   │   ├── data_service.py        # yfinance + simulator fallback
│   │   ├── data_simulator.py      # GBM market simulator
│   │   ├── feature_engineering.py # RSI, MACD, BB, ATR, OBV, ADX...
│   │   ├── ml_service.py          # XGBoost + calibration + persistence
│   │   ├── trading_logic.py       # EV formula + BUY/SELL/NO TRADE
│   │   ├── backtest_service.py    # Historical simulation + stats
│   │   ├── news_service.py        # RSS + NewsAPI sentiment
│   │   └── scheduler.py           # Background auto-refresh
│   └── models/
│       └── saved/                 # Persisted .pkl model files
│
└── frontend-app/
    ├── src/
    │   ├── App.jsx                # Root app + tab navigation
    │   ├── index.css              # Global dark theme variables
    │   ├── components/
    │   │   ├── Header.jsx         # Top bar + countdown + alerts
    │   │   ├── AssetCard.jsx      # Per-asset signal card
    │   │   ├── TopTradeBanner.jsx # Best signal spotlight
    │   │   ├── BacktestPanel.jsx  # Historical backtesting UI
    │   │   ├── ModelPanel.jsx     # Model status + retrain
    │   │   ├── Settings.jsx       # Configurable drawer
    │   │   └── Skeleton.jsx       # Loading states
    │   ├── hooks/
    │   │   └── useSignals.js      # Auto-refresh hooks
    │   └── utils/
    │       ├── api.js             # API client
    │       └── format.js          # Formatters + color helpers
    ├── .env.example
    └── package.json
```

---

## Quick Start

### 1. Clone / copy the project

```bash
git clone <repo>   # or unzip the archive
cd trading-ai
```

### 2. Backend setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env if needed (add NewsAPI key, etc.)

# Start backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend auto-trains models for all 3 assets on first startup (~30–60 sec).

### 3. Frontend setup

```bash
cd frontend-app

# Install dependencies
npm install

# Configure
cp .env.example .env
# VITE_API_URL=http://localhost:8000/api  (default, no changes needed)

# Development server
npm run dev
# → http://localhost:5173

# Production build
npm run build
npm run preview
```

### 4. (Optional) Pre-train models manually

```bash
# From backend directory, with venv active:
curl -X POST http://localhost:8000/api/retrain \
  -H "Content-Type: application/json" \
  -d '{"asset": null}'

# Check status
curl http://localhost:8000/api/model-status
```

---

## API Reference

### `GET /api/predict/all/signals`

Returns signals for all 3 assets simultaneously.

**Query params:**
| Param | Default | Description |
|-------|---------|-------------|
| `trade_size_eur` | 100 | Trade size in EUR |
| `min_probability_threshold` | 60 | Minimum % confidence to signal |
| `horizon_bars` | 6 | Prediction horizon (6 × 5min = 30min) |

**Response example:**
```json
{
  "signals": {
    "XAU/USD": {
      "asset": "XAU/USD",
      "action": "BUY",
      "up_probability": 67.3,
      "down_probability": 32.7,
      "expected_return_pct": 0.041,
      "expected_value_eur": 0.23,
      "potential_profit_eur": 1.84,
      "potential_loss_eur": -3.77,
      "fee_eur": 2.0,
      "win_probability": 67.3,
      "is_top_trade": false,
      "confidence_tier": "MEDIUM",
      "time_horizon": "30min",
      "current_price": 2318.45,
      "high_impact_news": false,
      "news_warning": null,
      "news_sentiment": 0.12,
      "raw_prediction": {
        "last_rsi": 58.4,
        "last_macd_hist": 0.00021,
        "last_bb_pct": 0.63,
        "atr_pct": 0.042
      }
    }
  },
  "top_trade": { ... },
  "global_news_alert": false
}
```

### `POST /api/backtest/{asset}`

```json
{
  "trade_size_eur": 100,
  "min_probability_threshold": 55,
  "fee_eur": 2.0,
  "horizon_bars": 6,
  "lookback_days": 30
}
```

### `POST /api/retrain`

```json
{ "asset": "XAU/USD" }   // or null to retrain all
```

### `GET /api/model-status`

Returns training metrics for all models:
- `test_auc`: Area Under ROC Curve (0.5 = random, 1.0 = perfect)
- `cv_auc_scores`: Per-fold time-series cross-validation scores
- `test_accuracy`: % correct direction predictions
- `class_balance`: % of UP labels in training data

---

## ML Model Details

### Feature Engineering (32 features)

| Category | Features |
|----------|----------|
| RSI | rsi, rsi_norm |
| MACD | macd, macd_signal, macd_hist, macd_hist_slope |
| Moving Averages | price_vs_sma20, price_vs_sma50, ema9_vs_ema21, sma20_slope |
| Bollinger Bands | bb_pct, bb_width |
| Volatility | atr_pct, volatility_5, volatility_20 |
| Stochastic | stoch_k_norm, stoch_d |
| ADX | adx, di_diff |
| Volume | volume_ratio, volume_slope, obv_slope |
| Momentum | return_1, return_3, return_5, return_10, return_20 |
| Candle | body_ratio, body_direction, upper_wick, lower_wick |
| Context | price_position_20 |

### Anti-Overfitting Measures

- `max_depth=4` — shallow trees
- `min_child_weight=10` — require substantial data per leaf
- `subsample=0.8`, `colsample_bytree=0.7` — stochastic training
- `gamma=1.0`, `reg_alpha=0.1`, `reg_lambda=1.0` — L1+L2 regularization
- **TimeSeriesSplit(n_splits=5)** — no look-ahead bias in CV
- **CalibratedClassifierCV** — Platt scaling for reliable probabilities
- **Chronological 80/20 split** — never shuffle financial time series

### Expected Value Formula

```
net_profit = trade_size × |expected_return| - fee
net_loss   = trade_size × |expected_return| + fee

EV = P(win) × net_profit − P(lose) × net_loss

Signal: BUY/SELL if P(win) ≥ threshold AND EV ≥ 0
        NO TRADE otherwise
```

---

## Data Sources

| Source | Type | Limit | Notes |
|--------|------|-------|-------|
| **yfinance** | Primary | 5min: 60 days | Free, no key |
| **GBM Simulator** | Fallback | Unlimited | Realistic GARCH-like prices |
| **RSS Feeds** | News | ~30 articles | MarketWatch, Yahoo Finance |
| **NewsAPI.org** | News | 100 req/day free | Requires free API key |

---

## Extending the System

### Add a new asset

1. In `data_service.py`: add to `ASSET_TICKERS` and `get_supported_assets()`
2. In `data_simulator.py`: add to `ASSET_PARAMS` with realistic volatility
3. In `frontend/utils/format.js`: add to `ASSET_META`
4. Retrain: `POST /api/retrain`

### Add a new feature

1. In `feature_engineering.py`: compute and add to `get_feature_columns()`
2. Retrain models (new feature count)

### Connect a live data broker (Interactive Brokers, OANDA)

Replace `fetch_ohlcv()` in `data_service.py`:
```python
from ib_insync import IB, Forex, util

def fetch_ohlcv_ib(asset, interval, lookback_days):
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)
    contract = Forex(asset.replace('/', ''))
    bars = ib.reqHistoricalData(contract, ...)
    return util.df(bars)
```

### Add more ML models

In `ml_service.py`, add after XGBoost:
```python
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier, VotingClassifier

# Ensemble: XGBoost + LightGBM
ensemble = VotingClassifier([('xgb', xgb), ('lgbm', lgbm)], voting='soft')
```

### Deploy to production

**Backend:**
```bash
# Docker
docker build -t oracle-ai-backend .
docker run -p 8000:8000 -e USE_SIMULATOR=false oracle-ai-backend

# Or systemd service
uvicorn main:app --workers 4 --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
npm run build
# Serve dist/ with nginx, Vercel, or Netlify
```

---

## Disclaimer

This software is provided for **educational and research purposes only**.  
It does **not** constitute financial advice.  
Past signal performance does not guarantee future results.  
Always test on a **demo account** before using real capital.  
Trading involves substantial risk of loss.
