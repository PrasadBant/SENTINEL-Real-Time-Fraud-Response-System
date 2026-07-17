import asyncio
import time
from datetime import datetime, timezone
import networkx as nx
from app.core.persistence import save_action

# Track already alerted bridge nodes to prevent spamming
_alerted_bridge_nodes = set()

async def run_global_graph_analyzer(manager, store: dict):
    print("  [Global Graph] Background analyzer started (15s loop)")
    while True:
        await asyncio.sleep(15)
        
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
                    print(f"  [Global Graph] BRIDGE NODE DETECTED: {node} (Betweenness Centrality: {score:.3f})")
                    
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
                    
                    save_action(action)
                    
                    # Ensure websocket can broadcast
                    try:
                        await manager.broadcast({"event": "ACTION_TAKEN", **action})
                    except Exception as e:
                        print(f"  [Global Graph] Broadcast failed: {e}")
                        
        except Exception as e:
            print(f"  [Global Graph] Analysis cycle failed: {e}")
