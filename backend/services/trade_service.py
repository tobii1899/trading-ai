"""
Trade Service — SQLite-backed persistent storage for trades.

Uses risk-based position sizing:
  risk_amount = account_balance * risk_pct  (default 1%)
  sl_distance = abs(entry - stop_loss)
  qty         = risk_amount / sl_distance

PnL:
  BUY:  (exit - entry) * qty - fee
  SELL: (entry - exit) * qty - fee
"""

import sqlite3
import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH         = os.path.join(os.path.dirname(__file__), "..", "models", "signals.db")
FEE_EUR         = 3.0    # Fixed fee per trade (EUR)
ACCOUNT_BALANCE = 5000.0 # Default paper-trading account (EUR)
RISK_PCT        = 0.01   # 1% risk per trade


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_trades_db():
    """Create trades table if it doesn't exist. Safe to call multiple times."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                asset       TEXT NOT NULL,
                action      TEXT NOT NULL,
                entryPrice  REAL NOT NULL,
                stopLoss    REAL NOT NULL,
                takeProfit  REAL NOT NULL,
                exitPrice   REAL,
                result      TEXT NOT NULL,
                profitLoss  REAL NOT NULL,
                qty         REAL NOT NULL DEFAULT 0,
                riskAmount  REAL NOT NULL DEFAULT 0,
                date        TEXT NOT NULL
            )
        """)
        # Add qty/riskAmount columns to existing DBs that predate this schema
        for col, typ in [("qty", "REAL"), ("riskAmount", "REAL")]:
            try:
                conn.execute(f"ALTER TABLE trades ADD COLUMN {col} {typ} NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()
    logger.info("Trades DB initialised at %s", DB_PATH)


def validate_trade(
    action: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
) -> Optional[str]:
    """
    BUY:  SL < entry < TP
    SELL: TP < entry < SL
    Returns an error string on failure, None on success.
    """
    if action == "BUY":
        if stop_loss >= entry:
            return f"BUY: Stop Loss ({stop_loss}) must be BELOW entry ({entry})"
        if take_profit <= entry:
            return f"BUY: Take Profit ({take_profit}) must be ABOVE entry ({entry})"
    elif action == "SELL":
        if stop_loss <= entry:
            return f"SELL: Stop Loss ({stop_loss}) must be ABOVE entry ({entry})"
        if take_profit >= entry:
            return f"SELL: Take Profit ({take_profit}) must be BELOW entry ({entry})"
    return None


def _position_size(entry: float, stop_loss: float) -> tuple[float, float]:
    """
    Returns (qty, risk_amount).
    risk_amount = ACCOUNT_BALANCE * RISK_PCT  →  €50 at defaults
    sl_distance = abs(entry - stop_loss)
    qty         = risk_amount / sl_distance
    """
    risk_amount = ACCOUNT_BALANCE * RISK_PCT
    sl_distance = abs(entry - stop_loss)
    if sl_distance == 0:
        raise ValueError("Entry and Stop Loss cannot be the same price")
    qty = risk_amount / sl_distance
    return round(qty, 6), round(risk_amount, 2)


def _calculate_pnl(
    action: str,
    entry: float,
    exit_price: float,
    stop_loss: float,
    take_profit: float,
    risk_amount: float,
    result_override=None
) -> tuple[float, str]:

    fee = FEE_EUR

    # 🔥 PRIORITY: MANUAL RESULT
    if result_override == "Loss":
        return round(-risk_amount - fee, 2), "Loss"

    if result_override == "Win":
        rr = abs(take_profit - entry) / abs(entry - stop_loss)
        profit = risk_amount * rr
        return round(profit - fee, 2), "Win"

    if result_override == "BE":
        return round(-fee, 2), "BE"
    
    # SL hit
    if (action == "BUY" and exit_price <= stop_loss) or \
       (action == "SELL" and exit_price >= stop_loss):
        return round(-risk_amount - fee, 2), "Loss"

    # TP hit
    if (action == "BUY" and exit_price >= take_profit) or \
       (action == "SELL" and exit_price <= take_profit):

        rr = abs(take_profit - entry) / abs(entry - stop_loss)
        profit = risk_amount * rr
        return round(profit - fee, 2), "Win"

    # manual exit
    if action == "BUY":
        pnl = (exit_price - entry)
    else:
        pnl = (entry - exit_price)

    # scale to risk
    rr_current = pnl / abs(entry - stop_loss)
    pnl_eur = risk_amount * rr_current

    pnl_eur -= fee
    result = "Win" if pnl_eur > 0 else "Loss"

    return round(pnl_eur, 2), result


def save_trade(
    asset: str,
    action: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    exit_price: Optional[float],
    result_override: Optional[str] = None,  # "Win" | "Loss" | "BE"
) -> Dict[str, Any]:
    """
    Validate → size position → calculate PnL → persist.

    - exit_price given  → PnL from actual exit
    - exit_price None   → assume TP was hit
    - result_override   → user can force Win / Loss / BE
    - Raises ValueError on invalid setup.
    """
    err = validate_trade(action, entry_price, stop_loss, take_profit)
    if err:
        raise ValueError(err)

    qty, risk_amount = _position_size(entry_price, stop_loss)
    effective_exit   = exit_price if exit_price is not None else take_profit
    pnl, result      = _calculate_pnl(action, entry_price, effective_exit, stop_loss, take_profit, risk_amount,result_override)
    VALID_RESULTS = {"Win", "Loss", "BE"}

    if result_override and result_override in VALID_RESULTS:
        result = result_override

    now = datetime.now(timezone.utc).isoformat()

    with _get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO trades
                (asset, action, entryPrice, stopLoss, takeProfit,
                 exitPrice, result, profitLoss, qty, riskAmount, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (asset, action, entry_price, stop_loss, take_profit,
             effective_exit, result, pnl, qty, risk_amount, now),
        )
        conn.commit()
        trade_id = cur.lastrowid

    return get_trade(trade_id)


def get_trade(trade_id: int) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    return dict(row) if row else None


def get_all_trades(
    asset: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM trades"
    params: list = []
    if asset:
        query += " WHERE asset = ?"
        params.append(asset)
    query += " ORDER BY date DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    with _get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_trade_stats() -> Dict[str, Any]:
    """Aggregate stats: total PnL, winrate, counts, avg win/loss."""
    with _get_conn() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)                                            AS total,
                SUM(profitLoss)                                     AS total_pnl,
                SUM(CASE WHEN result = 'Win'  THEN 1 ELSE 0 END)   AS wins,
                SUM(CASE WHEN result = 'Loss' THEN 1 ELSE 0 END)   AS losses,
                SUM(CASE WHEN result = 'BE'   THEN 1 ELSE 0 END)   AS breakevens,
                AVG(CASE WHEN result = 'Win'  THEN profitLoss END)  AS avg_win,
                AVG(CASE WHEN result = 'Loss' THEN profitLoss END)  AS avg_loss
            FROM trades
        """).fetchone()

    total = row["total"] or 0
    wins  = row["wins"]  or 0
    return {
        "totalTrades": total,
        "totalPnL":    round(row["total_pnl"] or 0, 2),
        "winrate":     round(wins / total * 100, 1) if total else 0.0,
        "wins":        wins,
        "losses":      row["losses"] or 0,
        "breakevens":  row["breakevens"] or 0,
        "avgWin":      round(row["avg_win"]  or 0, 2),
        "avgLoss":     round(row["avg_loss"] or 0, 2),
    }


def delete_trade(trade_id: int) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()
    return cur.rowcount > 0