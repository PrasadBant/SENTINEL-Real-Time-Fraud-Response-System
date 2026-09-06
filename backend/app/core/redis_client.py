"""
SENTINEL — Redis Client Access
=================================
Lazy singleton accessors for the two redis-py client flavors this app
needs:

  - get_redis()       a synchronous client, used by
                       app/services/orchestrator.py (which stays a plain
                       synchronous function — see its module docstring
                       for why).
  - get_async_redis()  an async client, used by
                        app/websocket/connection_manager.py's pub/sub
                        fanout and app/services/withdrawal_queue.py's
                        Arq pool.

Deliberately exposed as FUNCTIONS, not module-level client instances:
that's what lets tests substitute fakeredis cleanly (monkeypatch the
function itself, e.g. `redis_client.get_redis = lambda: fake_instance`)
without needing to touch every call site or worry about an object cached
at import time before the monkeypatch could apply. See
backend/tests/conftest.py.
"""

import redis
import redis.asyncio as aioredis

from app.core.config import REDIS_URL

_sync_client: redis.Redis | None = None
_async_client: aioredis.Redis | None = None


def get_redis() -> redis.Redis:
    """Synchronous Redis client (lazy singleton)."""
    global _sync_client
    if _sync_client is None:
        _sync_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _sync_client


def get_async_redis() -> aioredis.Redis:
    """Async Redis client (lazy singleton)."""
    global _async_client
    if _async_client is None:
        _async_client = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _async_client
