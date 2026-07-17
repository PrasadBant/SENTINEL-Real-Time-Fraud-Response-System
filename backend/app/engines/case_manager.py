import uuid
import random
from datetime import datetime, timezone
from app.core.config import GOLDEN_WINDOW_MINUTES

def _timeline_event(event_text: str) -> dict:
    return {
        "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": event_text,
        "actor": "system"
    }

def process_scored_tx(tx: dict, score_output: dict, store: dict) -> dict:
    score = score_output["risk_score"]
    case_id = tx.get("case_id")
    hop_number = tx.get("hop_number", 0)
    
    # GLOBAL DEPTH LIMIT: Stop processing chains deeper than 5 hops
    if hop_number > 5:
        return None

    # Allow chain persistence even with low scores, but keep a floor for new cases
    if score < 20 and not case_id:
        return None

    sender = tx["sender_account"]
    receiver = tx["receiver_account"]
    
    # FIX: Dynamic Node Capping (Random 2-5 for High Risk)
    if not case_id:
        # Check if we should link to an existing case, respecting its specific max_nodes
        existing_case = next((c for c in store["cases"].values() 
                              if (c["origin_account"] == sender or sender in c["chain"] or receiver in c["chain"]) 
                              and c["status"] in ["NEW", "HIGH_RISK"]
                              and len(c["chain"]) < c.get("max_nodes", 5)), None)
        
        if existing_case:
            case_id = existing_case["case_id"]
            tx["case_id"] = case_id
        else:
            case_id = f"CASE-{str(uuid.uuid4())[:8].upper()}"
            tx["case_id"] = case_id
            
            # Randomize limit between 3 and 6 nodes for variety
            max_nodes = random.randint(3, 6)
            store["cases"][case_id] = {
                "case_id": case_id,
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "status": "NEW",
                "risk_level": score,
                "primary_tx_id": tx.get("tx_id", ""), # Link to the starting transaction
                "max_nodes": max_nodes,
                "total_fraud_amount": 0.0,
                "recoverable_amount": 0.0,
                "golden_window_minutes": GOLDEN_WINDOW_MINUTES,
                "origin_account": sender,
                "chain": [sender],
                "chain_depth": 0,
                "urgency_score": 0.0,
                "transactions": [],
                "actions_taken": [],
                "timeline": [_timeline_event("case_created")]
            }

    case = store["cases"][case_id]

    tx_id = tx["tx_id"]
    if tx_id not in case["transactions"]:
        case["transactions"].append(tx_id)
        case["total_fraud_amount"] += float(tx.get("amount", 0.0))

    if receiver not in case["chain"]:
        # Only add to chain if we haven't hit the randomized limit
        if len(case["chain"]) < case.get("max_nodes", 5):
            case["chain"].append(receiver)
            case["chain_depth"] = max(case["chain_depth"], hop_number)
            case["timeline"].append(_timeline_event("account_added_to_chain"))
        else:
            # If limit hit, this tx effectively becomes an 'orphan' in this case 
            # or could be handled by starting a new case in a more complex setup.
            pass

    case["risk_level"] = max(case["risk_level"], score)
    
    # Escalation to HIGH_RISK
    if score >= 60 or hop_number > 0: # Using new threshold from config
        if case["status"] == "NEW":
            case["status"] = "HIGH_RISK"
            case["timeline"].append(_timeline_event("escalated_to_high_risk"))
            
    case["urgency_score"] = case["risk_level"] * (1 + 1 / max(case["golden_window_minutes"], 1))

    return case
