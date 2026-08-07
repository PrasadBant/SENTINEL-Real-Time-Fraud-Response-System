"""
SENTINEL — EC-03 Withdrawal Timer Tracker
============================================
Tracks in-flight mule-withdrawal timers keyed by "case_id:node_id", shared
between:
  - the transaction pipeline (app/api/transactions.py), which starts a
    timer when a case escalates to HIGH_RISK, and
  - the action handlers (app/api/actions.py), which cancel a node's timer
    when an investigator freezes it before the Golden Window closes.

Completed timers (fired, cancelled, or errored) are evicted automatically
via a done-callback so this dict doesn't grow for the life of the process.
"""

import asyncio

_pending: dict[str, asyncio.Task] = {}


def register(key: str, task: asyncio.Task) -> None:
    """Track a newly-scheduled withdrawal timer and auto-evict it when done."""
    _pending[key] = task
    task.add_done_callback(lambda _t, _k=key: _pending.pop(_k, None))


def is_active(key: str) -> bool:
    """True if a withdrawal timer for this key is still pending."""
    task = _pending.get(key)
    return bool(task and not task.done())


def cancel(key: str) -> bool:
    """Cancel a pending withdrawal timer (e.g. the node was just frozen). Returns True if one was cancelled."""
    task = _pending.get(key)
    if task and not task.done():
        task.cancel()
        return True
    return False
