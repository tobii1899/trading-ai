"""
Backtesting Service
Simulates historical trading performance using the ML model signals.
Reports: winrate, cumulative P&L, drawdown, Sharpe ratio, vs buy-and-hold.
"""

import numpy as np
import pandas as pd
import logging
from datetime import datetime

from services.feature_engineering import compute_features, create_target, get_feature_columns
from services.data_service import fetch_historical_daily, fetch_ohlcv
from services.ml_service import get_model

logger = logging.getLogger(__name__)


def run_backtest(
    asset: str,
    trade_size_eur: float = 100.0,
    min_probability_threshold: float = 62.0,
    fee_eur: float = 2.0,
    horizon_bars: int = 6,
    use_daily: bool = False,
    lookback_days: int = 365,
) -> dict:
    """
    Run historical backtest for an asset.
    
    Strategy:
    - At each bar, run model prediction
    - If probability ≥ threshold: enter trade in predicted direction
    - After `horizon_bars`, exit and record P&L
    - Prevent overlapping trades (no new trade if one is open)
    
    Args:
        asset: Asset name
        trade_size_eur: Position size in EUR
        min_probability_threshold: Min confidence % to enter trade
        fee_eur: Total round-trip fee in EUR
        horizon_bars: Bars to hold each trade
        use_daily: If True, use daily data; else 5min
        lookback_days: How many days of history to test on
    
    Returns:
        dict with full backtest statistics and equity curve data
    """
    model = get_model(asset)
    if not model.is_trained:
        model._load()
    if not model.is_trained:
        raise RuntimeError(f"Model not trained for {asset}. Run /retrain first.")

    feature_cols = get_feature_columns()

    # Fetch data
    if use_daily:
        df = fetch_historical_daily(asset, lookback_days=lookback_days)
        bar_label = "1d"
    else:
        # 30m backtest window
        days = min(lookback_days, 365)
        df = fetch_ohlcv(asset, interval="30m", lookback_days=days)
        bar_label = "30m"

    # Feature engineering
    df_feat = compute_features(df)
    df_feat = create_target(df_feat, horizon_bars=horizon_bars, asset=asset)
    df_feat = df_feat.dropna(subset=feature_cols + ["target", "future_return"])

    if len(df_feat) < 100:
        raise ValueError(f"Not enough data for backtest: {len(df_feat)} rows")

    # Inference compatibility:
    # - newer models use Pipeline+CalibratedClassifierCV and expect raw features
    # - older persisted models may still require an external scaler
    X = df_feat[feature_cols].values
    if model.scaler is not None:
        X_infer = model.scaler.transform(X)
    else:
        X_infer = X

    # Get all probabilities in batch (much faster than one-by-one)
    probs = model.model.predict_proba(X_infer)[:, 1]  # P(up)

    # Simulate trading
    n = len(df_feat)
    equity = [0.0]           # Cumulative P&L in EUR
    trades = []
    in_trade = False
    trade_end_idx = -1

    for i in range(n):
        # Skip if in open trade
        if in_trade and i <= trade_end_idx:
            equity.append(equity[-1])
            continue

        in_trade = False
        prob_up = float(probs[i])
        prob_down = 1.0 - prob_up
        max_prob = max(prob_up, prob_down)
        direction = 1 if prob_up >= prob_down else -1  # +1=long, -1=short

        # Entry condition
        if max_prob * 100 < min_probability_threshold:
            equity.append(equity[-1])
            continue

        # Check if we have enough future bars
        if i + horizon_bars >= n:
            equity.append(equity[-1])
            continue

        # Future return (actual)
        actual_return = float(df_feat["future_return"].iloc[i])

        # P&L calculation
        # direction: +1 if we went long, -1 if short
        # If long: profit when actual_return > 0
        raw_pnl = direction * actual_return * trade_size_eur
        net_pnl = raw_pnl - fee_eur

        # "Won" = correct directional prediction (gross, pre-fee)
        won = raw_pnl > 0
        trades.append({
            "timestamp": str(df_feat.index[i]),
            "direction": "BUY" if direction == 1 else "SELL",
            "probability": round(max_prob * 100, 2),
            "actual_return_pct": round(actual_return * 100, 4),
            "raw_pnl_eur": round(raw_pnl, 2),
            "net_pnl_eur": round(net_pnl, 2),
            "won": won,
            "cumulative_pnl": round(equity[-1] + net_pnl, 2),
        })

        equity.append(equity[-1] + net_pnl)
        in_trade = True
        trade_end_idx = i + horizon_bars

    # ── Statistics ─────────────────────────────────────────────────────────────
    if not trades:
        return {
            "asset": asset,
            "error": "No trades generated",
            "trades_count": 0,
        }

    n_trades = len(trades)
    wins = [t for t in trades if t["won"]]
    losses = [t for t in trades if not t["won"]]

    win_rate = len(wins) / n_trades * 100
    total_pnl = equity[-1]
    avg_win = np.mean([t["net_pnl_eur"] for t in wins]) if wins else 0
    avg_loss = np.mean([t["net_pnl_eur"] for t in losses]) if losses else 0

    # Profit factor
    gross_profit = sum(t["net_pnl_eur"] for t in wins) if wins else 0
    gross_loss = abs(sum(t["net_pnl_eur"] for t in losses)) if losses else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown
    equity_arr = np.array(equity)
    running_max = np.maximum.accumulate(equity_arr)
    drawdown = equity_arr - running_max
    max_drawdown = float(np.min(drawdown))

    # Sharpe ratio (simplified, per-trade)
    pnl_series = [t["net_pnl_eur"] for t in trades]
    sharpe = (np.mean(pnl_series) / (np.std(pnl_series) + 1e-8)) * np.sqrt(252) if pnl_series else 0

    # Buy & hold comparison
    first_price = float(df_feat["close"].iloc[0])
    last_price = float(df_feat["close"].iloc[-1])
    buy_hold_return_pct = (last_price - first_price) / first_price * 100
    buy_hold_pnl_eur = trade_size_eur * (last_price - first_price) / first_price

    # Equity curve (downsample to 200 points for API response size)
    step = max(1, len(equity) // 200)
    equity_curve = [
        {
            "index": i,
            "timestamp": str(df_feat.index[min(i, len(df_feat) - 1)]),
            "equity_eur": round(equity[i], 2),
        }
        for i in range(0, len(equity), step)
    ]

    return {
        "asset": asset,
        "config": {
            "trade_size_eur": trade_size_eur,
            "min_probability_threshold": min_probability_threshold,
            "fee_eur": fee_eur,
            "horizon_bars": horizon_bars,
            "bar_interval": bar_label,
            "lookback_days": lookback_days,
        },
        "summary": {
            "trades_count": n_trades,
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate_pct": round(win_rate, 2),
            "total_pnl_eur": round(total_pnl, 2),
            "avg_win_eur": round(avg_win, 2),
            "avg_loss_eur": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 3),
            "max_drawdown_eur": round(max_drawdown, 2),
            "sharpe_ratio": round(float(sharpe), 3),
            "buy_hold_return_pct": round(buy_hold_return_pct, 2),
            "buy_hold_pnl_eur": round(buy_hold_pnl_eur, 2),
            "strategy_vs_buyhold_eur": round(total_pnl - buy_hold_pnl_eur, 2),
        },
        "equity_curve": equity_curve,
        "recent_trades": sorted(trades, key=lambda t: t["timestamp"], reverse=True)[:50],
        "backtested_at": datetime.utcnow().isoformat(),
    }
