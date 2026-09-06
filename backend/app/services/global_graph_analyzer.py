import asyncio
import logging
import time
from datetime import datetime, timezone
import networkx as nx
from app.core.constants import DEFAULT_TENANT_ID
from app.core.repository import repository

logger = logging.getLogger("sentinel.global_graph")

# Track already alerted bridge nodes to prevent spamming repeat alerts for
# the same node on every 15s cycle. Reset periodically (see
# _BRIDGE_ALERT_RESET_CYCLES below) rather than growing forever, and capped
# defensively so a pathological run can't turn this into an unbounded leak.
_alerted_bridge_nodes = set()
_BRIDGE_ALERT_RESET_CYCLES = 240  # ~1 hour at 15s/cycle
_BRIDGE_ALERT_MAX_SIZE = 5000

async def run_global_graph_analyzer(manager, store: dict):
    """Proactive bridge-node detector — builds a NetworkX graph from
    store["transactions"] every 15s and flags high-betweenness-centrality
    nodes.

    Deliberately NOT made cross-replica-consistent by this fix pass:
    store["transactions"] here is this process's own local cache, so
    under multiple API replicas each one's analyzer only sees the subset
    of transactions IT has personally processed, and each runs its own
    independent 15s cycle (redundant work, and each may alert on a bridge
    node the others already alerted on, or miss one only visible in
    another replica's transaction set). This is an accepted, documented
    gap, not an oversight: it degrades the proactive-monitoring FEATURE
    (fewer/duplicate detections) rather than corrupting data or crashing
    anything, and a real fix means either querying Postgres for the full
    transaction set every cycle (expensive, redundant across replicas) or
    electing a single-instance-wide leader for this job — both are
    meaningfully bigger architectural changes than this fix pass's scope
    (see the build plan's explicit "no microservices/new infra" bound)."""
    logger.info("Background analyzer started (15s loop)")
    cycle = 0
    while True:
        await asyncio.sleep(15)
        cycle += 1

        # Periodically forget prior alerts so a node's risk can be
        # re-evaluated (e.g. it went quiet then became a bridge again),
        # and so the set doesn't grow unbounded over a long-running process.
        if cycle % _BRIDGE_ALERT_RESET_CYCLES == 0 or len(_alerted_bridge_nodes) > _BRIDGE_ALERT_MAX_SIZE:
            _alerted_bridge_nodes.clear()

        try:
            transactions = store.get("transactions", {})
            if not transactions:
                continue
                
            # Build DiGraph
            G = nx.DiGraph()
            for tx in transactions.values():
                src = tx.get("sender_account")
                dst = tx.get("receiver_account")
                if src and dst:
                    G.add_edge(src, dst)
                    
            if len(G.nodes) < 5:
                continue
                
            # Compute Betweenness Centrality to find true "Bridge Nodes"
            bc = nx.betweenness_centrality(G)
            
            # Find Bridge Nodes (High BC, > 0.05)
            for node, score in bc.items():
                if score > 0.05 and node not in _alerted_bridge_nodes:
                    # Ignore exit nodes which naturally act as sinks, not bridges
                    if str(node).startswith("ACC-EXIT"):
                        continue
                        
                    _alerted_bridge_nodes.add(node)
                    logger.info("BRIDGE NODE DETECTED: %s (Betweenness Centrality: %.3f)", node, score)
                    
                    # Flag proactively via an ACTION_TAKEN
                    action = {
                        "action_id": f"bridge_{node}_{int(time.time())}",
                        "case_id": "GLOBAL",
                        "action_type": "PROACTIVE_MONITOR",
                        "target_id": node,
                        "status": "DETECTED",
                        "reason": f"High Centrality (BC: {score:.3f}) - Potential Bridge Node",
                        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "payload": {"betweenness_centrality": score, "node": node}
                    }
                    
                    repository.save_action(action, tenant_id=DEFAULT_TENANT_ID)

                    # Ensure websocket can broadcast. DEFAULT_TENANT_ID:
                    # this analyzer scans store["transactions"] (the
                    # single ingestion tenant's own data — see the
                    # docstring above), so its alerts belong to that
                    # tenant, same reasoning as transactions.py's own
                    # broadcasts.
                    try:
                        await manager.broadcast({"event": "ACTION_TAKEN", **action}, DEFAULT_TENANT_ID)
                    except Exception as e:
                        logger.warning("Broadcast failed: %s", e)

        except Exception as e:
            logger.error("Analysis cycle failed: %s", e)
