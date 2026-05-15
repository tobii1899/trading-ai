"""
Feature engineering and target generation for trend-continuation trading.

Focus:
- 30m data with cleaner, trend-focused structure
- Strong, compact feature set (15 columns)
- Labels only when a trend setup exists (retracement or FVG)
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Base target thresholds (fractional return, not percent)
ASSET_THRESHOLDS = {
    "XAU/USD": 0.00030,
    "GBP/JPY": 0.00040,
    "NASDAQ100": 0.00055,
}
DEFAULT_THRESHOLD = 0.00050

ASSET_TARGET_MULTIPLIERS = {
    "XAU/USD": [1.00, 1.05, 1.10, 1.25],
    "GBP/JPY": [1.00, 1.05, 1.10, 1.25],
    "NASDAQ100": [1.00, 1.05, 1.10, 1.25],
}

ASSET_IMPULSE_MIN = {
    "XAU/USD": 0.75,
    "GBP/JPY": 0.80,
    "NASDAQ100": 0.85,
}


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False).mean()
    rs = gain / (loss + 1e-8)
    return 100 - (100 / (1 + rs))


def _macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    tr = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(span=window, adjust=False).mean()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14):
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr14 = _atr(high, low, close, window)
    plus_di = 100 * plus_dm.ewm(span=window, adjust=False).mean() / (atr14 + 1e-8)
    minus_di = 100 * minus_dm.ewm(span=window, adjust=False).mean() / (atr14 + 1e-8)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-8)
    adx = dx.ewm(span=window, adjust=False).mean()
    return adx, plus_di, minus_di


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute causal features for trend continuation.
    Requires: open, high, low, close, volume.
    """
    if len(df) < 80:
        raise ValueError(f"Need >=80 bars, got {len(df)}")

    df = df.copy()
    c, h, l, o, v = df["close"], df["high"], df["low"], df["open"], df["volume"]

    log_ret = np.log(c / c.shift(1))

    # Core trend/momentum features
    ma20 = c.rolling(20).mean()
    ma50 = c.rolling(50).mean()
    df["ma20_dev"] = (c - ma20) / (ma20 + 1e-8)
    df["ma50_dev"] = (c - ma50) / (ma50 + 1e-8)
    df["ma20_slope"] = ma20.pct_change(5)
    ema20 = c.ewm(span=20, adjust=False).mean()
    ema50 = c.ewm(span=50, adjust=False).mean()
    df["ema20_slope"] = ema20.pct_change(5)

    df["rsi14_norm"] = (_rsi(c, 14) - 50) / 50

    macd_line, signal_line, histogram = _macd(c)
    df["macd_hist"] = histogram / (c + 1e-8)

    df["vol_20"] = log_ret.rolling(20).std()

    df["mom_3"] = np.log(c / c.shift(3))
    df["mom_10"] = np.log(c / c.shift(10))

    atr14 = _atr(h, l, c, 14)
    df["atr14_pct"] = atr14 / (c + 1e-8)

    adx, plus_di, minus_di = _adx(h, l, c, 14)
    df["adx"] = adx / 100.0
    df["di_diff"] = (plus_di - minus_di) / (plus_di + minus_di + 1e-8)
    df["trend_regime"] = ((adx > 20) & (adx.diff() > 0)).astype(float)

    vol_50 = log_ret.rolling(50).std()
    df["vol_regime"] = df["vol_20"] / (vol_50 + 1e-8)

    # Setup context: trend direction + pullback + fair value gap
    trend_dir = np.sign(ema20 - ema50)
    trend_dir = trend_dir.replace(0, np.nan).ffill().fillna(0.0)
    df["trend_dir"] = trend_dir

    # Breakout structure (causal: compare against prior range only)
    prior_high_20 = h.shift(1).rolling(20).max()
    prior_low_20 = l.shift(1).rolling(20).min()
    breakout_long = c > prior_high_20
    breakout_short = c < prior_low_20
    breakout_long_recent = breakout_long.rolling(6, min_periods=1).max().astype(bool)
    breakout_short_recent = breakout_short.rolling(6, min_periods=1).max().astype(bool)
    trend_breakout = (
        ((trend_dir > 0) & breakout_long_recent) |
        ((trend_dir < 0) & breakout_short_recent)
    )
    df["trend_breakout"] = trend_breakout.astype(float)
    df["breakout_strength"] = np.where(
        trend_dir > 0,
        (c - prior_high_20) / (atr14 + 1e-8),
        (prior_low_20 - c) / (atr14 + 1e-8),
    )

    # Trend phase filter: ADX + EMA slope + breakout structure
    ema_slope_abs = df["ema20_slope"].abs()
    slope_floor = np.maximum(0.00006, df["atr14_pct"] * 0.12)
    trend_phase = (adx > 20) & (ema_slope_abs > slope_floor) & trend_breakout
    df["trend_phase"] = trend_phase.astype(float)

    df["retracement_depth"] = (c - ema20) / (atr14 + 1e-8)
    retrace_long = (trend_dir > 0) & (df["retracement_depth"] <= -0.35)
    retrace_short = (trend_dir < 0) & (df["retracement_depth"] >= 0.35)
    df["retracement_setup"] = (retrace_long | retrace_short).astype(float)

    # 3-candle FVG approximation
    fvg_up_gap = (l - h.shift(2)).clip(lower=0.0)
    fvg_down_gap = (l.shift(2) - h).clip(lower=0.0)
    fvg_up_norm = fvg_up_gap / (atr14 + 1e-8)
    fvg_down_norm = fvg_down_gap / (atr14 + 1e-8)

    fvg_up_recent = fvg_up_norm.rolling(3).max().fillna(0.0)
    fvg_down_recent = fvg_down_norm.rolling(3).max().fillna(0.0)

    bullish_fvg_setup = (trend_dir > 0) & (fvg_up_recent > 0.18)
    bearish_fvg_setup = (trend_dir < 0) & (fvg_down_recent > 0.18)
    df["fvg_setup"] = (bullish_fvg_setup | bearish_fvg_setup).astype(float)

    # Signed signal: + when bullish setup, - when bearish setup
    df["fvg_signal"] = (
        bullish_fvg_setup.astype(float) - bearish_fvg_setup.astype(float)
    )

    df = df.dropna()
    logger.info(f"Features computed: {df.shape[1]} cols, {len(df)} rows")
    return df


def get_feature_columns() -> list[str]:
    """Compact, strongest feature set (15)."""
    return [
        "ma20_dev",
        "ma50_dev",
        "ema20_slope",
        "macd_hist",
        "vol_20",
        "mom_10",
        "atr14_pct",
        "adx",
        "di_diff",
        "trend_regime",
        "trend_breakout",
        "vol_regime",
        "retracement_depth",
        "breakout_strength",
        "fvg_signal",
    ]


def create_target(
    df: pd.DataFrame,
    horizon_bars: int = 6,
    threshold_pct: float | None = None,
    asset: str | None = None,
) -> pd.DataFrame:
    """
    Build directional continuation targets after retracement/FVG setup.

    Label setup bars with strong impulsive outcomes after trend-continuation setups.

    Valid labeled row:
    1) Trend is active (ADX >= 20)
    2) A setup exists (retracement or FVG)
    3) Future return is available

    Target encoding remains directional:
    - 1: bullish outcome after setup (future_return >= +threshold)
    - 0: bearish outcome after setup (future_return <= -threshold)
    - NaN: near-zero/noise move around zero (inside threshold band)
    """
    df = df.copy()

    future_close = df["close"].shift(-horizon_bars)
    df["future_return"] = (future_close - df["close"]) / df["close"]

    base_thresh = threshold_pct
    if base_thresh is None:
        base_thresh = ASSET_THRESHOLDS.get(asset, DEFAULT_THRESHOLD) if asset else DEFAULT_THRESHOLD

    horizon_scale = np.sqrt(max(horizon_bars, 1) / 4.0)
    base_thresh = float(base_thresh * horizon_scale)

    atr_component = pd.Series(base_thresh, index=df.index, dtype=float)
    if "atr14_pct" in df.columns:
        atr_component = np.maximum(atr_component, df["atr14_pct"].astype(float) * 0.85 * horizon_scale)

    vol_component = pd.Series(base_thresh, index=df.index, dtype=float)
    if "vol_20" in df.columns:
        vol_component = np.maximum(
            vol_component,
            df["vol_20"].astype(float) * np.sqrt(max(horizon_bars, 1)) * 1.2,
        )

    base_dynamic_threshold = np.maximum(base_thresh * 1.30, np.maximum(atr_component, vol_component))

    # Trend and setup masks
    adx_raw = df["adx"].astype(float) * 100.0 if "adx" in df.columns else pd.Series(25.0, index=df.index)
    trend_active = adx_raw >= 20.0

    trend_dir = np.sign(df.get("trend_dir", pd.Series(0.0, index=df.index)).astype(float))
    setup_active_raw = (
        (df.get("retracement_setup", 0.0).astype(float) > 0.5)
        | (df.get("fvg_setup", 0.0).astype(float) > 0.5)
    )
    # Keep setup signal active for a short entry window to avoid overly sparse labels.
    setup_active = setup_active_raw.rolling(2, min_periods=1).max().astype(bool)
    trend_phase = df.get("trend_phase", pd.Series(0.0, index=df.index)).astype(float) > 0.5
    setup_mask = trend_active & trend_phase & (trend_dir != 0) & setup_active & df["future_return"].notna()

    setup_rows = max(1, int(setup_mask.sum()))
    multipliers = ASSET_TARGET_MULTIPLIERS.get(asset, [1.00, 1.10, 1.25])
    best = None
    min_labeled_rows = max(220, int(setup_rows * 0.18))
    impulse_min = float(ASSET_IMPULSE_MIN.get(asset, 0.80))

    for mult in multipliers:
        candidate_threshold = base_dynamic_threshold * mult
        abs_move = df["future_return"].abs()
        impulse_strength = abs_move / (
            (df["atr14_pct"].astype(float) * np.sqrt(max(horizon_bars, 1))) + 1e-8
        )
        valid_mask = setup_mask & (abs_move >= candidate_threshold) & (impulse_strength >= impulse_min)

        labeled_count = int(valid_mask.sum())
        if labeled_count < min_labeled_rows:
            continue

        candidate_target = (df.loc[valid_mask, "future_return"] > 0).astype(int)
        if candidate_target.empty:
            continue

        balance = float(candidate_target.mean())
        coverage = labeled_count / setup_rows

        # Prefer good directional balance while keeping enough samples.
        score = abs(balance - 0.50) + (0.20 * abs(coverage - 0.30))
        in_band = 0.35 <= balance <= 0.65
        priority = 0 if in_band else 1
        rank = (priority, round(score, 8), -labeled_count, mult)

        if best is None or rank < best["rank"]:
            best = {
                "rank": rank,
                "multiplier": float(mult),
                "balance": balance,
                "valid_mask": valid_mask,
                "threshold_series": candidate_threshold,
            }

    if best is None:
        fallback_threshold = base_dynamic_threshold * 1.00
        fallback_impulse_strength = df["future_return"].abs() / (
            (df["atr14_pct"].astype(float) * np.sqrt(max(horizon_bars, 1))) + 1e-8
        )
        fallback_valid = (
            setup_mask
            & (df["future_return"].abs() >= fallback_threshold)
            & (fallback_impulse_strength >= impulse_min)
        )
        fallback_target = (df.loc[fallback_valid, "future_return"] > 0).astype(int)
        fallback_balance = float(fallback_target.mean()) if len(fallback_target) else 0.5
        best = {
            "multiplier": 1.00,
            "balance": fallback_balance,
            "valid_mask": fallback_valid,
            "threshold_series": fallback_threshold,
        }

    df["target"] = np.nan
    df.loc[best["valid_mask"], "target"] = (
        df.loc[best["valid_mask"], "future_return"] > 0
    ).astype(int)
    df["label_valid"] = best["valid_mask"].astype(int)
    df["setup_active"] = setup_mask.astype(int)
    df["continuation_success"] = (
        (df["future_return"] * trend_dir) >= best["threshold_series"]
    ).astype(int)
    df["threshold_multiplier"] = float(best["multiplier"])
    df["threshold_used"] = float(best["threshold_series"].median())

    final_balance = float(df.loc[df["label_valid"] == 1, "target"].mean()) if int(df["label_valid"].sum()) else 0.5
    noise_pct = float((1.0 - (df["label_valid"].sum() / setup_rows)) * 100.0)
    threshold_for_log = float(df["threshold_used"].iloc[0]) if len(df) else 0.0
    logger.info(
        "Target created | threshold=%.6f | balance=%.2f%% | noise_filtered=%.1f%% | "
        "horizon=%s bars | trend_only=ADX>20",
        threshold_for_log,
        final_balance * 100.0,
        noise_pct,
        horizon_bars,
    )

    return df.iloc[:-horizon_bars]
