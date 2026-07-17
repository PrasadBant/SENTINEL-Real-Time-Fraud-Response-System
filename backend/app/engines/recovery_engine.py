def recalculate(case_id: str, store: dict) -> dict:
    case = store["cases"].get(case_id)
    if not case:
        return {"recoverable_amount": 0.0, "recovery_pct": 0.0}

    graph = store["graphs"].get(case_id, {"nodes": [], "edges": []})
    recoverable_amount = 0.0
    
    for node in graph["nodes"]:
        status = node.get("status", "active")
        # Withdrawn -> 0 recoverable. Frozen or active -> recoverable.
        if status != "withdrawn":
            # FIX 3: RECOVERY CAP
            node_balance = node.get("balance", 0.0)
            total_fraud_amount = case.get("total_fraud_amount", 0.0)
            recoverable_amount += min(node_balance, total_fraud_amount)

    # Recovery capped at total fraud amount
    total_fraud = case.get("total_fraud_amount", 0.0)
    recoverable_amount = min(recoverable_amount, total_fraud)

    if total_fraud > 0:
        recovery_pct = round((recoverable_amount / total_fraud) * 100, 2)
    else:
        recovery_pct = 0.0
        
    case["recoverable_amount"] = recoverable_amount
    case["recovery_pct"] = recovery_pct

    return {
        "recoverable_amount": recoverable_amount,
        "recovery_pct": recovery_pct
    }
