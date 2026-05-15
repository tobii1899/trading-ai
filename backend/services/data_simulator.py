"""
Market Data Simulator v2
Generates realistic OHLCV with LEARNABLE structure:
  - Regime switching (trend ↔ mean-reversion)
  - Momentum persistence (Hurst > 0.5 in trending regime)
  - Volatility clustering (GARCH-like)
  - Intraday seasonality
  - Mean-reversion around dynamic levels

This creates non-zero autocorrelation → ML can achieve AUC > 0.5.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
import hashlib

ASSET_PARAMS = {
    "XAU/USD":   {"base_price": 2320.0, "daily_vol": 0.008,  "volume_base": 85000,    "spread_pct": 0.00015},
    "GBP/JPY":   {"base_price": 197.50, "daily_vol": 0.006,  "volume_base": 120000,   "spread_pct": 0.0002},
    "NASDAQ100": {"base_price": 19800.0,"daily_vol": 0.012,  "volume_base": 45000000, "spread_pct": 0.0001},
}
MINUTES_PER_BAR = {"1m":1,"5m":5,"15m":15,"30m":30,"1h":60,"1d":1440}


def generate_ohlcv(asset: str, interval: str = "30m",
                   lookback_days: int = 365, seed: int | None = None) -> pd.DataFrame:
    params = ASSET_PARAMS.get(asset, ASSET_PARAMS["NASDAQ100"])
    bar_minutes = MINUTES_PER_BAR.get(interval, 30)

    if seed is None:
        date_str = datetime.utcnow().strftime("%Y%m%d%H")
        seed = int(hashlib.md5(f"{asset}{date_str}".encode()).hexdigest()[:8], 16) % (2**31)
    rng = np.random.default_rng(seed)

    # ── Timestamps ────────────────────────────────────────────────────────────
    end_dt = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
    end_dt = end_dt - timedelta(minutes=end_dt.minute % bar_minutes)
    timestamps = []
    dt = end_dt - timedelta(days=lookback_days)
    while dt <= end_dt:
        if asset == "NASDAQ100":
            if dt.weekday() >= 5:
                dt += timedelta(days=1); continue
            if not (13 <= dt.hour < 20):
                dt += timedelta(minutes=bar_minutes); continue
        timestamps.append(dt)
        dt += timedelta(minutes=bar_minutes)

    n = len(timestamps)
    if n < 200:
        n = 5000
        timestamps = [end_dt - timedelta(minutes=bar_minutes*(n-i)) for i in range(n)]

    bars_per_day = 1440 / bar_minutes
    bar_vol_base = params["daily_vol"] / np.sqrt(bars_per_day)

    # ── Regime-switching price path ────────────────────────────────────────────
    # Regime 0 = TRENDING (momentum), Regime 1 = MEAN-REVERTING
    prices = np.zeros(n + 1)
    prices[0] = params["base_price"]
    
    vol = bar_vol_base
    regime = 0          # start trending
    regime_counter = 0
    avg_regime_len = int(bars_per_day * 2)   # ~2 days per regime avg
    ma_window = 20
    
    log_returns = np.zeros(n)

    for i in range(n):
        # Regime transitions (Markov chain)
        regime_counter += 1
        switch_prob = 1 / avg_regime_len
        if rng.random() < switch_prob:
            regime = 1 - regime    # flip
            regime_counter = 0

        # Dynamic moving average (causal — only past prices)
        if i >= ma_window:
            ma = prices[max(0, i-ma_window):i].mean()
        else:
            ma = prices[0]

        deviation = (prices[i] - ma) / (ma + 1e-8)

        if regime == 0:
            # TRENDING: momentum — recent move predicts next move
            if i >= 3:
                recent_ret = (prices[i] - prices[i-3]) / prices[i-3]
            else:
                recent_ret = 0.0
            drift = 0.25 * recent_ret          # momentum carry
            drift += rng.normal(0, 0.0001)     # small noise
        else:
            # MEAN-REVERTING: price pulled back toward MA
            drift = -0.15 * deviation           # reversion force
            drift += rng.normal(0, 0.0001)

        # GARCH-like volatility
        if i > 0:
            vol = 0.92 * vol + 0.08 * (abs(log_returns[i-1]) * 0.7 + bar_vol_base * 0.3)
            vol = np.clip(vol, bar_vol_base * 0.3, bar_vol_base * 4.0)

        # Intraday seasonality: higher vol at open/close
        if bar_minutes < 60 and i % int(bars_per_day) in range(0, 6):
            intra_mult = 1.4
        elif bar_minutes < 60 and i % int(bars_per_day) in range(int(bars_per_day)-6, int(bars_per_day)):
            intra_mult = 1.3
        else:
            intra_mult = 1.0

        shock = rng.normal(drift, vol * intra_mult)
        log_returns[i] = shock
        prices[i+1] = prices[i] * (1 + shock)

    prices = prices[1:]  # drop initial seed

    # ── OHLC construction ─────────────────────────────────────────────────────
    opens = np.empty(n); opens[0] = params["base_price"]
    opens[1:] = prices[:-1]

    intrabar_range = np.abs(prices - opens) + prices * vol * rng.uniform(0.5, 1.5, n)
    spread = params["spread_pct"] * prices
    highs = np.maximum(prices, opens) + intrabar_range * rng.uniform(0.2, 0.8, n) + spread
    lows  = np.minimum(prices, opens) - intrabar_range * rng.uniform(0.2, 0.8, n) - spread

    # Volume: spikes on big moves
    abs_ret = np.abs(log_returns)
    vol_factor = 1.0 + 4.0 * (abs_ret / (abs_ret.mean() + 1e-8))
    vol_factor = np.nan_to_num(vol_factor, nan=1.0, posinf=5.0, neginf=0.5)
    volumes = (params["volume_base"] * vol_factor * rng.uniform(0.6, 1.4, n)).astype(int)

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": prices, "volume": volumes},
        index=pd.DatetimeIndex(timestamps, tz=timezone.utc)
    )
    df["high"] = df[["open","high","close"]].max(axis=1)
    df["low"]  = df[["open","low","close"]].min(axis=1)
    return df.sort_index()


def get_current_price_simulated(asset: str) -> float:
    df = generate_ohlcv(asset, "30m", lookback_days=365)
    return float(df["close"].iloc[-1])
