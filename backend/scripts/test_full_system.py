"""
SENTINEL Full Backend Integration Test
Tests every major backend feature against the live API at port 8000.
"""
import requests
import time
import uuid
from datetime import datetime, timezone

BASE = "http://127.0.0.1:8000"

PASS = 0
FAIL = 0

def _tx_id():
    return f"TEST-{str(uuid.uuid4())[:8].upper()}"

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} — {detail}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ─── Test 1: Health Check ────────────────────────────────────────────────────
section("TEST 1: Health Check")
r = requests.get(f"{BASE}/health")
check("Health endpoint returns 200", r.status_code == 200)
check("Health body has status=ok", r.json().get("status") == "ok")

# ─── Test 2: Normal Transaction (Low Risk) ───────────────────────────────────
section("TEST 2: Normal Transaction (LOW risk)")
tx_normal = {
    "tx_id": _tx_id(), "timestamp": _now(),
    "sender_account": "ACC-TEST-NORM-001", "receiver_account": "ACC-RECV-001",
    "amount": 1500, "currency": "INR", "channel": "UPI", "hop_number": 0,
    "simulator_meta": {"is_new_receiver": False, "tx_velocity": 1}
}
r = requests.post(f"{BASE}/transaction", json=tx_normal)
check("Normal TX returns 200", r.status_code == 200)
data = r.json()
tx = data.get("transaction", {})
check("Response has 'transaction' key", bool(tx))
check("Rule score present", "rule_score" in tx)
check("ML score present", "ml_score" in tx)
check("Hybrid risk_score present", "risk_score" in tx)
check("Reason present", bool(tx.get("reason")))
check("ml_feature_importance present", bool(tx.get("ml_feature_importance")))
check("Threshold is LOW", tx.get("threshold") == "LOW", f"Got: {tx.get('threshold')}")

# ─── Test 3: High Risk Transaction (Mule Chain Hop 0) ────────────────────────
section("TEST 3: High Risk Transaction (HIGH risk + Case creation)")
tx_high = {
    "tx_id": _tx_id(), "timestamp": _now(),
    "sender_account": "ACC-TEST-VICTIM-001", "receiver_account": "ACC-TEST-MULE-001",
    "amount": 350000, "currency": "INR", "channel": "IMPS", "hop_number": 0,
    "on_active_call": True, "is_cross_border": True,
    "simulator_meta": {"is_new_receiver": True, "tx_velocity": 8}
}
r = requests.post(f"{BASE}/transaction", json=tx_high)
check("High Risk TX returns 200", r.status_code == 200)
data = r.json()
tx_h = data.get("transaction", {})
case = data.get("case", {})
check("High risk score >= 70", tx_h.get("risk_score", 0) >= 70,
      f"Got: {tx_h.get('risk_score')}")
check("Threshold is HIGH_RISK", tx_h.get("threshold") == "HIGH_RISK",
      f"Got: {tx_h.get('threshold')}")
check("Case was created", bool(case and case.get("case_id")),
      f"Case: {case}")
check("ml_feature_importance is populated", len(tx_h.get("ml_feature_importance", {})) > 0)
check("ML score within 15 pts of Rule score",
      abs(tx_h.get("ml_score", 0) - tx_h.get("rule_score", 0)) <= 15,
      f"Rule={tx_h.get('rule_score')}, ML={tx_h.get('ml_score')}")
case_id = case.get("case_id") if case else None
hop0_hybrid = tx_h.get("risk_score", 0)
hop0_rule   = tx_h.get("rule_score", 0)
print(f"    Rule={tx_h.get('rule_score')}, ML={tx_h.get('ml_score')}, Hybrid={hop0_hybrid}, Case={case_id}")

# ─── Test 4: Mule Chain Risk Decay (Hop 1) ───────────────────────────────────
section("TEST 4: Mule Chain Risk Decay (Hop 1)")
if case_id:
    time.sleep(0.5)
    tx_hop1 = {
        "tx_id": _tx_id(), "timestamp": _now(),
        "sender_account": "ACC-TEST-MULE-001", "receiver_account": "ACC-TEST-EXIT-001",
        "amount": 150000, "currency": "INR", "channel": "NEFT",
        "hop_number": 1, "case_id": case_id,
        "simulator_meta": {"is_new_receiver": True, "tx_velocity": 1}
    }
    r = requests.post(f"{BASE}/transaction", json=tx_hop1)
    check("Hop 1 TX returns 200", r.status_code == 200)
    hop1_tx = r.json().get("transaction", {})
    hop1_rule = hop1_tx.get("rule_score", 0)
    hop1_hybrid = hop1_tx.get("risk_score", 0)
    expected_rule = int(hop0_rule * 0.85)
    check("Rule score decayed by 0.85 factor",
          hop1_rule == expected_rule,
          f"Expected {expected_rule}, got {hop1_rule}")
    check("Hybrid score is lower than Hop 0",
          hop1_hybrid < hop0_hybrid,
          f"Hop 0={hop0_hybrid}, Hop 1={hop1_hybrid}")
    print(f"    Hop 0 Rule={hop0_rule} -> Hop 1 Rule={hop1_rule} (expected {expected_rule})")
else:
    print("  [SKIP] No case_id available — skipping decay test")

# ─── Test 5: GET /cases ───────────────────────────────────────────────────────
section("TEST 5: GET /cases — Case listing")
r = requests.get(f"{BASE}/cases")
check("GET /cases returns 200", r.status_code == 200)
cases = r.json()
check("Cases is a list", isinstance(cases, list))
check("At least 1 case exists", len(cases) >= 1, f"Got {len(cases)} cases")
if cases:
    c = cases[0]
    check("Case has case_id", bool(c.get("case_id")))
    check("Case has nodes list", isinstance(c.get("nodes"), list))
    check("Case has edges list", isinstance(c.get("edges"), list))
    check("Case has actionLog", isinstance(c.get("actionLog"), list))
    check("Case has risk_level", "risk_level" in c)
    check("Case has recoverable_amount", "recoverable_amount" in c)

# ─── Test 6: Action — Freeze Account ────────────────────────────────────────
section("TEST 6: POST /action/freeze — Investigator Action")
if case_id:
    payload = {"case_id": case_id, "account_id": "ACC-TEST-MULE-001",
               "reason": "Confirmed mule from automated test"}
    r = requests.post(f"{BASE}/action/freeze", json=payload)
    check("Freeze action returns 200", r.status_code == 200)
    res = r.json()
    check("ok=True in freeze response", res.get("ok") == True,
          f"Got: {res}")
    check("action_id in freeze response", bool(res.get("action_id")))

    # Verify it was recorded
    r2 = requests.get(f"{BASE}/cases")
    found = next((c for c in r2.json() if c["case_id"] == case_id), None)
    if found:
        actions = found.get("actionLog", [])
        check("Freeze action recorded in case actionLog",
              any("FREEZE" in (a.get("action_type","")).upper() for a in actions),
              f"Actions: {actions}")
else:
    print("  [SKIP] No case_id — skipping freeze test")

# ─── Test 7: Action — Alert ──────────────────────────────────────────────────
section("TEST 7: POST /action/alert — Police Alert")
if case_id:
    r = requests.post(f"{BASE}/action/alert",
                      json={"case_id": case_id, "reason": "Automated test escalation"})
    check("Alert action returns 200", r.status_code == 200)
    check("Alert ok=True", r.json().get("ok") == True)

# ─── Test 8: Attack Mode Burst ───────────────────────────────────────────────
section("TEST 8: POST /attack-mode — Fraud Burst Injection")
r = requests.post(f"{BASE}/attack-mode")
check("Attack mode returns 200", r.status_code == 200)
check("Attack mode ok=True", r.json().get("ok") == True)
time.sleep(5)  # Let burst complete

# ─── Test 9: Correlation — ML closely tracks Rule score ─────────────────────
section("TEST 9: Rule-ML Correlation Spot Check (5 transactions)")
deviations = []
for _ in range(5):
    tx = {
        "tx_id": _tx_id(), "timestamp": _now(),
        "sender_account": f"ACC-COR-{uuid.uuid4().hex[:4]}",
        "receiver_account": f"ACC-COR-{uuid.uuid4().hex[:4]}",
        "amount": 100000, "currency": "INR", "channel": "IMPS",
        "hop_number": 0, "is_cross_border": True,
        "simulator_meta": {"is_new_receiver": True, "tx_velocity": 5}
    }
    r = requests.post(f"{BASE}/transaction", json=tx)
    if r.status_code == 200:
        t = r.json().get("transaction", {})
        dev = abs(t.get("rule_score", 0) - t.get("ml_score", 0))
        deviations.append(dev)

avg_dev = sum(deviations) / len(deviations) if deviations else 999
check("Average Rule-ML deviation <= 15 pts", avg_dev <= 15, f"Avg dev: {avg_dev:.1f}")
print(f"    Individual deviations: {deviations} | Avg: {avg_dev:.1f}")

# ─── Test 10: Export CSV ────────────────────────────────────────────────────
section("TEST 10: GET /export/sentinel_audit.csv — Audit Export")
r = requests.get(f"{BASE}/export/sentinel_audit.csv")
check("CSV export returns 200", r.status_code == 200)
check("Content-Type is text/csv",
      "text/csv" in r.headers.get("Content-Type", ""))
check("CSV has content", len(r.text) > 100, f"Len: {len(r.text)}")

# ─── Final Summary ──────────────────────────────────────────────────────────
section("FINAL RESULTS")
total = PASS + FAIL
print(f"  Passed : {PASS}/{total}")
print(f"  Failed : {FAIL}/{total}")
if FAIL == 0:
    print("  STATUS: ALL TESTS PASSED")
else:
    print(f"  STATUS: {FAIL} TEST(S) FAILED — review output above")
print("=" * 60)
