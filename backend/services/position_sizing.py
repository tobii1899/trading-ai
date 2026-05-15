
"""
Position Sizing v3 — Proper EV, signal-strength-aware filtering.

EV formula:
    EV = (prob_up × avg_up_move%) + (prob_down × avg_down_move%)
    converted to EUR: EV_eur = EV% / 100 × position_size - fee

Decision rules (in order):
    1. reject_reason from ml_service (prob, signal strength, vol filter)
    2. EV_eur > 0
    3. net_profit > fee_multiplier × fee
"""

from dataclasses import dataclass, asdict
from typing import Literal
import logging

logger = logging.getLogger(__name__)

DEFAULT_ACCOUNT_BALANCE    = 5000.0
DEFAULT_RISK_PER_TRADE_PCT = 0.01
DEFAULT_STOP_LOSS_PCT      = 0.005
DEFAULT_FEE_EUR            = 2.0
DEFAULT_FEE_MULTIPLIER     = 3.0
DEFAULT_MIN_PROBABILITY    = 62.0
DEFAULT_MAX_POSITION_PCT   = 0.30


@dataclass
class PositionResult:
    # Account
    account_balance: float
    risk_per_trade_pct: float
    stop_loss_pct: float

    # Sizing
    risk_amount: float
    position_size: float
    position_size_capped: float
    was_capped: bool

    # Signal
    asset: str
    action: Literal["BUY", "SELL", "NO TRADE"]
    direction: Literal["UP", "DOWN"]
    win_probability: float
    lose_probability: float
    expected_return_pct: float      # dominant-direction avg move
    expected_value_pct: float       # full EV: (p_up×avg_up) + (p_down×avg_down)
    avg_up_move: float
    avg_down_move: float
    signal_strength: float
    confidence_score: float

    # P&L
    fee_eur: float
    gross_profit: float
    gross_loss: float
    net_profit: float
    net_loss: float
    expected_value: float           # EV in EUR after fee

    # Decision
    reject_reason: str | None
    time_horizon: str
    current_price: float
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_position(
    asset: str,
    prediction: dict,
    account_balance: float    = DEFAULT_ACCOUNT_BALANCE,
    risk_per_trade_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
    stop_loss_pct: float      = DEFAULT_STOP_LOSS_PCT,
    fee_eur: float            = DEFAULT_FEE_EUR,
    fee_multiplier: float     = DEFAULT_FEE_MULTIPLIER,
    min_probability: float    = DEFAULT_MIN_PROBABILITY,
    max_position_pct: float   = DEFAULT_MAX_POSITION_PCT,
    horizon_bars: int         = 12,
    bar_minutes: int          = 30,
) -> PositionResult:

    up_prob   = prediction["up_probability"]   / 100.0
    down_prob = prediction["down_probability"] / 100.0
    price     = prediction["current_price"]
    timestamp = prediction["timestamp"]

    # avg moves in % (from training data)
    avg_up_move   = prediction.get("avg_up_move",   0.0)
    avg_down_move = prediction.get("avg_down_move", 0.0)

    # ── EV using proper formula ────────────────────────────────────────────────
    # EV% = (prob_up × avg_up_move) + (prob_down × avg_down_move)
    # avg_down_move is negative → naturally penalises mixed signals
    ev_pct = (up_prob * avg_up_move) + (down_prob * avg_down_move)

    # Dominant direction
    direction_up = up_prob >= down_prob
    direction    = "UP" if direction_up else "DOWN"
    win_prob     = up_prob if direction_up else down_prob
    lose_prob    = 1.0 - win_prob

    # Dominant-direction expected move (for P&L sizing)
    exp_ret = avg_up_move if direction_up else avg_down_move   # signed %

    # ── Position sizing ────────────────────────────────────────────────────────
    risk_amount   = account_balance * risk_per_trade_pct        # e.g. €50
    position_size = risk_amount / stop_loss_pct                 # e.g. €10,000
    max_position  = account_balance * max_position_pct
    was_capped    = position_size > max_position
    position_size_capped = min(position_size, max_position)

    # P&L on capped size
    abs_exp_ret  = abs(exp_ret) / 100.0
    gross_profit = position_size_capped * abs_exp_ret
    gross_loss   = position_size_capped * stop_loss_pct
    net_profit   = gross_profit - fee_eur
    net_loss     = gross_loss   + fee_eur

    # EV in EUR
    ev_eur = (win_prob * net_profit) - (lose_prob * net_loss)

    # ── Decision: inherit ml_service filter first, then EV checks ─────────────
    reject_reason = prediction.get("reject_reason")   # from ml_service

    if not reject_reason:
        if win_prob * 100 < min_probability:
            reject_reason = (
                f"Probability {win_prob*100:.1f}% < threshold {min_probability:.0f}%"
            )
        elif ev_eur <= 0:
            reject_reason = f"EV €{ev_eur:.2f} ≤ 0"
        elif net_profit < fee_multiplier * fee_eur:
            reject_reason = (
                f"Net profit €{net_profit:.2f} < {fee_multiplier:.0f}× fee"
            )
        elif abs(exp_ret) < 0.001:
            reject_reason = f"Expected move {exp_ret:.4f}% too small"

    action = "NO TRADE" if reject_reason else ("BUY" if direction_up else "SELL")

    total_min = horizon_bars * bar_minutes
    horizon   = f"{total_min}min" if total_min < 60 else f"{total_min//60}h"

    return PositionResult(
        account_balance      = round(account_balance, 2),
        risk_per_trade_pct   = round(risk_per_trade_pct * 100, 2),
        stop_loss_pct        = round(stop_loss_pct * 100, 3),
        risk_amount          = round(risk_amount, 2),
        position_size        = round(position_size, 2),
        position_size_capped = round(position_size_capped, 2),
        was_capped           = was_capped,
        asset                = asset,
        action               = action,
        direction            = direction,
        win_probability      = round(win_prob * 100, 2),
        lose_probability     = round(lose_prob * 100, 2),
        expected_return_pct  = round(exp_ret, 4),
        expected_value_pct   = round(ev_pct, 4),
        avg_up_move          = round(avg_up_move, 4),
        avg_down_move        = round(avg_down_move, 4),
        signal_strength      = round(prediction.get("signal_strength", 0.0), 4),
        confidence_score     = round(prediction.get("confidence_score", 0.0), 1),
        fee_eur              = round(fee_eur, 2),
        gross_profit         = round(gross_profit, 2),
        gross_loss           = round(gross_loss, 2),
        net_profit           = round(net_profit, 2),
        net_loss             = round(net_loss, 2),
        expected_value       = round(ev_eur, 2),
        reject_reason        = reject_reason,
        time_horizon         = horizon,
        current_price        = round(price, 4),
        timestamp            = str(timestamp),
    )
