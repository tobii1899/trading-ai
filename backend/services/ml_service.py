"""
ML service for asset-level directional models.

Quality-focused updates:
- Dynamic, volatility-aware target labels from feature_engineering.create_target
- Horizon search across 6/12/24 bars, choose best per asset
- Leak-safe TimeSeriesSplit with scaling inside Pipeline
- Candidate models: tuned XGBoost + LogisticRegression baseline
- Probability calibration selection (sigmoid/isotonic) based on out-of-sample quality
- Signal filtering for helper-tool behavior (probability, confidence, EV, volatility)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from typing import Optional

from services.data_service import fetch_ohlcv
from services.feature_engineering import compute_features, create_target, get_feature_columns

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "saved")
os.makedirs(MODEL_DIR, exist_ok=True)

# Signal-quality thresholds
MIN_PROB_THRESHOLD = 0.62
MIN_CONFIDENCE = 0.12
MIN_CONFIDENCE_SCORE = 62.0
MIN_ATR_PCT = 0.0001
MIN_SIGNAL_STRENGTH = 0.10
MIN_VOL_REGIME = 1.00
TRAIN_LOOKBACK_DAYS = 14600
MIN_TEST_AUC_ACCEPT = 0.52

DEFAULT_HORIZON_CANDIDATES = (3, 6, 9)


def _horizon_candidates_for_asset(asset: str) -> tuple[int, ...]:
    # Asset-specific horizon tuning for 30m continuation setups.
    asset_upper = asset.upper()
    if asset_upper == "XAU/USD":
        return (6, 9)
    if asset_upper == "NASDAQ100":
        return (6,)
    return DEFAULT_HORIZON_CANDIDATES


def _build_candidates(neg: int, pos: int) -> list[tuple[str, object]]:
    """Return candidate estimators with class imbalance handling."""
    pos = max(pos, 1)
    neg = max(neg, 1)
    scale_pos_weight = neg / pos

    xgb_d2 = XGBClassifier(
        n_estimators=320,
        max_depth=2,
        learning_rate=0.03,
        subsample=0.72,
        colsample_bytree=0.62,
        min_child_weight=14,
        gamma=1.8,
        reg_alpha=0.60,
        reg_lambda=6.0,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )

    xgb_d3 = XGBClassifier(
        n_estimators=360,
        max_depth=3,
        learning_rate=0.028,
        subsample=0.70,
        colsample_bytree=0.58,
        min_child_weight=18,
        gamma=2.2,
        reg_alpha=0.85,
        reg_lambda=8.0,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )

    lr = LogisticRegression(
        C=0.15,
        max_iter=2000,
        class_weight="balanced",
        random_state=42,
    )

    return [
        ("XGBoost_d2", xgb_d2),
        ("XGBoost_d3", xgb_d3),
        ("LogisticRegression", lr),
    ]


def _pipeline(estimator: object) -> Pipeline:
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("clf", estimator),
        ]
    )


def _calibration_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Higher is better: AUC first, then logloss, then spread."""
    if len(np.unique(y_true)) < 2:
        auc = 0.5
    else:
        auc = float(roc_auc_score(y_true, y_prob))
    ll = float(log_loss(y_true, y_prob, labels=[0, 1]))
    prob_std = float(np.std(y_prob))
    prob_range = float(np.max(y_prob) - np.min(y_prob))
    range_penalty = 0.0 if prob_range >= 0.25 else (0.25 - prob_range) * 0.50
    return auc - (0.18 * ll) + (0.20 * prob_std) - range_penalty


def _walk_forward_oos_auc(
    estimator: Pipeline,
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5,
) -> dict:
    """
    Expanding-window walk-forward AUC on full labeled series.
    Uses unclibrated base estimator to avoid nested calibration leakage in folds.
    """
    if len(X) < 450:
        return {
            "fold_count": 0,
            "auc_scores": [],
            "auc_mean": 0.5,
            "auc_std": 0.0,
        }

    tscv = TimeSeriesSplit(n_splits=n_splits)
    scores: list[float] = []

    for tr_idx, te_idx in tscv.split(X):
        X_tr, X_te = X[tr_idx], X[te_idx]
        y_tr, y_te = y[tr_idx], y[te_idx]
        if len(np.unique(y_tr)) < 2 or len(np.unique(y_te)) < 2:
            continue
        model = clone(estimator)
        model.fit(X_tr, y_tr)
        prob = model.predict_proba(X_te)[:, 1]
        auc = float(roc_auc_score(y_te, prob))
        scores.append(auc)

    if not scores:
        return {
            "fold_count": 0,
            "auc_scores": [],
            "auc_mean": 0.5,
            "auc_std": 0.0,
        }

    return {
        "fold_count": len(scores),
        "auc_scores": [round(float(s), 4) for s in scores],
        "auc_mean": round(float(np.mean(scores)), 4),
        "auc_std": round(float(np.std(scores)), 4),
    }


class TradingModel:
    def __init__(self, asset: str, horizon_bars: int = 8):
        self.asset = asset
        self.horizon_bars = horizon_bars
        self.feature_cols = get_feature_columns()
        self.model = None
        self.scaler = None  # retained for backward compatibility
        self.last_trained = None
        self.train_metrics: dict = {}
        self.is_trained = False
        self.best_model_name = None
        self.avg_up_move = 0.0
        self.avg_down_move = 0.0
        self.threshold_used = 0.0
        self.threshold_multiplier = 1.0
        self.median_atr_pct = 0.0
        self.median_vol_20 = 0.0

    def _model_path(self) -> str:
        return os.path.join(MODEL_DIR, f"{self.asset.replace('/', '_')}_model.pkl")

    def _select_calibrated_model(
        self,
        base_pipeline: Pipeline,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
    ) -> tuple[object, str, dict]:
        """Try sigmoid/isotonic and keep better calibrated model."""
        calibration_results: dict[str, dict] = {}

        calibration_options: list[str] = ["sigmoid"]
        class_counts = np.bincount(y_train.astype(int), minlength=2)
        if int(class_counts.min()) >= 80 and len(y_train) >= 700:
            calibration_options.append("isotonic")

        best_model = None
        best_method = None
        best_score = -1e9

        for method in calibration_options:
            calibrator = CalibratedClassifierCV(
                estimator=clone(base_pipeline),
                method=method,
                cv=TimeSeriesSplit(n_splits=3),
            )
            calibrator.fit(X_train, y_train)
            y_prob = calibrator.predict_proba(X_test)[:, 1]

            score = _calibration_score(y_test, y_prob)
            auc = float(roc_auc_score(y_test, y_prob)) if len(np.unique(y_test)) > 1 else 0.5
            ll = float(log_loss(y_test, y_prob, labels=[0, 1]))
            prob_std = float(np.std(y_prob))

            calibration_results[method] = {
                "score": round(score, 6),
                "test_auc": round(auc, 4),
                "test_logloss": round(ll, 4),
                "prob_std": round(prob_std, 4),
                "prob_range": [round(float(np.min(y_prob)), 4), round(float(np.max(y_prob)), 4)],
            }

            if score > best_score:
                best_score = score
                best_model = calibrator
                best_method = method

        if best_model is None or best_method is None:
            raise RuntimeError("Calibration failed for all methods")

        return best_model, best_method, calibration_results

    def _train_for_horizon(self, df_features: pd.DataFrame, horizon: int) -> dict:
        df_target_raw = create_target(df_features, horizon_bars=horizon, asset=self.asset)
        noise_pct = float((1.0 - df_target_raw["label_valid"].mean()) * 100.0)
        threshold_used = float(df_target_raw["threshold_used"].median())
        threshold_multiplier = float(df_target_raw["threshold_multiplier"].iloc[-1])

        df_target = df_target_raw
        df_target = df_target.dropna(subset=self.feature_cols + ["target", "future_return"])

        setup_rows = int(df_target_raw["setup_active"].sum()) if "setup_active" in df_target_raw.columns else len(df_target_raw)
        min_labeled_rows = max(220, int(setup_rows * 0.16))
        if len(df_target) < min_labeled_rows:
            raise ValueError(
                f"Not enough labeled rows for horizon {horizon}: {len(df_target)} "
                f"(required >= {min_labeled_rows})"
            )

        X = df_target[self.feature_cols].values
        y = df_target["target"].astype(int).values

        class_balance = float(y.mean())
        if class_balance < 0.25 or class_balance > 0.75:
            raise ValueError(f"Class balance unstable at horizon {horizon}: {class_balance:.2%}")

        split_idx = int(len(X) * 0.80)  # strict 80/20 chronological split
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        if len(X_test) < 45:
            raise ValueError(f"Test split too small for horizon {horizon}: {len(X_test)} rows")

        if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
            raise ValueError(f"Single-class split for horizon {horizon}")

        neg = int((y_train == 0).sum())
        pos = int((y_train == 1).sum())
        candidates = _build_candidates(neg, pos)
        tscv = TimeSeriesSplit(n_splits=5)

        cv_results: dict[str, dict] = {}
        best_cv_score = -1.0
        best_name = None
        best_pipeline = None

        for name, estimator in candidates:
            pipe = _pipeline(estimator)
            scores = cross_val_score(
                pipe,
                X_train,
                y_train,
                cv=tscv,
                scoring="roc_auc",
                n_jobs=-1,
                error_score=0.5,
            )
            mean_auc = float(np.mean(scores))
            std_auc = float(np.std(scores))
            cv_results[name] = {
                "cv_auc_scores": [round(float(s), 4) for s in scores],
                "cv_auc_mean": round(mean_auc, 4),
                "cv_auc_std": round(std_auc, 4),
                "cv_stability_score": round(mean_auc - 0.75 * std_auc, 4),
            }

            # Prefer consistency: robust CV score penalizes fold variance.
            cv_robust_score = mean_auc - (0.75 * std_auc)
            if cv_robust_score > best_cv_score:
                best_cv_score = cv_robust_score
                best_name = name
                best_pipeline = pipe

        if best_pipeline is None or best_name is None:
            raise RuntimeError(f"All candidate models failed for horizon {horizon}")

        walk_forward = _walk_forward_oos_auc(best_pipeline, X, y, n_splits=5)

        calibrated_model, calibration_method, calibration_details = self._select_calibrated_model(
            base_pipeline=best_pipeline,
            X_train=X_train,
            y_train=y_train,
            X_test=X_test,
            y_test=y_test,
        )

        y_prob = calibrated_model.predict_proba(X_test)[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)

        test_auc = float(roc_auc_score(y_test, y_prob)) if len(np.unique(y_test)) > 1 else 0.5
        if test_auc < MIN_TEST_AUC_ACCEPT:
            raise ValueError(
                f"Rejected horizon {horizon}: test_auc={test_auc:.4f} < {MIN_TEST_AUC_ACCEPT:.2f}"
            )

        test_acc = float(accuracy_score(y_test, y_pred))
        test_ll = float(log_loss(y_test, y_prob, labels=[0, 1]))
        prob_std = float(np.std(y_prob))
        prob_min = float(np.min(y_prob))
        prob_max = float(np.max(y_prob))
        prob_range_width = prob_max - prob_min

        up_mask = df_target["target"] == 1
        down_mask = df_target["target"] == 0

        avg_up_move = float(df_target.loc[up_mask, "future_return"].mean() * 100.0) if up_mask.any() else 0.0
        avg_down_move = float(df_target.loc[down_mask, "future_return"].mean() * 100.0) if down_mask.any() else 0.0

        metrics = {
            "horizon_bars": int(horizon),
            "best_model": best_name,
            "calibration_method": calibration_method,
            "train_samples": int(len(X_train)),
            "test_samples": int(len(X_test)),
            "class_balance": round(class_balance, 4),
            "threshold_used": round(threshold_used, 6),
            "threshold_multiplier": round(threshold_multiplier, 4),
            "noise_pct": round(noise_pct, 2),
            "test_auc": round(test_auc, 4),
            "test_accuracy": round(test_acc, 4),
            "test_logloss": round(test_ll, 4),
            "prob_std": round(prob_std, 4),
            "prob_range": [round(prob_min, 4), round(prob_max, 4)],
            "prob_range_width": round(prob_range_width, 4),
            "cv_model_stability": round(best_cv_score, 4),
            "walk_forward_auc_mean": walk_forward["auc_mean"],
            "walk_forward_auc_std": walk_forward["auc_std"],
            "walk_forward_auc_scores": walk_forward["auc_scores"],
            "walk_forward_folds": walk_forward["fold_count"],
            "cv_results": cv_results,
            "calibration_details": calibration_details,
            "n_features": len(self.feature_cols),
            "avg_up_move": round(avg_up_move, 4),
            "avg_down_move": round(avg_down_move, 4),
            "median_atr_pct": round(float(df_target["atr14_pct"].median()), 6),
            "median_vol_20": round(float(df_target["vol_20"].median()), 6),
        }

        stability_penalty = max(0.0, 0.60 - best_cv_score) * 0.50
        range_penalty = max(0.0, 0.22 - prob_range_width) * 0.40
        wf_penalty = max(0.0, 0.58 - walk_forward["auc_mean"]) * 0.60
        wf_std_penalty = max(0.0, walk_forward["auc_std"] - 0.08) * 0.80
        quality_score = (
            test_auc
            + (0.20 * prob_std)
            + (0.20 * best_cv_score)
            - (0.04 * test_ll)
            - stability_penalty
            - range_penalty
            - wf_penalty
            - wf_std_penalty
        )

        return {
            "model": calibrated_model,
            "metrics": metrics,
            "quality_score": quality_score,
            "avg_up_move": avg_up_move,
            "avg_down_move": avg_down_move,
        }

    def train(self, df: pd.DataFrame) -> dict:
        # Always retrain with the current feature schema, even if an old model was loaded before.
        self.feature_cols = get_feature_columns()
        horizon_candidates = _horizon_candidates_for_asset(self.asset)
        logger.info(f"Training {self.asset} with horizon search {horizon_candidates} ({len(df)} rows)")

        df_features = compute_features(df)
        if len(df_features) < 380:
            raise ValueError(f"Not enough feature rows after engineering: {len(df_features)}")

        horizon_results: dict[int, dict] = {}
        best_result = None

        for horizon in horizon_candidates:
            try:
                result = self._train_for_horizon(df_features, horizon)
                horizon_results[horizon] = result
                logger.info(
                    f"{self.asset} horizon={horizon}: AUC={result['metrics']['test_auc']:.4f}, "
                    f"prob_std={result['metrics']['prob_std']:.4f}, model={result['metrics']['best_model']}"
                )
                if best_result is None or result["quality_score"] > best_result["quality_score"]:
                    best_result = result
            except Exception as exc:
                logger.warning(f"{self.asset} horizon={horizon} skipped: {exc}")

        if best_result is None:
            raise RuntimeError("No viable model found for any horizon")

        selected_metrics = dict(best_result["metrics"])
        selected_horizon = int(selected_metrics["horizon_bars"])

        self.model = best_result["model"]
        self.scaler = None
        self.horizon_bars = selected_horizon
        self.best_model_name = selected_metrics["best_model"]
        self.avg_up_move = float(best_result["avg_up_move"])
        self.avg_down_move = float(best_result["avg_down_move"])
        self.threshold_used = float(selected_metrics["threshold_used"])
        self.threshold_multiplier = float(selected_metrics["threshold_multiplier"])
        self.median_atr_pct = float(selected_metrics["median_atr_pct"])
        self.median_vol_20 = float(selected_metrics["median_vol_20"])
        self.last_trained = datetime.utcnow()
        self.is_trained = True

        horizon_summary = {
            str(h): {
                "test_auc": hr["metrics"]["test_auc"],
                "prob_std": hr["metrics"]["prob_std"],
                "prob_range_width": hr["metrics"]["prob_range_width"],
                "cv_model_stability": hr["metrics"]["cv_model_stability"],
                "walk_forward_auc_mean": hr["metrics"]["walk_forward_auc_mean"],
                "walk_forward_auc_std": hr["metrics"]["walk_forward_auc_std"],
                "walk_forward_folds": hr["metrics"]["walk_forward_folds"],
                "class_balance": hr["metrics"]["class_balance"],
                "best_model": hr["metrics"]["best_model"],
                "calibration_method": hr["metrics"]["calibration_method"],
            }
            for h, hr in horizon_results.items()
        }

        selected_metrics.update(
            {
                "asset": self.asset,
                "selected_horizon": selected_horizon,
                "horizon_candidates": horizon_summary,
                "horizon_tested": list(horizon_candidates),
                "quality_score": round(float(best_result["quality_score"]), 6),
                "trained_at": self.last_trained.isoformat(),
            }
        )

        self.train_metrics = selected_metrics

        self._save()

        logger.info(
            f"Trained {self.asset}: horizon={selected_horizon}, model={self.best_model_name}, "
            f"AUC={selected_metrics['test_auc']:.4f}, prob_std={selected_metrics['prob_std']:.4f}"
        )
        return self.train_metrics

    def predict(self, df: pd.DataFrame) -> dict:
        if not self.is_trained:
            self._load()
        if not self.is_trained:
            raise RuntimeError(f"Model for {self.asset} not trained. Call /retrain.")

        df_feat = compute_features(df).dropna(subset=self.feature_cols)
        if df_feat.empty:
            raise ValueError("No valid rows after feature computation")

        latest = df_feat[self.feature_cols].iloc[-1:].values
        if self.scaler is not None:
            latest_input = self.scaler.transform(latest)
        else:
            latest_input = latest

        prob_up = float(self.model.predict_proba(latest_input)[0, 1])
        prob_down = 1.0 - prob_up

        atr_pct = float(df_feat["atr14_pct"].iloc[-1])
        vol_20 = float(df_feat["vol_20"].iloc[-1])
        adx_val = float(df_feat["adx"].iloc[-1])
        is_trending = float((adx_val * 100.0) >= 20.0)
        trend_regime = float(df_feat["trend_regime"].iloc[-1])
        trend_phase = float(df_feat["trend_phase"].iloc[-1]) if "trend_phase" in df_feat.columns else 0.0
        vol_regime = float(df_feat["vol_regime"].iloc[-1])

        confidence = abs(prob_up - 0.5)
        signal_strength = confidence * 2.0
        confidence_score = round(min(100.0, confidence * 220.0), 1)

        ev_raw = (prob_up * self.avg_up_move) + (prob_down * self.avg_down_move)

        expected_return_pct = self.avg_up_move if prob_up >= 0.5 else self.avg_down_move

        atr_floor = max(MIN_ATR_PCT, self.median_atr_pct * 0.65)
        vol_floor = max(1e-6, self.median_vol_20 * 0.65)
        dynamic_prob_threshold = 0.66 if atr_pct < atr_floor else MIN_PROB_THRESHOLD
        retracement_setup = float(df_feat["retracement_setup"].iloc[-1]) if "retracement_setup" in df_feat.columns else 0.0
        fvg_setup = float(df_feat["fvg_setup"].iloc[-1]) if "fvg_setup" in df_feat.columns else 0.0
        setup_active = max(retracement_setup, fvg_setup) > 0.5

        reject_reason = None
        if atr_pct < atr_floor:
            reject_reason = f"Volatility too low (ATR {atr_pct * 100:.4f}% < {atr_floor * 100:.4f}%)"
        elif vol_20 < vol_floor:
            reject_reason = f"Realized vol too low ({vol_20:.6f} < {vol_floor:.6f})"
        elif adx_val * 100.0 < 20.0:
            reject_reason = f"ADX too low ({adx_val * 100.0:.1f} < 20.0)"
        elif trend_regime < 0.45:
            reject_reason = "Trend regime too weak"
        elif trend_phase < 0.5:
            reject_reason = "Trend phase inactive (slope/breakout filter)"
        elif not setup_active:
            reject_reason = "No active continuation setup (retracement/FVG)"
        elif vol_regime < MIN_VOL_REGIME:
            reject_reason = f"Volatility regime inactive ({vol_regime:.3f} < {MIN_VOL_REGIME:.2f})"
        elif max(prob_up, prob_down) < dynamic_prob_threshold:
            reject_reason = (
                f"Probability {max(prob_up, prob_down) * 100:.1f}% "
                f"below threshold {dynamic_prob_threshold * 100:.0f}%"
            )
        elif confidence < MIN_CONFIDENCE:
            reject_reason = f"Confidence {confidence:.4f} < {MIN_CONFIDENCE:.4f}"
        elif confidence_score < MIN_CONFIDENCE_SCORE:
            reject_reason = f"Confidence score {confidence_score:.1f} < {MIN_CONFIDENCE_SCORE:.1f}"
        elif ev_raw <= 0:
            reject_reason = f"EV {ev_raw:.4f}% <= 0"

        return {
            "up_probability": round(prob_up * 100.0, 2),
            "down_probability": round(prob_down * 100.0, 2),
            "avg_up_move": round(self.avg_up_move, 4),
            "avg_down_move": round(self.avg_down_move, 4),
            "expected_return_pct": round(expected_return_pct, 4),
            "expected_value_pct": round(ev_raw, 4),
            "signal_strength": round(signal_strength, 4),
            "confidence": round(confidence, 4),
            "confidence_score": confidence_score,
            "reject_reason": reject_reason,
            "atr_pct": round(atr_pct * 100.0, 4),
            "volatility_5bar": round(vol_20 * 100.0, 4),
            "adx": round(adx_val * 100.0, 1),
            "is_trending": bool(is_trending),
            "trend_regime": round(trend_regime, 3),
            "trend_phase": round(trend_phase, 3),
            "vol_regime": round(vol_regime, 3),
            "retracement_setup": bool(retracement_setup > 0.5),
            "fvg_setup": bool(fvg_setup > 0.5),
            "setup_active": bool(setup_active),
            "min_prob_threshold": round(dynamic_prob_threshold * 100.0, 2),
            "last_rsi": round(float(df_feat["rsi14_norm"].iloc[-1] * 50.0 + 50.0), 2),
            "last_macd_hist": round(float(df_feat["macd_hist"].iloc[-1]), 8),
            "last_bb_pct": None,
            "current_price": float(df_feat["close"].iloc[-1]),
            "timestamp": str(df_feat.index[-1])
        }

    def _save(self):
        joblib.dump(
            {
                "model": self.model,
                "scaler": self.scaler,
                "feature_cols": self.feature_cols,
                "metrics": self.train_metrics,
                "last_trained": self.last_trained,
                "horizon_bars": self.horizon_bars,
                "best_model_name": self.best_model_name,
                "avg_up_move": self.avg_up_move,
                "avg_down_move": self.avg_down_move,
                "threshold_used": self.threshold_used,
                "threshold_multiplier": self.threshold_multiplier,
                "median_atr_pct": self.median_atr_pct,
                "median_vol_20": self.median_vol_20,
            },
            self._model_path(),
        )
        logger.info(f"Saved model {self.asset} -> {self._model_path()}")

    def _load(self):
        model_path = self._model_path()
        if not os.path.exists(model_path):
            return

        data = joblib.load(model_path)
        self.model = data["model"]
        self.scaler = data.get("scaler")
        self.feature_cols = data.get("feature_cols", get_feature_columns())
        self.train_metrics = data.get("metrics", {})
        self.last_trained = data.get("last_trained")
        self.horizon_bars = data.get("horizon_bars", 8)
        self.best_model_name = data.get("best_model_name")
        self.avg_up_move = data.get("avg_up_move", 0.0)
        self.avg_down_move = data.get("avg_down_move", 0.0)
        self.threshold_used = data.get("threshold_used", 0.0)
        self.threshold_multiplier = data.get("threshold_multiplier", 1.0)
        self.median_atr_pct = data.get("median_atr_pct", 0.0)
        self.median_vol_20 = data.get("median_vol_20", 0.0)
        self.is_trained = True
        logger.info(f"Loaded model {self.asset} (trained at {self.last_trained})")


_registry: dict[str, TradingModel] = {}


def get_model(asset: str) -> TradingModel:
    if asset not in _registry:
        _registry[asset] = TradingModel(asset)
    return _registry[asset]


async def train_all_models() -> dict:
    from services.data_service import get_supported_assets

    results = {}
    for asset_info in get_supported_assets():
        asset = asset_info["id"]
        try:
            df = fetch_ohlcv(asset, interval="30m", lookback_days=TRAIN_LOOKBACK_DAYS)
            model = get_model(asset)
            results[asset] = {"status": "success", **model.train(df)}
        except Exception as exc:
            logger.error(f"Failed to train {asset}: {exc}")
            results[asset] = {"status": "error", "error": str(exc)}
    return results
