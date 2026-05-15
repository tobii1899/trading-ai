"""
Trading Logic Service
- Calculates Expected Value (EV) for each trade signal
- Applies decision rules: BUY / SELL / NO TRADE
- Estimates profit/loss given trade size and fees
- Supports configurable thresholds
"""

from dataclasses import dataclass, asdict
from typing import Literal
import logging

logger = logging.getLogger(__name__)

# ── Fee model approximation (MetaTrader / Trade Republic) ──────────────────────
# Trade Republic: 1€ flat fee per trade side
# MetaTrader: typically 0.02-0.05% spread-based
TRADE_REPUBLIC_FEE = 1.0  # EUR per trade (entry + exit = 2€ total)
METATRADER_SPREAD_PCT = 0.03  # 0.03% per side = 0.06% round trip


@dataclass
class TradeDecision:
    """Full trade decision output for one asset."""
    asset: str
    action: Literal["BUY", "SELL", "NO TRADE"]
    up_probability: float          # % probability price goes up
    down_probability: float        # % probability price goes down
    expected_return_pct: float     # Expected % price move
    expected_profit_eur: float     # Expected profit in EUR
    expected_loss_eur: float       # Expected loss in EUR
    expected_value_eur: float      # EV = P(win)*profit - P(lose)*loss
    trade_size_eur: float          # Configured trade size
    fee_eur: float                 # Total round-trip fee
    win_probability: float         # Probability used for win side
    lose_probability: float        # Probability used for lose side
    potential_profit_eur: float    # Best-case profit (at expected move)
    potential_loss_eur: float      # Worst-case loss (at expected move, opposite direction)
    is_top_trade: bool             # True if prob > 75% AND EV > 0
    confidence_tier: str           # "HIGH", "MEDIUM", "LOW"
    time_horizon: str              # Human-readable horizon (e.g. "30min")
    current_price: float
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_trade_decision(
    asset: str,
    prediction: dict,
    trade_size_eur: float = 100.0,
    min_probability_threshold: float = 62.0,  # Min % confidence to trade
    min_ev_eur: float = 0.0,                  # Min EV to trade
    fee_model: str = "trade_republic",        # "trade_republic" or "metatrader"
    horizon_bars: int = 12,
    bar_minutes: int = 30,
) -> TradeDecision:
    """
    Given ML prediction output, compute a full trading decision.
    
    Decision logic:
    1. Determine direction: UP if up_prob > 50%, DOWN if down_prob > 50%
    2. Calculate potential profit/loss using expected return %
    3. Calculate fees
    4. Compute EV = P(win) * profit - P(lose) * loss
    5. Signal BUY/SELL if: prob > threshold AND EV > min_ev
       Otherwise: NO TRADE
    
    Args:
        prediction: Output from TradingModel.predict()
        trade_size_eur: Size of the trade in EUR
        min_probability_threshold: Minimum directional probability to trade (default 60%)
        min_ev_eur: Minimum expected value in EUR to trigger a trade
        fee_model: Fee structure to use
        horizon_bars: Number of bars in prediction horizon
        bar_minutes: Minutes per bar
    
    Returns:
        TradeDecision dataclass
    """
    up_prob = prediction["up_probability"] / 100.0  # Convert % → ratio
    down_prob = prediction["down_probability"] / 100.0
    expected_return_pct = prediction["expected_return_pct"]  # Already in %
    current_price = prediction["current_price"]
    timestamp = prediction["timestamp"]

    # Determine dominant direction
    direction_up = up_prob > down_prob
    win_prob = up_prob if direction_up else down_prob
    lose_prob = 1.0 - win_prob

    # Potential price move in EUR terms
    abs_return_pct = abs(expected_return_pct) / 100.0  # Convert % → ratio

    # For simplicity, assume linear PnL (CFD/futures style):
    # profit = trade_size * expected_return_pct
    potential_profit_eur = trade_size_eur * abs_return_pct
    # Potential loss = same magnitude but opposite direction
    potential_loss_eur = trade_size_eur * abs_return_pct

    # Fee calculation
    if fee_model == "trade_republic":
        fee_eur = TRADE_REPUBLIC_FEE * 2  # Entry + exit = 2€
    else:  # metatrader
        fee_eur = trade_size_eur * (METATRADER_SPREAD_PCT / 100) * 2  # Round trip

    # Net profit/loss after fees
    net_profit = max(potential_profit_eur - fee_eur, 0)
    net_loss = potential_loss_eur + fee_eur

    # Expected Value
    ev = (win_prob * net_profit) - (lose_prob * net_loss)

    # Expected profit/loss in EUR (signed)
    expected_profit_eur = ev  # EV is the expected outcome
    expected_loss_eur = -net_loss  # Worst case

    # Decision logic
    win_prob_pct = win_prob * 100
    should_trade = (win_prob_pct >= min_probability_threshold) and (ev >= min_ev_eur)
    # Also require non-trivial expected move (above fee noise)
    if abs(expected_return_pct) < 0.01:  # Less than 0.01% expected move
        should_trade = False

    if should_trade:
        action = "BUY" if direction_up else "SELL"
    else:
        action = "NO TRADE"

    # Confidence tier
    if win_prob_pct >= 70:
        confidence_tier = "HIGH"
    elif win_prob_pct >= 60:
        confidence_tier = "MEDIUM"
    else:
        confidence_tier = "LOW"

    # Top trade: high confidence + positive EV
    is_top_trade = (win_prob_pct >= 75) and (ev > 0)

    # Human-readable horizon
    total_minutes = horizon_bars * bar_minutes
    if total_minutes < 60:
        time_horizon = f"{total_minutes}min"
    else:
        hours = total_minutes / 60
        time_horizon = f"{hours:.0f}h" if hours == int(hours) else f"{hours:.1f}h"

    return TradeDecision(
        asset=asset,
        action=action,
        up_probability=round(up_prob * 100, 2),
        down_probability=round(down_prob * 100, 2),
        expected_return_pct=round(expected_return_pct, 3),
        expected_profit_eur=round(ev, 2),
        expected_loss_eur=round(-net_loss, 2),
        expected_value_eur=round(ev, 2),
        trade_size_eur=trade_size_eur,
        fee_eur=round(fee_eur, 2),
        win_probability=round(win_prob * 100, 2),
        lose_probability=round(lose_prob * 100, 2),
        potential_profit_eur=round(net_profit, 2),
        potential_loss_eur=round(-net_loss, 2),
        is_top_trade=is_top_trade,
        confidence_tier=confidence_tier,
        time_horizon=time_horizon,
        current_price=current_price,
        timestamp=timestamp,
    )


def format_decision_for_api(decision: TradeDecision, sentiment: dict) -> dict:
    """Merge trade decision with news sentiment for API response."""
    d = decision.to_dict()
    d["news_sentiment"] = sentiment.get("overall_sentiment", 0.0)
    d["high_impact_news"] = sentiment.get("high_impact_detected", False)
    d["news_warning"] = sentiment.get("warning_message")
    d["recent_news"] = sentiment.get("recent_articles", [])[:3]
    return d
