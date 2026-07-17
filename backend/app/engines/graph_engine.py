"""
SENTINEL — Graph Engine
========================
Optimized with O(1) duplicate detection using parallel node_ids / edge_ids sets.
The lists (nodes, edges) remain for serialization; sets are the index.
"""


def get_graph(case_id: str, store: dict) -> dict:
    if "graphs" not in store:
        store["graphs"] = {}
    if case_id not in store["graphs"]:
        return {"nodes": [], "edges": [], "node_ids": set(), "edge_ids": set()}
    return store["graphs"][case_id]


def _ensure_graph(case_id: str, store: dict) -> dict:
    """Get or initialize a graph entry with O(1) index sets."""
    if "graphs" not in store:
        store["graphs"] = {}
    if case_id not in store["graphs"]:
        store["graphs"][case_id] = {
            "nodes": [],
            "edges": [],
            "node_ids": set(),   # O(1) duplicate guard for nodes
            "edge_ids": set(),   # O(1) duplicate guard for edges
        }
    g = store["graphs"][case_id]
    # Back-fill sets for graphs created before this optimization
    if "node_ids" not in g:
        g["node_ids"] = {
            str(n.get("account_id") or n.get("id") or n.get("accountId", ""))
            for n in g.get("nodes", [])
        }
    if "edge_ids" not in g:
        g["edge_ids"] = {str(e.get("tx_id", "")) for e in g.get("edges", [])}
    return g


def add_node(case_id: str, account: dict, store: dict) -> None:
    graph = _ensure_graph(case_id, store)
    account_id = str(account.get("account_id", ""))
    if not account_id:
        return

    # O(1) duplicate check (was O(N) linear scan)
    if account_id in graph["node_ids"]:
        return

    graph["node_ids"].add(account_id)
    graph["nodes"].append({
        "account_id": account_id,
        "status":     account.get("status", "active"),
        "balance":    float(account.get("current_balance_sim", 0.0)),
    })


def add_edge(case_id: str, from_acc: str, to_acc: str, tx_id: str, amount: float, store: dict) -> None:
    graph = _ensure_graph(case_id, store)
    tx_id_str = str(tx_id)

    # O(1) duplicate check (was O(N) linear scan)
    if tx_id_str in graph["edge_ids"]:
        return

    graph["edge_ids"].add(tx_id_str)
    graph["edges"].append({
        "from":   from_acc,
        "to":     to_acc,
        "source": from_acc,
        "target": to_acc,
        "tx_id":  tx_id_str,
        "amount": float(amount),
    })
