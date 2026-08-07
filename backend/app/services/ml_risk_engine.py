"""
SENTINEL ML Risk Engine
=======================
Mode 1 (XGB_MODEL_AVAILABLE=True):  real fraud-probability inference from a
    trained XGBoost classifier (see scripts/train_xgb_model.py — trains on
    15k synthetic transactions labeled by a set of independent fraud
    heuristics, distinct from the rule engine's own weighting, so the two
    signals aren't just restating each other).
Mode 2 (XGB_MODEL_AVAILABLE=False): Rule-Guided Emulator fallback — adds
    bounded noise around the rule score. Used only if xgboost/joblib/numpy
    aren't installed or app/data/xgb_model.joblib is missing; never claims
    to be a trained model.

An earlier version of this module also had a "GNN" scoring path
(FraudGraphSAGE, PyTorch Geometric) — it was never trained, just a
randomly-initialized network whose output was indistinguishable from
noise. It's been removed rather than left in place pretending to be real
graph-based inference. If real GNN scoring is wanted later, it needs an
actual training pipeline over labeled case graphs, not hand-set weights.
"""

import random
import os

XGB_MODEL_AVAILABLE = False
_xgb_model = None

try:
    import joblib
    import numpy as np
    import xgboost as xgb
    model_path = os.path.join(os.path.dirname(__file__), "../data/xgb_model.joblib")
    if os.path.exists(model_path):
        _xgb_model = joblib.load(model_path)
        XGB_MODEL_AVAILABLE = True
        print(f"  [ML Engine] XGBoost model loaded from {model_path}")
except ImportError:
    print("  [ML Engine] joblib/numpy/xgboost not found — XGB disabled")
except Exception as _e:
    print(f"  [ML Engine] XGB init error ({_e})")


# ── Feature metadata (used by orchestrator for importance display) ────────────
feature_names = ["amount", "hour", "is_new_receiver", "velocity", "chain_depth", "call_flag"]


# ── Public API ────────────────────────────────────────────────────────────────

def predict_ml_score(rule_score: float, tx: dict = None, account: dict = None) -> float:
    """
    If the trained XGBoost model is available, use it to predict fraud
    probability. Otherwise, fall back to the rule-guided emulator.
    """
    if XGB_MODEL_AVAILABLE and _xgb_model and tx is not None and account is not None:
        try:
            from datetime import datetime as _dt
            sim_meta = tx.get("simulator_meta", {})

            ts = tx.get("timestamp", "")
            try:
                dt = _dt.fromisoformat(ts.replace("Z", "+00:00"))
                hour_val = dt.hour / 23.0
            except Exception:
                hour_val = 0.5

            amount_val = min(float(tx.get("amount", 0)) / 500000.0, 1.0)
            velocity_raw = sim_meta.get("tx_velocity", account.get("tx_velocity", 1))
            velocity_val = min(float(velocity_raw) / 15.0, 1.0)
            is_new_raw = sim_meta.get("is_new_receiver", account.get("is_new_receiver", False))
            is_new_val = 1.0 if is_new_raw else 0.08
            call_val = 1.0 if tx.get("on_active_call", False) else 0.04
            hop_val = min(float(tx.get("hop_number", 0)) / 5.0, 1.0)

            features = np.array([[amount_val, hour_val, is_new_val, velocity_val, hop_val, call_val]])
            prob = _xgb_model.predict_proba(features)[0][1] # Probability of fraud (class 1)

            xgb_score = float(prob * 100.0)
            print(f"  [ML Engine] XGBoost score: {xgb_score:.1f}")
            return xgb_score
        except Exception as e:
            print(f"  [ML Engine] XGB prediction error: {e}")

    # Fallback to emulator
    if rule_score >= 80:
        noise = random.uniform(-5, 5)
    elif rule_score >= 50:
        noise = random.uniform(-10, 10)
    else:
        noise = random.uniform(-15, 15)

    return max(0.0, min(100.0, rule_score + noise))
