"""
Data Service - Fetches market data for all supported assets.
Primary: tvDatafeed (TradingView). Fallback: built-in realistic simulator.
"""

import logging
import os
import math
from datetime import timedelta

import numpy as np
import pandas as pd
from tvDatafeed import Interval, TvDatafeed

logger = logging.getLogger(__name__)
USE_SIMULATOR = os.getenv("USE_SIMULATOR", "auto")
tv = TvDatafeed()

TV_SYMBOLS = {
    "XAU/USD": ("XAUUSD", "OANDA"),
    "GBP/JPY": ("GBPJPY", "OANDA"),
    "NASDAQ100": ("US100", "CAPITALCOM"),
}


def _interval_minutes(interval: str) -> int:
    minutes_map = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "1d": 1440,
    }
    return minutes_map.get(interval, 30)


def _bars_from_lookback(interval: str, lookback_days: int) -> int:
    interval_min = max(1, _interval_minutes(interval))
    # Safety factor for weekends/market pauses + cleaning drops.
    est_bars = int(math.ceil((lookback_days * 1440 / interval_min) * 1.20))
    return min(max(est_bars, 500), 15000)


def _interval_delta(interval: str) -> timedelta:
    return timedelta(minutes=_interval_minutes(interval))


def _augment_with_simulated_history(
    asset: str,
    interval: str,
    lookback_days: int,
    live_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Ensure sufficient bar depth by prepending simulated historical chunks when live source is short.
    Keeps the latest live data intact and fills older history before it.
    """
    from services.data_simulator import generate_ohlcv

    required_bars = _bars_from_lookback(interval, lookback_days)
    if live_df is None:
        parts: list[pd.DataFrame] = []
        total = 0
    else:
        parts = [live_df]
        total = len(live_df)

    if total >= required_bars:
        return live_df if live_df is not None else pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    delta = _interval_delta(interval)
    if parts:
        earliest = parts[0].index.min()
    else:
        now_utc = pd.Timestamp.utcnow()
        earliest = now_utc.tz_localize("UTC") if now_utc.tz is None else now_utc.tz_convert("UTC")
    chunk_days = min(max(365, lookback_days), 3650)
    chunk_idx = 0

    while total < required_bars:
        chunk = generate_ohlcv(
            asset=asset,
            interval=interval,
            lookback_days=chunk_days,
            seed=41_000 + (chunk_idx * 997),
        )
        if not isinstance(chunk.index, pd.DatetimeIndex):
            chunk.index = pd.to_datetime(chunk.index, utc=True)
        else:
            chunk.index = chunk.index.tz_convert("UTC") if chunk.index.tz else chunk.index.tz_localize("UTC")

        chunk_span = chunk.index.max() - chunk.index.min()
        new_end = earliest - delta
        shift = new_end - chunk.index.max()
        chunk.index = chunk.index + shift

        parts.insert(0, chunk)
        total += len(chunk)
        earliest = chunk.index.min()
        chunk_idx += 1

        if chunk_idx > 24:
            break

    out = pd.concat(parts).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    if len(out) > required_bars:
        out = out.iloc[-required_bars:]
    return out[["open", "high", "low", "close", "volume"]]


def _try_tv_datafeed(asset: str, interval: str, lookback_days: int = 365) -> pd.DataFrame | None:
    interval_30m = getattr(Interval, "in_30_minute", None)
    interval_map = {
        "1m": Interval.in_1_minute,
        "5m": Interval.in_5_minute,
        "15m": Interval.in_15_minute,
        "30m": interval_30m,
        "1h": Interval.in_1_hour,
        "1d": Interval.in_daily,
    }
    if interval not in interval_map or interval_map[interval] is None:
        logger.warning(f"Unsupported interval '{interval}' for tvDatafeed")
        return None

    if asset not in TV_SYMBOLS:
        return None

    if USE_SIMULATOR == "true":
        return None

    try:
        symbol, exchange = TV_SYMBOLS[asset]
        df = tv.get_hist(
            symbol=symbol,
            exchange=exchange,
            interval=interval_map[interval],
            n_bars=_bars_from_lookback(interval, lookback_days),
        )
        if df is None or len(df) < 50:
            return None

        df = df.dropna().sort_index()
        df = df[~df.index.duplicated()]
        df.index = pd.to_datetime(df.index, utc=True)

        for col in ("open", "high", "low", "close", "volume"):
            if col not in df.columns:
                df[col] = 0.0 if col == "volume" else np.nan

        df = df.dropna(subset=["open", "high", "low", "close"])
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)

        return df[["open", "high", "low", "close", "volume"]]
    except Exception as exc:
        logger.warning(f"TradingView fetch failed for {asset}: {exc}")
        return None


def fetch_ohlcv(asset: str, interval: str = "30m", lookback_days: int = 365) -> pd.DataFrame:
    """Fetch OHLCV. Falls back to realistic simulator if live API unavailable."""
    if asset not in TV_SYMBOLS:
        raise ValueError(f"Unknown asset: {asset}")
    df_live = _try_tv_datafeed(asset, interval, lookback_days=lookback_days)
    required_bars = _bars_from_lookback(interval, lookback_days)

    if df_live is not None and len(df_live) > 50 and len(df_live) >= required_bars:
        return df_live

    if df_live is not None and len(df_live) > 50:
        logger.warning(
            "Live data depth short for %s %s: got %s bars, need ~%s. "
            "Prepending simulated history for training depth.",
            asset, interval, len(df_live), required_bars,
        )
    else:
        logger.warning(
            "Live data unavailable for %s %s. Using simulated history for full lookback depth (~%s bars).",
            asset, interval, required_bars,
        )

    return _augment_with_simulated_history(
        asset=asset,
        interval=interval,
        lookback_days=lookback_days,
        live_df=df_live,
    )


def fetch_historical_daily(asset: str, lookback_days: int = 365) -> pd.DataFrame:
    """Daily OHLCV for backtesting."""
    df = _try_tv_datafeed(asset, "1d", lookback_days=lookback_days)
    if df is not None and len(df) > 50:
        return df
    from services.data_simulator import generate_ohlcv

    return generate_ohlcv(asset, interval="1d", lookback_days=lookback_days)


def get_current_price(asset: str) -> float:
    try:
        df = _try_tv_datafeed(asset, "1m")
        if df is not None and not df.empty:
            p = float(df["close"].iloc[-1])
            if not np.isnan(p):
                return p
    except Exception:
        pass

    from services.data_simulator import get_current_price_simulated

    return get_current_price_simulated(asset)

def get_supported_assets() -> list[dict]:
    return [
        {"id":"XAU/USD","name":"Gold","ticker":"GC=F","type":"commodity",
         "description":"Gold / US Dollar","pip_size":0.01,"typical_spread_pct":0.02,"currency":"USD"},
        {"id":"GBP/JPY","name":"Cable-Yen","ticker":"GBPJPY=X","type":"forex",
         "description":"British Pound / Japanese Yen","pip_size":0.01,"typical_spread_pct":0.03,"currency":"JPY"},
        {"id":"NASDAQ100","name":"NASDAQ 100","ticker":"QQQ","type":"index",
         "description":"NASDAQ-100 Index (QQQ ETF)","pip_size":0.01,"typical_spread_pct":0.01,"currency":"USD"},
    ]
