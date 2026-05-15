"""
API Routes v2 — includes position sizing, signal logger, and signals history.
"""

import asyncio, logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from services.data_service import fetch_ohlcv, get_supported_assets
from services.ml_service import get_model, train_all_models
from services.position_sizing import calculate_position, DEFAULT_ACCOUNT_BALANCE
from services.signal_logger import log_signal, get_signals, get_signal_stats
from services.news_service import get_market_sentiment
from services.backtest_service import run_backtest
from services.trade_service import (
    save_trade, get_all_trades, get_trade_stats, delete_trade, init_trades_db
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic models ────────────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    trade_size_eur: float           = Field(default=5000.0, ge=10)
    min_probability_threshold: float= Field(default=62.0, ge=50, le=95)
    fee_eur: float                  = Field(default=2.0, ge=0)
    horizon_bars: int               = Field(default=6, ge=1, le=48)
    lookback_days: int              = Field(default=180, ge=30, le=365)

class RetrainRequest(BaseModel):
    asset: Optional[str] = None

class TradeRequest(BaseModel):
    asset:          str   = Field(..., description="XAU/USD | GBP/JPY | NASDAQ100")
    action:         str   = Field(..., description="BUY | SELL")
    entryPrice:     float = Field(..., gt=0)
    stopLoss:       float = Field(..., gt=0)
    takeProfit:     float = Field(..., gt=0)
    exitPrice:      Optional[float] = Field(default=None, gt=0)
    resultOverride: Optional[str]   = Field(default=None, description="Win | Loss | BE")

# Initialise trades table once at import time
init_trades_db()

class PositionConfig(BaseModel):
    account_balance: float      = Field(default=5000.0, ge=100)
    risk_per_trade_pct: float   = Field(default=1.0, ge=0.1, le=10,
                                        description="% of account to risk per trade")
    stop_loss_pct: float        = Field(default=0.5, ge=0.05, le=10,
                                        description="stop loss in % of price")
    fee_eur: float              = Field(default=2.0, ge=0)
    fee_multiplier: float       = Field(default=3.0, ge=1)
    min_probability: float      = Field(default=62.0, ge=50, le=95)
    horizon_bars: int           = Field(default=6, ge=1, le=48)


def _pct_to_fraction(cfg: PositionConfig):
    """Convert % inputs to fractions for position calculator."""
    return dict(
        account_balance    = cfg.account_balance,
        risk_per_trade_pct = cfg.risk_per_trade_pct / 100.0,
        stop_loss_pct      = cfg.stop_loss_pct / 100.0,
        fee_eur            = cfg.fee_eur,
        fee_multiplier     = cfg.fee_multiplier,
        min_probability    = cfg.min_probability,
        horizon_bars       = cfg.horizon_bars,
    )


# ── Assets ────────────────────────────────────────────────────────────────────

@router.get("/assets")
async def list_assets():
    assets = get_supported_assets()
    for a in assets:
        m = get_model(a["id"]); m._load()
        a["model_trained"]    = m.is_trained
        a["model_trained_at"] = m.last_trained.isoformat() if m.last_trained else None
        a["model_metrics"]    = m.train_metrics if m.is_trained else None
        a["best_model"]       = m.best_model_name
    return {"assets": assets}


# ── Predict all ───────────────────────────────────────────────────────────────

@router.get("/predict/all/signals")
async def predict_all(
    account_balance: float   = Query(default=5000.0),
    risk_per_trade_pct: float= Query(default=1.0),
    stop_loss_pct: float     = Query(default=0.5),
    min_probability: float   = Query(default=62.0),
    fee_eur: float           = Query(default=2.0),
    fee_multiplier: float    = Query(default=3.0),
    horizon_bars: int        = Query(default=6),
):
    assets = [a["id"] for a in get_supported_assets()]

    async def predict_one(asset: str) -> dict:
        try:
            df = await asyncio.get_event_loop().run_in_executor(
                None, lambda: fetch_ohlcv(asset, interval="30m", lookback_days=365)
            )
            model = get_model(asset)
            prediction = await asyncio.get_event_loop().run_in_executor(
                None, lambda: model.predict(df)
            )
            result = calculate_position(
                asset=asset,
                prediction=prediction,
                account_balance=account_balance,
                risk_per_trade_pct=risk_per_trade_pct / 100.0,
                stop_loss_pct=stop_loss_pct / 100.0,
                fee_eur=fee_eur,
                fee_multiplier=fee_multiplier,
                min_probability=min_probability,
                horizon_bars=horizon_bars,
            )
            # Log if criteria met (async, non-blocking)
            asyncio.get_event_loop().run_in_executor(None, lambda: log_signal(result))

            sentiment = await get_market_sentiment(asset)
            d = result.to_dict()
            d["news_sentiment"]    = sentiment.get("overall_sentiment", 0.0)
            d["high_impact_news"]  = sentiment.get("high_impact_detected", False)
            d["news_warning"]      = sentiment.get("warning_message")
            d["recent_news"]       = sentiment.get("recent_articles", [])[:3]
            d["raw_prediction"]    = prediction
            d["status"]            = "success"
            return d
        except RuntimeError as e:
            return {"asset": asset, "status": "not_trained", "error": str(e)}
        except Exception as e:
            logger.error(f"Error predicting {asset}: {e}")
            return {"asset": asset, "status": "error", "error": str(e)}

    results = await asyncio.gather(*[predict_one(a) for a in assets])

    valid = [r for r in results if r.get("status") == "success"]
    top_trade = None
    top_candidates = [r for r in valid
                      if r.get("action") in ("BUY","SELL") and r.get("expected_value",0) > 0]
    if top_candidates:
        top_trade = max(top_candidates, key=lambda r: r.get("win_probability", 0))

    return {
        "signals":          {r["asset"]: r for r in results if "asset" in r},
        "top_trade":        top_trade,
        "global_news_alert":any(r.get("high_impact_news") for r in valid),
        "refreshed_at":     max((r.get("raw_prediction",{}).get("timestamp","") for r in results), default=""),
    }


# ── Predict single ─────────────────────────────────────────────────────────────

@router.get("/predict/{asset}")
async def predict_single(asset: str, cfg: PositionConfig = None,
    account_balance: float   = Query(default=5000.0),
    risk_per_trade_pct: float= Query(default=1.0),
    stop_loss_pct: float     = Query(default=0.5),
    min_probability: float   = Query(default=62.0),
    fee_eur: float           = Query(default=2.0),
    horizon_bars: int        = Query(default=6),
):
    asset = asset.upper()
    if asset not in {a["id"] for a in get_supported_assets()}:
        raise HTTPException(404, f"Unknown asset: {asset}")
    try:
        df = fetch_ohlcv(asset, interval="30m", lookback_days=365)
    except Exception as e:
        raise HTTPException(503, f"Data fetch failed: {e}")

    model = get_model(asset)
    try:
        prediction = model.predict(df)
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    result = calculate_position(
        asset=asset, prediction=prediction,
        account_balance=account_balance,
        risk_per_trade_pct=risk_per_trade_pct / 100.0,
        stop_loss_pct=stop_loss_pct / 100.0,
        fee_eur=fee_eur, min_probability=min_probability,
        horizon_bars=horizon_bars,
    )
    log_signal(result)
    sentiment = await get_market_sentiment(asset)
    d = result.to_dict()
    d.update({"news_sentiment": sentiment.get("overall_sentiment", 0.0),
              "high_impact_news": sentiment.get("high_impact_detected", False),
              "news_warning": sentiment.get("warning_message"),
              "recent_news": sentiment.get("recent_articles", [])[:3],
              "raw_prediction": prediction})
    return d


# ── Backtest ──────────────────────────────────────────────────────────────────

@router.post("/backtest/{asset}")
async def backtest_asset(asset: str, request: BacktestRequest):
    asset = asset.upper()
    if asset not in {a["id"] for a in get_supported_assets()}:
        raise HTTPException(404, f"Unknown asset: {asset}")
    try:
        result = await asyncio.get_event_loop().run_in_executor(None, lambda: run_backtest(
            asset=asset,
            trade_size_eur=request.trade_size_eur,
            min_probability_threshold=request.min_probability_threshold,
            fee_eur=request.fee_eur,
            horizon_bars=request.horizon_bars,
            lookback_days=request.lookback_days,
        ))
        return result
    except Exception as e:
        raise HTTPException(500, f"Backtest failed: {e}")


# ── Retrain ───────────────────────────────────────────────────────────────────

_retraining = False

@router.post("/retrain")
async def retrain_models(request: RetrainRequest, background_tasks: BackgroundTasks):
    global _retraining
    if _retraining:
        raise HTTPException(409, "Retraining already in progress")

    async def do_retrain():
        global _retraining
        _retraining = True
        try:
            if request.asset:
                asset = request.asset.upper()
                df = fetch_ohlcv(asset, interval="30m", lookback_days=14600)
                get_model(asset).train(df)
            else:
                await train_all_models()
        except Exception as e:
            logger.error(f"Retrain error: {e}")
        finally:
            _retraining = False

    background_tasks.add_task(do_retrain)
    return {"status": "retraining_started", "asset": request.asset or "all",
            "message": "Retraining started. Check /model-status for progress."}


@router.get("/model-status")
async def model_status():
    statuses = {}
    for a in get_supported_assets():
        m = get_model(a["id"]); m._load()
        statuses[a["id"]] = {
            "is_trained":   m.is_trained,
            "trained_at":   m.last_trained.isoformat() if m.last_trained else None,
            "metrics":      m.train_metrics,
            "best_model":   m.best_model_name,
        }
    return {"models": statuses, "retraining_in_progress": _retraining}


# ── Signal history ────────────────────────────────────────────────────────────

@router.get("/signals/history")
async def signal_history(
    asset:  Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    limit:  int           = Query(default=50, ge=1, le=500),
    offset: int           = Query(default=0, ge=0),
):
    """Return logged signals from DB (only BUY/SELL with prob>=60% & profit>0)."""
    rows = get_signals(asset=asset, action=action, limit=limit, offset=offset)
    return {"signals": rows, "count": len(rows), "offset": offset}


@router.get("/signals/stats")
async def signal_stats():
    """Aggregate statistics over all stored signals."""
    return get_signal_stats()


# ── Trades ────────────────────────────────────────────────────────────────────

@router.get("/trades")
async def list_trades(
    asset:  Optional[str] = Query(default=None),
    limit:  int           = Query(default=200, ge=1, le=1000),
    offset: int           = Query(default=0, ge=0),
):
    """Return all stored trades from DB, newest first."""
    rows = get_all_trades(asset=asset, limit=limit, offset=offset)
    return {"trades": rows, "count": len(rows)}


@router.post("/trades")
async def create_trade(body: TradeRequest):
    """Save a new trade. PnL and result are computed server-side."""
    action = body.action.upper()
    if action not in ("BUY", "SELL"):
        raise HTTPException(400, "action must be BUY or SELL")

    try:
        trade = save_trade(
            asset=body.asset,
            action=action,
            entry_price=body.entryPrice,
            stop_loss=body.stopLoss,
            take_profit=body.takeProfit,
            exit_price=body.exitPrice,
            result_override=body.resultOverride,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return trade


@router.get("/trades/stats")
async def trade_stats():
    """Aggregate trade statistics: PnL, winrate, counts, avg win/loss."""
    return get_trade_stats()


@router.delete("/trades/{trade_id}")
async def remove_trade(trade_id: int):
    ok = delete_trade(trade_id)
    if not ok:
        raise HTTPException(404, f"Trade {trade_id} not found")
    return {"deleted": trade_id}
