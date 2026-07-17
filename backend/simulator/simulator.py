import requests
import time
import random
import string
import uuid
from datetime import datetime, timezone

API_URL = "http://127.0.0.1:8000/transaction"

# ─── Channel Amount Caps ───────────────────────────────────────────────────────
CHANNEL_CAPS = {
    "UPI":     100000,
    "IMPS":    500000,
    "NEFT":    500000,
    "CARD":    200000,
}

def _generate_tx_id():
    return f"TX-{str(uuid.uuid4())[:8].upper()}"

def _generate_timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _random_account(prefix="ACC"):
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{suffix}-{random.randint(1000, 9999)}"

def _pick_channel():
    return random.choice(list(CHANNEL_CAPS.keys()))

def _cap_amount(amount, channel):
    return min(amount, CHANNEL_CAPS.get(channel, 500000))

def _run_forked_scenario(name, start_prefix, amount_range, extra_flags=None):
    print(f"Executing Scenario {name} (Forked Style)...")
    channel = _pick_channel()
    base_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    victim = f"{start_prefix}-{base_id}"

    low, high = amount_range
    high = min(high, CHANNEL_CAPS.get(channel, 500000))
    total_amount = round(random.uniform(low, high), 2)

    max_hops = random.randint(1, 4)
    queue = [(victim, total_amount, 0, None)]

    while queue:
        sender, amount, hop, case_id = queue.pop(0)
        if hop >= max_hops: continue

        num_branches = 2 if hop == 1 else 1
        branch_amount = amount / num_branches

        for _ in range(num_branches):
            prefix = "ACC-LAYER1" if hop == 0 else f"ACC-MULE-H{hop}"
            if hop == max_hops - 1: prefix = "ACC-EXIT"

            receiver = _random_account(prefix)
            tx = {
                "tx_id": _generate_tx_id(),
                "timestamp": _generate_timestamp(),
                "sender_account": sender,
                "receiver_account": receiver,
                "amount": round(_cap_amount(branch_amount, channel), 2),
                "currency": "INR",
                "channel": channel,
                "hop_number": hop,
                "case_id": case_id
            }
            if extra_flags:
                tx.update(extra_flags)

            try:
                resp = requests.post(API_URL, json=tx)
                data = resp.json()
                res_tx = data.get("transaction") or {}
                res_case = data.get("case") or {}
                case_id = res_tx.get("case_id") or res_case.get("case_id") or case_id
                print(f"  {name} Hop {hop}: {sender} -> {receiver} | Amt: {tx['amount']} | Ch: {channel}")

                if hop < max_hops - 1:
                    queue.append((receiver, branch_amount * 0.98, hop + 1, case_id))
            except Exception as e:
                print(f"  Error: {e}")
            time.sleep(0.3)

# ─── HIGH RISK Scenarios ──────────────────────────────────────────────────────
def run_sc01_mule_chain():
    _run_forked_scenario("SC-01", "ACC-VICTIM", (200000, 500000))

def run_sc05_cross_border_fraud():
    _run_forked_scenario("SC-05", "ACC-VICTIM", (150000, 400000), extra_flags={"is_cross_border": True})

def run_sc06_account_takeover():
    _run_forked_scenario("SC-06", "ACC-VICTIM", (100000, 300000), extra_flags={"device_changed": True, "location_changed": True})

def run_sc08_crypto_drain():
    _run_forked_scenario("SC-08", "ACC-VICTIM", (200000, 500000), extra_flags={"is_crypto_related": True})

# ─── MEDIUM RISK Scenarios ────────────────────────────────────────────────────
def run_sc02_sim_swap():
    print("Executing Scenario SC-02: SIM Swap (MEDIUM)...")
    channel = _pick_channel()
    amount = round(random.uniform(25000, 95000), 2)
    amount = _cap_amount(amount, channel)
    tx = {
        "tx_id": _generate_tx_id(), "timestamp": _generate_timestamp(),
        "sender_account": _random_account("ACC-USR"), "receiver_account": _random_account("ACC-DRAIN"),
        "amount": amount, "currency": "INR", "channel": channel,
        "on_active_call": True, "is_scripted": True
    }
    try:
        resp = requests.post(API_URL, json=tx)
        data = resp.json().get("transaction") or {}
        print(f"  SIM Swap Alert | Amount: {tx['amount']} | Score: {data.get('risk_score', 0)}")
    except: pass

def run_sc11_aggregation_mule():
    print("Executing Scenario SC-11: Aggregation (MEDIUM)...")
    channel = _pick_channel()
    mule = _random_account("ACC-AGGR-MULE")
    case_id = None
    for _ in range(2):
        victim = _random_account("ACC-VICTIM")
        amount = _cap_amount(round(random.uniform(50000, 150000), 2), channel)
        tx = {
            "tx_id": _generate_tx_id(), "timestamp": _generate_timestamp(),
            "sender_account": victim, "receiver_account": mule,
            "amount": amount, "currency": "INR", "channel": channel,
            "case_id": case_id, "bulk_transfer_flag": True
        }
        try:
            resp = requests.post(API_URL, json=tx)
            case_id = resp.json().get("transaction", {}).get("case_id")
        except: pass
        time.sleep(0.5)

# ─── LOW RISK Scenarios ───────────────────────────────────────────────────────
def run_sc03_low_risk():
    print("Executing Scenario SC-03: Low Risk (ROUTINE)...")
    channel = _pick_channel()
    amount = _cap_amount(round(random.uniform(100, 9000), 2), channel)
    tx = {
        "tx_id": _generate_tx_id(), "timestamp": _generate_timestamp(),
        "sender_account": _random_account("ACC-USR"), "receiver_account": _random_account("ACC-MERCH"),
        "amount": amount, "currency": "INR", "channel": channel
    }
    try:
        requests.post(API_URL, json=tx)
        print(f"  Routine TX | Amount: {tx['amount']} | Ch: {channel}")
    except: pass

def run_sc07_small_payment():
    print("Executing Scenario SC-07: Small Payment (ROUTINE)...")
    channel = random.choice(["UPI", "CARD"])
    amount = _cap_amount(round(random.uniform(50, 5000), 2), channel)
    tx = {
        "tx_id": _generate_tx_id(), "timestamp": _generate_timestamp(),
        "sender_account": _random_account("ACC-RETAIL"), "receiver_account": _random_account("ACC-SHOP"),
        "amount": amount, "currency": "INR", "channel": channel
    }
    try:
        requests.post(API_URL, json=tx)
        print(f"  Small Payment | Amount: {tx['amount']} | Ch: {channel}")
    except: pass

def run_sc04_velocity_attack():
    print("Executing Scenario SC-04: Velocity Attack (LOW-MEDIUM)...")
    channel = _pick_channel()
    sender = _random_account("ACC-USR")
    receiver = _random_account("ACC-MERCH")
    for _ in range(3):
        amount = _cap_amount(round(random.uniform(10, 50), 2), channel)
        tx = {
            "tx_id": _generate_tx_id(), "timestamp": _generate_timestamp(),
            "sender_account": sender, "receiver_account": receiver,
            "amount": amount, "channel": channel, "velocity_flag": True
        }
        try:
            requests.post(API_URL, json=tx)
        except: pass
        time.sleep(0.5)

# ─── Main Loop: Equal risk distribution, 6 tx/min ─────────────────────────────
HIGH_RISK_SCENARIOS  = [run_sc01_mule_chain, run_sc05_cross_border_fraud, run_sc06_account_takeover, run_sc08_crypto_drain]
MEDIUM_RISK_SCENARIOS = [run_sc02_sim_swap, run_sc11_aggregation_mule]
LOW_RISK_SCENARIOS   = [run_sc03_low_risk, run_sc07_small_payment, run_sc04_velocity_attack]

if __name__ == "__main__":
    print("SENTINEL Simulator Started — 6 tx/min | Equal Risk Distribution (Ctrl+C to stop)")
    while True:
        # Pick one tier at equal probability (1/3 each), then random scenario within
        tier = random.choice(["HIGH", "MEDIUM", "LOW"])
        if tier == "HIGH":
            random.choice(HIGH_RISK_SCENARIOS)()
        elif tier == "MEDIUM":
            random.choice(MEDIUM_RISK_SCENARIOS)()
        else:
            random.choice(LOW_RISK_SCENARIOS)()

        time.sleep(10)  # 6 transactions per minute
