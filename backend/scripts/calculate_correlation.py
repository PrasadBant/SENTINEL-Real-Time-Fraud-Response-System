import requests
import time
import random
import uuid
from datetime import datetime, timezone
import numpy as np

API_URL = "http://127.0.0.1:8000/transaction"


def generate_sample_tx():
    """
    Generates diverse transaction payloads across 4 risk tiers.
    All are Hop 0 (origin) so the Rule Engine scores them directly.
    Risk flags are passed via tx-level fields (not just simulator_meta)
    so the scoring_engine picks them up reliably.
    """
    scenarios = ["NORMAL", "HIGH_AMOUNT", "VELOCITY", "CALL_FRAUD"]
    scenario = random.choice(scenarios)

    if scenario == "NORMAL":
        tx = {
            "amount": round(random.uniform(500, 8000), 2),
            "on_active_call": False,
            "simulator_meta": {"is_new_receiver": False, "tx_velocity": 1}
        }
    elif scenario == "HIGH_AMOUNT":
        tx = {
            "amount": round(random.uniform(200000, 450000), 2),
            "on_active_call": False,
            "is_cross_border": True,       # triggers high rule scores
            "simulator_meta": {"is_new_receiver": True, "tx_velocity": 2}
        }
    elif scenario == "VELOCITY":
        tx = {
            "amount": round(random.uniform(50000, 150000), 2),
            "on_active_call": False,
            "velocity_flag": True,          # triggers velocity_spike rule factor
            "simulator_meta": {"is_new_receiver": True, "tx_velocity": 15}
        }
    else:  # CALL_FRAUD
        tx = {
            "amount": round(random.uniform(30000, 80000), 2),
            "on_active_call": True,
            "is_scripted": True,
            "simulator_meta": {"is_new_receiver": True, "tx_velocity": 3}
        }

    # Shared fields
    tx.update({
        "tx_id": f"CORR-{str(uuid.uuid4())[:6].upper()}",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sender_account": f"ACC-COR-{random.randint(1000,9999)}",
        "receiver_account": f"ACC-COR-{random.randint(1000,9999)}",
        "currency": "INR",
        "channel": "IMPS",
        "hop_number": 0,     # always origin hop for clean scoring
    })
    return tx, scenario


def run_correlation_test(n=10):
    print(f"Generating {n} samples for correlation analysis...")
    print("-" * 60)
    rule_scores = []
    ml_scores = []

    for i in range(n):
        tx, scenario = generate_sample_tx()
        try:
            resp = requests.post(API_URL, json=tx)
            data = resp.json()
            tx_data = data.get("transaction", {})
            r_score = tx_data.get("rule_score", 0)
            m_score = tx_data.get("ml_score", 0)
            h_score = tx_data.get("risk_score", 0)

            rule_scores.append(r_score)
            ml_scores.append(m_score)
            print(f"Sample {i+1:2d} [{scenario:<12}] Rule={r_score:3d}, ML={m_score:3d} | Hybrid={h_score:3d}")
        except Exception as e:
            print(f"Error at sample {i+1}: {e}")
        time.sleep(0.3)

    if len(rule_scores) < 2:
        print("Not enough data to calculate correlation.")
        return

    rule_arr = np.array(rule_scores, dtype=float)
    ml_arr = np.array(ml_scores, dtype=float)

    # Handle constant arrays (edge case)
    if rule_arr.std() == 0 or ml_arr.std() == 0:
        print("\nAll scores are identical — cannot compute correlation.")
        print(f"Rule scores: {rule_scores}")
        print(f"ML   scores: {ml_scores}")
        return

    correlation = np.corrcoef(rule_arr, ml_arr)[0, 1]

    print("\n" + "=" * 60)
    print("CORRELATION ANALYSIS RESULTS")
    print("=" * 60)
    print(f"Sample Size   : {len(rule_scores)}")
    print(f"Avg Rule Score: {rule_arr.mean():.2f}  (std={rule_arr.std():.2f})")
    print(f"Avg ML Score  : {ml_arr.mean():.2f}  (std={ml_arr.std():.2f})")
    print(f"Pearson r     : {correlation:.4f}")
    print("=" * 60)

    if correlation > 0.90:
        print("RESULT: EXCELLENT — Rule-ML alignment is near-perfect (r > 0.90)")
    elif correlation > 0.75:
        print("RESULT: GOOD — Engines are well-aligned (r > 0.75)")
    elif correlation > 0.5:
        print("RESULT: MODERATE — Some alignment exists (r > 0.50)")
    else:
        print("RESULT: LOW CORRELATION — Engines have divergent views")

    # Deviation summary
    deviations = np.abs(rule_arr - ml_arr)
    print(f"\nAvg Deviation  : {deviations.mean():.2f} points")
    print(f"Max Deviation  : {deviations.max():.2f} points")


if __name__ == "__main__":
    run_correlation_test(10)
