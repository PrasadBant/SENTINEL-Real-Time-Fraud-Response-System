"""
SENTINEL ML Risk Engine
=======================
Mode 1 (GNN_AVAILABLE=True):  Real GraphSAGE forward pass on live case graph.
Mode 2 (GNN_AVAILABLE=False): Rule-Guided Emulator fallback (no dependencies needed).

The GNN accepts a 6-dimensional node feature vector per account node:
  [normalized_amount, normalized_hour, is_new_receiver, normalized_velocity,
   normalized_chain_depth, call_flag]

Graph-level risk = mean sigmoid score across all nodes, scaled to [0, 100].
"""

import random
import os

from app.core.constants import AccountStatus

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

# ── Try to import PyTorch Geometric stack ────────────────────────────────────
GNN_AVAILABLE = False
_gnn_model = None

try:
    import torch
    import torch.nn.functional as F
    from torch_geometric.nn import SAGEConv

    class FraudGraphSAGE(torch.nn.Module):
        """2-layer GraphSAGE for node-level fraud probability."""
        IN_CHANNELS = 6
        HIDDEN = 16

        def __init__(self):
            super().__init__()
            self.conv1 = SAGEConv(self.IN_CHANNELS, self.HIDDEN)
            self.conv2 = SAGEConv(self.HIDDEN, self.HIDDEN)
            self.fc = torch.nn.Linear(self.HIDDEN, 1)

        def forward(self, x, edge_index):
            x = F.relu(self.conv1(x, edge_index))
            x = F.dropout(x, p=0.2, training=self.training)
            x = F.relu(self.conv2(x, edge_index))
            x = F.dropout(x, p=0.2, training=self.training)
            return torch.sigmoid(self.fc(x)).squeeze(-1)

    _gnn_model = FraudGraphSAGE()
    _gnn_model.eval()
    GNN_AVAILABLE = True
    print("  [ML Engine] FraudGraphSAGE loaded (PyTorch Geometric available)")

except ImportError:
    print("  [ML Engine] PyTorch Geometric not found — using Rule-Guided Emulator fallback")
except Exception as _e:
    print(f"  [ML Engine] GNN init error ({_e}) — using Rule-Guided Emulator fallback")


# ── Feature metadata (used by orchestrator for importance display) ────────────
feature_names = ["amount", "hour", "is_new_receiver", "velocity", "chain_depth", "call_flag"]
model = _gnn_model  # expose for compatibility


# ── Public API ────────────────────────────────────────────────────────────────

def predict_gnn_score(graph_nodes: list, graph_edges: list, rule_score: float) -> float:
    """
    Run a real GraphSAGE forward pass on the current case graph.

    Args:
        graph_nodes: list of node dicts from store["graphs"][case_id]["nodes"]
        graph_edges: list of edge dicts from store["graphs"][case_id]["edges"]
        rule_score:  fallback rule score (0–100) for blending

    Returns:
        float in [0, 100] — hybrid GNN+Rule score
    """
    if not GNN_AVAILABLE or _gnn_model is None:
        return predict_ml_score(rule_score, {}, {})

    if not graph_nodes:
        return predict_ml_score(rule_score, {}, {})

    try:
        import torch as _torch

        # ── Build node-id → index map ─────────────────────────────────────
        node_ids = [
            str(n.get("account_id") or n.get("id") or n.get("accountId", f"N{i}"))
            for i, n in enumerate(graph_nodes)
        ]
        id_to_idx = {nid: i for i, nid in enumerate(node_ids)}
        N = len(graph_nodes)

        # ── Build feature matrix X  [N, 6] ───────────────────────────────
        rows = []
        for node in graph_nodes:
            balance   = float(node.get("balance", 0.0))
            status    = node.get("status", AccountStatus.ACTIVE)
            # Features derived from node metadata (best-effort)
            feat_amount   = min(balance / 500_000.0, 1.0)
            feat_hour     = 0.5          # not stored per-node; use neutral
            feat_new_recv = 1.0 if status == AccountStatus.ACTIVE else 0.1
            feat_velocity = 0.5          # neutral default
            feat_depth    = 0.3          # neutral default
            feat_call     = 0.0
            rows.append([feat_amount, feat_hour, feat_new_recv,
                         feat_velocity, feat_depth, feat_call])

        x = _torch.tensor(rows, dtype=_torch.float)

        # ── Build edge_index [2, E] ───────────────────────────────────────
        src_list, dst_list = [], []
        for edge in graph_edges:
            src_id = str(edge.get("source") or edge.get("from") or "")
            dst_id = str(edge.get("target") or edge.get("to") or "")
            if src_id in id_to_idx and dst_id in id_to_idx:
                src_list.append(id_to_idx[src_id])
                dst_list.append(id_to_idx[dst_id])

        if src_list:
            edge_index = _torch.tensor([src_list, dst_list], dtype=_torch.long)
        else:
            # Self-loops fallback so conv doesn't crash on isolated nodes
            idx = list(range(N))
            edge_index = _torch.tensor([idx, idx], dtype=_torch.long)

        # ── Forward pass ─────────────────────────────────────────────────
        with _torch.no_grad():
            node_scores = _gnn_model(x, edge_index)  # [N]
            gnn_score = float(node_scores.mean().item()) * 100.0

        # ── Blend: 50% GNN + 50% Rule ────────────────────────────────────
        hybrid = 0.5 * gnn_score + 0.5 * rule_score
        hybrid = max(0.0, min(100.0, hybrid))

        print(f"  [GNN Engine] GNN={round(gnn_score,1)}, Rule={round(rule_score,1)}, Hybrid={round(hybrid,1)}")
        return hybrid

    except Exception as _e:
        print(f"  [GNN Engine] Inference failed ({_e}) — falling back to emulator")
        return predict_ml_score(rule_score, {}, {})


def predict_ml_score(rule_score: float, tx: dict = None, account: dict = None) -> float:
    """
    If XGBoost model is available, use it to predict fraud probability.
    Otherwise, fall back to Rule-Guided ML Emulator.
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


def normalize_features(features: list) -> list:
    """Kept for backward compatibility — not used in GNN/emulator mode."""
    if not features or len(features) < 6:
        return features
    return [
        min(features[0] / 100_000, 1.0),
        features[1] / 23.0,
        features[2],
        min(features[3] / 10, 1.0),
        min(features[4] / 5, 1.0),
        features[5]
    ]
