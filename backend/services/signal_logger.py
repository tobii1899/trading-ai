""" Signal Logger — SQLite-backed persistent storage for trading signals. 

Saves every signal where: 
- probability >= 62% AND 
- net_profit > 0 (positive expected profit after fees) 

Schema: signals table with full PositionResult fields + metadata. 
Provides query methods for the UI (history, stats, export). """ 

import sqlite3 
import json 
import os 
import logging 
from datetime import datetime, timezone 
from typing import Optional 

logger = logging.getLogger(__name__) 

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "signals.db") 

def _get_conn() -> sqlite3.Connection: 
    conn = sqlite3.connect(DB_PATH, check_same_thread=False) 
    conn.row_factory = sqlite3.Row 
    return conn 

def init_db(): 
    """Create tables if they don't exist. Safe to call multiple times.""" 
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) 
    with _get_conn() as conn: 
        conn.execute(""" CREATE TABLE IF NOT EXISTS signals ( 
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    logged_at TEXT NOT NULL, 
                    asset TEXT NOT NULL, 
                    action TEXT NOT NULL, 
                    direction TEXT NOT NULL, 
                    win_probability REAL, 
                    lose_probability REAL, 
                    expected_return_pct REAL, 
                    position_size REAL, 
                    position_size_capped REAL, 
                    risk_amount REAL, 
                    account_balance REAL, 
                    risk_per_trade_pct REAL, 
                    stop_loss_pct REAL, 
                    gross_profit REAL, 
                    gross_loss REAL, 
                    net_profit REAL, 
                    net_loss REAL, 
                    expected_value REAL, 
                    fee_eur REAL, 
                    was_capped INTEGER, 
                    time_horizon TEXT, 
                    current_price REAL, 
                    signal_timestamp TEXT, 
                    raw_json TEXT 
                    ) 
                """) 
        conn.execute(""" 
            CREATE TABLE IF NOT EXISTS signal_outcomes ( 
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    signal_id INTEGER REFERENCES signals(id), 
                    outcome_at TEXT NOT NULL, 
                    actual_return_pct REAL, 
                    actual_pnl_eur REAL, 
                    won INTEGER, 
                    notes TEXT ) 
            """) 
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_asset ON signals(asset)") 
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_action ON signals(action)") 
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_logged_at ON signals(logged_at)") 
        conn.commit() 
        
        logger.info(f"Signal DB initialised at {DB_PATH}") 
def should_log(result) -> tuple[bool, str]: 
    """ 
    Returns (True, reason) if signal should be saved, (False, reason) if not. 
    Criteria: action is BUY or SELL (not NO TRADE) — position_sizing already 
    enforced prob >= 62% and net_profit > 3× fee before setting action. 
    """ 
    
    if result.action == "NO TRADE": 
        return False, f"NO TRADE: {result.reject_reason}" 
    if result.net_profit <= 0: 
        return False, f"net_profit={result.net_profit:.2f} <= 0" 
    if result.win_probability < 62.0: 
        return False, f"probability={result.win_probability:.1f}% < 62%" 
    return True, "Signal meets criteria" 

def log_signal(result) -> Optional[int]: 
    """ Persist a PositionResult to the database if it meets logging criteria. 
    Returns the new row ID if saved, None if skipped. 
    """ 

    ok, reason = should_log(result) 

    if not ok: 
        logger.debug(f"Signal skipped ({result.asset}): {reason}") 
        return None 
    
    now = datetime.now(tz=timezone.utc).isoformat() 
    d = result.to_dict() 
    
    with _get_conn() as conn: 
        cursor = conn.execute(""" 
            INSERT INTO signals ( 
                    logged_at, asset, action, direction, 
                    win_probability, lose_probability, expected_return_pct, 
                    position_size, position_size_capped, risk_amount, 
                    account_balance, risk_per_trade_pct, stop_loss_pct, 
                    gross_profit, gross_loss, net_profit, net_loss, 
                    expected_value, fee_eur, was_capped, 
                    time_horizon, current_price, signal_timestamp, raw_json 
                ) VALUES ( 
                    :logged_at, :asset, :action, :direction, 
                    :win_probability, :lose_probability, :expected_return_pct, 
                    :position_size, :position_size_capped, :risk_amount, 
                    :account_balance, :risk_per_trade_pct, :stop_loss_pct, 
                    :gross_profit, :gross_loss, :net_profit, :net_loss, 
                    :expected_value, :fee_eur, :was_capped, 
                    :time_horizon, :current_price, :signal_timestamp, :raw_json 
                ) 
            """, { 
                "logged_at": now, 
                "asset": d["asset"], 
                "action": d["action"], 
                "direction": d["direction"], 
                "win_probability": d["win_probability"], 
                "lose_probability": d["lose_probability"], 
                "expected_return_pct": d["expected_return_pct"], 
                "position_size": d["position_size"], 
                "position_size_capped": d["position_size_capped"], 
                "risk_amount": d["risk_amount"], 
                "account_balance": d["account_balance"], 
                "risk_per_trade_pct": d["risk_per_trade_pct"], 
                "stop_loss_pct": d["stop_loss_pct"], 
                "gross_profit": d["gross_profit"], 
                "gross_loss": d["gross_loss"], 
                "net_profit": d["net_profit"], 
                "net_loss": d["net_loss"], 
                "expected_value": d["expected_value"], 
                "fee_eur": d["fee_eur"], 
                "was_capped": int(d["was_capped"]), 
                "time_horizon": d["time_horizon"], 
                "current_price": d["current_price"], 
                "signal_timestamp": d["timestamp"], 
                "raw_json": json.dumps(d), }) 
        
        signal_id = cursor.lastrowid 
        conn.commit() 
        
        logger.info(f"✅ Signal logged #{signal_id}: {result.asset} {result.action} " 
                    f"P={result.win_probability:.1f}% size=€{result.position_size_capped:.0f} " 
                    f"EV=€{result.expected_value:.2f}") 
        
        return signal_id 
    
def get_signals( 
    asset: Optional[str] = None, 
    action: Optional[str] = None, 
    limit: int = 100, 
    offset: int = 0, 
    ) -> list[dict]: 
    """Fetch saved signals with optional filters.""" 
    where, params = [], [] 
    
    if asset: 
        where.append("asset = ?"); params.append(asset) 
    if action: 
        where.append("action = ?"); params.append(action) 
        
    sql = "SELECT * FROM signals" 
    
    if where: 
        sql += " WHERE " + " AND ".join(where) 
    
    sql += " ORDER BY logged_at DESC LIMIT ? OFFSET ?" 
    params += [limit, offset] 
    
    with _get_conn() as conn: 
        rows = conn.execute(sql, params).fetchall() 
        return [dict(r) for r in rows] 
    
def get_signal_stats() -> dict: 
    """Aggregate statistics over all logged signals.""" 
    with _get_conn() as conn: 
        total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] 
        
        by_asset = conn.execute(""" 
            SELECT asset, 
                COUNT(*) as count, 
                SUM(CASE action WHEN 'BUY' THEN 1 ELSE 0 END) as buys, 
                SUM(CASE action WHEN 'SELL' THEN 1 ELSE 0 END) as sells, 
                ROUND(AVG(win_probability),2) as avg_prob, 
                ROUND(AVG(expected_value),2) as avg_ev, 
                ROUND(SUM(expected_value),2) as total_ev, 
                ROUND(AVG(position_size_capped),2) as avg_position 
            FROM signals GROUP BY asset """).fetchall() 
        
        recent = conn.execute( 
            "SELECT logged_at FROM signals ORDER BY logged_at DESC LIMIT 1" ).fetchone() 
        
    return { 
        "total_signals": total, 
        "last_signal_at": recent[0] if recent else None, 
        "by_asset": [dict(r) for r in by_asset], 
    } 

def get_signal_count() -> int: 
    with _get_conn() as conn: 
        return conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] 
    
# Initialise on import 
init_db()
