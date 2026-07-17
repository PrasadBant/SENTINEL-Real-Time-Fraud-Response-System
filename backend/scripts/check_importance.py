import requests, json, uuid
from datetime import datetime, timezone

def make_tx(amount, call=False, is_new=True, hop=0, velocity=1):
    return {
        "tx_id": f"CHK-{str(uuid.uuid4())[:6].upper()}",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "sender_account": f"ACC-{str(uuid.uuid4())[:4]}",
        "receiver_account": f"ACC-{str(uuid.uuid4())[:4]}",
        "amount": amount, "currency": "INR", "channel": "IMPS",
        "hop_number": hop, "on_active_call": call,
        "simulator_meta": {"is_new_receiver": is_new, "tx_velocity": velocity}
    }

scenarios = [
    ("Low Risk",   make_tx(500,    call=False, is_new=False, velocity=1)),
    ("Med Normal", make_tx(15000,  call=False, is_new=True,  velocity=3)),
    ("High Call",  make_tx(200000, call=True,  is_new=True,  velocity=8)),
]

for name, t in scenarios:
    r = requests.post("http://127.0.0.1:8000/transaction", json=t)
    d = r.json().get("transaction", {})
    imp = d.get("ml_feature_importance", {})
    print(f"[{name}] Rule={d['rule_score']} ML={d['ml_score']} Hybrid={d['risk_score']}")
    for feat, pct in imp.items():
        bar = "#" * int(pct * 30)
        print(f"  {feat:<20} {pct*100:5.1f}%  {bar}")
    print()
